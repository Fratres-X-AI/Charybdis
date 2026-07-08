"""Autonomy layer for Charybdis.

Pure decision functions (no dependency on the core module, to avoid import
cycles) that turn the raw nav/physics state into vehicle behaviour:

  * a mission finite-state machine  PATROL -> INSPECT -> TCM FIX -> RTB -> ON STATION,
  * an endurance / energy model that forces return-to-base when the battery is low,
  * adaptive terrain fixing: divert to the nearest strong contour when the
    inertial uncertainty exceeds a trigger, instead of waiting to stumble on one,
  * active-acoustic management: stay passive unless uncertainty is severe *and*
    the threat environment tolerates radiating,
  * reactive terrain avoidance in the vertical channel (forward-look sonar keeps
    a minimum clearance over rising seabed without touching the 2-D track).
"""
from __future__ import annotations

import numpy as np

INSPECT_RADIUS = 6.0


def _err(P: np.ndarray) -> float:
    w = np.linalg.eigvalsh(P[:2, :2])
    return float(np.sqrt(max(w.max(), 0.0)))


def _nearest(points, pos: np.ndarray) -> np.ndarray:
    pts = [np.asarray(p, float) for p in points]
    return min(pts, key=lambda p: float(np.hypot(*(p - pos)))).copy()


# --------------------------------------------------------------------------- #
#  MISSION FSM
# --------------------------------------------------------------------------- #
def plan_guidance(s, params, geom) -> np.ndarray:
    """Update the mission state machine and return the guidance target."""
    route, base, final = geom["route"], geom["base"], geom["final"]
    err = _err(s.P)

    # 1. Endurance override: return to base when the battery is low.
    if s.energy_frac <= params.rtb_frac and s.mission_state not in ("RTB", "ON STATION"):
        s.mission_state = "RTB"
    if s.mission_state == "RTB":
        s.mission_target = np.asarray(base, float).copy()
        return s.mission_target

    # 2. Adaptive terrain fixing: divert to the nearest contour when uncertain.
    if params.adaptive_tcm and err > params.tcm_trigger and s.mission_state != "TCM FIX":
        s.mission_state = "TCM FIX"
    if s.mission_state == "TCM FIX":
        if err <= params.tcm_clear:
            s.mission_state = "PATROL"          # uncertainty bounded, resume
        else:
            s.mission_target = _nearest(geom["anomalies"].values(), s.est_pos)
            return s.mission_target

    # 3. Inspection loiter.
    if s.inspect_ticks > 0:
        s.mission_state = "INSPECT"
        s.inspect_ticks -= 1
        return s.mission_target

    # 4. Patrol the route.
    s.mission_state = "PATROL"
    if s.wp_idx >= len(route):
        s.mission_target = np.asarray(final, float).copy()
        return s.mission_target
    wp = np.asarray(route[s.wp_idx], float)
    s.mission_target = wp.copy()
    if float(np.hypot(*(s.true_pos - wp))) <= INSPECT_RADIUS:
        s.inspect_ticks = params.inspect_ticks
        s.wp_idx += 1
    return s.mission_target


def mission_complete(s, params, geom) -> bool:
    """True once the vehicle has settled on its terminal objective."""
    if s.mission_state == "RTB":
        goal = np.asarray(geom["base"], float)
    elif s.wp_idx >= len(geom["route"]):
        goal = np.asarray(geom["final"], float)
    else:
        return False
    return float(np.hypot(*(s.true_pos - goal))) <= params.arrival_radius


# --------------------------------------------------------------------------- #
#  ENERGY / ENDURANCE
# --------------------------------------------------------------------------- #
def update_energy(s, params, speed: float, base_speed: float) -> None:
    """Deplete normalised battery: hotel load + cubic propulsion + sonar."""
    frac = (speed / base_speed) if base_speed > 0 else 0.0
    sonar = 0.6 if (s.ping_ticks > 0 or s.acoustic_mode == "ACTIVE") else 0.0
    power = 0.3 + 0.7 * frac ** 3 + sonar
    s.energy_frac = max(0.0, s.energy_frac - power / max(params.endurance, 1.0))


# --------------------------------------------------------------------------- #
#  ACTIVE-ACOUSTIC MANAGEMENT
# --------------------------------------------------------------------------- #
def wants_active_ping(s, params) -> bool:
    """Passive-first policy: only radiate when badly lost and threat tolerates."""
    if not (params.autonomy and params.acoustic_mgmt) or s.ping_ticks > 0:
        return False
    return (_err(s.P) > params.active_ping_trigger
            and params.threat_level <= params.threat_tolerance)


# --------------------------------------------------------------------------- #
#  REACTIVE TERRAIN AVOIDANCE (vertical channel)
# --------------------------------------------------------------------------- #
def update_avoidance(s, params, bathy, heading: np.ndarray) -> None:
    """Bottom-following depth control with forward-look terrain avoidance.

    The vehicle holds a nominal altitude over the seabed. The forward-look sonar
    anticipates rising terrain (ridges, seamounts); when the required climb rate
    saturates or the current clearance drops below the safety floor, avoidance
    is flagged. Acts purely in the vertical channel - the 2-D track is untouched.
    """
    x, y = float(s.true_pos[0]), float(s.true_pos[1])
    seabed = float(bathy(x, y))
    ahead = float(bathy(x + heading[0] * params.lookahead,
                        y + heading[1] * params.lookahead))
    shallowest = max(seabed, ahead)                     # less-negative = shallower
    desired = min(shallowest + params.cruise_altitude, params.max_depth_shallow)
    raw_dz = desired - s.vehicle_depth
    dz = float(np.clip(raw_dz, -params.max_depth_rate, params.max_depth_rate))
    s.vehicle_depth += dz
    s.altitude = s.vehicle_depth - seabed
    # avoidance = climbing over rising terrain faster than we can, or low clearance
    s.avoid_active = raw_dz > params.max_depth_rate or s.altitude < params.min_clearance
