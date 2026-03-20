"""
OIMS V4 — SAMUDRA NETRA X
Streamlit Cloud Deployment-Ready Version

Fixes applied:
  1. Google Fonts @import removed  (blocked by Streamlit Cloud CSP → blank screen)
  2. streamlit-folium cache removed (serialization crash on Cloud)
  3. All optional imports wrapped in try/except (no silent crashes)
  4. requirements.txt friendly — only pip-installable packages
"""

import streamlit as st

st.set_page_config(
    page_title="OIMS V4 — SAMUDRA NETRA X",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Safe imports (no crash if package missing) ────────────────────────────────
import numpy as np
import pandas as pd
import time
import hashlib
import uuid
from datetime import datetime, timezone

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except ImportError:
    FOLIUM_OK = False

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ── CSS (NO Google Fonts import — use system monospace/sans) ─────────────────
st.markdown("""
<style>
/* ── Global ── */
html, body, .stApp { background-color: #050A0E !important; color: #C8D8E8 !important; }
.main .block-container { background: #050A0E !important; padding: 1rem 2rem 2rem; max-width: 1400px; }

/* ── Typography — system fonts only (no external import) ── */
h1, h2, h3 { font-family: 'Courier New', Courier, monospace !important; letter-spacing:.06em; }
p, div, span, td, th { font-family: 'Segoe UI', Arial, sans-serif !important; }
code, pre { font-family: 'Courier New', Courier, monospace !important; }

/* ── Scanline ── */
.stApp::before {
    content:''; position:fixed; top:0; left:0; width:100%; height:100%;
    background: repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,170,.008) 2px,rgba(0,255,170,.008) 4px);
    pointer-events:none; z-index:9999;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg,#0A1520,#0D1E2E) !important;
    border: 1px solid #00FFAA33 !important;
    border-radius: 4px !important;
    box-shadow: 0 0 16px #00FFAA11 !important;
}
[data-testid="stMetricLabel"] { color:#5A8FA8 !important; font-family:'Courier New',monospace !important; font-size:11px !important; text-transform:uppercase; letter-spacing:.1em; }
[data-testid="stMetricValue"] { color:#00FFAA !important; font-family:'Courier New',monospace !important; font-size:24px !important; text-shadow:0 0 12px #00FFAA66; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap:4px; background:#0A1520; padding:5px; border-radius:4px; border:1px solid #1A3040; }
.stTabs [data-baseweb="tab"] { background:transparent; border-radius:3px; color:#5A8FA8 !important; font-family:'Courier New',monospace !important; font-size:12px !important; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,#003322,#005533) !important; color:#00FFAA !important; box-shadow:0 0 10px #00FFAA22; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border:1px solid #1A3040 !important; border-radius:4px; }
.stDataFrame thead th { background:#0A1520 !important; color:#00FFAA !important; font-family:'Courier New',monospace !important; font-size:11px !important; border-bottom:1px solid #00FFAA33 !important; }

/* ── Buttons ── */
.stButton button { background:transparent !important; border:1px solid #00FFAA44 !important; color:#00FFAA !important; font-family:'Courier New',monospace !important; border-radius:3px; }
.stButton button:hover { border-color:#00FFAA !important; box-shadow:0 0 10px #00FFAA33; }

/* ── Select / Input ── */
.stSelectbox select, .stTextInput input {
    background:#0A1520 !important; color:#C8D8E8 !important;
    border:1px solid #1A3040 !important; font-family:'Courier New',monospace !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] { background:#040810 !important; border-right:1px solid #1A3040 !important; }

/* ── ROE badges ── */
.roe-obs { background:#00332210; color:#00FFAA; border:1px solid #00FFAA44; padding:2px 10px; border-radius:2px; font-family:'Courier New',monospace; font-size:11px; font-weight:700; }
.roe-war { background:#33220010; color:#FFCC00; border:1px solid #FFCC0044; padding:2px 10px; border-radius:2px; font-family:'Courier New',monospace; font-size:11px; font-weight:700; box-shadow:0 0 8px #FFCC0033; }
.roe-kin { background:#33000015; color:#FF0055; border:1px solid #FF005566; padding:2px 10px; border-radius:2px; font-family:'Courier New',monospace; font-size:11px; font-weight:700; box-shadow:0 0 12px #FF005566; }
.roe-ecm { background:#33110010; color:#FF8800; border:1px solid #FF880044; padding:2px 10px; border-radius:2px; font-family:'Courier New',monospace; font-size:11px; font-weight:700; }
.roe-sha { background:#00223310; color:#00CCFF; border:1px solid #00CCFF44; padding:2px 10px; border-radius:2px; font-family:'Courier New',monospace; font-size:11px; font-weight:700; }

/* ── Section header ── */
.sec-hdr { font-family:'Courier New',monospace; font-size:11px; color:#00FFAA; text-transform:uppercase; letter-spacing:.15em; border-bottom:1px solid #00FFAA33; padding-bottom:6px; margin-bottom:12px; }

/* ── Status bar ── */
.status-bar { display:flex; align-items:center; gap:16px; background:#040810; border:1px solid #1A3040; border-radius:4px; padding:8px 14px; margin-bottom:12px; font-family:'Courier New',monospace; font-size:11px; }
.dot-g { display:inline-block; width:6px; height:6px; border-radius:50%; background:#00FFAA; box-shadow:0 0 5px #00FFAA; margin-right:5px; }
.dot-y { display:inline-block; width:6px; height:6px; border-radius:50%; background:#FFCC00; box-shadow:0 0 5px #FFCC00; margin-right:5px; }
.dot-r { display:inline-block; width:6px; height:6px; border-radius:50%; background:#FF0055; box-shadow:0 0 5px #FF0055; margin-right:5px; }
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
AWRS_CONTACTS = [
    {"id":"CONTACT-A","lat":8.2,  "lon":72.1,"speed":8, "threat":0.10,"piracy":0.05,"dark":False,"roe":"OBSERVE",      "rcls":"roe-obs","col":"#00FFAA","act":"Deploy USV shadow"},
    {"id":"CONTACT-B","lat":12.4, "lon":74.8,"speed":16,"threat":0.45,"piracy":0.30,"dark":True, "roe":"WARN",         "rcls":"roe-war","col":"#FFCC00","act":"Ch16 warning + flare"},
    {"id":"CONTACT-C","lat":11.5, "lon":51.0,"speed":24,"threat":0.78,"piracy":0.70,"dark":True, "roe":"KINETIC",      "rcls":"roe-kin","col":"#FF0055","act":"Human auth required"},
    {"id":"CONTACT-D","lat":13.1, "lon":50.2,"speed":30,"threat":0.95,"piracy":0.92,"dark":True, "roe":"KINETIC",      "rcls":"roe-kin","col":"#FF0055","act":"Human auth required"},
    {"id":"DARK-003", "lat":15.6, "lon":82.4,"speed":18,"threat":0.50,"piracy":0.35,"dark":True, "roe":"ELECTRONIC JAM","rcls":"roe-ecm","col":"#FF8800","act":"ECM jamming active"},
]

# FIX: xaxis/yaxis removed from PLOT_BG base dict.
# Passing **PLOT_BG + xaxis=dict(...) caused:
# TypeError: got multiple values for keyword argument 'xaxis'
_AX = dict(gridcolor="#0D1E2E", zerolinecolor="#0D1E2E", linecolor="#1A3040")

PLOT_BG = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(5,10,14,0.95)",
    font=dict(family="Courier New", color="#5A8FA8", size=11),
    margin=dict(l=48,r=16,t=36,b=32),
    legend=dict(bgcolor="rgba(0,0,0,0)",bordercolor="#1A3040",borderwidth=1,font=dict(size=10)),
)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "audit_chain" not in st.session_state:
    st.session_state.audit_chain = []
if "vessels" not in st.session_state:
    st.session_state.vessels = 1847
if "sst" not in st.session_state:
    st.session_state.sst = 28.4
if "data_tb" not in st.session_state:
    st.session_state.data_tb = 3.80

# ── HELPERS ───────────────────────────────────────────────────────────────────
def sha256_chain(prev: str, contact: str, roe: str, action: str) -> str:
    payload = f"{prev}|{contact}|{roe}|{action}|{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

def live_metric(base: float, noise: float = 0.05) -> float:
    return round(base + np.random.uniform(-noise, noise), 2)

# ── PLOTS ─────────────────────────────────────────────────────────────────────
def seas_fig():
    gens = np.arange(1,61)
    sonar = np.clip(94.1 + gens*0.094 + np.sin(gens*.3)*.5, 0, 100)
    yolo  = np.clip(91.2 + gens*0.14  + np.cos(gens*.4)*.6, 0, 100)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=gens,y=sonar,name="SonarCNN V4",line=dict(color="#00FFAA",width=1.5),fill="tozeroy",fillcolor="rgba(0,255,170,.05)",mode="lines"))
    fig.add_trace(go.Scatter(x=gens,y=yolo, name="YOLOv8 V4", line=dict(color="#9966FF",width=1.5),fill="tozeroy",fillcolor="rgba(153,102,255,.05)",mode="lines"))
    fig.update_layout(**PLOT_BG, height=280,
        title=dict(text="Self-Evolution Convergence (60 Generations)",font=dict(color="#00FFAA",size=12)),
        yaxis=dict(**_AX, ticksuffix="%", range=[89,101]),
        xaxis=dict(**_AX, title="Generation"))
    return fig

def slr_fig():
    labels=["Now","2yr","4yr","6yr","8yr","10yr"]
    mean=[0,10.1,20.5,31.4,40.9,50.4]
    hi=[0,13.2,26.1,39.8,52.1,64.3]
    lo=[0,7.3,15.4,23.6,30.2,37.8]
    thresh=[45]*6
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=labels+labels[::-1],y=hi+lo[::-1],fill="toself",fillcolor="rgba(0,204,255,.07)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    fig.add_trace(go.Scatter(x=labels,y=mean,name="Mean SLR",line=dict(color="#00CCFF",width=2),mode="lines+markers",marker=dict(color="#00CCFF",size=5)))
    # UPGRADE 4: red zone threshold line
    fig.add_trace(go.Scatter(x=labels,y=thresh,name="⚠ Evacuation threshold",line=dict(color="rgba(255,0,85,0.6)",width=1.5,dash="dash"),mode="lines"))
    fig.add_hrect(y0=45,y1=70,fillcolor="rgba(255,0,85,.06)",line_width=0)
    fig.update_layout(**PLOT_BG, height=260,
        title=dict(text="Sea Level Rise Forecast + Red Zone",font=dict(color="#00CCFF",size=12)),
        yaxis=dict(**_AX, ticksuffix=" mm"),
        xaxis=dict(**_AX))
    return fig

def qaie_fig():
    states=["PEACEFUL","STORM_WARNING","THREAT_AMBER","THREAT_RED","POLLUTION"]
    counts=[28,8,5,3,2]
    colors=["#00FFAA","#00CCFF","#FFCC00","#FF0055","#9966FF"]
    fig=go.Figure(go.Bar(x=states,y=counts,marker_color=colors,marker_line_width=0))
    fig.update_layout(**PLOT_BG, height=240,
        title=dict(text="QAIE Quantum State Distribution (4.7× speedup)",font=dict(color="#9966FF",size=12)),
        bargap=0.3,
        xaxis=dict(**_AX),
        yaxis=dict(**_AX))
    return fig

def model_fig():
    models = ["YOLOv8 V4","SonarCNN V4","Storm PINN","Anomaly IF","AWRS Bayes"]
    # FIX: Python list + numpy array TypeError → use np.array explicitly
    base = np.array([94, 97, 87, 89, 99], dtype=float)
    pcts = np.clip(base + np.random.uniform(-2, 2, 5), 0, 100)
    colors = ["#00FFAA","#9966FF","#00CCFF","#FFCC00","#FF0055"]
    fig = go.Figure(go.Bar(
        y=models, x=pcts, orientation="h",
        marker_color=colors, marker_line_width=0,
        text=[f"{p:.0f}%" for p in pcts], textposition="inside",
        textfont=dict(color="#050A0E", family="Courier New", size=10),
    ))
    # FIX: xaxis no longer in PLOT_BG — safe to pass directly
    fig.update_layout(**PLOT_BG, height=220,
        title=dict(text="AI Model Activity", font=dict(color="#00FFAA",size=12)),
        xaxis=dict(**_AX, ticksuffix="%", range=[0, 105]),
        yaxis=dict(**_AX))
    return fig

# ── TACTICAL MAP ──────────────────────────────────────────────────────────────
def build_map():
    m = folium.Map(location=[12.0, 72.0], zoom_start=5, tiles="CartoDB dark_matter")

    for c in AWRS_CONTACTS:
        popup_html = f"""
        <div style='background:#050A0E;color:#C8D8E8;font-family:monospace;
                    padding:10px;min-width:190px;border:1px solid {c["col"]}'>
            <b style='color:{c["col"]}'>{c["id"]}</b><br>
            ROE: <span style='color:{c["col"]}'>{c["roe"]}</span><br>
            Speed: {c["speed"]} kts | Threat: {c["threat"]:.0%}<br>
            Action: {c["act"]}
        </div>"""
        folium.RegularPolygonMarker(
            location=[c["lat"]+np.random.uniform(-.1,.1),
                      c["lon"]+np.random.uniform(-.1,.1)],
            number_of_sides=4, radius=10,
            color=c["col"], fill=True, fill_color=c["col"], fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=f"⚠ {c['id']} | {c['roe']}",
        ).add_to(m)

    friendly = [("INS-Delhi",14.2,73.5),("AUV-007",10.5,71.8),("CG-Kochi",9.9,76.3)]
    for name, lat, lon in friendly:
        folium.RegularPolygonMarker(
            location=[lat,lon], number_of_sides=3, radius=8,
            color="#00FFAA", fill=True, fill_color="#00FFAA", fill_opacity=0.85,
            tooltip=f"✓ {name}",
        ).add_to(m)

    folium.Circle([13.5,76.0],radius=280_000,color="#FF8800",fill=True,
        fill_color="#FF8800",fill_opacity=0.05,dash_array="8 4",
        tooltip="⚡ Cyclone zone — 95 kts").add_to(m)
    folium.Circle([10.8,73.2],radius=55_000,color="#FF0055",fill=True,
        fill_color="#FF0055",fill_opacity=0.15,
        tooltip="☠ Oil spill — 14.2 km²").add_to(m)
    folium.Circle([12.0,72.0],radius=800_000,color="#00CCFF",fill=False,
        weight=1,dash_array="12 6",tooltip="India EEZ").add_to(m)
    return m

# ── STATUS BAR ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="status-bar">
  <span style='font-family:Courier New,monospace;font-size:14px;color:#00FFAA;
    text-shadow:0 0 12px #00FFAA66;letter-spacing:.1em'>
    OIMS V4 &nbsp;·&nbsp; SAMUDRA NETRA X
  </span>
  <span><span class="dot-g"></span>15 MODULES ONLINE</span>
  <span><span class="dot-g"></span>SENSOR GRID ACTIVE</span>
  <span><span class="dot-y"></span>7 THREATS TRACKED</span>
  <span><span class="dot-r"></span>2 KINETIC PENDING</span>
  <span style='margin-left:auto;color:#5A8FA8'>{utc_now()}</span>
</div>
""", unsafe_allow_html=True)

# ── METRICS ───────────────────────────────────────────────────────────────────
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Vessels Tracked",  f"{st.session_state.vessels:,}",   "+12 last 5 min")
c2.metric("Threat Alerts",    "7",                               "2 critical")
c3.metric("SST (°C)",         str(st.session_state.sst),         "+0.2 vs baseline")
c4.metric("AUVs Active",      "42 / 45",                         "3 charging")
c5.metric("Data Ingested",    f"{st.session_state.data_tb:.2f} TB", "today")

# ── TABS ──────────────────────────────────────────────────────────────────────
tab_map, tab_awrs, tab_seas, tab_climate, tab_audit = st.tabs([
    "⬡  TACTICAL MAP",
    "⚔  AWRS CONTACTS",
    "🧬  SEAS EVOLUTION",
    "🌍  CLIMATE ENGINE",
    "🔐  AUDIT CHAIN",
])

# ════════════════════════ TAB 1: MAP ═════════════════════════════════════════
with tab_map:
    col_map, col_right = st.columns([2.2, 1])
    with col_map:
        st.markdown('<div class="sec-hdr">Live Ocean Map — Indian Ocean</div>',
                    unsafe_allow_html=True)
        if FOLIUM_OK:
            # FIX 2: NO cache_data on folium map — causes serialization error on Cloud
            st_folium(build_map(), width=None, height=500, returned_objects=[])
        else:
            st.warning("📦 Install: `pip install folium streamlit-folium`")

    with col_right:
        st.markdown('<div class="sec-hdr">Alert Feed</div>', unsafe_allow_html=True)
        alerts = [
            ("#FF0055","CRITICAL","CONTACT-D: ROE KINETIC — human auth pending"),
            ("#FF0055","CRITICAL","CONTACT-C: ROE KINETIC — confirmation required"),
            ("#FFCC00","HIGH",    "DARK-003: AIS off, 18 kts, EEZ entry"),
            ("#FFCC00","HIGH",    "EAMA: MMSI 987654 piracy prob 1.0"),
            ("#00CCFF","MEDIUM",  "SHESN Node-3F offline → rerouted"),
            ("#00CCFF","MEDIUM",  "Cyclone 95 kts, surge 13.1m forecast"),
            ("#00FFAA","INFO",    "QIRO fleet: +39% route saving"),
            ("#00FFAA","INFO",    "SEAS SonarCNN gen13 → 97.8%"),
        ]
        for col, sev, msg in alerts:
            st.markdown(f"""
            <div style='padding:6px 0;border-bottom:1px solid #0D1E2E;font-size:12px'>
              <span style='background:{col}15;color:{col};border:1px solid {col}44;
                font-size:10px;padding:1px 7px;border-radius:2px;
                font-family:Courier New,monospace;margin-right:8px'>{sev}</span>{msg}
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">AI Models</div>', unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(model_fig(), use_container_width=True,
                            config={"displayModeBar": False})

# ════════════════════════ TAB 2: AWRS ════════════════════════════════════════
with tab_awrs:
    st.markdown('<div class="sec-hdr">Autonomous War Response — Live Contact Matrix</div>',
                unsafe_allow_html=True)

    cols = st.columns(len(AWRS_CONTACTS))
    for col, c in zip(cols, AWRS_CONTACTS):
        tp = round(c["threat"] + np.random.uniform(-.02,.02), 2)
        with col:
            st.markdown(f"""
            <div style='background:#0A1520;border:1px solid {c["col"]}33;border-radius:4px;
                        padding:12px;text-align:center'>
              <div style='font-family:Courier New,monospace;font-size:11px;
                          color:{c["col"]};margin-bottom:8px'>{c["id"]}</div>
              <span class="{c['rcls']}">{c["roe"]}</span>
              <div style='font-family:Courier New,monospace;font-size:11px;
                          color:#5A8FA8;margin:6px 0'>{c["speed"]} kts</div>
              <div style='font-family:Courier New,monospace;font-size:22px;
                          font-weight:700;color:{c["col"]}'>{tp:.2f}</div>
              <div style='font-size:10px;color:#5A8FA8;font-family:Courier New,monospace'>
                THREAT PROB</div>
              <div style='font-size:11px;color:#C8D8E8;margin-top:5px'>{c["act"]}</div>
              {"<div style='font-size:10px;color:#FF8800;margin-top:3px'>⚠ AIS DARK</div>" if c["dark"] else ""}
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    df = pd.DataFrame([{
        "Contact": c["id"],
        "Position": f"{c['lat']}°N {c['lon']}°E",
        "Speed": f"{c['speed']} kts",
        "Threat": f"{round(c['threat']+np.random.uniform(-.02,.02),2):.2f}",
        "Piracy NLP": f"{round(c['piracy']+np.random.uniform(-.02,.02),2):.2f}",
        "AIS Dark": "YES" if c["dark"] else "no",
        "ROE": c["roe"],
        "Action": c["act"],
    } for c in AWRS_CONTACTS])
    st.dataframe(df, use_container_width=True, hide_index=True)

    if PLOTLY_OK:
        st.plotly_chart(qaie_fig(), use_container_width=True,
                        config={"displayModeBar": False})

# ════════════════════════ TAB 3: SEAS ════════════════════════════════════════
with tab_seas:
    col_chart, col_stats = st.columns([2, 1])
    with col_chart:
        st.markdown('<div class="sec-hdr">Self-Evolution Convergence</div>',
                    unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(seas_fig(), use_container_width=True,
                            config={"displayModeBar": False})

    with col_stats:
        st.markdown('<div class="sec-hdr">Model Genome Stats</div>',
                    unsafe_allow_html=True)
        evo_models = [
            ("SonarCNN V4", 94.1, 99.9, 13, "Neuroevolution",    "#00FFAA"),
            ("YOLOv8 V4",   91.2, 99.9, 55, "Bayesian Hyperopt", "#9966FF"),
            ("Storm PINN",  87.0, 94.3, 38, "MAML-inspired",     "#00CCFF"),
            ("Anomaly IF",  89.0, 95.1, 29, "Online SGD",        "#FFCC00"),
        ]
        for name, start, best, gen, strat, col in evo_models:
            st.markdown(f"""
            <div style='border-left:3px solid {col};padding:9px 12px;margin-bottom:8px;
                        background:#0A1520;border-radius:0 4px 4px 0'>
              <div style='font-family:Courier New,monospace;font-size:12px;color:{col}'>{name}</div>
              <div style='display:flex;gap:16px;margin-top:4px;font-size:13px'>
                <span>{start}% <span style='color:#5A8FA8;font-size:10px'>start</span></span>
                <span style='color:{col}'>{best}%</span>
                <span style='color:#00FFAA'>+{best-start:.1f}%</span>
              </div>
              <div style='font-size:10px;color:#5A8FA8;margin-top:2px;font-family:Courier New,monospace'>
                Gen {gen} · {strat}
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style='background:#050A0E;border:1px solid #1A3040;border-radius:4px;
                    padding:10px 13px;font-family:Courier New,monospace;
                    font-size:11px;color:#5A8FA8;line-height:1.9'>
            Human retraining: <span style='color:#00FFAA'>0 interventions</span><br>
            Mutation rate: <span style='color:#9966FF'>5%</span><br>
            Strategy: <span style='color:#00CCFF'>(1+1)-ES + Neuroevolution</span>
        </div>""", unsafe_allow_html=True)

# ════════════════════════ TAB 4: CLIMATE ══════════════════════════════════════
with tab_climate:
    col_slr, col_coral, col_poll = st.columns(3)

    with col_slr:
        st.markdown('<div class="sec-hdr">Sea Level Rise + Red Zone</div>',
                    unsafe_allow_html=True)
        if PLOTLY_OK:
            st.plotly_chart(slr_fig(), use_container_width=True,
                            config={"displayModeBar": False})
        st.markdown("""
        <div style='background:#FF005510;border:1px solid #FF005533;border-radius:3px;
                    padding:7px 10px;font-family:Courier New,monospace;font-size:10px;color:#FF8800'>
            ⚠ RED ZONE: 8yr+ SLR > 45mm — coastal evacuation trigger
        </div>""", unsafe_allow_html=True)

    with col_coral:
        st.markdown('<div class="sec-hdr">Coral Reef Health (SACRDT)</div>',
                    unsafe_allow_html=True)
        for reef, live, bleach, dead in [
            ("Lakshadweep Atoll", 72, 18, 10),
            ("Andaman Barrier",   61, 27, 12),
            ("Gulf of Mannar",    55, 32, 13),
            ("Palk Bay",          48, 38, 14),
        ]:
            st.markdown(f"""
            <div style='margin-bottom:12px'>
              <div style='font-size:12px;margin-bottom:3px'>{reef}</div>
              <div style='display:flex;height:8px;border-radius:3px;overflow:hidden;gap:1px'>
                <div style='flex:{live};background:#00FFAA;border-radius:2px 0 0 2px'></div>
                <div style='flex:{bleach};background:#FFCC00'></div>
                <div style='flex:{dead};background:#FF0055;border-radius:0 2px 2px 0'></div>
              </div>
              <div style='display:flex;gap:12px;font-size:10px;margin-top:2px;font-family:Courier New,monospace'>
                <span style='color:#00FFAA'>{live}% live</span>
                <span style='color:#FFCC00'>{bleach}% bleach</span>
                <span style='color:#FF0055'>{dead}% dead</span>
              </div>
            </div>""", unsafe_allow_html=True)

    with col_poll:
        st.markdown('<div class="sec-hdr">Pollution Events</div>',
                    unsafe_allow_html=True)
        for name, area, col, status in [
            ("Oman Sea Spill", 14.2, "#FF0055", "ACTIVE"),
            ("Gulf of Mannar",  3.8, "#FFCC00", "CONTAINED"),
            ("Chennai Coast",   1.1, "#00FFAA", "RESOLVED"),
        ]:
            st.markdown(f"""
            <div style='background:#0A1520;border:1px solid #1A3040;border-radius:4px;
                        padding:10px 13px;margin-bottom:8px'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <div style='font-size:13px;font-weight:600'>{name}</div>
                <span style='background:{col}15;color:{col};border:1px solid {col}44;
                  font-size:10px;padding:2px 8px;border-radius:2px;
                  font-family:Courier New,monospace'>{status}</span>
              </div>
              <div style='font-size:11px;color:#5A8FA8;margin-top:3px;
                          font-family:Courier New,monospace'>{area} km² affected</div>
            </div>""", unsafe_allow_html=True)

# ════════════════════════ TAB 5: AUDIT CHAIN ══════════════════════════════════
with tab_audit:
    col_chain, col_form = st.columns([2, 1])

    with col_chain:
        st.markdown('<div class="sec-hdr">SHA-256 Hash Chain — Immutable Decision Log</div>',
                    unsafe_allow_html=True)

        depth = len(st.session_state.audit_chain)
        latest = st.session_state.audit_chain[-1]["hash"] if st.session_state.audit_chain else "genesis"

        m1, m2 = st.columns([1, 3])
        m1.metric("Chain Depth", str(depth))
        m2.markdown(f"""
        <div style='background:#0A1520;border:1px solid #00CCFF33;border-radius:4px;
                    padding:10px 14px'>
          <div style='font-family:Courier New,monospace;font-size:10px;color:#5A8FA8;margin-bottom:4px'>
            LATEST HASH</div>
          <div style='font-family:Courier New,monospace;font-size:11px;color:#00CCFF;
                      word-break:break-all'>{latest}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # Show entries (newest first)
        for entry in reversed(st.session_state.audit_chain[-8:]):
            roe_col = {"OBSERVE":"#00FFAA","SHADOW":"#00CCFF","WARN":"#FFCC00",
                       "INTERDICT":"#FF8800","ELECTRONIC_JAM":"#FF8800",
                       "KINETIC":"#FF0055"}.get(entry["roe"], "#5A8FA8")
            st.markdown(f"""
            <div style='background:#050A0E;border:1px solid #0D1E2E;border-radius:4px;
                        padding:8px 11px;margin-bottom:6px;
                        font-family:Courier New,monospace;font-size:11px'>
              <div style='display:flex;justify-content:space-between;align-items:center'>
                <span style='color:#C8D8E8'>{entry["contact"]}</span>
                <span style='background:{roe_col}15;color:{roe_col};
                  border:1px solid {roe_col}44;padding:2px 8px;border-radius:2px;
                  font-size:10px'>{entry["roe"]}</span>
              </div>
              <div style='color:#5A8FA8;font-size:10px;margin-top:2px'>{entry["action"]}</div>
              <div style='color:#00CCFF;font-size:10px;margin-top:4px;
                          word-break:break-all'>{entry["hash"][:48]}…</div>
            </div>""", unsafe_allow_html=True)

    with col_form:
        st.markdown('<div class="sec-hdr">Sign & Append Entry</div>',
                    unsafe_allow_html=True)

        contact = st.selectbox("Contact ID",
            [c["id"] for c in AWRS_CONTACTS] + ["CUSTOM"])
        if contact == "CUSTOM":
            contact = st.text_input("Custom ID", value="NEW-CONTACT")

        roe = st.selectbox("ROE Level",
            ["OBSERVE","SHADOW","WARN","INTERDICT","ELECTRONIC_JAM","KINETIC"])

        action = st.text_input("Action", value="deploy_usv_shadow")

        if st.button("⊕  Sign & Append to Chain"):
            prev = (st.session_state.audit_chain[-1]["hash"]
                    if st.session_state.audit_chain else "genesis")
            new_hash = sha256_chain(prev, contact, roe, action)
            st.session_state.audit_chain.append({
                "contact": contact,
                "roe": roe,
                "action": action,
                "hash": new_hash,
                "ts": utc_now(),
            })
            st.success(f"✓ Signed: {new_hash[:24]}…")
            st.rerun()

        st.markdown(f"""
        <div style='background:#001020;border:1px solid #00CCFF22;border-radius:4px;
                    padding:10px 13px;margin-top:10px;
                    font-family:Courier New,monospace;font-size:11px;color:#5A8FA8;line-height:1.9'>
            Storage: <span style='color:#00FFAA'>st.session_state</span><br>
            Algorithm: <span style='color:#9966FF'>SHA-256</span><br>
            Chain type: <span style='color:#00CCFF'>Append-only</span><br>
            Entries: <span style='color:#C8D8E8'>{len(st.session_state.audit_chain)}</span><br>
            Kinetic auth: <span style='color:#FF0055'>Human required</span>
        </div>""", unsafe_allow_html=True)

        # Export button
        if st.session_state.audit_chain:
            import json
            export = json.dumps(st.session_state.audit_chain, indent=2)
            st.download_button(
                label="⬇ Export Chain JSON",
                data=export,
                file_name="oims_audit_chain.json",
                mime="application/json",
            )

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:12px;margin-top:8px;border-top:1px solid #0D1E2E;
    font-family:Courier New,monospace;font-size:10px;color:#2A4050'>
    OIMS V4 × SAMUDRA NETRA X &nbsp;·&nbsp; QAIE · SEAS · AWRS &nbsp;·&nbsp; 15 Modules Active
</div>""", unsafe_allow_html=True)
