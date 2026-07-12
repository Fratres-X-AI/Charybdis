# Changelog

Material user-facing changes are recorded here. This project uses semantic
versioning where practical, but research interfaces marked beta or experimental
may change before the next major release.

## Unreleased

### Validation

- Enforced GPS reacquisition jump as a blocking release gate with per-run metrics
  and bootstrap assessment in Phase 2 matrices.
- Pod sprint scripts for private-repo sync, 45s polling, and artifact fetch.

### Documentation

- Added repository hero image and validation snapshot to the README.

### Documentation (earlier)

- Defined the hybrid-only root API and explicit legacy/experimental boundaries.
- Documented the wheel exclusion for the paused console.
- Added reproducible fast-CI and RunPod Phase 2 procedures, metrics, confidence
  gates, artifact provenance, worker limits, and non-certification limitations.

### Validation

- Added seven-scenario engineering and release matrices with canonical 64-run
  and 256-run-per-scenario tiers.
- Added deterministic Wilson and bootstrap confidence bounds for synthetic
  completion, health, divergence, horizontal-error, and depth-error gates.
- Added provenance-tracked GEBCO 2020 tile preparation and fixed-seed
  terrain-matcher characterization.
- Added matrix reports, dependency capture, real-bathymetry reports, legacy
  stress output, and a SHA-256 artifact inventory.

### Examples

- Added production-oriented `HybridNavigator` integration wiring.
- Added terrain-profile matching and degraded-sensor examples.
- Added an explicit `charybdis.legacy` usage example.

## Historical releases

Release history before this changelog was introduced has not been reconstructed.
Use repository tags and their source revisions when auditing earlier builds.
