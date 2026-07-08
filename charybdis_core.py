"""CHARYBDIS - GNC core for GPS-denied UUV navigation and TCM.

Pure NumPy engine, fully decoupled from any UI. Three isolated scopes:

  1. TRUE PHYSICS      - ground truth motion under a hidden ocean current.
  2. SENSOR HARDWARE   - DVL (bottom-lock velocity) + drifting strap-down IMU.
  3. NAV FILTER        - dead-reckoned belief with a growing 2-D covariance,
                         corrected by Terrain Contour Matching (TCM) fixes.

The NAV FILTER never reads TRUE PHYSICS state; it only consumes sensor
measurements produced by the hardware models. TCM/ping fixes are the only
mechanism that re-couples the belief to reality.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

import charybdis_sensors as sensors
import charybdis_tracking as tracking
import charybdis_autonomy as autonomy

# --------------------------------------------------------------------------- #
#  MISSION CONSTANTS
# --------------------------------------------------------------------------- #
START = np.array([0.0, 0.0])
WAYPOINT = np.array([120.0, 120.0])
BASE_SPEED = 1.5                       # units / tick  (~5 kn)
DT = 1.0                               # sim seconds per tick
TICK_SECONDS = 0.2                     # wall-clock cadence (5 Hz console)
CURRENT_BIAS = np.array([0.4, -0.15])  # hidden structural set/drift
CURRENT_WAVE = 0.10                    # tidal sinusoid amplitude
TCM_RADIUS = 5.0                       # bathymetric lock radius [units]
PING_DURATION = 20                     # ticks radiating after an active ping
ARRIVAL_RADIUS = 1.5

ANOMALIES: dict[str, np.ndarray] = {
    "TRENCH ALPHA":    np.array([35.0, 25.0]),
    "RIDGE BRAVO":     np.array([70.0, 85.0]),
    "SEAMOUNT CHARLIE": np.array([100.0, 105.0]),
}

# Bathymetric signatures: (amplitude [m], sigma [units]).  Trench is negative
# relief (deepening), ridge and seamount are positive relief.
_ANOMALY_SIG: dict[str, tuple[float, float]] = {
    "TRENCH ALPHA":    (-55.0, 4.5),
    "RIDGE BRAVO":     (40.0, 6.0),
    "SEAMOUNT CHARLIE": (75.0, 5.0),
}


# --------------------------------------------------------------------------- #
#  BATHYMETRY (stored high-fidelity sea-floor map)
# --------------------------------------------------------------------------- #
def _synthetic_bathymetry(x, y):
    """Analytic fallback map: deepening slope + three Gaussian anomalies."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    z = -120.0 - 0.35 * (x + y)
    z += 6.0 * np.sin(x / 11.0) + 5.0 * np.cos(y / 9.0)
    for name, center in ANOMALIES.items():
        amp, sig = _ANOMALY_SIG[name]
        r2 = (x - center[0]) ** 2 + (y - center[1]) ** 2
        z = z + amp * np.exp(-r2 / (2.0 * sig ** 2))
    return z


_BATHY_PROVIDER = None   # optional real-data override (see charybdis_bathy)


def set_bathymetry(func) -> None:
    """Swap in a real bathymetric field (any callable ``f(x, y) -> depth``)."""
    global _BATHY_PROVIDER
    _BATHY_PROVIDER = func


def reset_bathymetry() -> None:
    """Restore the built-in synthetic map."""
    global _BATHY_PROVIDER
    _BATHY_PROVIDER = None


def bathymetry(x, y):
    """Sea-floor depth [m] at continuous coord(s), vectorised over arrays.

    Uses a loaded real-data provider when one is installed via
    :func:`set_bathymetry`, otherwise the analytic synthetic map.
    """
    if _BATHY_PROVIDER is not None:
        return _BATHY_PROVIDER(x, y)
    return _synthetic_bathymetry(x, y)


# --------------------------------------------------------------------------- #
#  PARAMETERS AND STATE
# --------------------------------------------------------------------------- #
@dataclass
class SimParams:
    """Operator-tunable degradation factors and autonomy configuration."""
    # --- core degradation (sidebar sliders) ------------------------------- #
    tidal: float = 1.0      # Tidal Current Intensity
    drift: float = 12.0     # IMU Drift Coefficient
    dvl: float = 1.0        # DVL Noise Factor

    # --- DVL/IMU sensor realism ------------------------------------------- #
    dvl_scale: float = 0.01     # velocity scale-factor 1-sigma (sound-speed cal)
    dvl_dropout: float = 0.0    # per-beam bottom-lock dropout probability

    # --- autonomy master switches ---------------------------------------- #
    autonomy: bool = False      # enable the mission FSM / active behaviours
    adaptive_tcm: bool = True   # divert to a contour when uncertainty is high
    acoustic_mgmt: bool = True  # manage passive/active acoustic posture
    avoid: bool = True          # reactive vertical terrain avoidance

    # --- mission / endurance --------------------------------------------- #
    inspect_ticks: int = 8
    arrival_radius: float = ARRIVAL_RADIUS
    endurance: float = 320.0    # cruise endurance [ticks] at full power
    rtb_frac: float = 0.20      # battery fraction that forces return-to-base

    # --- terrain-fix triggering ------------------------------------------ #
    tcm_trigger: float = 18.0       # 1-sigma error [m] that triggers a divert
    tcm_clear: float = 4.0          # error [m] considered "fixed"
    tcm_quality_gate: float = 0.55  # min correlation peak to accept a fix
    active_ping_trigger: float = 40.0
    threat_level: float = 0.3       # 0 (benign) .. 1 (hostile)
    threat_tolerance: float = 0.6   # max threat at which we will radiate

    # --- multi-contact tracking ------------------------------------------ #
    n_contacts: int = 3

    # --- vertical terrain avoidance (bottom-following) ------------------- #
    cruise_altitude: float = 40.0   # nominal height above seabed [m]
    min_clearance: float = 20.0     # avoidance alerts below this altitude
    max_depth_shallow: float = -8.0 # shallowest allowed depth (no broaching)
    max_depth_rate: float = 6.0     # max vertical rate [m/tick]
    lookahead: float = 10.0         # forward-look sonar range [units]

    # --- adversarial spoofing scenario ----------------------------------- #
    spoof: bool = False
    spoof_center: tuple = (70.0, 85.0)
    spoof_radius: float = 12.0
    spoof_amp: float = 45.0          # amplitude of injected false micro-relief

    # --- learned TCM (optional torch) ------------------------------------ #
    use_nn_tcm: bool = False
    nn_model_path: str = "models/tcm_cnn.pt"


@dataclass
class SimState:
    tick: int = 0
    true_pos: np.ndarray = field(default_factory=lambda: START.copy())
    est_pos: np.ndarray = field(default_factory=lambda: START.copy())
    imu_bias: np.ndarray = field(default_factory=lambda: np.zeros(2))
    # Error covariance over [ex, ey, evx, evy] (position + velocity-bias error).
    P: np.ndarray = field(default_factory=lambda: np.diag([0.25, 0.25, 0.0025, 0.0025]))
    true_path: list = field(default_factory=lambda: [START.copy()])
    est_path: list = field(default_factory=lambda: [START.copy()])
    telemetry: list = field(default_factory=list)   # dict rows for charts
    events: list = field(default_factory=list)      # (tick, level, text)
    fixes: list = field(default_factory=list)       # (tick, kind, pos)
    active_features: set = field(default_factory=set)
    ping_request: bool = False
    ping_ticks: int = 0
    ew_state: str = "RUNNING SILENT"
    reached: bool = False
    last_deflection: float = 0.0
    drift_rate: float = 0.0
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng())
    # --- autonomy / subsystem state --------------------------------------- #
    rng_aux: np.random.Generator = field(default_factory=lambda: np.random.default_rng())
    mission_state: str = "PATROL"
    mission_target: np.ndarray = field(default_factory=lambda: WAYPOINT.copy())
    wp_idx: int = 0
    inspect_ticks: int = 0
    energy_frac: float = 1.0
    vehicle_depth: float = -60.0
    altitude: float = 0.0
    avoid_active: bool = False
    acoustic_mode: str = "PASSIVE"
    exposure: float = 0.0
    dvl_quality: float = 1.0
    heading_bias: float = 0.0
    last_est_vel: np.ndarray = field(default_factory=lambda: np.zeros(2))
    world: object = None
    spoof_detected: bool = False


def _geom() -> dict:
    """Mission geometry: inspect the three contours, then push to the waypoint."""
    return {
        "route": [ANOMALIES["TRENCH ALPHA"], ANOMALIES["RIDGE BRAVO"],
                  ANOMALIES["SEAMOUNT CHARLIE"], WAYPOINT],
        "base": START, "final": WAYPOINT, "anomalies": ANOMALIES,
    }


def init_state(seed: int | None = None, params: SimParams | None = None) -> SimState:
    params = params or SimParams()
    s = SimState()
    s.rng = np.random.default_rng(seed)
    s.rng_aux = np.random.default_rng(None if seed is None else seed + 4041)
    s.vehicle_depth = float(bathymetry(*START)) + params.cruise_altitude
    s.altitude = s.vehicle_depth - float(bathymetry(*START))
    if params.n_contacts > 0:
        s.world = tracking.spawn(params.n_contacts, s.rng_aux)
    s.telemetry.append(_telemetry_row(s))
    _log(s, "INFO", "Nav filter initialised. Bottom-lock acquired. Departing origin.")
    return s


# --------------------------------------------------------------------------- #
#  1. TRUE PHYSICS
# --------------------------------------------------------------------------- #
def guidance_velocity(pos: np.ndarray, target: np.ndarray = WAYPOINT) -> np.ndarray:
    """Commanded body velocity: steer straight at the target, cap speed."""
    to_wp = np.asarray(target, float) - pos
    dist = float(np.hypot(*to_wp))
    if dist < 1e-9:
        return np.zeros(2)
    speed = min(BASE_SPEED, dist)
    return to_wp / dist * speed


def ocean_current(tick: int, tidal: float) -> np.ndarray:
    """Hidden current: structural set-and-drift + time-variant tidal wave."""
    wave = CURRENT_WAVE * np.array([np.sin(tick / 10.0), np.cos(tick / 10.0)])
    return tidal * (CURRENT_BIAS + wave)


# --------------------------------------------------------------------------- #
#  2. SENSOR HARDWARE MODELS
# --------------------------------------------------------------------------- #
def dvl_measure(true_vel: np.ndarray, params: SimParams,
                rng: np.random.Generator) -> np.ndarray:
    """Compat shim: horizontal velocity from the Janus beam model."""
    return sensors.dvl_beam_measure(true_vel, params, rng).velocity


def imu_walk(bias: np.ndarray, params: SimParams,
             rng: np.random.Generator) -> np.ndarray:
    """Advance the IMU accelerometer/rate bias by one random-walk increment."""
    return sensors.imu_velocity_bias_walk(bias, params, rng)


# --------------------------------------------------------------------------- #
#  3. DEAD-RECKONING COVARIANCE (error ellipse)
# --------------------------------------------------------------------------- #
def propagate_covariance(P: np.ndarray, params: SimParams) -> np.ndarray:
    """Grow the error covariance for one un-aided dead-reckoning tick.

    Error state is [ex, ey, evx, evy]: position error and velocity-bias error.
    The IMU bias is a velocity-level random walk, so position error is the
    double integral of white noise and its variance grows ~ cubically in time -
    the hallmark of an un-aided inertial solution. Propagation is the exact
    constant-velocity model  P = F P F^T + Q  (no fudge factors):

        F = [[1,0,DT,0],[0,1,0,DT],[0,0,1,0],[0,0,0,1]]
        Q_pos = (sigma_dvl * DT)^2   (DVL white noise on the position step)
        Q_vel =  sigma_bias^2        (IMU bias random-walk on velocity)
    """
    sigma_dvl = params.dvl * 0.05
    sigma_bias = 0.002 * params.drift
    F = np.array([
        [1.0, 0.0, DT, 0.0],
        [0.0, 1.0, 0.0, DT],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ])
    Q = np.diag([
        (sigma_dvl * DT) ** 2, (sigma_dvl * DT) ** 2,
        sigma_bias ** 2, sigma_bias ** 2,
    ])
    return F @ P @ F.T + Q


def _pos_cov(P: np.ndarray) -> np.ndarray:
    return P[:2, :2] if P.shape[0] >= 2 else P


def error_radius(P: np.ndarray) -> float:
    """Major semi-axis of the 1-sigma position-uncertainty ellipse."""
    w = np.linalg.eigvalsh(_pos_cov(P))
    return float(np.sqrt(max(w.max(), 0.0)))


def ellipse_points(center: np.ndarray, P: np.ndarray, n: int = 72,
                   nsigma: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Polygon tracing the n-sigma position covariance ellipse for plotting."""
    w, v = np.linalg.eigh(_pos_cov(P))
    w = np.clip(w, 0.0, None)
    t = np.linspace(0.0, 2.0 * np.pi, n)
    circle = np.stack([np.cos(t), np.sin(t)], axis=0)
    axes = v @ np.diag(nsigma * np.sqrt(w))
    pts = axes @ circle
    return center[0] + pts[0], center[1] + pts[1]


# --------------------------------------------------------------------------- #
#  4. TERRAIN CONTOUR MATCHING
# --------------------------------------------------------------------------- #
def tcm_cross_correlation(true_pos: np.ndarray, est_pos: np.ndarray,
                          patch: int = 9, span: float = 6.0,
                          search: float = 10.0, step: float = 0.5,
                          distort=None
                          ) -> tuple[np.ndarray, float, np.ndarray]:
    """Correlate the observed seabed profile against the stored map.

    The sonar observes a bathymetric patch centred on the vehicle's TRUE
    position. We slide the stored map patch (anchored on the dead-reckoned
    estimate) across a search grid and pick the offset maximising the
    normalised cross-correlation. The winning offset is added to the estimate
    to yield a bounded, high-confidence position fix.

    ``distort(obs, gx, gy) -> obs`` optionally corrupts the observed patch to
    model an adversary spoofing the returned bathymetry.

    Returns (corrected_position, peak_correlation, correlation_surface).
    """
    axis = np.linspace(-span, span, patch)
    gx, gy = np.meshgrid(axis, axis)
    observed = bathymetry(true_pos[0] + gx, true_pos[1] + gy)
    if distort is not None:
        observed = distort(observed, gx, gy)
    o = observed - observed.mean()
    o_norm = np.sqrt(np.sum(o * o)) + 1e-12

    offs = np.arange(-search, search + 1e-9, step)
    surface = np.empty((offs.size, offs.size))
    for i, ox in enumerate(offs):
        for j, oy in enumerate(offs):
            cand = bathymetry(est_pos[0] + ox + gx, est_pos[1] + oy + gy)
            c = cand - cand.mean()
            surface[i, j] = float(np.sum(o * c) / (o_norm * (np.sqrt(np.sum(c * c)) + 1e-12)))

    i0, j0 = np.unravel_index(np.argmax(surface), surface.shape)
    ox, oy = _parabolic_peak(offs, surface, i0, j0)
    corrected = est_pos + np.array([ox, oy])
    return corrected, float(surface[i0, j0]), surface


def _parabolic_peak(offs, surf, i0, j0):
    def refine(a, b, c, step, center):
        d = a - 2 * b + c
        if abs(d) < 1e-9:
            return center
        return center + 0.5 * step * (a - c) / d
    step = offs[1] - offs[0]
    ox, oy = offs[i0], offs[j0]
    if 0 < i0 < offs.size - 1:
        ox = refine(surf[i0 - 1, j0], surf[i0, j0], surf[i0 + 1, j0], step, offs[i0])
    if 0 < j0 < offs.size - 1:
        oy = refine(surf[i0, j0 - 1], surf[i0, j0], surf[i0, j0 + 1], step, offs[j0])
    return ox, oy


def _apply_fix(s: SimState, corrected: np.ndarray, kind: str, label: str,
               peak: float | None = None) -> None:
    s.est_pos = corrected.copy()
    s.imu_bias = np.zeros(2)
    s.P = np.diag([1e-4, 1e-4, 1e-6, 1e-6])
    s.fixes.append((s.tick, kind, corrected.copy()))
    if peak is not None:
        _log(s, "FIX", f"{label}: contour lock r={peak:.3f}. Error bounded, P reset.")
    else:
        _log(s, "FIX", label)


# --------------------------------------------------------------------------- #
#  ACTIVE ACOUSTIC PING (dangerous manual override)
# --------------------------------------------------------------------------- #
def request_ping(s: SimState) -> None:
    s.ping_request = True


# --------------------------------------------------------------------------- #
#  MAIN STEP
# --------------------------------------------------------------------------- #
def step(s: SimState, params: SimParams) -> None:
    if s.reached:
        return
    s.tick += 1

    # --- 0. GUIDANCE (mission FSM when autonomous, else straight run) ------ #
    if params.autonomy:
        prev = s.mission_state
        target = autonomy.plan_guidance(s, params, _geom())
        if s.mission_state != prev:
            _log(s, "INFO", f"MISSION STATE -> {s.mission_state}.")
    else:
        target = WAYPOINT
    vehicle_vel = guidance_velocity(s.true_pos, target)
    speed = float(np.hypot(*vehicle_vel))
    heading = vehicle_vel / speed if speed > 1e-9 else np.array([1.0, 0.0])

    # --- 1. TRUE PHYSICS -------------------------------------------------- #
    current = ocean_current(s.tick, params.tidal)
    true_vel = vehicle_vel + current
    s.true_pos = s.true_pos + true_vel * DT

    # --- 2. SENSORS (Janus DVL + IMU heading/velocity bias) --------------- #
    dvl = sensors.dvl_beam_measure(true_vel, params, s.rng)
    s.dvl_quality = dvl.quality
    s.heading_bias = sensors.imu_heading_bias_walk(s.heading_bias, params, s.rng)
    s.imu_bias = sensors.imu_velocity_bias_walk(s.imu_bias, params, s.rng)
    if dvl.quality > 0.0:
        est_vel = sensors.rotate(dvl.velocity, s.heading_bias) + s.imu_bias
        s.last_est_vel = est_vel.copy()
    else:                                    # bottom-lock lost: coast
        est_vel = s.last_est_vel.copy()
        _log(s, "WARN", "DVL bottom-lock DEGRADED - coasting on inertial only.")

    # --- 3. DEAD-RECKONING BELIEF ---------------------------------------- #
    s.est_pos = s.est_pos + est_vel * DT
    s.P = propagate_covariance(s.P, params)

    s.true_path.append(s.true_pos.copy())
    s.est_path.append(s.est_pos.copy())

    # --- 4. FIXES (manual ping > autonomous ping > terrain contour) ------- #
    if s.ping_request:
        s.ping_request = False
        s.ping_ticks = PING_DURATION
        _apply_fix(s, s.true_pos.copy(), "PING",
                   "ACTIVE ACOUSTIC PING - transponder fix accepted")
        _log(s, "ALERT", "EW STATE -> COMPROMISED. Radiating acoustic signature.")
    elif autonomy.wants_active_ping(s, params):
        s.ping_ticks = PING_DURATION
        _apply_fix(s, s.true_pos.copy(), "PING",
                   "AUTONOMOUS ACOUSTIC FIX - severe drift, threat tolerable")
        _log(s, "ALERT", "ACOUSTIC MGMT -> ACTIVE. Radiating to bound drift.")
    else:
        _run_tcm(s, params)

    # --- EW / acoustic posture ------------------------------------------- #
    if s.ping_ticks > 0:
        s.ping_ticks -= 1
        s.ew_state = "COMPROMISED - RADIATING ACOUSTIC SIGNATURE"
        if s.ping_ticks == 0:
            s.ew_state = "RUNNING SILENT"
            _log(s, "INFO", "Acoustic emission ceased. Returning to silent running.")
    s.acoustic_mode = "ACTIVE" if s.ping_ticks > 0 else "PASSIVE"

    # --- 5. ENDURANCE + VERTICAL AVOIDANCE + CONTACTS -------------------- #
    autonomy.update_energy(s, params, speed, BASE_SPEED)
    if params.avoid:
        was = s.avoid_active
        autonomy.update_avoidance(s, params, bathymetry, heading)
        if s.avoid_active and not was:
            _log(s, "WARN", f"TERRAIN AVOIDANCE - rising seabed, altitude "
                            f"{s.altitude:.0f} m. Ascending.")
    if s.world is not None:
        tracking.step(s.world, s.est_pos, DT, s.rng_aux)

    # --- counter-detection exposure integral ----------------------------- #
    s.exposure += {"LOW": 0.0, "HIGH": 1.0, "CRITICAL": 5.0}.get(
        counter_detection_risk(s), 0.0)

    # --- telemetry -------------------------------------------------------- #
    deflection = float(np.hypot(*(s.true_pos - s.est_pos)))
    s.drift_rate = (deflection - s.last_deflection) / TICK_SECONDS
    s.last_deflection = deflection
    s.telemetry.append(_telemetry_row(s))

    # --- arrival ---------------------------------------------------------- #
    if params.autonomy:
        if autonomy.mission_complete(s, params, _geom()):
            s.reached = True
            s.mission_state = "ON STATION"
            _log(s, "INFO", "OBJECTIVE SECURED. Asset on station. All stop.")
    elif float(np.hypot(*(WAYPOINT - s.true_pos))) <= ARRIVAL_RADIUS:
        s.reached = True
        _log(s, "INFO", "WAYPOINT REACHED. Mission phase complete. All stop.")


def _spoof_distort(s: SimState, params: SimParams | None):
    """Return a patch-distortion callable if the vehicle is inside a spoof zone."""
    if not params or not getattr(params, "spoof", False):
        return None
    c = np.asarray(params.spoof_center, float)
    if float(np.hypot(*(s.true_pos - c))) > params.spoof_radius:
        return None

    def distort(obs, gx, gy):                # inject false high-frequency relief
        return obs + params.spoof_amp * np.sin(2.4 * gx) * np.cos(2.4 * gy)
    return distort


def _run_tcm(s: SimState, params: SimParams | None = None) -> None:
    """Contour match on entry into a lock radius, with spoof-resistant gating."""
    gate = getattr(params, "tcm_quality_gate", 0.0) if params else 0.0
    use_nn = bool(params and getattr(params, "use_nn_tcm", False))
    distort = _spoof_distort(s, params)
    for name, center in ANOMALIES.items():
        d = float(np.hypot(*(s.true_pos - center)))
        if d <= TCM_RADIUS:
            if name not in s.active_features:
                s.active_features.add(name)
                if use_nn:
                    try:
                        import charybdis_nn as nn
                        corrected, peak, _ = nn.tcm_nn_match(
                            s.true_pos, s.est_pos, bathymetry,
                            model_path=getattr(params, "nn_model_path", None),
                            distort=distort)
                    except Exception:
                        corrected, peak, _ = tcm_cross_correlation(
                            s.true_pos, s.est_pos, distort=distort)
                else:
                    corrected, peak, _ = tcm_cross_correlation(
                        s.true_pos, s.est_pos, distort=distort)
                if peak < gate:
                    s.spoof_detected = True
                    _log(s, "ALERT", f"{name}: LOW-CONFIDENCE contour r={peak:.2f} "
                                     f"- possible spoofing. FIX REJECTED.")
                else:
                    _apply_fix(s, corrected, "TCM", name, peak)
        else:
            s.active_features.discard(name)


# --------------------------------------------------------------------------- #
#  TELEMETRY / RISK / LOG
# --------------------------------------------------------------------------- #
def counter_detection_risk(s: SimState) -> str:
    """Loudness-based EW posture: radiating is worst, then predictable transits."""
    if s.ping_ticks > 0 or getattr(s, "acoustic_mode", "PASSIVE") == "ACTIVE":
        return "CRITICAL"
    near = any(np.hypot(*(s.true_pos - c)) <= TCM_RADIUS + 3.0
               for c in ANOMALIES.values())
    return "HIGH" if near else "LOW"


def mission_phase(s: SimState) -> str:
    if s.reached:
        return "ON STATION"
    frac = float(np.hypot(*(s.true_pos - START))) / float(np.hypot(*(WAYPOINT - START)))
    if frac < 0.33:
        return "INGRESS"
    if frac < 0.85:
        return "TRANSIT"
    return "TERMINAL APPROACH"


def _telemetry_row(s: SimState) -> dict:
    deflection = float(np.hypot(*(s.true_pos - s.est_pos)))
    return {
        "tick": s.tick,
        "t": s.tick * TICK_SECONDS,
        "deflection": deflection,
        "error_radius": error_radius(s.P),
        "drift_rate": s.drift_rate,
        "true_x": s.true_pos[0], "true_y": s.true_pos[1],
        "est_x": s.est_pos[0], "est_y": s.est_pos[1],
        "altitude": s.altitude,
        "energy": s.energy_frac,
        "dvl_q": s.dvl_quality,
    }


def _log(s: SimState, level: str, text: str) -> None:
    s.events.append((s.tick, level, text))
    if len(s.events) > 400:
        del s.events[:-400]


# --------------------------------------------------------------------------- #
#  HEADLESS SELF-TEST
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    p = SimParams(autonomy=True)
    st_ = init_state(seed=7, params=p)
    max_defl = 0.0
    while not st_.reached and st_.tick < 600:
        step(st_, p)
        max_defl = max(max_defl, st_.telemetry[-1]["deflection"])
        if st_.tick % 15 == 0:
            r = st_.telemetry[-1]
            print(f"t={st_.tick:3d} true=({r['true_x']:6.1f},{r['true_y']:6.1f}) "
                  f"defl={r['deflection']:6.2f} err_r={r['error_radius']:6.2f} "
                  f"alt={r['altitude']:5.0f} batt={r['energy']*100:4.0f}% "
                  f"{st_.mission_state:9s} {counter_detection_risk(st_)}")
    print("\n--- FIXES ---")
    for tick, kind, pos in st_.fixes:
        print(f"  t={tick:3d} {kind:4s} -> ({pos[0]:6.1f},{pos[1]:6.1f})")
    trk = tracking.track_error(st_.world) if st_.world else 0.0
    print(f"\nticks={st_.tick} reached={st_.reached} peak_defl={max_defl:.2f} "
          f"batt={st_.energy_frac*100:.0f}% contacts={len(st_.world.contacts) if st_.world else 0} "
          f"track_err={trk:.2f}m exposure={st_.exposure:.0f}")
