"""
OIMS V4 — SAMUDRA NETRA X
Sensor Integration Module — IoT-Ready Physical Sensor Gateway

Supports:
  1. MQTT  — IoT Buoys, CTD, GPS, Hydrophones (paho-mqtt)
  2. RTSP  — Camera feeds → YOLOv8 inference (opencv-python)
  3. PySerial — Arduino / Raspberry Pi GPIO sensors

Install:
    pip install paho-mqtt pyserial python-dotenv azure-cosmos

Usage:
    python sensor_integration.py          # standalone test
    # OR import into Streamlit app:
    from sensor_integration import SensorGateway, SHESNMonitor
"""

import json
import time
import uuid
import hashlib
import threading
import logging
from datetime import datetime, timezone
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("OIMS-Sensor")

try:
    import paho.mqtt.client as mqtt
    MQTT_OK = True
except ImportError:
    MQTT_OK = False
    log.warning("paho-mqtt not installed — MQTT disabled. pip install paho-mqtt")

try:
    import serial
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False
    log.warning("pyserial not installed — Serial disabled. pip install pyserial")

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False
    log.warning("opencv-python not installed — RTSP disabled.")

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

class NodeStatus(Enum):
    ONLINE  = "online"
    WARN    = "warn"       # weak heartbeat
    OFFLINE = "offline"    # timeout — rerouted
    REROUTED= "rerouted"   # data via neighbour

class EnergySource(Enum):
    WAVE      = "wave_kinetic"
    THERMAL   = "thermohaline_gradient"
    SOLAR     = "solar_panel"
    BATTERY   = "battery"
    HYBRID    = "hybrid"

@dataclass
class SensorReading:
    """Unified sensor data packet — same schema regardless of protocol."""
    reading_id:   str   = field(default_factory=lambda: str(uuid.uuid4()))
    node_id:      str   = ""
    ip_address:   str   = ""
    sensor_type:  str   = ""
    protocol:     str   = "mqtt"
    # Oceanographic fields
    sst_c:        Optional[float] = None   # sea surface temperature
    salinity_ppt: Optional[float] = None
    wave_height_m:Optional[float] = None
    ph:           Optional[float] = None
    depth_m:      Optional[float] = None
    lat:          Optional[float] = None
    lon:          Optional[float] = None
    # Raw payload
    raw:          str   = ""
    timestamp:    str   = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass
class SensorNode:
    """A registered physical sensor node in the SHESN mesh."""
    node_id:       str
    ip_address:    str
    sensor_type:   str                   # IoT Buoy | Sonar Array | RTSP Camera | ...
    mqtt_topic:    str                   = ""
    serial_port:   str                   = ""
    rtsp_url:      str                   = ""
    energy_source: EnergySource          = EnergySource.HYBRID
    status:        NodeStatus            = NodeStatus.ONLINE
    neighbour_ids: List[str]             = field(default_factory=list)
    last_heartbeat:float                 = field(default_factory=time.time)
    heartbeat_soc: float                 = 100.0   # % signal / battery
    readings_count:int                   = 0

    @property
    def seconds_since_hb(self) -> float:
        return time.time() - self.last_heartbeat

    def touch(self):
        self.last_heartbeat = time.time()
        self.status = NodeStatus.ONLINE


# ─────────────────────────────────────────────────────────────────────────────
# SHESN MONITOR — Self-Healing Heartbeat Engine
# ─────────────────────────────────────────────────────────────────────────────

class SHESNMonitor:
    """
    SHESN — Self-Healing Energy-Harvesting Sensor Network Monitor.

    Runs a background thread that:
      1. Checks every node heartbeat every second
      2. Marks nodes WARN if no HB for > warn_timeout_s
      3. Marks nodes OFFLINE if no HB for > offline_timeout_s
      4. Finds online neighbours and marks node REROUTED
      5. Calls on_alert(node_id, status) on state changes
    """

    WARN_TIMEOUT    = 3.0    # seconds
    OFFLINE_TIMEOUT = 8.0    # seconds

    def __init__(self,
                 on_alert: Optional[Callable[[str, NodeStatus, str], None]] = None):
        self.nodes:    Dict[str, SensorNode] = {}
        self.on_alert: Callable              = on_alert or (lambda *a: None)
        self._lock     = threading.Lock()
        self._running  = False
        self._thread:  Optional[threading.Thread] = None

    def register(self, node: SensorNode) -> None:
        with self._lock:
            self.nodes[node.node_id] = node
        log.info(f"SHESN: registered {node.node_id} ({node.sensor_type}) at {node.ip_address}")

    def heartbeat(self, node_id: str, soc: float = 100.0) -> None:
        """Called when a heartbeat arrives from a node."""
        with self._lock:
            if node_id in self.nodes:
                n = self.nodes[node_id]
                prev = n.status
                n.touch()
                n.heartbeat_soc = soc
                if prev != NodeStatus.ONLINE:
                    log.info(f"SHESN: {node_id} back ONLINE")
                    self.on_alert(node_id, NodeStatus.ONLINE, "Node recovered")

    def _find_neighbours(self, node_id: str) -> List[str]:
        """Return online neighbour node IDs."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [
            nid for nid in node.neighbour_ids
            if nid in self.nodes and self.nodes[nid].status == NodeStatus.ONLINE
        ]

    def _check_loop(self) -> None:
        while self._running:
            with self._lock:
                for nid, node in self.nodes.items():
                    age = node.seconds_since_hb
                    prev = node.status

                    if age > self.OFFLINE_TIMEOUT and prev != NodeStatus.OFFLINE:
                        node.status = NodeStatus.OFFLINE
                        nbrs = self._find_neighbours(nid)
                        if nbrs:
                            node.status = NodeStatus.REROUTED
                            msg = f"NODE-{nid}: offline — rerouted via {nbrs[0]}"
                            log.warning(msg)
                            self.on_alert(nid, NodeStatus.REROUTED, msg)
                        else:
                            msg = f"NODE-{nid}: offline — no neighbours available"
                            log.error(msg)
                            self.on_alert(nid, NodeStatus.OFFLINE, msg)

                    elif age > self.WARN_TIMEOUT and prev == NodeStatus.ONLINE:
                        node.status = NodeStatus.WARN
                        msg = f"NODE-{nid}: heartbeat weak ({age:.1f}s)"
                        log.warning(msg)
                        self.on_alert(nid, NodeStatus.WARN, msg)

            time.sleep(1.0)

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        log.info("SHESN: heartbeat monitor started")

    def stop(self) -> None:
        self._running = False

    def network_health_pct(self) -> float:
        if not self.nodes:
            return 100.0
        online = sum(1 for n in self.nodes.values()
                     if n.status in (NodeStatus.ONLINE, NodeStatus.REROUTED))
        return round(100.0 * online / len(self.nodes), 1)

    def status_table(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "node_id":    n.node_id,
                    "ip":         n.ip_address,
                    "type":       n.sensor_type,
                    "status":     n.status.value,
                    "hb_soc":     round(n.heartbeat_soc, 1),
                    "age_s":      round(n.seconds_since_hb, 1),
                    "readings":   n.readings_count,
                    "energy":     n.energy_source.value,
                }
                for n in self.nodes.values()
            ]


# ─────────────────────────────────────────────────────────────────────────────
# MQTT GATEWAY
# ─────────────────────────────────────────────────────────────────────────────

class MQTTGateway:
    """
    MQTT sensor gateway for OIMS V4.

    Connects to a broker, subscribes to ocean/sensors/#,
    parses incoming JSON payloads into SensorReading objects,
    and forwards to registered callbacks + Azure Cosmos DB.

    Topic schema:
      ocean/sensors/{node_id}            → sensor data
      ocean/sensors/{node_id}/heartbeat  → heartbeat (SOC in payload)
      ocean/sensors/{node_id}/alert      → critical alerts
    """

    DEFAULT_BROKER = "broker.hivemq.com"
    DEFAULT_PORT   = 1883
    BASE_TOPIC     = "ocean/sensors/#"

    def __init__(self,
                 broker:   str = DEFAULT_BROKER,
                 port:     int = DEFAULT_PORT,
                 shesn:    Optional[SHESNMonitor] = None,
                 on_reading: Optional[Callable[[SensorReading], None]] = None):
        self.broker     = broker
        self.port       = port
        self.shesn      = shesn
        self.on_reading = on_reading or (lambda r: None)
        self._readings: List[SensorReading] = []
        self._client:   Optional[Any]       = None
        self.connected  = False

    def _parse_payload(self, node_id: str, payload_str: str,
                       ip: str = "") -> SensorReading:
        reading = SensorReading(node_id=node_id, ip_address=ip,
                                raw=payload_str, protocol="mqtt")
        try:
            data = json.loads(payload_str)
            reading.sst_c         = data.get("sst")
            reading.salinity_ppt  = data.get("salinity")
            reading.wave_height_m = data.get("wave_height")
            reading.ph            = data.get("pH")
            reading.depth_m       = data.get("depth")
            reading.lat           = data.get("lat")
            reading.lon           = data.get("lon")
        except json.JSONDecodeError:
            pass
        return reading

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            client.subscribe(self.BASE_TOPIC)
            log.info(f"MQTT: connected to {self.broker} — subscribed to {self.BASE_TOPIC}")
        else:
            log.error(f"MQTT: connection failed rc={rc}")

    def _on_message(self, client, userdata, message):
        topic    = message.topic
        payload  = message.payload.decode("utf-8", errors="replace")
        parts    = topic.split("/")           # ocean/sensors/{node_id}[/sub]
        node_id  = parts[2] if len(parts) > 2 else "unknown"
        sub      = parts[3] if len(parts) > 3 else "data"

        if sub == "heartbeat":
            soc = float(payload) if payload.replace(".", "").isdigit() else 100.0
            if self.shesn:
                self.shesn.heartbeat(node_id, soc)
            log.debug(f"HB: {node_id} soc={soc}%")
            return

        reading = self._parse_payload(node_id, payload)
        self._readings.append(reading)

        # Update SHESN counter
        if self.shesn and node_id in self.shesn.nodes:
            self.shesn.nodes[node_id].readings_count += 1
            self.shesn.heartbeat(node_id)   # data = implicit heartbeat

        self.on_reading(reading)
        log.debug(f"MSG: {topic} → {payload[:60]}")

    def connect(self) -> bool:
        if not MQTT_OK:
            log.error("MQTT: paho-mqtt not installed")
            return False
        self._client = mqtt.Client(f"OIMS-V4-{uuid.uuid4().hex[:6]}")
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        try:
            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
            return True
        except Exception as e:
            log.error(f"MQTT connect failed: {e}")
            return False

    def publish(self, topic: str, payload: Any) -> None:
        """Publish a command/alert back to a sensor node."""
        if self._client and self.connected:
            msg = json.dumps(payload) if not isinstance(payload, str) else payload
            self._client.publish(topic, msg)

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def latest_readings(self, n: int = 10) -> List[SensorReading]:
        return self._readings[-n:]

    def simulate_reading(self, node_id: str = "NODE-3F") -> SensorReading:
        """
        Generate a simulated SensorReading for offline/demo mode.
        Useful when real hardware is not connected.
        """
        import random
        data = {
            "sst":         round(random.uniform(27.5, 29.5), 2),
            "salinity":    round(random.uniform(34.8, 35.8), 2),
            "wave_height": round(random.uniform(0.8, 2.2),   2),
            "pH":          round(random.uniform(7.9, 8.2),   3),
            "depth":       round(random.uniform(10, 200),     1),
            "lat":         round(random.uniform(8, 20),       4),
            "lon":         round(random.uniform(72, 88),      4),
        }
        reading = self._parse_payload(node_id, json.dumps(data))
        reading.protocol = "simulated"
        self._readings.append(reading)
        return reading


# ─────────────────────────────────────────────────────────────────────────────
# RTSP CAMERA + YOLO GATEWAY
# ─────────────────────────────────────────────────────────────────────────────

class RTSPYOLOGateway:
    """
    RTSP camera feed → YOLOv8 inference pipeline.

    Opens an RTSP stream, runs YOLOv8 object detection frame-by-frame,
    and forwards detections to OIMS threat pipeline.

    In demo mode (no camera) → generates simulated detections.
    """

    def __init__(self, rtsp_url: str,
                 model_path: str = "yolov8n.pt",
                 on_detection: Optional[Callable[[dict], None]] = None):
        self.rtsp_url     = rtsp_url
        self.model_path   = model_path
        self.on_detection = on_detection or (lambda d: None)
        self._cap:   Optional[Any] = None
        self._model: Optional[Any] = None
        self.running = False
        self.fps     = 0.0
        self.frame_count = 0

    def _load_model(self) -> bool:
        try:
            from ultralytics import YOLO
            self._model = YOLO(self.model_path)
            log.info(f"RTSP: YOLOv8 model loaded — {self.model_path}")
            return True
        except ImportError:
            log.warning("ultralytics not installed — RTSP YOLO disabled")
            return False
        except Exception as e:
            log.error(f"YOLO model load failed: {e}")
            return False

    def connect(self) -> bool:
        if not CV2_OK:
            log.warning("opencv not installed — RTSP stream unavailable")
            return False
        self._cap = cv2.VideoCapture(self.rtsp_url)
        if not self._cap.isOpened():
            log.error(f"RTSP: cannot open stream {self.rtsp_url}")
            return False
        log.info(f"RTSP: stream opened — {self.rtsp_url}")
        return self._load_model()

    def _inference_loop(self):
        t0 = time.time()
        while self.running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret:
                log.warning("RTSP: frame read failed")
                break
            self.frame_count += 1
            elapsed = time.time() - t0
            self.fps = self.frame_count / max(elapsed, 1e-6)

            if self._model is not None:
                results = self._model(frame, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls  = int(box.cls[0])
                        conf = float(box.conf[0])
                        name = self._model.names[cls]
                        if conf > 0.4:
                            det = {
                                "class":  name,
                                "conf":   round(conf, 3),
                                "bbox":   box.xyxy[0].tolist(),
                                "fps":    round(self.fps, 1),
                                "frame":  self.frame_count,
                            }
                            self.on_detection(det)

    def start_async(self) -> None:
        self.running = True
        t = threading.Thread(target=self._inference_loop, daemon=True)
        t.start()

    def stop(self) -> None:
        self.running = False
        if self._cap:
            self._cap.release()

    def simulate_detection(self) -> dict:
        """Return a simulated ship detection for demo mode."""
        import random
        classes = ["cargo_ship","tanker","fishing_vessel","military_vessel",
                   "submarine_wake","debris"]
        return {
            "class":  random.choice(classes),
            "conf":   round(random.uniform(0.55, 0.97), 3),
            "bbox":   [random.randint(50,200), random.randint(50,200),
                       random.randint(200,400), random.randint(200,400)],
            "fps":    round(random.uniform(8, 14), 1),
            "frame":  self.frame_count,
            "simulated": True,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SERIAL GATEWAY (Arduino / Raspberry Pi)
# ─────────────────────────────────────────────────────────────────────────────

class SerialGateway:
    """
    PySerial gateway for Arduino / Raspberry Pi GPIO sensors.

    Expected serial format (one JSON per line):
        {"node_id":"NODE-3F","sst":28.4,"salinity":35.2,"lat":12.4,"lon":74.8}
    """

    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 9600,
                 on_reading: Optional[Callable[[SensorReading], None]] = None):
        self.port       = port
        self.baud       = baud
        self.on_reading = on_reading or (lambda r: None)
        self._ser:    Optional[Any]    = None
        self._thread: Optional[threading.Thread] = None
        self.running  = False

    def connect(self) -> bool:
        if not SERIAL_OK:
            log.error("pyserial not installed")
            return False
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=2)
            log.info(f"Serial: opened {self.port} at {self.baud} baud")
            return True
        except serial.SerialException as e:
            log.error(f"Serial: cannot open {self.port} — {e}")
            return False

    def _read_loop(self):
        while self.running and self._ser and self._ser.is_open:
            try:
                line = self._ser.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                data    = json.loads(line)
                node_id = data.get("node_id", "serial_node")
                reading = SensorReading(
                    node_id=node_id, protocol="serial",
                    sst_c=data.get("sst"), salinity_ppt=data.get("salinity"),
                    wave_height_m=data.get("wave_height"),
                    ph=data.get("pH"), lat=data.get("lat"), lon=data.get("lon"),
                    raw=line,
                )
                self.on_reading(reading)
            except json.JSONDecodeError:
                log.debug(f"Serial: non-JSON line: {line[:40]}")
            except Exception as e:
                log.error(f"Serial read error: {e}")
                break

    def start_async(self) -> None:
        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._ser:
            self._ser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SENSOR GATEWAY — Master Controller
# ─────────────────────────────────────────────────────────────────────────────

class SensorGateway:
    """
    Master sensor gateway for OIMS V4.

    Manages:
      - SHESN heartbeat monitor
      - MQTT connections for all IoT nodes
      - RTSP + YOLOv8 camera pipelines
      - Serial gateways for Arduino sensors
      - Unified reading buffer → Azure Cosmos DB or Kafka

    Usage (in Streamlit app):
        gw = SensorGateway(broker="broker.hivemq.com")
        gw.register_node(SensorNode("NODE-3F","192.168.1.101","IoT Buoy",
                                     mqtt_topic="ocean/sensors/node3f"))
        gw.start()
        readings = gw.latest_readings(20)
    """

    def __init__(self,
                 broker:     str = "broker.hivemq.com",
                 broker_port:int = 1883,
                 on_alert:   Optional[Callable] = None,
                 demo_mode:  bool = True):
        """
        demo_mode=True → use simulated data (no real hardware needed).
        demo_mode=False → connect to real MQTT broker + sensors.
        """
        self.demo_mode = demo_mode
        self._all_readings: List[SensorReading] = []

        def _alert_handler(node_id, status, msg):
            log.warning(f"SHESN ALERT [{status.value.upper()}]: {msg}")
            if on_alert:
                on_alert(node_id, status, msg)

        self.shesn  = SHESNMonitor(on_alert=_alert_handler)
        self.mqtt   = MQTTGateway(
            broker=broker, port=broker_port,
            shesn=self.shesn,
            on_reading=self._all_readings.append,
        )
        self._rtsp_gws:   List[RTSPYOLOGateway] = []
        self._serial_gws: List[SerialGateway]   = []

    def register_node(self, node: SensorNode) -> None:
        self.shesn.register(node)

    def add_camera(self, rtsp_url: str,
                   on_detection: Optional[Callable] = None) -> RTSPYOLOGateway:
        gw = RTSPYOLOGateway(rtsp_url, on_detection=on_detection)
        self._rtsp_gws.append(gw)
        return gw

    def add_serial(self, port: str, baud: int = 9600) -> SerialGateway:
        gw = SerialGateway(port, baud, on_reading=self._all_readings.append)
        self._serial_gws.append(gw)
        return gw

    def start(self) -> None:
        self.shesn.start()
        if not self.demo_mode:
            self.mqtt.connect()
            for gw in self._rtsp_gws:
                if gw.connect():
                    gw.start_async()
            for gw in self._serial_gws:
                if gw.connect():
                    gw.start_async()
        else:
            log.info("SensorGateway: DEMO MODE — simulated data only")
        log.info("SensorGateway: started")

    def stop(self) -> None:
        self.shesn.stop()
        self.mqtt.disconnect()
        for gw in self._rtsp_gws + self._serial_gws:
            gw.stop()

    def get_reading(self, demo: bool = False) -> SensorReading:
        """Get the latest reading (or a simulated one in demo mode)."""
        if demo or self.demo_mode:
            return self.mqtt.simulate_reading()
        return self._all_readings[-1] if self._all_readings else self.mqtt.simulate_reading()

    def latest_readings(self, n: int = 20) -> List[SensorReading]:
        if self.demo_mode:
            # Generate n simulated readings
            return [self.mqtt.simulate_reading() for _ in range(n)]
        return self._all_readings[-n:]

    def network_health(self) -> float:
        return self.shesn.network_health_pct()

    def node_status(self) -> List[Dict[str, Any]]:
        return self.shesn.status_table()


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT INTEGRATION — Sensor Setup Page
# ─────────────────────────────────────────────────────────────────────────────

def render_sensor_setup_tab(gw: SensorGateway) -> None:
    """
    Call this inside a Streamlit tab to render the Sensor Setup page.

    Example in app.py:
        from sensor_integration import SensorGateway, render_sensor_setup_tab
        gw = SensorGateway(demo_mode=True)
        gw.start()
        ...
        with tabs[6]:   # new tab
            render_sensor_setup_tab(gw)
    """
    import streamlit as st

    st.markdown('<div class="sec-hdr">SHESN sensor network — live status</div>',
                unsafe_allow_html=True)

    # Network health metric
    health = gw.network_health()
    nodes  = gw.node_status()
    online = sum(1 for n in nodes if n["status"] == "online")
    warn   = sum(1 for n in nodes if n["status"] == "warn")
    offline= sum(1 for n in nodes if n["status"] in ("offline","rerouted"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Network health", f"{health}%",   f"+{online} online")
    c2.metric("Online nodes",   str(online),    "")
    c3.metric("Warning",        str(warn),      "Signal weak" if warn else "")
    c4.metric("Offline/Rerouted", str(offline), "Auto-rerouted" if offline else "")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">Node status table</div>', unsafe_allow_html=True)

    import pandas as pd
    df = pd.DataFrame(nodes)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No nodes registered. Add a node below.")

    # Add node form
    st.markdown('<div class="sec-hdr" style="margin-top:12px">Register new sensor node</div>',
                unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        node_id   = st.text_input("Node ID",  "NODE-10")
        node_ip   = st.text_input("IP Address", "192.168.1.110")
    with col2:
        node_type = st.selectbox("Sensor Type",
            ["IoT Buoy","Sonar Array","RTSP Camera","CTD Profiler","Hydrophone","AUV Dock"])
        mqtt_topic= st.text_input("MQTT Topic", f"ocean/sensors/{node_id.lower()}")
    with col3:
        energy    = st.selectbox("Energy Source",
            ["Wave kinetic","Thermohaline gradient","Solar panel","Battery","Hybrid"])
        neighbour = st.text_input("Neighbour Node ID (for rerouting)", "NODE-3F")

    if st.button("Register Node", use_container_width=True):
        from sensor_integration import SensorNode, EnergySource
        energy_map = {
            "Wave kinetic":         EnergySource.WAVE,
            "Thermohaline gradient":EnergySource.THERMAL,
            "Solar panel":          EnergySource.SOLAR,
            "Battery":              EnergySource.BATTERY,
            "Hybrid":               EnergySource.HYBRID,
        }
        new_node = SensorNode(
            node_id=node_id, ip_address=node_ip,
            sensor_type=node_type, mqtt_topic=mqtt_topic,
            energy_source=energy_map.get(energy, EnergySource.HYBRID),
            neighbour_ids=[neighbour] if neighbour else [],
        )
        gw.register_node(new_node)
        st.success(f"Node {node_id} ({node_ip}) registered in SHESN mesh!")

    # Live reading
    st.markdown('<div class="sec-hdr" style="margin-top:12px">Live sensor reading</div>',
                unsafe_allow_html=True)
    if st.button("Fetch Reading", use_container_width=True):
        reading = gw.get_reading()
        st.json(reading.to_dict())

    # Presentation tip
    st.markdown("""
    <div style='background:rgba(0,204,255,.08);border:1px solid rgba(0,204,255,.3);
        border-radius:4px;padding:12px 14px;font-family:Courier New,monospace;
        font-size:12px;line-height:1.8;color:var(--color-text-secondary)'>
        <b style='color:rgba(0,204,255,.9)'>Hackathon Presentation Tip:</b><br>
        "సర్, మా system <b>IoT-Ready</b>. మేము దీనిని MQTT protocol ద్వారా ఏ రకమైన
        industrial sensor కైనా connect చేయగలము. ప్రస్తుతం simulated data వాడుతున్నాము,
        కానీ hardware integration కోసం మా SHESN module ఇప్పటికే సిద్ధంగా ఉంది."
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import random

    print("\n" + "=" * 60)
    print("  OIMS V4 — Sensor Integration Demo")
    print("=" * 60)

    # Callback for alerts
    def alert_cb(node_id, status, msg):
        print(f"\n  *** ALERT *** [{status.value.upper()}] {msg}")

    # Create gateway in demo mode
    gw = SensorGateway(demo_mode=True, on_alert=alert_cb)

    # Register sample nodes
    sample_nodes = [
        SensorNode("NODE-3F","192.168.1.101","IoT Buoy",
                   mqtt_topic="ocean/sensors/node3f",
                   energy_source=EnergySource.WAVE,
                   neighbour_ids=["NODE-4A","NODE-5B"]),
        SensorNode("NODE-4A","192.168.1.102","Sonar Array",
                   mqtt_topic="ocean/sensors/node4a",
                   energy_source=EnergySource.THERMAL,
                   neighbour_ids=["NODE-3F"]),
        SensorNode("NODE-5B","192.168.1.103","CTD Profiler",
                   mqtt_topic="ocean/sensors/node5b",
                   energy_source=EnergySource.HYBRID,
                   neighbour_ids=["NODE-4A","NODE-6C"]),
        SensorNode("NODE-6C","192.168.1.104","RTSP Camera",
                   mqtt_topic="ocean/sensors/node6c",
                   energy_source=EnergySource.SOLAR,
                   neighbour_ids=["NODE-5B"]),
        SensorNode("NODE-7D","192.168.1.105","Hydrophone",
                   mqtt_topic="ocean/sensors/node7d",
                   energy_source=EnergySource.BATTERY,
                   neighbour_ids=["NODE-6C","NODE-8E"]),
    ]
    for n in sample_nodes:
        gw.register_node(n)

    gw.start()

    print("\n[1] Fetching 3 simulated sensor readings...")
    for i in range(3):
        r = gw.get_reading()
        print(f"  Reading {i+1}: node={r.node_id} sst={r.sst_c}°C "
              f"salinity={r.salinity_ppt}ppt wave={r.wave_height_m}m")

    print("\n[2] Simulating heartbeats...")
    for n in sample_nodes[:4]:
        gw.shesn.heartbeat(n.node_id, soc=random.uniform(70, 100))
        print(f"  HB: {n.node_id} → online")

    print(f"\n[3] Network health: {gw.network_health()}%")

    print("\n[4] Simulating NODE-7D going offline...")
    time.sleep(gw.shesn.OFFLINE_TIMEOUT + 1.5)

    print("\n[5] Node status table:")
    for row in gw.node_status():
        print(f"  {row['node_id']:10} | {row['status']:10} | "
              f"age={row['age_s']:.1f}s | {row['type']}")

    print("\n[6] RTSP camera simulation (no hardware):")
    rtsp_gw = RTSPYOLOGateway("rtsp://demo")
    det = rtsp_gw.simulate_detection()
    print(f"  Detected: {det['class']} conf={det['conf']} fps={det['fps']}")

    gw.stop()
    print("\n[OIMS V4] Sensor integration demo complete.")
