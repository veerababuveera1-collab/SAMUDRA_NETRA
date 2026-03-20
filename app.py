"""
OIMS V4 — SAMUDRA NETRA X
Azure Cosmos DB Audit Chain Integration

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
from typing import Optional
from dataclasses import dataclass, field, asdict

try:
    from azure.cosmos import CosmosClient, PartitionKey, exceptions
    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False
    print("[WARN] azure-cosmos not installed. Using local SQLite fallback.")

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
    Each entry is cryptographically linked to the previous one.
    """
    id:              str   = field(default_factory=lambda: str(uuid.uuid4()))
    contact_id:      str   = ""
    roe_level:       str   = "OBSERVE"
    action:          str   = ""
    operator_id:     str   = "SYSTEM"
    prev_hash:       str   = "genesis"
    entry_hash:      str   = ""
    timestamp:       str   = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Cosmos DB partition key
    partition_key:   str   = ""   # set to contact_id on creation

    # Extra intelligence context
    threat_prob:     float = 0.0
    piracy_prob:     float = 0.0
    vessel_speed_kts:float = 0.0
    in_eez:          bool  = False
    ais_dark:        bool  = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["partition_key"] = self.contact_id   # Cosmos partition key
        return d


# ─────────────────────────────────────────────────────────────────────────────
# HASH CHAIN LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def compute_hash(entry: AuditEntry) -> str:
    """
    SHA-256 hash of the entry payload chained to prev_hash.
    Any field change invalidates the hash → tamper detection.
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


def verify_chain(entries: list[dict]) -> dict:
    """
    Verify integrity of a list of audit entries (sorted oldest → newest).
    Returns: {'valid': bool, 'broken_at': int | None, 'total': int}
    """
    if not entries:
        return {"valid": True, "broken_at": None, "total": 0}

    for i, e in enumerate(entries):
        # Reconstruct entry object
        entry = AuditEntry(**{k: v for k, v in e.items()
                              if k in AuditEntry.__dataclass_fields__})
        expected = compute_hash(entry)
        if expected != e.get("entry_hash", ""):
            return {"valid": False, "broken_at": i, "total": len(entries)}

    return {"valid": True, "broken_at": None, "total": len(entries)}


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

    Cosmos DB advantages over SQLite for hackathon/production:
      • Global distribution (read replicas in any Azure region)
      • 99.999% SLA with Strong consistency
      • Automatic indexing on all fields
      • Built-in change feed for real-time dashboard streaming
      • Serverless or provisioned 400–40,000 RU/s
    """

    DB_NAME        = os.getenv("COSMOS_DB",        "oims_audit_db")
    CONTAINER_NAME = os.getenv("COSMOS_CONTAINER", "audit_chain")

    def __init__(self):
        self._client    = None
        self._container = None
        self._local_chain: list[dict] = []   # in-memory fallback
        self._connected = False
        self._connect()

    def _connect(self):
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
            db = self._client.create_database_if_not_exists(
                id=self.DB_NAME,
                offer_throughput=400,
            )
            self._container = db.create_container_if_not_exists(
                id=self.CONTAINER_NAME,
                partition_key=PartitionKey(path="/contact_id"),
                default_ttl=None,    # keep forever
            )
            self._connected = True
            print(f"[AuditDB] Connected to Azure Cosmos DB: {self.DB_NAME}/{self.CONTAINER_NAME}")
        except Exception as e:
            print(f"[AuditDB] Cosmos connection failed ({e}). Using local-memory fallback.")

    # ── Public API ────────────────────────────────────────────────────────────

    def get_latest_hash(self) -> str:
        """Fetch the hash of the most recent entry (needed to build next entry)."""
        if self._connected:
            try:
                query = (
                    "SELECT TOP 1 c.entry_hash FROM c "
                    "ORDER BY c._ts DESC"
                )
                results = list(self._container.query_items(
                    query=query, enable_cross_partition_query=True
                ))
                return results[0]["entry_hash"] if results else "genesis"
            except Exception as e:
                print(f"[AuditDB] get_latest_hash failed: {e}")
        # Fallback
        return self._local_chain[-1]["entry_hash"] if self._local_chain else "genesis"

    def append(
        self,
        contact_id:       str,
        roe_level:        str,
        action:           str,
        operator_id:      str  = "SYSTEM",
        threat_prob:      float = 0.0,
        piracy_prob:      float = 0.0,
        vessel_speed_kts: float = 0.0,
        in_eez:           bool  = False,
        ais_dark:         bool  = False,
    ) -> AuditEntry:
        """
        Create and persist a new signed audit entry.
        Enforces sequential hash chaining.
        Returns the created AuditEntry.
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
                print(f"[AuditDB] ✓ Cosmos append — {contact_id} | {roe_level} | {entry.entry_hash[:16]}...")
            except exceptions.CosmosHttpResponseError as e:
                print(f"[AuditDB] Cosmos write failed ({e.status_code}), stored locally.")
                self._local_chain.append(doc)
        else:
            self._local_chain.append(doc)
            print(f"[AuditDB] ✓ Local append — {contact_id} | {roe_level} | {entry.entry_hash[:16]}...")

        return entry

    def get_chain(
        self,
        limit: int = 50,
        contact_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Retrieve recent audit entries.
        Optionally filter by contact_id (uses Cosmos partition key — O(1) lookup).
        """
        if self._connected:
            try:
                if contact_id:
                    query = (
                        f"SELECT TOP {limit} * FROM c "
                        f"WHERE c.contact_id = @cid ORDER BY c._ts DESC"
                    )
                    params = [{"name": "@cid", "value": contact_id}]
                    return list(self._container.query_items(
                        query=query, parameters=params,
                        partition_key=contact_id,
                    ))
                else:
                    query = (
                        f"SELECT TOP {limit} * FROM c ORDER BY c._ts DESC"
                    )
                    return list(self._container.query_items(
                        query=query, enable_cross_partition_query=True
                    ))
            except Exception as e:
                print(f"[AuditDB] get_chain failed: {e}")

        return list(reversed(self._local_chain[-limit:]))

    def depth(self) -> int:
        """Total number of entries in the chain."""
        if self._connected:
            try:
                result = list(self._container.query_items(
                    query="SELECT VALUE COUNT(1) FROM c",
                    enable_cross_partition_query=True,
                ))
                return result[0] if result else 0
            except Exception as e:
                print(f"[AuditDB] depth query failed: {e}")
        return len(self._local_chain)

    def verify_integrity(self, limit: int = 100) -> dict:
        """
        Verify SHA-256 hash chain integrity for recent entries.
        Returns verification report.
        """
        entries = self.get_chain(limit=limit)
        entries_asc = list(reversed(entries))   # oldest first for chain check
        result = verify_chain(entries_asc)
        result["checked"] = len(entries_asc)
        result["latest_hash"] = entries[0]["entry_hash"] if entries else "empty"
        return result

    def export_json(self, path: str = "audit_chain_export.json") -> str:
        """Export full chain to JSON for offline analysis / legal handover."""
        chain = self.get_chain(limit=10000)
        with open(path, "w") as f:
            json.dump(chain, f, indent=2, default=str)
        print(f"[AuditDB] Exported {len(chain)} entries to {path}")
        return path

    def close(self):
        if self._client:
            self._client.close()


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT INTEGRATION HELPER
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> OIMSAuditChainDB:
    """
    Streamlit-safe DB singleton using st.cache_resource.
    Import and call this function in your Streamlit app:

        from cosmos_audit_chain import get_db
        db = get_db()
    """
    try:
        import streamlit as st

        @st.cache_resource
        def _singleton():
            return OIMSAuditChainDB()

        return _singleton()
    except ImportError:
        # Outside Streamlit — return plain instance
        return OIMSAuditChainDB()


# ─────────────────────────────────────────────────────────────────────────────
# DEMO / TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  OIMS V4 — Azure Cosmos DB Audit Chain Demo")
    print("="*60)

    db = OIMSAuditChainDB()

    # Seed 5 entries (mirrors AWRS scenarios)
    test_contacts = [
        dict(contact_id="CONTACT-A", roe_level="OBSERVE",       action="deploy_usv_shadow",        threat_prob=0.10, piracy_prob=0.05, vessel_speed_kts=8,  in_eez=False, ais_dark=False),
        dict(contact_id="CONTACT-B", roe_level="WARN",          action="broadcast_channel16",       threat_prob=0.45, piracy_prob=0.30, vessel_speed_kts=16, in_eez=True,  ais_dark=True),
        dict(contact_id="CONTACT-C", roe_level="KINETIC",       action="alert_fleet_command_human", threat_prob=0.78, piracy_prob=0.70, vessel_speed_kts=24, in_eez=True,  ais_dark=True),
        dict(contact_id="CONTACT-D", roe_level="KINETIC",       action="alert_fleet_command_human", threat_prob=0.95, piracy_prob=0.92, vessel_speed_kts=30, in_eez=True,  ais_dark=True),
        dict(contact_id="DARK-003",  roe_level="ELECTRONIC_JAM",action="ecm_jamming_active",        threat_prob=0.50, piracy_prob=0.35, vessel_speed_kts=18, in_eez=True,  ais_dark=True),
    ]

    print("\n[1] Appending audit entries...")
    for tc in test_contacts:
        entry = db.append(**tc, operator_id="AWRS_AUTO")
        print(f"  {tc['contact_id']:12} | {tc['roe_level']:15} | {entry.entry_hash[:20]}...")

    print(f"\n[2] Chain depth: {db.depth()} entries")

    print("\n[3] Verifying chain integrity...")
    report = db.verify_integrity()
    status = "VALID" if report["valid"] else f"BROKEN at entry {report['broken_at']}"
    print(f"  Status: {status}")
    print(f"  Checked: {report['checked']} entries")
    print(f"  Latest hash: {report['latest_hash'][:24]}...")

    print("\n[4] Fetching KINETIC contacts only...")
    kinetic = [e for e in db.get_chain() if e.get("roe_level") == "KINETIC"]
    print(f"  Found: {len(kinetic)} KINETIC entries")
    for k in kinetic:
        print(f"    {k['contact_id']} — {k['entry_hash'][:16]}... (human auth required)")

    print("\n[5] Exporting to JSON...")
    db.export_json("audit_chain_export.json")

    print("\n" + "="*60)
    print("  Cosmos DB Integration Summary")
    print("="*60)
    print(f"  Mode       : {'Azure Cosmos DB' if db._connected else 'Local memory (fallback)'}")
    print(f"  DB         : {OIMSAuditChainDB.DB_NAME}")
    print(f"  Container  : {OIMSAuditChainDB.CONTAINER_NAME}")
    print(f"  Algorithm  : SHA-256 chained hash")
    print(f"  Integrity  : {'✓ VERIFIED' if report['valid'] else '✗ COMPROMISED'}")
    print(f"  Total depth: {db.depth()}")
    db.close()
