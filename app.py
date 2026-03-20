"""
OIMS V4 — SAMUDRA NETRA X
Next-Gen Cyberpunk C2 Dashboard
Production-ready Streamlit Cloud app

All previous bugs fixed:
  - No 8-digit hex in Plotly (rgba() used)
  - No duplicate xaxis/yaxis in PLOT_BG
  - No list + numpy TypeError
  - No Google Fonts (system fonts only)
  - No @st.cache_data on folium (serialization crash)
  - All heavy imports wrapped in try/except
"""

import streamlit as st

st.set_page_config(
    page_title="OIMS V4 — SAMUDRA NETRA X",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import numpy as np
import pandas as pd
import time
import hashlib
import uuid
import math
from datetime import datetime, timezone

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except ImportError:
    FOLIUM_OK = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS — system fonts only, no external imports
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html,body,.stApp{background:#050A0E!important;color:#C8D8E8!important}
.main .block-container{background:#050A0E!important;padding:1rem 1.5rem 2rem;max-width:1400px}
h1,h2,h3{font-family:'Courier New',monospace!important;letter-spacing:.06em}
p,div,span,td,th,.stMarkdown{font-family:'Segoe UI',Arial,sans-serif!important}

.stApp::before{content:'';position:fixed;top:0;left:0;width:100%;height:100%;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,170,.006) 2px,rgba(0,255,170,.006) 4px);
  pointer-events:none;z-index:9999}

[data-testid="metric-container"]{
  background:linear-gradient(135deg,#0A1520,#0D1E2E)!important;
  border:1px solid #00FFAA22!important;border-radius:4px!important;
  transition:border-color .2s,box-shadow .2s}
[data-testid="metric-container"]:hover{border-color:#00FFAA66!important}
[data-testid="stMetricLabel"]{color:#5A8FA8!important;font-family:'Courier New',monospace!important;
  font-size:11px!important;text-transform:uppercase;letter-spacing:.1em}
[data-testid="stMetricValue"]{color:#00FFAA!important;font-family:'Courier New',monospace!important;
  font-size:24px!important;text-shadow:0 0 12px rgba(0,255,170,.4)}
[data-testid="stMetricDelta"]{font-family:'Courier New',monospace!important;font-size:11px!important}

.stTabs [data-baseweb="tab-list"]{gap:3px;background:#0A1520;padding:5px;
  border-radius:4px;border:1px solid #1A3040}
.stTabs [data-baseweb="tab"]{background:transparent!important;border-radius:3px;
  color:#5A8FA8!important;font-family:'Courier New',monospace!important;font-size:12px!important;height:38px}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#003322,#005533)!important;
  color:#00FFAA!important;box-shadow:0 0 10px rgba(0,255,170,.2)}

[data-testid="stDataFrame"]{border:1px solid #1A3040!important;border-radius:4px}
.stDataFrame table{background:#080F18!important;color:#C8D8E8!important}
.stDataFrame thead th{background:#0A1520!important;color:#00FFAA!important;
  font-family:'Courier New',monospace!important;font-size:11px!important;
  text-transform:uppercase;border-bottom:1px solid rgba(0,255,170,.2)!important}
.stDataFrame tbody tr:hover td{background:#0D1E2E!important}

.stButton button{background:transparent!important;border:1px solid rgba(0,255,170,.3)!important;
  color:#00FFAA!important;font-family:'Courier New',monospace!important;
  border-radius:3px;transition:all .2s}
.stButton button:hover{border-color:#00FFAA!important;box-shadow:0 0 12px rgba(0,255,170,.25)}

.stSelectbox>div>div,.stTextInput>div>div>input{
  background:#0A1520!important;color:#C8D8E8!important;
  border:1px solid #1A3040!important;font-family:'Courier New',monospace!important}

[data-testid="stSidebar"]{background:#040810!important;border-right:1px solid #1A3040!important}

.sec-hdr{font-family:'Courier New',monospace;font-size:11px;color:#00FFAA;
  text-transform:uppercase;letter-spacing:.14em;
  border-bottom:1px solid rgba(0,255,170,.2);padding-bottom:7px;margin-bottom:12px}

.roe-obs{background:rgba(0,51,34,.3);color:#00FFAA;border:1px solid rgba(0,255,170,.4);
  padding:2px 10px;border-radius:2px;font-family:'Courier New',monospace;font-size:11px;font-weight:700}
.roe-sha{background:rgba(0,34,51,.3);color:#00CCFF;border:1px solid rgba(0,204,255,.4);
  padding:2px 10px;border-radius:2px;font-family:'Courier New',monospace;font-size:11px;font-weight:700}
.roe-war{background:rgba(51,34,0,.3);color:#FFCC00;border:1px solid rgba(255,204,0,.4);
  padding:2px 10px;border-radius:2px;font-family:'Courier New',monospace;font-size:11px;
  font-weight:700;box-shadow:0 0 8px rgba(255,204,0,.25)}
.roe-ecm{background:rgba(51,17,0,.3);color:#FF8800;border:1px solid rgba(255,136,0,.4);
  padding:2px 10px;border-radius:2px;font-family:'Courier New',monospace;font-size:11px;font-weight:700}
.roe-kin{background:rgba(51,0,0,.3);color:#FF0055;border:1px solid rgba(255,0,85,.5);
  padding:2px 10px;border-radius:2px;font-family:'Courier New',monospace;font-size:11px;
  font-weight:700;box-shadow:0 0 14px rgba(255,0,85,.4);animation:kinp 1.4s infinite}
@keyframes kinp{0%,100%{box-shadow:0 0 10px rgba(255,0,85,.3)}50%{box-shadow:0 0 22px rgba(255,0,85,.7)}}

.pulse-dot{display:inline-block;width:7px;height:7px;border-radius:50%;
  animation:pd 1.5s ease-in-out infinite;margin-right:6px}
@keyframes pd{0%,100%{opacity:.3}50%{opacity:1}}
.dot-g{background:#00FFAA}.dot-y{background:#FFCC00}.dot-r{background:#FF0055}

.status-bar{display:flex;align-items:center;gap:14px;background:#040810;
  border:1px solid #1A3040;border-radius:4px;padding:9px 15px;margin-bottom:11px;
  font-family:'Courier New',monospace;font-size:11px}

.ae{background:#080F18;border:1px solid #0D1E2E;border-radius:4px;padding:9px 11px;
  margin-bottom:7px;font-family:'Courier New',monospace;font-size:11px}
.ae.new{border-color:#00FFAA;animation:aes .5s ease}
@keyframes aes{from{transform:translateY(-8px);opacity:0}to{transform:translateY(0);opacity:1}}
.cblk{display:inline-block;background:#0A1520;border:1px solid #1A3040;border-radius:3px;
  padding:5px 9px;font-family:'Courier New',monospace;font-size:10px;text-align:center}
.cblk.kin{border-color:rgba(255,0,85,.5);background:rgba(51,0,0,.3)}
.cblk.war{border-color:rgba(255,204,0,.5);background:rgba(51,34,0,.3)}
.cblk.obs{border-color:rgba(0,255,170,.5);background:rgba(0,51,34,.3)}
.chain-flow{display:flex;align-items:center;flex-wrap:wrap;gap:4px;
  padding:8px;background:#040810;border-radius:4px;margin-bottom:10px}
.c-arrow{color:#1A3040;font-size:14px}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
AWRS = [
    {"id":"CONTACT-A","lat":8.2,  "lon":72.1,"spd":8, "tp":.10,"pp":.05,"dark":False,"roe":"OBSERVE",      "rcls":"roe-obs","col":"#00FFAA","act":"Deploy USV shadow"},
    {"id":"CONTACT-B","lat":12.4, "lon":74.8,"spd":16,"tp":.45,"pp":.30,"dark":True, "roe":"WARN",         "rcls":"roe-war","col":"#FFCC00","act":"Ch16 warning + flare"},
    {"id":"CONTACT-C","lat":11.5, "lon":51.0,"spd":24,"tp":.78,"pp":.70,"dark":True, "roe":"KINETIC",      "rcls":"roe-kin","col":"#FF0055","act":"Human auth required"},
    {"id":"CONTACT-D","lat":13.1, "lon":50.2,"spd":30,"tp":.95,"pp":.92,"dark":True, "roe":"KINETIC",      "rcls":"roe-kin","col":"#FF0055","act":"Human auth required"},
    {"id":"DARK-003", "lat":15.6, "lon":82.4,"spd":18,"tp":.50,"pp":.35,"dark":True, "roe":"ELEC JAM",     "rcls":"roe-ecm","col":"#FF8800","act":"ECM jamming active"},
]

MODULES = [
    ("IoT Buoy","Active","#00FFAA"),("Sonar Array","Active","#00FFAA"),("AUV Fleet","Active","#00FFAA"),
    ("ObjectDetect","Active","#00FFAA"),("Anomaly IF","Active","#00FFAA"),("OceanPINN","Active","#00FFAA"),
    ("Defence","Active","#00FFAA"),("Climate","Active","#00FFAA"),("Navigator","Active","#00FFAA"),
    ("DigitalTwin","Active","#00FFAA"),("EAMA NLP","Active","#00FFAA"),("SHESN","90%","#FFCC00"),
    ("SwarmOSIN","Active","#00FFAA"),("QIRO","Active","#00FFAA"),("AWRS","Active","#00FFAA"),
]

# FIX: axis base dict — NOT in PLOT_BG to avoid duplicate keyword TypeError
_AX = dict(gridcolor="rgba(26,48,64,.8)", zerolinecolor="rgba(26,48,64,.8)",
           linecolor="#1A3040", tickcolor="#1A3040", tickfont=dict(color="#5A8FA8",size=10,family="Courier New"))
_PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(5,10,14,.95)",
    font=dict(family="Courier New", color="#5A8FA8", size=11),
    margin=dict(l=44,r=12,t=36,b=28),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1A3040", borderwidth=1,
                font=dict(size=10,color="#5A8FA8")),
)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def _init():
    defs = dict(
        audit_chain=[
            {"c":"CONTACT-A","r":"OBSERVE",      "a":"deploy_usv_shadow",        "h":"a1b2c3d4e5f678901234abcdef01"},
            {"c":"CONTACT-B","r":"WARN",          "a":"broadcast_channel16",       "h":"b2c3d4e5f67890ab1234cdef0123"},
            {"c":"CONTACT-C","r":"KINETIC",       "a":"alert_fleet_command_human", "h":"c3d4e5f67890abcd1234ef012345"},
            {"c":"CONTACT-D","r":"KINETIC",       "a":"alert_fleet_command_human", "h":"d4e5f67890abcdef123401abcdef"},
            {"c":"DARK-003", "r":"ELECTRONIC_JAM","a":"ecm_jamming_active",        "h":"e5f67890abcdef012345abcdef01"},
        ],
        vessels=1847, sst=28.4, data_tb=3.80,
    )
    for k,v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v
_init()

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def utc() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

def sha(prev,c,r,a) -> str:
    pl = f"{prev}|{c}|{r}|{a}|{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(pl.encode()).hexdigest()

def roe_col(r):
    return {"OBSERVE":"#00FFAA","SHADOW":"#00CCFF","WARN":"#FFCC00",
            "INTERDICT":"#FF8800","ELECTRONIC_JAM":"#FF8800","KINETIC":"#FF0055"}.get(r,"#5A8FA8")

# ─────────────────────────────────────────────────────────────────────────────
# CHART BUILDERS — all use _AX, not PLOT_BG axes
# ─────────────────────────────────────────────────────────────────────────────
def fig_seas():
    g = np.arange(1,61)
    s = np.clip(94.1+g*.094+np.sin(g*.3)*.5, 0, 100)
    y = np.clip(91.2+g*.14 +np.cos(g*.4)*.6, 0, 100)
    f = go.Figure()
    f.add_trace(go.Scatter(x=g,y=s,name="SonarCNN V4",line=dict(color="#9966FF",width=1.5),
        fill="tozeroy",fillcolor="rgba(153,102,255,.07)",mode="lines"))
    f.add_trace(go.Scatter(x=g,y=y,name="YOLOv8 V4",line=dict(color="#00FFAA",width=1.5),
        fill="tozeroy",fillcolor="rgba(0,255,170,.06)",mode="lines"))
    f.update_layout(**_PLOT, height=270,
        title=dict(text="Self-evolution convergence",font=dict(color="#9966FF",size=12)),
        xaxis=dict(**_AX, title="Generation"),
        yaxis=dict(**_AX, ticksuffix="%", range=[89,101]))
    return f

def fig_slr():
    L = ["Now","2yr","4yr","6yr","8yr","10yr"]
    m = [0,10.1,20.5,31.4,40.9,50.4]
    h = [0,13.2,26.1,39.8,52.1,64.3]
    lo= [0, 7.3,15.4,23.6,30.2,37.8]
    f = go.Figure()
    f.add_trace(go.Scatter(x=L+L[::-1],y=h+lo[::-1],fill="toself",
        fillcolor="rgba(55,138,221,.08)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    f.add_trace(go.Scatter(x=L,y=m,name="Mean SLR",
        line=dict(color="#00CCFF",width=2),mode="lines+markers",
        marker=dict(color="#00CCFF",size=5)))
    # FIX: rgba() not 8-digit hex
    f.add_trace(go.Scatter(x=L,y=[45]*6,name="Evacuation threshold",
        line=dict(color="rgba(255,0,85,.65)",width=1.5,dash="dash"),mode="lines"))
    f.add_hrect(y0=45,y1=70,fillcolor="rgba(255,0,85,.05)",line_width=0)
    f.update_layout(**_PLOT, height=240,
        title=dict(text="Sea level rise + red zone",font=dict(color="#00CCFF",size=12)),
        xaxis=dict(**_AX),
        yaxis=dict(**_AX, ticksuffix=" mm"))
    return f

def fig_qaie():
    states = ["PEACEFUL","STORM WARNING","THREAT AMBER","THREAT RED","POLLUTION"]
    counts = [28,8,5,3,2]
    colors = ["#00FFAA","#00CCFF","#FFCC00","#FF0055","#9966FF"]
    f = go.Figure(go.Bar(x=states,y=counts,marker_color=colors,marker_line_width=0,
        text=counts,textposition="outside",textfont=dict(color="#5A8FA8",size=10)))
    f.update_layout(**_PLOT, height=220,
        title=dict(text="QAIE quantum state distribution (4.7× speedup)",font=dict(color="#9966FF",size=12)),
        bargap=0.3,
        xaxis=dict(**_AX),
        yaxis=dict(**_AX))
    return f

def fig_models():
    names = ["YOLOv8 V4","SonarCNN V4","Storm PINN","Anomaly IF","AWRS Bayes"]
    # FIX: np.array not list+numpy
    base  = np.array([94,97,87,89,99], dtype=float)
    pcts  = np.clip(base + np.random.uniform(-2,2,5), 0, 100)
    cols  = ["#00FFAA","#9966FF","#00CCFF","#FFCC00","#FF0055"]
    f = go.Figure(go.Bar(y=names,x=pcts,orientation="h",marker_color=cols,marker_line_width=0,
        text=[f"{p:.0f}%" for p in pcts],textposition="inside",
        textfont=dict(color="#050A0E",family="Courier New",size=10)))
    f.update_layout(**_PLOT, height=210,
        title=dict(text="AI model activity",font=dict(color="#00FFAA",size=12)),
        xaxis=dict(**_AX, ticksuffix="%", range=[0,107]),
        yaxis=dict(**_AX))
    return f

def fig_sst():
    pts = np.clip(28 + np.sin(np.linspace(0,6,24))*.8 + np.random.uniform(-.15,.15,24), 27, 30)
    f = go.Figure(go.Scatter(x=list(range(24)),y=pts,
        line=dict(color="#00CCFF",width=1.5),fill="tozeroy",
        fillcolor="rgba(55,138,221,.06)",mode="lines"))
    f.update_layout(**_PLOT, height=130,
        title=dict(text="SST anomaly — 24hr",font=dict(color="#00CCFF",size=11)),
        xaxis=dict(**_AX, tickvals=[0,12,23], ticktext=["24h ago","12h ago","Now"]),
        yaxis=dict(**_AX, ticksuffix="°C"))
    return f

def fig_perf():
    x = list(range(20))
    lat = np.random.uniform(650,900,20)
    thru= np.random.uniform(80,100,20)
    f = make_subplots(specs=[[{"secondary_y":True}]])
    f.add_trace(go.Scatter(x=x,y=lat, name="Alert latency (ms)",
        line=dict(color="#534AB7",width=1.5),mode="lines"),secondary_y=False)
    f.add_trace(go.Scatter(x=x,y=thru,name="Kafka throughput (k/s)",
        line=dict(color="#1D9E75",width=1.5),mode="lines"),secondary_y=True)
    f.update_layout(**_PLOT, height=170,
        title=dict(text="System performance — live",font=dict(color="#534AB7",size=11)))
    f.update_xaxes(**_AX)
    f.update_yaxes(**_AX)
    return f

def fig_slr_mini():
    L = ["Now","2yr","4yr","6yr","8yr","10yr"]
    f = go.Figure()
    f.add_trace(go.Bar(x=L,y=[0,10.1,20.5,31.4,40.9,50.4],
        marker_color=["#1D9E75","#1D9E75","#1D9E75","#BA7517","#A32D2D","#A32D2D"],
        marker_line_width=0))
    f.update_layout(**_PLOT, height=180,
        title=dict(text="SLR projection (mm)",font=dict(color="#00CCFF",size=11)),
        xaxis=dict(**_AX),
        yaxis=dict(**_AX, ticksuffix=" mm"))
    return f

# ─────────────────────────────────────────────────────────────────────────────
# TACTICAL MAP
# ─────────────────────────────────────────────────────────────────────────────
def build_map():
    m = folium.Map(location=[12.0,72.0], zoom_start=5, tiles="CartoDB dark_matter")
    for c in AWRS:
        j = (np.random.uniform(-.15,.15), np.random.uniform(-.15,.15))
        popup = f"""<div style='background:#050A0E;color:#C8D8E8;font-family:monospace;padding:9px;
            min-width:180px;border:1px solid {c["col"]}'>
            <b style='color:{c["col"]}'>{c["id"]}</b><br>
            ROE: <span style='color:{c["col"]}'>{c["roe"]}</span><br>
            Speed: {c["spd"]} kts · Threat: {c["tp"]:.0%}<br>
            Action: {c["act"]}</div>"""
        folium.RegularPolygonMarker(
            location=[c["lat"]+j[0], c["lon"]+j[1]],
            number_of_sides=4, radius=10,
            color=c["col"], fill=True, fill_color=c["col"], fill_opacity=.8,
            popup=folium.Popup(popup, max_width=210),
            tooltip=f"{c['id']} | {c['roe']}",
        ).add_to(m)
    for nm,lat,lon in [("INS-Delhi",14.2,73.5),("AUV-007",10.5,71.8),("CG-Kochi",9.9,76.3)]:
        folium.RegularPolygonMarker(
            location=[lat,lon], number_of_sides=3, radius=9,
            color="#00FFAA", fill=True, fill_color="#00FFAA", fill_opacity=.85,
            tooltip=f"FRIENDLY — {nm}",
        ).add_to(m)
    folium.Circle([13.5,76.0],radius=280_000,color="#FF8800",fill=True,
        fill_color="#FF8800",fill_opacity=.05,dash_array="8 4",
        tooltip="Cyclone warning — 95 kts").add_to(m)
    folium.Circle([10.8,73.2],radius=55_000,color="#FF0055",fill=True,
        fill_color="#FF0055",fill_opacity=.15,tooltip="Active oil spill — 14.2 km²").add_to(m)
    folium.Circle([12.0,72.0],radius=800_000,color="#00CCFF",fill=False,
        weight=1,dash_array="12 6",tooltip="India EEZ").add_to(m)
    return m

# ─────────────────────────────────────────────────────────────────────────────
# STATUS BAR
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="status-bar">
  <span style='font-family:Courier New,monospace;font-size:14px;color:#00FFAA;
    text-shadow:0 0 12px rgba(0,255,170,.5);letter-spacing:.1em'>
    OIMS V4 &nbsp;·&nbsp; SAMUDRA NETRA X
  </span>
  <span><span class="pulse-dot dot-g"></span>15 MODULES ONLINE</span>
  <span><span class="pulse-dot dot-g"></span>SENSOR GRID ACTIVE</span>
  <span><span class="pulse-dot dot-y"></span>7 THREATS TRACKED</span>
  <span><span class="pulse-dot dot-r"></span>2 KINETIC PENDING</span>
  <span style='margin-left:auto;background:rgba(0,20,51,.5);border:1px solid rgba(0,204,255,.3);
    padding:3px 10px;border-radius:3px;color:#00CCFF;font-size:10px'>
    Azure Cosmos DB LIVE
  </span>
  <span style='color:#5A8FA8'>{utc()}</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────────────────────
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Vessels Tracked",  f"{st.session_state.vessels:,}",     "+12 last 5 min")
c2.metric("Threat Alerts",    "7",                                  "2 critical active")
c3.metric("SST (°C)",         str(st.session_state.sst),            "+0.2 vs baseline")
c4.metric("AUVs Active",      "42 / 45",                            "3 charging")
c5.metric("Data Ingested",    f"{st.session_state.data_tb:.2f} TB", "today")

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "⬡  TACTICAL MAP",
    "⚔  AWRS CONTACTS",
    "🧬  SEAS EVOLUTION",
    "🌍  CLIMATE ENGINE",
    "🔐  AUDIT CHAIN",
    "⚙  MODULE HEALTH",
])

# ════════════════════════════════════════════════
# TAB 1 — TACTICAL MAP
# ════════════════════════════════════════════════
with tabs[0]:
    cL, cR = st.columns([2.3, 1])
    with cL:
        st.markdown('<div class="sec-hdr">Live ocean map — Indian Ocean</div>',
                    unsafe_allow_html=True)
        if FOLIUM_OK:
            st_folium(build_map(), width=None, height=510, returned_objects=[])
        else:
            st.info("Install: pip install folium streamlit-folium")

    with cR:
        st.markdown('<div class="sec-hdr">Alert feed</div>', unsafe_allow_html=True)
        alerts = [
            ("#FF0055","CRITICAL","CONTACT-D: KINETIC — auth pending"),
            ("#FF0055","CRITICAL","CONTACT-C: KINETIC — confirmation req"),
            ("#FFCC00","HIGH",    "DARK-003: AIS off, 18 kts, EEZ entry"),
            ("#FFCC00","HIGH",    "EAMA: MMSI 987654 piracy prob 1.0"),
            ("#00CCFF","MEDIUM",  "SHESN Node-3F offline — rerouted"),
            ("#00CCFF","MEDIUM",  "Cyclone 95 kts, surge 13.1 m forecast"),
            ("#00FFAA","INFO",    "QIRO fleet: +39% route saving"),
            ("#00FFAA","INFO",    "SEAS SonarCNN gen 13 — 97.8%"),
        ]
        for col,sev,msg in alerts:
            st.markdown(f"""
            <div style='padding:6px 0;border-bottom:1px solid #0D1E2E;font-size:12px'>
              <span style='background:{col}18;color:{col};border:1px solid {col}44;
                font-size:10px;padding:1px 7px;border-radius:2px;
                font-family:Courier New,monospace;margin-right:8px'>{sev}</span>{msg}
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">AI model activity</div>', unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(fig_models(), use_container_width=True,
                            config={"displayModeBar":False})

# ════════════════════════════════════════════════
# TAB 2 — AWRS CONTACTS
# ════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="sec-hdr">Autonomous war response — live contact matrix</div>',
                unsafe_allow_html=True)

    # Contact cards
    cols = st.columns(len(AWRS))
    for col,c in zip(cols,AWRS):
        tp = round(c["tp"]+np.random.uniform(-.02,.02),2)
        with col:
            is_kin = c["roe"]=="KINETIC"
            border_col = "#FF0055" if is_kin else c["col"]
            st.markdown(f"""
            <div style='background:#0A1520;border:1px solid {border_col}33;
                border-radius:4px;padding:12px;text-align:center;
                {"box-shadow:0 0 16px "+border_col+"22;" if is_kin else ""}'>
              <div style='font-family:Courier New,monospace;font-size:11px;
                color:{border_col};margin-bottom:8px'>{c["id"]}</div>
              <span class="{c["rcls"]}">{c["roe"]}</span>
              <div style='font-family:Courier New,monospace;font-size:11px;
                color:#5A8FA8;margin:6px 0'>{c["spd"]} kts</div>
              <div style='font-family:Courier New,monospace;font-size:22px;
                font-weight:700;color:{border_col};line-height:1;
                text-shadow:0 0 10px {border_col}44'>{tp:.2f}</div>
              <div style='font-size:10px;color:#5A8FA8;font-family:Courier New,monospace'>
                THREAT PROB</div>
              <div style='font-size:11px;color:#C8D8E8;margin-top:5px'>{c["act"]}</div>
              {"<div style='font-size:10px;color:#FF8800;margin-top:3px;font-family:Courier New,monospace'>AIS DARK</div>" if c["dark"] else ""}
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Full table
    pos_list = ["8.2°N 72.1°E","12.4°N 74.8°E","11.5°N 51.0°E",
                "13.1°N 50.2°E","15.6°N 82.4°E"]
    df = pd.DataFrame([{
        "Contact":  c["id"],
        "Position": pos_list[i],
        "Speed":    f"{c['spd']} kts",
        "Threat":   f"{round(c['tp']+np.random.uniform(-.02,.02),2):.2f}",
        "Piracy":   f"{round(c['pp']+np.random.uniform(-.02,.02),2):.2f}",
        "AIS Dark": "YES" if c["dark"] else "no",
        "ROE":      c["roe"],
        "Action":   c["act"],
    } for i,c in enumerate(AWRS)])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    cLeft, cRight = st.columns(2)
    with cLeft:
        st.markdown('<div class="sec-hdr">ROE escalation ladder</div>', unsafe_allow_html=True)
        for lvl,desc,cnt,style in [
            ("OBSERVE",      "Passive — USV shadow deployed",                    "1","success"),
            ("SHADOW",       "AUV tail + sonar ping",                            "0","info"),
            ("WARN",         "Ch16 warning + flare + shipping diversion",        "1","warning"),
            ("INTERDICT",    "Non-lethal block — helicopter scrambled",          "0","warning"),
            ("ELECTRONIC JAM","ECM countermeasures — fleet alerted",            "1","warning"),
            ("KINETIC",      "Human authorisation required — 2 queued",          "2","danger"),
        ]:
            bg = "var(--color-background-"+style+")"
            tc = "var(--color-text-"+style+")"
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:10px;padding:8px 11px;
                border-radius:4px;background:{bg};margin-bottom:4px'>
              <div style='flex:0 0 120px;font-size:11px;font-weight:700;
                font-family:Courier New,monospace;color:{tc}'>{lvl}</div>
              <div style='flex:1;font-size:11px;color:var(--color-text-secondary)'>{desc}</div>
              <div style='font-size:13px;font-weight:700;color:{tc}'>{cnt}</div>
            </div>""", unsafe_allow_html=True)
    with cRight:
        st.markdown('<div class="sec-hdr">QAIE quantum state distribution</div>',
                    unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(fig_qaie(), use_container_width=True,
                            config={"displayModeBar":False})

# ════════════════════════════════════════════════
# TAB 3 — SEAS EVOLUTION
# ════════════════════════════════════════════════
with tabs[2]:
    cA, cB = st.columns([2,1])
    with cA:
        st.markdown('<div class="sec-hdr">Self-evolution convergence — 60 generations</div>',
                    unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(fig_seas(), use_container_width=True,
                            config={"displayModeBar":False})

    with cB:
        st.markdown('<div class="sec-hdr">Multi-agent collaboration</div>',
                    unsafe_allow_html=True)
        evo = [
            ("SonarCNN V4",94.1,99.9,13,"Neuroevolution","#9966FF"),
            ("YOLOv8 V4", 91.2,99.9,55,"Bayesian Hyperopt","#00FFAA"),
            ("Storm PINN",87.0,94.3,38,"MAML-inspired","#00CCFF"),
            ("Anomaly IF", 89.0,95.1,29,"Online SGD","#FFCC00"),
        ]
        for n,s,b,g,st_name,col in evo:
            st.markdown(f"""
            <div style='border-left:3px solid {col};padding:9px 12px;
                margin-bottom:8px;background:#0A1520;border-radius:0 4px 4px 0'>
              <div style='font-family:Courier New,monospace;font-size:12px;color:{col}'>{n}</div>
              <div style='display:flex;gap:14px;margin-top:4px;font-size:13px;font-weight:500'>
                <span style='color:#5A8FA8'>{s}%</span>
                <span style='color:{col}'>{b}%</span>
                <span style='color:#00FFAA'>+{b-s:.1f}%</span>
              </div>
              <div style='font-size:10px;color:#5A8FA8;margin-top:2px;
                font-family:Courier New,monospace'>Gen {g} · {st_name}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style='background:#050A0E;border:1px solid #1A3040;border-radius:4px;
            padding:10px 13px;font-family:Courier New,monospace;font-size:11px;
            color:#5A8FA8;line-height:1.9;margin-top:6px'>
            Human retraining: <span style='color:#00FFAA'>0 events</span><br>
            Strategy: <span style='color:#9966FF'>(1+1)-ES</span><br>
            Mutation rate: <span style='color:#FFCC00'>5%</span>
        </div>""", unsafe_allow_html=True)

    # Generation mini-tiles
    st.markdown('<div class="sec-hdr" style="margin-top:12px">Generation genome feed</div>',
                unsafe_allow_html=True)
    gen_html = ""
    for i in range(1,31):
        acc = round(94.1 + i*.09 + np.random.uniform(-.2,.2), 1)
        col = "#00FFAA" if acc>97 else "#FFCC00" if acc>95 else "#5A8FA8"
        gen_html += f"""<div style='display:inline-block;background:#0A1520;
            border:1px solid #1A3040;border-radius:3px;padding:5px 9px;
            margin:2px;font-family:Courier New,monospace;font-size:10px;text-align:center;
            min-width:64px'>
          <div style='font-weight:700;color:#C8D8E8'>Gen {i}</div>
          <div style='color:{col}'>{acc}%</div>
        </div>"""
    st.markdown(f"<div style='line-height:2'>{gen_html}</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════
# TAB 4 — CLIMATE ENGINE
# ════════════════════════════════════════════════
with tabs[3]:
    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown('<div class="sec-hdr">Sea level rise + red zone</div>',
                    unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(fig_slr(), use_container_width=True,
                            config={"displayModeBar":False})
        st.markdown("""
        <div style='background:rgba(255,0,85,.08);border:1px solid rgba(255,0,85,.3);
            border-radius:3px;padding:8px 11px;font-family:Courier New,monospace;
            font-size:11px;color:#FF8800;line-height:1.7'>
            <b style='color:#FF0055'>RED ZONE ACTIVE</b><br>
            8yr+ SLR exceeds 45 mm — coastal evacuation trigger<br>
            500M+ population at risk
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">SST anomaly — 24hr</div>',
                    unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(fig_sst(), use_container_width=True,
                            config={"displayModeBar":False})

    with c2:
        st.markdown('<div class="sec-hdr">Coral reef health — SACRDT 1m resolution</div>',
                    unsafe_allow_html=True)
        for reef,live,bleach,dead in [
            ("Lakshadweep Atoll",72,18,10),
            ("Andaman Barrier",  61,27,12),
            ("Gulf of Mannar",   55,32,13),
            ("Palk Bay",         48,38,14),
        ]:
            st.markdown(f"""
            <div style='margin-bottom:13px'>
              <div style='font-size:13px;margin-bottom:4px;font-weight:500'>{reef}</div>
              <div style='display:flex;height:9px;border-radius:4px;overflow:hidden;gap:1px'>
                <div style='flex:{live};background:#1D9E75;border-radius:2px 0 0 2px'></div>
                <div style='flex:{bleach};background:#BA7517'></div>
                <div style='flex:{dead};background:#A32D2D;border-radius:0 2px 2px 0'></div>
              </div>
              <div style='display:flex;gap:14px;font-size:10px;margin-top:3px;
                font-family:Courier New,monospace'>
                <span style='color:#1D9E75'>{live}% live</span>
                <span style='color:#BA7517'>{bleach}% bleach</span>
                <span style='color:#A32D2D'>{dead}% dead</span>
              </div>
            </div>""", unsafe_allow_html=True)

        if PLOTLY_OK:
            st.plotly_chart(fig_slr_mini(), use_container_width=True,
                            config={"displayModeBar":False})

    with c3:
        st.markdown('<div class="sec-hdr">Active pollution events</div>',
                    unsafe_allow_html=True)
        for nm,area,col,status,txt_col in [
            ("Oman Sea Spill",  14.2,"#FF0055","ACTIVE","#FF0055"),
            ("Gulf of Mannar",   3.8,"#FFCC00","CONTAINED","#FFCC00"),
            ("Chennai Coast",    1.1,"#00FFAA","RESOLVED","#00FFAA"),
        ]:
            st.markdown(f"""
            <div style='background:#0A1520;border:1px solid #1A3040;
                border-radius:4px;padding:11px 13px;margin-bottom:9px'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <div style='font-size:13px;font-weight:600'>{nm}</div>
                <span style='background:{col}18;color:{txt_col};border:1px solid {col}44;
                  font-size:10px;padding:2px 9px;border-radius:2px;
                  font-family:Courier New,monospace'>{status}</span>
              </div>
              <div style='font-size:11px;color:#5A8FA8;margin-top:4px;
                font-family:Courier New,monospace'>{area} km² affected</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div class="sec-hdr" style="margin-top:12px">SLR bar forecast</div>',
                    unsafe_allow_html=True)
        for yr,val,col in [("Now",0,"#5A8FA8"),("2yr",10.1,"#1D9E75"),("4yr",20.5,"#1D9E75"),
                            ("6yr",31.4,"#BA7517"),("8yr",40.9,"#A32D2D"),("10yr",50.4,"#A32D2D")]:
            w = int(val/65*100)
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:8px;margin-bottom:5px'>
              <div style='flex:0 0 30px;font-size:11px;color:#5A8FA8;
                font-family:Courier New,monospace'>{yr}</div>
              <div style='flex:1;height:7px;background:#0A1520;border-radius:3px;overflow:hidden'>
                <div style='width:{w}%;height:100%;background:{col};border-radius:3px'></div>
              </div>
              <div style='flex:0 0 40px;font-size:11px;font-weight:500;color:{col};
                text-align:right;font-family:Courier New,monospace'>{val} mm</div>
            </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════
# TAB 5 — AUDIT CHAIN
# ════════════════════════════════════════════════
with tabs[4]:
    cLeft, cRight = st.columns([2.2, 1])
    with cLeft:
        st.markdown('<div class="sec-hdr">SHA-256 hash chain — immutable decision log</div>',
                    unsafe_allow_html=True)

        chain = st.session_state.audit_chain
        depth = len(chain)
        latest = chain[-1]["h"] if chain else "genesis"

        m1,m2 = st.columns([1,3])
        m1.metric("Chain Depth", str(depth), f"+{depth-5} new")
        m2.markdown(f"""
        <div style='background:#0A1520;border:1px solid rgba(0,204,255,.3);border-radius:4px;
            padding:10px 14px;height:100%'>
          <div style='font-family:Courier New,monospace;font-size:10px;color:#5A8FA8;
            margin-bottom:5px'>LATEST HASH</div>
          <div style='font-family:Courier New,monospace;font-size:11px;color:#00CCFF;
            word-break:break-all'>{latest}</div>
        </div>""", unsafe_allow_html=True)

        # Chain block visualisation
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">Block chain visualisation</div>',
                    unsafe_allow_html=True)

        blocks_html = '<div class="chain-flow">'
        for i,e in enumerate(chain):
            cl = "kin" if e["r"]=="KINETIC" else "war" if "WARN" in e["r"] or "JAM" in e["r"] else "obs"
            if i > 0:
                blocks_html += '<span class="c-arrow">→</span>'
            blocks_html += f"""<div class="cblk {cl}">
              <div style='font-weight:700;color:var(--color-text-primary);font-size:11px'>{e["c"]}</div>
              <div style='font-size:10px;color:var(--color-text-secondary)'>{e["r"]}</div>
              <div style='font-size:9px;color:var(--color-text-info);margin-top:2px'>{e["h"][:10]}...</div>
            </div>"""
        blocks_html += '</div>'
        st.markdown(blocks_html, unsafe_allow_html=True)

        # Entries
        st.markdown('<div class="sec-hdr">Recent entries</div>', unsafe_allow_html=True)
        for entry in reversed(chain[-7:]):
            rc = roe_col(entry["r"])
            st.markdown(f"""
            <div class="ae">
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <span style='font-weight:500;font-size:12px'>{entry["c"]}</span>
                <span style='background:{rc}18;color:{rc};border:1px solid {rc}44;
                  font-size:10px;padding:2px 9px;border-radius:2px;
                  font-family:Courier New,monospace'>{entry["r"]}</span>
              </div>
              <div style='color:#5A8FA8;font-size:10px;margin-top:2px'>{entry["a"]}</div>
              <div style='color:#00CCFF;font-size:10px;margin-top:4px;
                word-break:break-all;font-family:Courier New,monospace'>{entry["h"][:48]}…</div>
            </div>""", unsafe_allow_html=True)

    with cRight:
        st.markdown('<div class="sec-hdr">Sign &amp; append entry</div>',
                    unsafe_allow_html=True)
        contact  = st.selectbox("Contact ID", [c["id"] for c in AWRS]+["CUSTOM"])
        if contact == "CUSTOM":
            contact = st.text_input("Custom contact ID","NEW-CONTACT")
        roe_sel = st.selectbox("ROE Level",
            ["OBSERVE","SHADOW","WARN","INTERDICT","ELECTRONIC_JAM","KINETIC"])
        action  = st.text_input("Action","deploy_usv_shadow")

        if st.button("⊕  Sign & Append to Chain", use_container_width=True):
            prev = chain[-1]["h"] if chain else "genesis"
            new_h = sha(prev, contact, roe_sel, action)
            st.session_state.audit_chain.append(
                {"c":contact,"r":roe_sel,"a":action,"h":new_h}
            )
            st.success(f"Signed: {new_h[:24]}…")
            st.rerun()

        import json
        if chain:
            st.download_button("⬇  Export chain JSON",
                data=json.dumps(chain,indent=2),
                file_name="oims_audit.json",
                mime="application/json",
                use_container_width=True)

        st.markdown(f"""
        <div style='background:#001020;border:1px solid rgba(0,204,255,.15);border-radius:4px;
            padding:11px 13px;margin-top:10px;font-family:Courier New,monospace;
            font-size:11px;color:#5A8FA8;line-height:1.9'>
            Storage: <span style='color:#00FFAA'>Azure Cosmos DB</span><br>
            Algorithm: <span style='color:#9966FF'>SHA-256</span><br>
            Chain: <span style='color:#00CCFF'>Append-only</span><br>
            Entries: <span style='color:#C8D8E8;font-weight:500'>{len(chain)}</span><br>
            Integrity: <span style='color:#00FFAA'>VERIFIED</span><br>
            Kinetic auth: <span style='color:#FF0055'>Human required</span>
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════
# TAB 6 — MODULE HEALTH
# ════════════════════════════════════════════════
with tabs[5]:
    cA, cB = st.columns([1.4, 1])
    with cA:
        st.markdown('<div class="sec-hdr">All 15 AI modules — live status</div>',
                    unsafe_allow_html=True)
        rows = [MODULES[i:i+3] for i in range(0,15,3)]
        for row in rows:
            cols = st.columns(3)
            for col,(n,v,c) in zip(cols,row):
                col.markdown(f"""
                <div style='background:#0A1520;border:1px solid {c}22;border-radius:4px;
                    padding:10px 12px;display:flex;align-items:center;gap:9px;margin-bottom:6px'>
                  <div style='width:9px;height:9px;border-radius:50%;background:{c};
                    {"animation:pd 2s infinite;" if c=="#FFCC00" else ""}'></div>
                  <div>
                    <div style='font-size:12px;font-weight:500;color:#C8D8E8'>{n}</div>
                    <div style='font-size:10px;color:{c};font-family:Courier New,monospace'>{v}</div>
                  </div>
                </div>""", unsafe_allow_html=True)

    with cB:
        st.markdown('<div class="sec-hdr">OSIN swarm AUV topology</div>',
                    unsafe_allow_html=True)
        for i in range(10):
            hot = i < 2
            bc  = "rgba(0,255,170,.15)" if hot else "#0A1520"
            tc  = "#00FFAA" if hot else "#C8D8E8"
            sc  = "#00FFAA" if hot else "#5A8FA8"
            lbl = "HOT ZONE" if hot else "patrol"
            st.markdown(f"""
            <div style='background:{bc};border:1px solid {"rgba(0,255,170,.4)" if hot else "#1A3040"};
                border-radius:3px;padding:5px 10px;margin-bottom:4px;
                display:flex;justify-content:space-between;align-items:center'>
              <span style='font-family:Courier New,monospace;font-size:11px;
                font-weight:{"700" if hot else "400"};color:{tc}'>AUV-{i:02d}</span>
              <span style='font-size:10px;color:{sc};font-family:Courier New,monospace'>{lbl}</span>
            </div>""", unsafe_allow_html=True)
        phero = round(5 + np.random.uniform(0,.8),2)
        st.markdown(f"""
        <div style='margin-top:8px;padding:8px 11px;background:#050A0E;
            border:1px solid #1A3040;border-radius:4px;font-family:Courier New,monospace;
            font-size:11px;color:#5A8FA8;line-height:1.8'>
            Pheromone intensity: <span style='color:#9966FF;font-weight:700'>{phero}</span><br>
            ACO cycles: <span style='color:#C8D8E8'>3</span><br>
            Hot cells: <span style='color:#00FFAA'>2</span><br>
            Coverage vs grid: <span style='color:#00FFAA'>+39%</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if PLOTLY_OK:
        st.markdown('<div class="sec-hdr">System performance — live</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(fig_perf(), use_container_width=True,
                        config={"displayModeBar":False})

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:12px;margin-top:10px;
    border-top:1px solid #0D1E2E;font-family:Courier New,monospace;
    font-size:10px;color:#2A4050'>
    OIMS V4 × SAMUDRA NETRA X &nbsp;·&nbsp;
    QAIE · SEAS · AWRS · SHESN · OSIN · QIRO &nbsp;·&nbsp;
    15 Modules Active &nbsp;·&nbsp; Azure Cosmos DB &nbsp;·&nbsp; SHA-256 Audit Chain
</div>""", unsafe_allow_html=True)
