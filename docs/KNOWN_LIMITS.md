# Known limits

Charybdis is a **research-grade hybrid navigation library**. Release-tier
validation PASS means the declared synthetic gates held for a fixed seed set —
not operational deployment, certification, or safety assurance.

## What this software does not provide

- Hardware-in-the-loop or vehicle integration
- Field trials, sea trials, or independent reference estimators
- Collision avoidance, geofencing, or mission supervision
- Actuator control, saturation handling, or safety interlocks
- Cyber security, tamper evidence, or configuration management beyond git SHA
- MIL-STD, DO-178, or regulatory certification claims
- High-resolution bathymetry navigation guarantees (coarse GEBCO is characterization only)
- Current estimation inside the core filter (truth may include current; filter does not)

## Synthetic validation scope

- Seven harbor and six deep scenarios use modeled maps, dynamics, sensor errors,
  outages, and outliers.
- GEBCO characterization uses a real grid with **synthetic** positions and matcher
  observations.
- Engineering (64 runs) and release (256 runs) tiers share seeds and implementation;
  there is no independent holdout set.
- Wilson and bootstrap interval checks do not correct for multiple comparisons.

## Integrator responsibilities

See [`PRODUCTION_INTEGRATION.md`](PRODUCTION_INTEGRATION.md) for frame conventions,
sensor packet policy, health handoff, and required external supervision.

## Current release baseline

| Field | Value |
|---|---|
| Git SHA | `ad7fa3e` |
| Harbor release | 7/7 PASS (CEP95 ~1.0–1.4 m) |
| Deep release | 6/6 PASS (CEP95 ~1.1–1.3 m) |
| Promoted matcher | `models/tcm_so2.pt` (A100 pass 5, ~66 m after_mean hard eval) |
| Bronze stamp | `20260714T153106Z-ad7fa3e` |
| A100 stamp | `20260714T132210Z-ad7fa3e` |

Artifact trees with `SHA256SUMS` live under `artifacts/pod_*_pull_20260714/`.
