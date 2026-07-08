"""BLACK SEA SENTRY - Tactical Command Console.

Real-time Streamlit + Plotly console for a GPS-denied UUV running dead-reckoned
inertial navigation aided by Terrain Contour Matching (TCM). The GNC engine
lives in `sentry_core`; this module is purely the operator-facing console and
the ~5 Hz real-time loop.

    uv add streamlit numpy plotly pandas
    uv run streamlit run blacksea_sentry.py
"""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import sentry_core as core

st.set_page_config(page_title="BLACK SEA SENTRY // TCM CONSOLE",
                   page_icon="\U0001F6F0", layout="wide")

# --------------------------------------------------------------------------- #
#  TACTICAL THEME
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-family: 'Consolas','SFMono-Regular',monospace; }
    .stApp { background:
        radial-gradient(circle at 20% 10%, #071018 0%, #05080B 55%, #02040A 100%); }
    #MainMenu, footer { visibility: hidden; }
    .hud-title { color:#39FF14; font-size:26px; font-weight:700; letter-spacing:4px;
        text-shadow:0 0 8px rgba(57,255,20,.55); }
    .hud-sub { color:#5FBF8F; font-size:12px; letter-spacing:3px; margin-top:-6px; }
    .metric-card { background:rgba(10,22,28,.75); border:1px solid #123; border-radius:6px;
        padding:10px 14px; box-shadow:0 0 12px rgba(0,0,0,.5) inset; }
    .metric-label { color:#5FBF8F; font-size:11px; letter-spacing:2px; }
    .metric-value { font-size:26px; font-weight:700; }
    .badge { padding:2px 10px; border-radius:4px; font-weight:700; letter-spacing:2px; }
    .r-LOW { background:#0d3b1e; color:#39FF14; border:1px solid #1f7a3d; }
    .r-HIGH { background:#4a3400; color:#FFB000; border:1px solid #8a6200; }
    .r-CRITICAL { background:#4a0d0d; color:#FF4B4B; border:1px solid #8a1f1f;
        animation:pulse 1s infinite; }
    @keyframes pulse { 0%{opacity:1} 50%{opacity:.45} 100%{opacity:1} }
    .ew-silent { color:#39FF14; } .ew-compromised { color:#FF4B4B; font-weight:700; }
    .logbox { background:#02060A; border:1px solid #12303a; border-radius:6px;
        padding:8px 12px; font-size:12px; line-height:1.5; }
    .stButton>button { width:100%; font-weight:700; letter-spacing:1px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
#  BATHYMETRY BACKDROP (cached)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def bathy_grid(lo: float = -10.0, hi: float = 135.0, n: int = 150):
    axis = np.linspace(lo, hi, n)
    gx, gy = np.meshgrid(axis, axis)
    z = core.bathymetry(gx, gy)
    return axis, z


# --------------------------------------------------------------------------- #
#  SESSION STATE
# --------------------------------------------------------------------------- #
def boot(seed: int = 7):
    st.session_state.sim = core.init_state(seed=seed)
    st.session_state.running = True


if "sim" not in st.session_state:
    boot()

sim: core.SimState = st.session_state.sim

# --------------------------------------------------------------------------- #
#  SIDEBAR CONTROL UNIT
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### \u2699\ufe0f CONTROL UNIT")
    params = core.SimParams(
        tidal=st.slider("Tidal Current Intensity", 0.0, 3.0, 1.0, 0.1),
        drift=st.slider("IMU Drift Coefficient", 0.0, 30.0, 12.0, 0.5),
        dvl=st.slider("DVL Noise Factor", 0.0, 5.0, 1.0, 0.1),
    )
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("\u25B6 ARM" if not st.session_state.running else "\u23F8 HOLD"):
        st.session_state.running = not st.session_state.running
    if c2.button("\u21BA RESET"):
        boot(seed=int(st.session_state.get("seed", 7)))
        sim = st.session_state.sim
    st.session_state.seed = st.number_input("Nav seed", 0, 9999,
                                            int(st.session_state.get("seed", 7)))
    st.divider()
    if st.button("\U0001F6A8 EMERGENCY ACOUSTIC PING", type="primary"):
        core.request_ping(sim)
    st.caption("Active ping forces a fix but radiates an acoustic signature "
               f"for {core.PING_DURATION} ticks.")
    st.divider()
    st.caption(f"TCM lock radius {core.TCM_RADIUS:.0f} u  |  base speed "
               f"{core.BASE_SPEED} u/tick  |  console 5 Hz")


# --------------------------------------------------------------------------- #
#  HEADER + TELEMETRY MATRIX
# --------------------------------------------------------------------------- #
st.markdown('<div class="hud-title">BLACK SEA SENTRY</div>', unsafe_allow_html=True)
st.markdown('<div class="hud-sub">GPS-DENIED UUV // INERTIAL + TERRAIN CONTOUR '
            'MATCHING // TACTICAL COMMAND CONSOLE</div>', unsafe_allow_html=True)
st.write("")

deflection = float(np.hypot(*(sim.true_pos - sim.est_pos)))
risk = core.counter_detection_risk(sim)
phase = core.mission_phase(sim)
err_r = core.error_radius(sim.P)

m1, m2, m3, m4 = st.columns(4)
m1.markdown(f'<div class="metric-card"><div class="metric-label">STRUCTURAL '
            f'DEFLECTION</div><div class="metric-value" style="color:#FF6B6B">'
            f'{deflection:6.2f} m</div><div class="metric-label">true \u2194 estimate'
            f'</div></div>', unsafe_allow_html=True)
m2.markdown(f'<div class="metric-card"><div class="metric-label">INS DRIFT '
            f'ACCELERATION</div><div class="metric-value" style="color:#FFB000">'
            f'{sim.drift_rate:+6.2f} m/s</div><div class="metric-label">error accrual '
            f'rate</div></div>', unsafe_allow_html=True)
m3.markdown(f'<div class="metric-card"><div class="metric-label">COUNTER-DETECTION '
            f'RISK</div><div class="metric-value"><span class="badge r-{risk}">{risk}'
            f'</span></div><div class="metric-label">EW posture</div></div>',
            unsafe_allow_html=True)
ew_cls = "ew-compromised" if sim.ping_ticks > 0 else "ew-silent"
m4.markdown(f'<div class="metric-card"><div class="metric-label">UNCERTAINTY / '
            f'PHASE</div><div class="metric-value" style="color:#39FF14">'
            f'{err_r:5.2f} m</div><div class="metric-label {ew_cls}">{phase} \u2022 '
            f'{sim.ew_state.split(" - ")[0]}</div></div>', unsafe_allow_html=True)

st.write("")


# --------------------------------------------------------------------------- #
#  TACTICAL PLOT
# --------------------------------------------------------------------------- #
def build_map(sim: core.SimState) -> go.Figure:
    axis, Z = bathy_grid()
    fig = go.Figure()
    fig.add_trace(go.Contour(
        x=axis, y=axis, z=Z, showscale=False, opacity=0.55,
        ncontours=22, colorscale=[[0, "#020c14"], [0.5, "#063142"], [1, "#0d6f7d"]],
        contours=dict(coloring="fill"), line=dict(width=0.4, color="#0a3a44"),
        hoverinfo="skip"))

    tp = np.array(sim.true_path)
    ep = np.array(sim.est_path)
    fig.add_trace(go.Scatter(x=tp[:, 0], y=tp[:, 1], mode="lines",
                  line=dict(color="#3AA0FF", width=3), name="Ground Truth"))
    fig.add_trace(go.Scatter(x=ep[:, 0], y=ep[:, 1], mode="lines",
                  line=dict(color="#FF4B4B", width=2, dash="dash"),
                  name="INS Estimate"))

    ex, ey = core.ellipse_points(sim.est_pos, sim.P, nsigma=1.0)
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", fill="toself",
                  fillcolor="rgba(255,60,60,0.18)",
                  line=dict(color="rgba(255,90,90,0.65)", width=1),
                  name="1\u03c3 Error Ellipse", hoverinfo="skip"))

    if sim.fixes:
        fx = np.array([f[2] for f in sim.fixes])
        fig.add_trace(go.Scatter(x=fx[:, 0], y=fx[:, 1], mode="markers",
                      marker=dict(symbol="star", size=15, color="#39FF14",
                                  line=dict(color="#0a2", width=1)),
                      name="TCM / Ping Fix"))

    ax = np.array([c for c in core.ANOMALIES.values()])
    labels = list(core.ANOMALIES.keys())
    fig.add_trace(go.Scatter(x=ax[:, 0], y=ax[:, 1], mode="markers+text",
                  marker=dict(symbol="diamond", size=13, color="#FFD400",
                              line=dict(color="#000", width=1)),
                  text=labels, textposition="top center",
                  textfont=dict(color="#FFD400", size=10), name="Bathymetric Node"))

    fig.add_trace(go.Scatter(x=[core.WAYPOINT[0]], y=[core.WAYPOINT[1]],
                  mode="markers+text", marker=dict(symbol="x", size=16,
                  color="#FF00E5", line=dict(width=2)), text=["WAYPOINT"],
                  textposition="bottom center", textfont=dict(color="#FF00E5", size=10),
                  name="Waypoint"))
    fig.add_trace(go.Scatter(x=[core.START[0]], y=[core.START[1]], mode="markers",
                  marker=dict(symbol="circle", size=11, color="#39FF14"), name="Launch"))

    fig.add_trace(go.Scatter(x=[sim.true_pos[0]], y=[sim.true_pos[1]], mode="markers",
                  marker=dict(symbol="triangle-up", size=16, color="#00E5FF",
                  line=dict(color="#012", width=1)), name="Asset (true)"))
    fig.add_trace(go.Scatter(x=[sim.est_pos[0]], y=[sim.est_pos[1]], mode="markers",
                  marker=dict(symbol="triangle-up-open", size=16, color="#FF4B4B"),
                  name="Asset (belief)"))

    fig.update_layout(
        height=640, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="#05080B", plot_bgcolor="#05080B",
        font=dict(color="#8FF0C0", family="monospace"),
        legend=dict(bgcolor="rgba(5,12,16,.6)", bordercolor="#123", borderwidth=1,
                    font=dict(size=10), orientation="v", x=0.01, y=0.99),
        xaxis=dict(range=[-10, 135], gridcolor="#0d1f26", zeroline=False,
                   title="EAST [m]", constrain="domain"),
        yaxis=dict(range=[-10, 135], gridcolor="#0d1f26", zeroline=False,
                   title="NORTH [m]", scaleanchor="x", scaleratio=1),
        title=dict(text="TACTICAL BATHYMETRIC PLOT", x=0.5,
                   font=dict(color="#39FF14", size=14)))
    return fig


left, right = st.columns([3, 2])
with left:
    st.plotly_chart(build_map(sim), use_container_width=True,
                    config={"displayModeBar": False})

with right:
    df = pd.DataFrame(sim.telemetry)
    if len(df) > 1:
        tfig = go.Figure()
        tfig.add_trace(go.Scatter(x=df["t"], y=df["deflection"], mode="lines",
                       line=dict(color="#FF6B6B", width=2), name="Deflection [m]"))
        tfig.add_trace(go.Scatter(x=df["t"], y=df["error_radius"], mode="lines",
                       line=dict(color="#39FF14", width=1, dash="dot"),
                       name="1\u03c3 Error [m]"))
        for f in sim.fixes:
            tfig.add_vline(x=f[0] * core.TICK_SECONDS, line=dict(
                color="#FFD400" if f[1] == "TCM" else "#FF00E5", width=1, dash="dot"))
        tfig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10),
                           paper_bgcolor="#05080B", plot_bgcolor="#05080B",
                           font=dict(color="#8FF0C0", size=10, family="monospace"),
                           legend=dict(orientation="h", y=1.18, font=dict(size=9)),
                           xaxis=dict(title="MISSION TIME [s]", gridcolor="#0d1f26"),
                           yaxis=dict(title="[m]", gridcolor="#0d1f26"),
                           title=dict(text="NAV ERROR HISTORY", x=0.5,
                                      font=dict(color="#39FF14", size=13)))
        st.plotly_chart(tfig, use_container_width=True,
                        config={"displayModeBar": False})

    st.markdown("**\U0001F4E1 TACTICAL LOG**")
    colors = {"INFO": "#8FF0C0", "FIX": "#39FF14", "ALERT": "#FF4B4B", "WARN": "#FFB000"}
    rows = []
    for tick, level, text in reversed(sim.events[-120:]):
        c = colors.get(level, "#8FF0C0")
        stamp = time.strftime("%H:%M:%S")
        rows.append(f'<div><span style="color:#3a6">[t{tick:03d}]</span> '
                    f'<span style="color:{c}">[{level:5s}]</span> '
                    f'<span style="color:#bfe">{text}</span></div>')
    with st.container(height=300):
        st.markdown('<div class="logbox">' + "".join(rows) + "</div>",
                    unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
#  REAL-TIME LOOP (~5 Hz)
# --------------------------------------------------------------------------- #
_LOOP_ENABLED = os.environ.get("SENTRY_NO_LOOP") != "1"  # test hook
if _LOOP_ENABLED and st.session_state.running and not sim.reached:
    core.step(sim, params)
    time.sleep(core.TICK_SECONDS)
    st.rerun()
elif sim.reached:
    st.success("MISSION COMPLETE - asset on station at waypoint. Hold for tasking.")
