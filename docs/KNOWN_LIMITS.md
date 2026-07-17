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
| Branch | `main` |
| CI | PASS on `main`; workflow definition in `.github/workflows/ci.yml` |
| Mission matrix | 6/6 PASS @ 256 runs |
| Holdout harbor release | 7/7 PASS @ 256 runs |
| Holdout deep release | 7/7 PASS @ 256 runs |
| Harbor + deep release | 7/7 PASS @ 256 runs each |
| Highres NOAA Monterey | PASS; CEP95 **9.78 m**; 256/256 accepted |
| Terrain matcher baseline | `models/tcm_so2.pt` |
| Validation artifacts | Retained outside git; verify local pull with `scripts/pod/verify_release_cpu.sh` |
| Stable API | `docs/STABLE_API.md` |
| Replay harness | `charybdis.evaluation.packet_replay`, schema version `1` |
| RunPod ops | `docs/REMOTE_VALIDATION.md` |
| Release CPU verify | `bash scripts/pod/verify_release_cpu.sh` |

Artifact trees with `SHA256SUMS` or pull manifests are retained outside the
repository. Do not commit large validation trees, pod logs, credentials, or
model experiments unless a maintainer explicitly requests them.
