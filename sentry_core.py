"""BLACK SEA SENTRY - GNC core for GPS-denied UUV navigation and TCM.

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
def bathymetry(x, y):
    """Sea-floor depth [m] at continuous coord(s). Vectorised over arrays.

    A gently deepening regional slope with three localized Gaussian anomalies
    that give the seabed a locally unique, correlatable contour signature.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    z = -120.0 - 0.35 * (x + y)
    z += 6.0 * np.sin(x / 11.0) + 5.0 * np.cos(y / 9.0)
    for name, center in ANOMALIES.items():
        amp, sig = _ANOMALY_SIG[name]
        r2 = (x - center[0]) ** 2 + (y - center[1]) ** 2
        z = z + amp * np.exp(-r2 / (2.0 * sig ** 2))
    return z


# --------------------------------------------------------------------------- #
#  PARAMETERS AND STATE
# --------------------------------------------------------------------------- #
@dataclass
class SimParams:
    """Operator-tunable degradation factors (sidebar sliders)."""
    tidal: float = 1.0      # Tidal Current Intensity
    drift: float = 12.0     # IMU Drift Coefficient
    dvl: float = 1.0        # DVL Noise Factor


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


def init_state(seed: int | None = None) -> SimState:
    s = SimState()
    s.rng = np.random.default_rng(seed)
    s.telemetry.append(_telemetry_row(s))
    _log(s, "INFO", "Nav filter initialised. Bottom-lock acquired. Departing origin.")
    return s


# --------------------------------------------------------------------------- #
#  1. TRUE PHYSICS
# --------------------------------------------------------------------------- #
def guidance_velocity(pos: np.ndarray) -> np.ndarray:
    """Commanded body velocity: steer straight at the waypoint, cap speed."""
    to_wp = WAYPOINT - pos
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
    """Doppler Velocity Log: true seabed-relative velocity + white noise."""
    std = params.dvl * 0.05
    return true_vel + rng.normal(0.0, std, size=2)


def imu_walk(bias: np.ndarray, params: SimParams,
             rng: np.random.Generator) -> np.ndarray:
    """Advance the IMU accelerometer/rate bias by one random-walk increment."""
    std = 0.002 * params.drift
    return bias + rng.normal(0.0, std, size=2)


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
                          search: float = 10.0, step: float = 0.5
                          ) -> tuple[np.ndarray, float, np.ndarray]:
    """Correlate the observed seabed profile against the stored map.

    The sonar observes a bathymetric patch centred on the vehicle's TRUE
    position. We slide the stored map patch (anchored on the dead-reckoned
    estimate) across a search grid and pick the offset maximising the
    normalised cross-correlation. The winning offset is added to the estimate
    to yield a bounded, high-confidence position fix.

    Returns (corrected_position, peak_correlation, correlation_surface).
    """
    axis = np.linspace(-span, span, patch)
    gx, gy = np.meshgrid(axis, axis)
    observed = bathymetry(true_pos[0] + gx, true_pos[1] + gy)
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

    # --- 1. TRUE PHYSICS -------------------------------------------------- #
    vehicle_vel = guidance_velocity(s.true_pos)
    current = ocean_current(s.tick, params.tidal)
    true_vel = vehicle_vel + current
    s.true_pos = s.true_pos + true_vel * DT

    # --- 2. SENSORS ------------------------------------------------------- #
    dvl = dvl_measure(true_vel, params, s.rng)
    s.imu_bias = imu_walk(s.imu_bias, params, s.rng)
    est_vel = dvl + s.imu_bias                     # drift corrupts the belief

    # --- 3. DEAD-RECKONING BELIEF ---------------------------------------- #
    s.est_pos = s.est_pos + est_vel * DT
    s.P = propagate_covariance(s.P, params)

    s.true_path.append(s.true_pos.copy())
    s.est_path.append(s.est_pos.copy())

    # --- 4. FIXES (ping overrides scheduled TCM) ------------------------- #
    if s.ping_request:
        s.ping_request = False
        s.ping_ticks = PING_DURATION
        _apply_fix(s, s.true_pos.copy(), "PING",
                   "ACTIVE ACOUSTIC PING - transponder fix accepted")
        _log(s, "ALERT", "EW STATE -> COMPROMISED. Radiating acoustic signature.")
    else:
        _run_tcm(s)

    # --- EW / risk bookkeeping ------------------------------------------- #
    if s.ping_ticks > 0:
        s.ping_ticks -= 1
        s.ew_state = "COMPROMISED - RADIATING ACOUSTIC SIGNATURE"
        if s.ping_ticks == 0:
            s.ew_state = "RUNNING SILENT"
            _log(s, "INFO", "Acoustic emission ceased. Returning to silent running.")

    # --- telemetry -------------------------------------------------------- #
    deflection = float(np.hypot(*(s.true_pos - s.est_pos)))
    s.drift_rate = (deflection - s.last_deflection) / TICK_SECONDS
    s.last_deflection = deflection
    s.telemetry.append(_telemetry_row(s))

    if float(np.hypot(*(WAYPOINT - s.true_pos))) <= ARRIVAL_RADIUS:
        s.reached = True
        _log(s, "INFO", "WAYPOINT REACHED. Mission phase complete. All stop.")


def _run_tcm(s: SimState) -> None:
    """Trigger a contour match on entry into any anomaly's lock radius."""
    for name, center in ANOMALIES.items():
        d = float(np.hypot(*(s.true_pos - center)))
        if d <= TCM_RADIUS:
            if name not in s.active_features:
                s.active_features.add(name)
                corrected, peak, _ = tcm_cross_correlation(s.true_pos, s.est_pos)
                _apply_fix(s, corrected, "TCM", name, peak)
        else:
            s.active_features.discard(name)


# --------------------------------------------------------------------------- #
#  TELEMETRY / RISK / LOG
# --------------------------------------------------------------------------- #
def counter_detection_risk(s: SimState) -> str:
    if s.ping_ticks > 0:
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
    }


def _log(s: SimState, level: str, text: str) -> None:
    s.events.append((s.tick, level, text))
    if len(s.events) > 400:
        del s.events[:-400]


# --------------------------------------------------------------------------- #
#  HEADLESS SELF-TEST
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    p = SimParams()
    st_ = init_state(seed=7)
    max_defl = 0.0
    while not st_.reached and st_.tick < 400:
        step(st_, p)
        max_defl = max(max_defl, st_.telemetry[-1]["deflection"])
        if st_.tick % 10 == 0:
            r = st_.telemetry[-1]
            print(f"t={st_.tick:3d} true=({r['true_x']:6.1f},{r['true_y']:6.1f}) "
                  f"defl={r['deflection']:6.2f} err_r={r['error_radius']:6.2f} "
                  f"risk={counter_detection_risk(st_):8s} {mission_phase(st_)}")
    print("\n--- FIXES ---")
    for tick, kind, pos in st_.fixes:
        print(f"  t={tick:3d} {kind:4s} -> ({pos[0]:6.1f},{pos[1]:6.1f})")
    print(f"\nticks={st_.tick} reached={st_.reached} peak_deflection={max_defl:.2f}")
