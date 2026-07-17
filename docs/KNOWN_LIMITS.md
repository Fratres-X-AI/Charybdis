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
- Navigation-grade bathymetry guarantees. Coarse GEBCO is characterization only;
  integration claims require `--require-integration-grade-map`.
- Current estimation inside the core filter (truth may include current; filter does not)

## Synthetic validation scope

- Seven harbor and seven deep scenarios use modeled maps, dynamics, sensor errors,
  outages, and outliers.
- GEBCO characterization uses a real grid with **synthetic** positions and matcher
  observations.
- Engineering (64 runs) and release (256 runs) tiers share seeds and implementation.
  `validation/seeds_holdout_v1.txt` is a disjoint synthetic holdout set for
  post-tuning confirmation, not field validation.
- Wilson and bootstrap interval checks do not correct for multiple comparisons.

## Integrator responsibilities

See [`PRODUCTION_INTEGRATION.md`](PRODUCTION_INTEGRATION.md) for frame conventions,
sensor packet policy, health handoff, and required external supervision.

## Current release baseline

| Field | Value |
|---|---|
| Git SHA | `d960562` |
| CI | PASS (`29499556631`) |
| Mission matrix | 6/6 PASS at 256 runs |
| Holdout harbor release | 7/7 PASS at 256 runs |
| Holdout deep release | 7/7 PASS at 256 runs |
| Highres NOAA | PASS; CEP95 ~9.78 m |
| Stable API | `docs/STABLE_API.md` |
| Replay harness | `charybdis.evaluation.packet_replay`, schema version `1` |
| Promoted matcher | `models/tcm_so2.pt` (A100 pass 5, ~66 m after_mean hard eval) |
| L40S stamp | `artifacts/pod_l40s_pull_20260714T180953Z` |
| A100 stamp | `20260714T132210Z-ad7fa3e` |

Artifact trees with `SHA256SUMS` or pull manifests live under
`artifacts/pod_*_pull_20260714*/` and
`artifacts/pod_final_pull_20260716T122643Z/`.
