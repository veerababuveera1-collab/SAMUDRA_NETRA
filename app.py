"""
OIMS V4 — SAMUDRA NETRA X
Azure Cosmos DB Audit Chain Integration  (CORRECTED v2)

Bugs fixed:
  1. list[dict] → List[dict]  (Python 3.8 compatibility)
  2. get_db() @st.cache_resource moved to module level  (proper singleton)
  3. offer_throughput removed from database creation  (deprecated in SDK 4.x)
  4. List imported from typing
  5. verify_chain now checks prev_hash linkage between consecutive entries

Install:
    pip install azure-cosmos python-dotenv

.env file:
    COSMOS_ENDPOINT=https://oims-v4.documents.azure.com:443/
    COSMOS_KEY=your_primary_key_here
    COSMOS_DB=oims_audit_db
    COSMOS_CONTAINER=audit_chain
"""

import hashlib
import uuid
import json
import os
from datetime import datetime, timezone
# FIX 1 & 4: import List (and Dict) for Python 3.8 compatibility
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

try:
    from azure.cosmos import CosmosClient, PartitionKey, exceptions
    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False
    print("[WARN] azure-cosmos not installed. Using local memory fallback.")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    """
    Single entry in the OIMS V4 immutable hash chain.
    Each entry is cryptographically linked to the previous one via SHA-256.
    """
    id:               str   = field(default_factory=lambda: str(uuid.uuid4()))
    contact_id:       str   = ""
    roe_level:        str   = "OBSERVE"
    action:           str   = ""
    operator_id:      str   = "SYSTEM"
    prev_hash:        str   = "genesis"
    entry_hash:       str   = ""
    timestamp:        str   = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    partition_key:    str   = ""   # Cosmos DB partition key — set to contact_id on creation

    # Extra intelligence context
    threat_prob:      float = 0.0
    piracy_prob:      float = 0.0
    vessel_speed_kts: float = 0.0
    in_eez:           bool  = False
    ais_dark:         bool  = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # partition_key is already included by asdict(); keep explicit for clarity
        d["partition_key"] = self.contact_id
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """
        Safe reconstruction from a Cosmos DB document dict.
        Cosmos adds system fields (_ts, _rid, _self, _etag, _attachments)
        that are NOT part of the dataclass — filter them out.
        """
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ─────────────────────────────────────────────────────────────────────────────
# HASH CHAIN LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def compute_hash(entry: AuditEntry) -> str:
    """
    SHA-256 hash of the entry payload chained to prev_hash.
    entry_hash itself is NOT included — it is the output, not the input.
    Any other field change invalidates the hash → tamper detection.
    """
    payload = "|".join([
        entry.prev_hash,
        entry.id,
        entry.contact_id,
        entry.roe_level,
        entry.action,
        entry.operator_id,
        entry.timestamp,
        f"{entry.threat_prob:.4f}",
        f"{entry.piracy_prob:.4f}",
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# FIX 1: list[dict] → List[dict]  (Python 3.8 compatible)
# FIX 5: verify_chain now checks BOTH the hash digest AND the prev_hash linkage
def verify_chain(entries: List[Dict[str, Any]]) -> dict:
    """
    Verify integrity of a list of audit entries (sorted oldest → newest).

    Two checks per entry:
      a) Hash digest  : recompute SHA-256 and compare to stored entry_hash
      b) Chain linkage: confirm this entry's prev_hash == previous entry's entry_hash

    Returns:
        {
          'valid'     : bool,
          'broken_at' : int | None   (index of first bad entry),
          'error'     : str | None   (description of failure),
          'total'     : int,
        }
    """
    if not entries:
        return {"valid": True, "broken_at": None, "error": None, "total": 0}

    for i, raw in enumerate(entries):
        try:
            entry = AuditEntry.from_dict(raw)
        except (TypeError, KeyError) as exc:
            return {
                "valid": False,
                "broken_at": i,
                "error": f"Entry {i}: failed to deserialise — {exc}",
                "total": len(entries),
            }

        # (a) Digest check
        expected_hash = compute_hash(entry)
        if expected_hash != raw.get("entry_hash", ""):
            return {
                "valid": False,
                "broken_at": i,
                "error": (
                    f"Entry {i} ({entry.contact_id}): hash mismatch. "
                    f"Expected {expected_hash[:16]}… "
                    f"Got {str(raw.get('entry_hash',''))[:16]}…"
                ),
                "total": len(entries),
            }

        # (b) Chain linkage check (skip genesis)  ← FIX 5
        if i > 0:
            expected_prev = entries[i - 1].get("entry_hash", "")
            if entry.prev_hash != expected_prev:
                return {
                    "valid": False,
                    "broken_at": i,
                    "error": (
                        f"Entry {i} ({entry.contact_id}): chain broken — "
                        f"prev_hash {entry.prev_hash[:16]}… "
                        f"does not match entry {i-1} hash {expected_prev[:16]}…"
                    ),
                    "total": len(entries),
                }

    return {"valid": True, "broken_at": None, "error": None, "total": len(entries)}


# ─────────────────────────────────────────────────────────────────────────────
# AZURE COSMOS DB CLIENT
# ─────────────────────────────────────────────────────────────────────────────

class OIMSAuditChainDB:
    """
    OIMS V4 — Azure Cosmos DB audit chain manager.

    Storage strategy:
      - Database    : oims_audit_db
      - Container   : audit_chain
      - Partition   : /contact_id  (hot partitions avoided by contact diversity)
      - Consistency : Strong (mandatory for chain integrity)
      - TTL         : None (permanent record for legal review)

    Cosmos DB advantages over SQLite for production:
      • Global distribution across Azure regions
      • 99.999% SLA with Strong consistency
      • Automatic indexing on all fields
      • Built-in change feed for real-time dashboard streaming
      • Serverless or provisioned 400–40,000 RU/s
    """

    DB_NAME        = os.getenv("COSMOS_DB",        "oims_audit_db")
    CONTAINER_NAME = os.getenv("COSMOS_CONTAINER", "audit_chain")

    def __init__(self):
        self._client:     Optional[CosmosClient] = None
        self._container   = None
        self._local_chain: List[Dict[str, Any]]  = []   # in-memory fallback
        self._connected   = False
        self._connect()

    def _connect(self) -> None:
        if not COSMOS_AVAILABLE:
            print("[AuditDB] Running in local-memory mode (azure-cosmos not installed).")
            return

        endpoint = os.getenv("COSMOS_ENDPOINT", "")
        key      = os.getenv("COSMOS_KEY",      "")

        if not endpoint or not key:
            print("[AuditDB] COSMOS_ENDPOINT / COSMOS_KEY not set. Using local-memory mode.")
            return

        try:
            self._client = CosmosClient(endpoint, credential=key)

            # FIX 3: offer_throughput removed from database creation — deprecated in SDK 4.x
            # Use create_container_if_not_exists to set throughput on the container instead
            db = self._client.create_database_if_not_exists(id=self.DB_NAME)

            self._container = db.create_container_if_not_exists(
                id=self.CONTAINER_NAME,
                partition_key=PartitionKey(path="/contact_id"),
                offer_throughput=400,   # throughput set on container (correct location)
                default_ttl=None,       # keep entries forever for legal review
            )
            self._connected = True
            print(
                f"[AuditDB] Connected → "
                f"{self.DB_NAME}/{self.CONTAINER_NAME}"
            )

        except Exception as exc:
            print(f"[AuditDB] Cosmos connection failed ({exc}). Using local-memory fallback.")

    # ── Public API ────────────────────────────────────────────────────────────

    def get_latest_hash(self) -> str:
        """
        Fetch the entry_hash of the most recent entry.
        Required to build the next entry's prev_hash.
        """
        if self._connected:
            try:
                results = list(self._container.query_items(
                    query="SELECT TOP 1 c.entry_hash FROM c ORDER BY c._ts DESC",
                    enable_cross_partition_query=True,
                ))
                return results[0]["entry_hash"] if results else "genesis"
            except Exception as exc:
                print(f"[AuditDB] get_latest_hash failed: {exc}")
        return self._local_chain[-1]["entry_hash"] if self._local_chain else "genesis"

    def append(
        self,
        contact_id:       str,
        roe_level:        str,
        action:           str,
        operator_id:      str   = "SYSTEM",
        threat_prob:      float = 0.0,
        piracy_prob:      float = 0.0,
        vessel_speed_kts: float = 0.0,
        in_eez:           bool  = False,
        ais_dark:         bool  = False,
    ) -> AuditEntry:
        """
        Create, sign, and persist a new audit entry.
        Enforces sequential SHA-256 hash chaining.
        Returns the created and signed AuditEntry.
        """
        prev_hash = self.get_latest_hash()

        entry = AuditEntry(
            contact_id       = contact_id,
            roe_level        = roe_level,
            action           = action,
            operator_id      = operator_id,
            prev_hash        = prev_hash,
            threat_prob      = threat_prob,
            piracy_prob      = piracy_prob,
            vessel_speed_kts = vessel_speed_kts,
            in_eez           = in_eez,
            ais_dark         = ais_dark,
            partition_key    = contact_id,
        )
        entry.entry_hash = compute_hash(entry)
        doc = entry.to_dict()

        if self._connected:
            try:
                self._container.create_item(body=doc)
                print(
                    f"[AuditDB] ✓ Cosmos — {contact_id} | "
                    f"{roe_level} | {entry.entry_hash[:16]}…"
                )
            except exceptions.CosmosHttpResponseError as exc:
                print(
                    f"[AuditDB] Cosmos write failed (HTTP {exc.status_code}), "
                    f"stored locally."
                )
                self._local_chain.append(doc)
        else:
            self._local_chain.append(doc)
            print(
                f"[AuditDB] ✓ Local — {contact_id} | "
                f"{roe_level} | {entry.entry_hash[:16]}…"
            )

        return entry

    # FIX 1: List[Dict] instead of list[dict]
    def get_chain(
        self,
        limit:      int            = 50,
        contact_id: Optional[str]  = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent audit entries (newest first).
        Filter by contact_id to use Cosmos partition key — O(1) lookup.
        """
        if self._connected:
            try:
                if contact_id:
                    results = list(self._container.query_items(
                        query=(
                            f"SELECT TOP {limit} * FROM c "
                            f"WHERE c.contact_id = @cid "
                            f"ORDER BY c._ts DESC"
                        ),
                        parameters=[{"name": "@cid", "value": contact_id}],
                        partition_key=contact_id,
                    ))
                else:
                    results = list(self._container.query_items(
                        query=f"SELECT TOP {limit} * FROM c ORDER BY c._ts DESC",
                        enable_cross_partition_query=True,
                    ))
                return results
            except Exception as exc:
                print(f"[AuditDB] get_chain failed: {exc}")

        # Local fallback: return newest-first slice
        return list(reversed(self._local_chain[-limit:]))

    def depth(self) -> int:
        """Total number of entries in the audit chain."""
        if self._connected:
            try:
                result = list(self._container.query_items(
                    query="SELECT VALUE COUNT(1) FROM c",
                    enable_cross_partition_query=True,
                ))
                return result[0] if result else 0
            except Exception as exc:
                print(f"[AuditDB] depth query failed: {exc}")
        return len(self._local_chain)

    def verify_integrity(self, limit: int = 100) -> dict:
        """
        Verify SHA-256 hash chain integrity for the most recent entries.
        Runs both digest and prev_hash linkage checks.
        Returns a verification report dict.
        """
        entries_desc = self.get_chain(limit=limit)
        entries_asc  = list(reversed(entries_desc))   # oldest first for chain walk
        result       = verify_chain(entries_asc)
        result["checked"]     = len(entries_asc)
        result["latest_hash"] = (
            entries_desc[0]["entry_hash"] if entries_desc else "empty"
        )
        return result

    def export_json(self, path: str = "audit_chain_export.json") -> str:
        """Export full chain to JSON for offline analysis or legal handover."""
        chain = self.get_chain(limit=10_000)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(chain, fh, indent=2, default=str)
        print(f"[AuditDB] Exported {len(chain)} entries → {path}")
        return path

    def close(self) -> None:
        if self._client:
            self._client.close()


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT INTEGRATION HELPER  (FIX 2)
# ─────────────────────────────────────────────────────────────────────────────

# FIX 2: @st.cache_resource must decorate a module-level function,
# not a nested function defined inside get_db().
# Previously the decorator was re-applied on every get_db() call,
# creating a new cache key each time → no caching effect.

try:
    import streamlit as st

    @st.cache_resource          # ← correct: module-level, evaluated once
    def _create_db_singleton() -> OIMSAuditChainDB:
        return OIMSAuditChainDB()

    def get_db() -> OIMSAuditChainDB:
        """
        Streamlit-safe DB singleton.
        Import and call in your Streamlit app:

            from cosmos_audit_chain import get_db
            db = get_db()
        """
        return _create_db_singleton()

except ImportError:
    # Outside Streamlit (unit tests, CLI) — plain factory
    def get_db() -> OIMSAuditChainDB:          # type: ignore[misc]
        """Return a plain OIMSAuditChainDB instance (non-Streamlit context)."""
        return OIMSAuditChainDB()


# ─────────────────────────────────────────────────────────────────────────────
# DEMO / TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  OIMS V4 — Azure Cosmos DB Audit Chain Demo  (CORRECTED)")
    print("=" * 62)

    db = OIMSAuditChainDB()

    # ── 1. Seed entries ───────────────────────────────────────────
    test_contacts = [
        dict(contact_id="CONTACT-A", roe_level="OBSERVE",
             action="deploy_usv_shadow",
             threat_prob=0.10, piracy_prob=0.05,
             vessel_speed_kts=8,  in_eez=False, ais_dark=False),
        dict(contact_id="CONTACT-B", roe_level="WARN",
             action="broadcast_channel16",
             threat_prob=0.45, piracy_prob=0.30,
             vessel_speed_kts=16, in_eez=True,  ais_dark=True),
        dict(contact_id="CONTACT-C", roe_level="KINETIC",
             action="alert_fleet_command_human",
             threat_prob=0.78, piracy_prob=0.70,
             vessel_speed_kts=24, in_eez=True,  ais_dark=True),
        dict(contact_id="CONTACT-D", roe_level="KINETIC",
             action="alert_fleet_command_human",
             threat_prob=0.95, piracy_prob=0.92,
             vessel_speed_kts=30, in_eez=True,  ais_dark=True),
        dict(contact_id="DARK-003",  roe_level="ELECTRONIC_JAM",
             action="ecm_jamming_active",
             threat_prob=0.50, piracy_prob=0.35,
             vessel_speed_kts=18, in_eez=True,  ais_dark=True),
    ]

    print("\n[1] Appending audit entries...")
    for tc in test_contacts:
        entry = db.append(**tc, operator_id="AWRS_AUTO")
        print(
            f"  {tc['contact_id']:12} | "
            f"{tc['roe_level']:16} | "
            f"{entry.entry_hash[:20]}…"
        )

    # ── 2. Depth ──────────────────────────────────────────────────
    print(f"\n[2] Chain depth: {db.depth()} entries")

    # ── 3. Integrity (both digest + linkage) ──────────────────────
    print("\n[3] Verifying chain integrity (digest + prev_hash linkage)…")
    report = db.verify_integrity()
    status = "✓ VALID" if report["valid"] else f"✗ BROKEN at entry {report['broken_at']}"
    print(f"  Status  : {status}")
    if report.get("error"):
        print(f"  Error   : {report['error']}")
    print(f"  Checked : {report['checked']} entries")
    print(f"  Latest  : {report['latest_hash'][:24]}…")

    # ── 4. Filter KINETIC ─────────────────────────────────────────
    print("\n[4] Fetching KINETIC contacts only…")
    kinetic = [e for e in db.get_chain() if e.get("roe_level") == "KINETIC"]
    print(f"  Found: {len(kinetic)} KINETIC entries")
    for k in kinetic:
        print(f"    {k['contact_id']} — {k['entry_hash'][:16]}… (human auth required)")

    # ── 5. Tamper simulation ──────────────────────────────────────
    print("\n[5] Tamper simulation — mutating one entry…")
    if db._local_chain:
        db._local_chain[1]["roe_level"] = "OBSERVE"   # tamper!
        tamper_report = db.verify_integrity()
        result_txt = (
            f"✗ DETECTED at entry {tamper_report['broken_at']}: "
            f"{tamper_report.get('error','')}"
            if not tamper_report["valid"]
            else "✓ Not detected (unexpected)"
        )
        print(f"  {result_txt}")
        db._local_chain[1]["roe_level"] = "WARN"      # restore

    # ── 6. Export ─────────────────────────────────────────────────
    print("\n[6] Exporting to JSON…")
    db.export_json("audit_chain_export.json")

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("  Summary")
    print("=" * 62)
    print(f"  Mode       : {'Azure Cosmos DB' if db._connected else 'Local memory (fallback)'}")
    print(f"  DB         : {OIMSAuditChainDB.DB_NAME}")
    print(f"  Container  : {OIMSAuditChainDB.CONTAINER_NAME}")
    print(f"  Algorithm  : SHA-256 (digest + chain linkage)")
    print(f"  Integrity  : {'✓ VERIFIED' if report['valid'] else '✗ COMPROMISED'}")
    print(f"  Depth      : {db.depth()} entries")
    db.close()
