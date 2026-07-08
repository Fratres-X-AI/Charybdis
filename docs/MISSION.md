# Charybdis mission

## Primary goal

**Charybdis is a GPS-denied terrain-aided navigation research platform.**

The primary deliverable is a trustworthy navigation stack:

- strapdown INS (dead-reckoning baseline)
- TERCOM / TRN terrain aiding
- EKF + particle filter (+ optional PMF)
- Monte-Carlo evaluation (CEP, NEES, stress gates)

If a change does not improve filter correctness, evaluation honesty, or the ability to run those filters on real bathymetry, it is secondary.

## Secondary product

**UUV tactical console** (`charybdis_core.py` + Streamlit UI) is an application layer that demonstrates contested underwater TCM, autonomy, and tracking. It shares the *problem domain* (GPS-denied terrain aiding) but is a separate codebase spine from the airborne GDI package (`charybdis/`).

Do not force a premature merge of the two stacks. Share ideas and APIs (`NavEstimate`, bathymetry loaders) first; share implementations only when adapters are clean.

## Non-goals (for now)

- Production flight / dive software certification
- Hardware-in-the-loop as a near-term gate
- Expanding experimental features (NN TCM, SLAM, swarm, ROS2) before the core nav APIs are stable
- Treating every research idea as a default import

## Feature promotion bar

A module moves from **Experimental → Beta** only when all of the following hold:

1. Beats a named baseline on a documented MC or stress scenario
2. Has tests that run in CI, or are marked `@slow` with a documented pod recipe
3. Is listed in [`MATURITY.md`](MATURITY.md) with an owner note
4. Is **not** required for `import charybdis` to succeed

**Beta → Stable** additionally requires: used by `Navigator` or the UUV core path, covariance/uncertainty exposed, and no known silent failure modes in the stress harness.

## Default import policy

```python
import charybdis                    # Stable / Beta nav + data APIs only
import charybdis.experimental       # NN matcher, SLAM, swarm (unstable)
```

## Related docs

- [`MATURITY.md`](MATURITY.md) — per-module maturity labels
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — package layout and stack split
