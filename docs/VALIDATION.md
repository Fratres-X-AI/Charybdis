# Validation

This document records the current reproducible checks. They cover software
tests, synthetic simulation, and synthetic matching against a real bathymetry
grid; they do not establish real-world performance, safety, or certification.

## Fast CI-equivalent checks

Run these commands from the repository root in a Linux shell. CI runs lint and
typing on Python 3.11, tests on Python 3.11 and 3.12, and packaging on Python
3.12.

Install the CI-constrained development environment:

```bash
python -m pip install --upgrade pip
python -m pip install -c requirements/ci.txt -e ".[dev]"
```

Run the source-quality gates exactly as CI does:

```bash
ruff check charybdis tests scripts examples run_sim.py
ruff format --check charybdis tests scripts examples run_sim.py
mypy charybdis/hybrid \
  charybdis/bathy.py \
  charybdis/simulation/hybrid.py \
  charybdis/evaluation/confidence.py \
  charybdis/evaluation/hybrid.py \
  charybdis/evaluation/scenarios.py \
  charybdis/evaluation/validation.py
```

Run the compile, architecture, test, and coverage gates:

```bash
python -m compileall -q charybdis console run_sim.py scripts
python -m pytest tests/test_architecture.py
for example in examples/*.py; do
  python "$example" >/dev/null
done
export MPLBACKEND=Agg
python -m pytest --timeout=120 --timeout-method=thread \
  -m "not console" --cov=charybdis --cov-report=term-missing \
  --cov-report=xml --cov-fail-under=80
coverage report --include="charybdis/hybrid/*" --fail-under=90
```

The package job builds the wheel with:

```bash
python -m pip install --upgrade pip
python -m pip install -c requirements/ci.txt build
python -m build
```

CI then verifies that `charybdis/py.typed` is present, no wheel member starts
with `console/`, and a clean virtual environment can import version `0.3.0` and
`HybridNavigator`.

The workflow definition in `.github/workflows/ci.yml` is authoritative if these
commands and CI ever differ.

## RunPod Phase 2

Phase 2 is a Linux-only, confidence-bounded validation workflow. It runs harbor
and deep seven-scenario synthetic matrices, characterizes the terrain matcher on a
projected GEBCO tile, runs the retained legacy stress harness, captures
dependency versions, and hashes the completed artifact set.

The official workflow requires:

- the repository at `/workspace/Charybdis`;
- an installed `/workspace/Charybdis/.venv`;
- a clean Git worktree;
- outbound access to the NOAA ERDDAP endpoint; and
- enough storage for the downloaded NetCDF file and generated artifacts.

From a prepared RunPod shell:

```bash
cd /workspace/Charybdis
bash scripts/pod/pod_hybrid_phase2.sh
```

The explicit defaults are:

```bash
cd /workspace/Charybdis
VALIDATION_WORKERS=31 \
ENGINEERING_RUNS=64 \
RELEASE_RUNS=256 \
LEGACY_STRESS_RUNS=64 \
SEEDS_FILE=validation/seeds_v1.txt \
bash scripts/pod/pod_hybrid_phase2.sh
```

The script rejects worker counts outside 1 through 31, matrix sizes outside 2
through 512, and legacy stress sizes outside 1 through 512. Overriding the run
counts produces a nonstandard tier and must be reported as such.

The shell wrapper activates `.venv`, sets `MPLBACKEND=Agg`, and limits OpenMP,
OpenBLAS, and MKL to one thread each. It creates:

```text
artifacts/validation/<UTC_STAMP>-<SHORT_SHA>/
```

before executing the following phases in order:

1. dependency freeze;
2. 64-run-per-scenario engineering matrix;
3. 256-run-per-scenario release matrix;
4. GEBCO download and projection;
5. 64-case and 256-case real-tile matcher characterization;
6. 64-seed legacy stress harness; and
7. SHA-256 inventory.

Because the wrapper uses `set -euo pipefail`, a blocking failure stops later
phases. A failed run can therefore leave a useful but incomplete artifact
directory without `SHA256SUMS`.

## Synthetic scenario matrices

The canonical matrix commands run by the wrapper are:

```bash
python scripts/hybrid_validate_matrix.py \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output-dir "artifacts/validation/<RUN>/engineering"

python scripts/hybrid_validate_matrix.py \
  --tier release \
  --runs 256 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output-dir "artifacts/validation/<RUN>/release"
```

`validation/seeds_v1.txt` is ordered. Each scenario in a tier uses the same
first `N` seeds, so the 64 engineering seeds are a subset of the 256 release
seeds; the tiers are not statistically independent.

`validation/seeds_holdout_v1.txt` is the frozen holdout set introduced after
the July 16 pod characterization. It is disjoint from `seeds_v1` and is reserved
for post-tuning confirmation runs, not parameter selection.

Both tiers run these seven named configurations:

- `harbor_nominal` — the default surface, dive, submerged patrol, and
  resurfacing route.
- `long_submerge` — a 480-step route with an extended submerged leg and depths
  up to 12 metres.
- `gps_dvl_dropout` — initial GPS dropout and a later DVL-style velocity
  dropout.
- `sparse_outlier_bathymetry` — less frequent profiles, a bathymetry outage,
  and three configured profile-distortion steps.
- `steady_current` — a constant horizontal current of `(0.25, -0.15)` m/s.
- `large_initial_error` — an initial horizontal offset of `(12, -8)` metres.
- `repeated_mode_transitions` — a 480-step route with repeated dives and
  resurfacings.

The canonical workload is 448 synthetic runs in the engineering matrix and
1,792 in the release matrix.

`hybrid_validate_matrix.py` refuses a dirty worktree unless called directly
with `--allow-dirty`. The pod wrapper never opts into dirty validation. Direct
smoke runs may select a subset with `--scenarios`, but they are not Phase 2
evidence. A directly supplied output directory must not already exist.

## Confidence-bounded synthetic gates

The matrix computes deterministic two-sided 95% intervals:

- Wilson score intervals for route completion, final health, and divergence
  rates;
- a 4,000-resample percentile bootstrap interval for the 95th percentile of
  final horizontal error; and
- a separately seeded 4,000-resample percentile bootstrap interval for the
  95th percentile of absolute final depth error.

The bootstrap seeds are fixed in source so repeated assessments of identical
samples produce identical bounds.

Every scenario checks the conservative interval endpoint:

- route-completion lower bound must be at least `0.90`;
- final-health lower bound must be at least `0.90`;
- divergence-rate upper bound must be at most `0.06`, where divergence means
  final horizontal error greater than 50 metres;
- horizontal CEP95 upper bound must not exceed the scenario threshold; and
- depth CEP95 upper bound must not exceed the scenario threshold.

Current horizontal/depth thresholds are:

- `harbor_nominal`: 10.0 m / 1.0 m;
- `long_submerge` and `steady_current`: 22.0 m / 1.5 m;
- `large_initial_error`: 18.0 m / 1.5 m; and
- `gps_dvl_dropout`, `sparse_outlier_bathymetry`, and
  `repeated_mode_transitions`: 25.0 m / 1.5 m.

The engineering tier always returns exit status zero after writing assessments,
even when a gate reports `FAIL`. The release tier returns status 2 when any
selected scenario fails, which makes the pod workflow stop.

`ValidationGates` also declares `max_gps_reacquisition_jump_m=12.0`. Each run
records the largest horizontal estimate jump on a GPS reacquisition step: a
cycle where GPS is present after at least one prior cycle without GPS and after
the mission's initial GPS acquisition. The release tier applies a deterministic
bootstrap upper bound to the 95th percentile of those per-run maxima and fails
when the bound exceeds 12.0 m.

Very small smoke samples are not substitutes for either tier. In particular,
wide Wilson intervals can make the rate gates fail even when every smoke case
completes successfully.

## Synthetic metrics

Each scenario artifact reports:

- `runs` and `seeds`;
- `cep50_m` and `cep95_m` for final horizontal error;
- `depth_cep95_m` for absolute final depth error;
- `route_completion_rate`;
- `healthy_rate` for final estimator health;
- `position_anees_mean` and `depth_anees_mean`;
- `divergence_rate_50m`;
- `fusion_rejections_total`;
- `gps_reacquisition_jump_cep95_m` and per-run `max_gps_reacquisition_jump_m`;
- wall-clock `runtime_s`;
- a `peak_rss_mib` resource-usage estimate when supported;
- declared gates; and
- the complete confidence-bound assessment.

CEP values summarize final error, not maximum error over the route.
`position_anees_mean` is the mean across runs of time-averaged 2D position NEES
divided by two; `depth_anees_mean` is the corresponding scalar depth value.
ANEES diagnoses model consistency and is not an accuracy metric by itself.

## GEBCO matcher characterization

The wrapper prepares its external tile with:

```bash
python scripts/prepare_gebco_tile.py \
  --output "artifacts/validation/<RUN>/real_bathymetry/gebco_monterey.npz" \
  --download "artifacts/validation/<RUN>/real_bathymetry/gebco_subset.nc"
```

By default this downloads a GEBCO 2020 subset for latitude 36.50–36.90 and
longitude -122.50–-122.10 through NOAA ERDDAP. The preparation script:

- hashes the downloaded bytes;
- converts longitude/latitude to a local metric approximation;
- interpolates to a square-cell grid;
- converts positive-up elevation to positive-down depth;
- rejects a tile that is less than 95% underwater; and
- writes the source URL, source hash, ranges, resolution, shape, depth range,
  and a navigation-use warning.

The `.npz` contains `depth_m`, `extent_m`, `source_url`, and `source_sha256`.
The adjacent `.json` is the human-readable source metadata.

The canonical characterization commands are:

```bash
python scripts/real_bathymetry_validate.py \
  --tile "artifacts/validation/<RUN>/real_bathymetry/gebco_monterey.npz" \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output "artifacts/validation/<RUN>/real_bathymetry/engineering.json"

python scripts/real_bathymetry_validate.py \
  --tile "artifacts/validation/<RUN>/real_bathymetry/gebco_monterey.npz" \
  --tier release \
  --runs 256 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output "artifacts/validation/<RUN>/real_bathymetry/release.json"
```

For each fixed seed, the characterization chooses a location with at least
2 metres of nine-point profile relief when possible, adds 0.75 m Gaussian depth
noise, offsets the prior by a two-cell standard deviation, and runs the profile
matcher. It reports match statuses and position error only for accepted fixes.

The real-tile checks require:

- the 95% Wilson lower bound on acceptance rate to be at least `0.70`; and
- the upper 95% bootstrap bound on accepted-fix CEP95 to be no more than
  `1.5 * map_resolution_m`.

As with the synthetic matrix, the engineering characterization records failure
but returns zero; the release characterization returns status 2 on failure.

This is real-map characterization, not real-world navigation validation. The
vehicle position, observed profiles, prior error, and sensor noise are
synthetic. The generated metadata explicitly warns that the GEBCO data is not
for navigation or safety-at-sea use.

For integration-grade bathymetry claims, run the same script with
`--require-integration-grade-map`. That option rejects tiles coarser than
50 metres per cell before running matcher statistics. The default GEBCO subset is
coarse characterization only and is expected to record
`resolution_class="coarse_characterization"`.

## Legacy stress phase

The wrapper also runs:

```bash
python scripts/stress_run.py 64 \
  | tee "artifacts/validation/<RUN>/legacy_stress.log"
```

This exercises retained legacy terrain-aided stress cases using seeds 1 through 64 and
a hard-coded maximum of 31 workers. It is separate from the hybrid matrices and
does not use `validation/seeds_v1.txt`.

## Artifact layout and provenance

A completed default run contains:

```text
artifacts/validation/<UTC_STAMP>-<SHORT_SHA>/
  requirements-freeze.txt
  engineering/
    harbor_nominal.json
    long_submerge.json
    gps_dvl_dropout.json
    sparse_outlier_bathymetry.json
    steady_current.json
    large_initial_error.json
    repeated_mode_transitions.json
    matrix_summary.json
    REPORT.md
  release/
    <the same scenario artifacts>
    matrix_summary.json
    REPORT.md
  real_bathymetry/
    gebco_subset.nc
    gebco_monterey.npz
    gebco_monterey.json
    engineering.json
    engineering.md
    release.json
    release.md
  legacy_stress.log
  SHA256SUMS
```

Each synthetic scenario artifact carries top-level `schema_version="1"`.
Each synthetic scenario manifest records the full Git SHA, ordered seeds, worker
count, scenario, UTC creation time, package/Python/NumPy/platform versions,
tier, dirty-worktree flag, seed-file path, synthetic-map SHA-256, and the fully
serialized scenario configuration.

`matrix_summary.json` also carries top-level `schema_version="1"` and records
tier-level outcomes and artifact names; `REPORT.md` provides a concise readable
summary. The root dependency freeze and `SHA256SUMS` cover the generated JSON,
reports, real-bathymetry source and tile, legacy log, and dependency list.

The real-bathymetry result separately records Git SHA, tier, seeds, worker
count, tile path and SHA-256, map shape, map resolution, resolution class, and
whether integration-grade map resolution was required. Source URL and download
hash remain in the tile and its metadata sidecar.

Retain the entire artifact directory, source revision, pod or container image
identity, and hardware details. The generated metadata does not identify the
container image or hardware.

## Worker policy

Standalone validation uses at most 31 worker processes:

- the pod wrapper rejects `VALIDATION_WORKERS` outside 1 through 31;
- both matrix scripts reject `--workers` outside 1 through 31;
- `charybdis.parallel.pool_workers()` caps hybrid Monte Carlo at 31;
- hybrid Monte Carlo invoked inside pytest or pytest-xdist is forced to one
  process; and
- the standalone legacy stress runner requests exactly 31 workers.

Do not nest a validation process pool under pytest-xdist. Thread-limited BLAS
settings reduce, but do not prove the absence of all runtime oversubscription.

## Limitations

- The seven scenario matrices use synthetic maps, vehicle dynamics, sensor
  errors, currents, outages, and outliers. They are regression evidence for
  those models only.
- The GEBCO phase uses a real bathymetry grid but synthesizes every matcher
  observation and prior. It is neither a sea trial nor independent validation.
- Confidence bounds quantify sampling uncertainty within the fixed seed set;
  they do not make the seed set or modeled faults representative of deployment.
- The engineering and release tiers share seeds, models, implementation, and
  gates. The frozen holdout seed set provides a post-tuning regression check,
  but it is still synthetic and does not replace an external reference estimator.
- The interval checks do not correct for multiple comparisons across scenarios
  and metrics.
- Aggregate artifacts omit per-step trajectories and most per-run values,
  limiting retrospective analysis.
- Direct real-bathymetry runs do not reject a dirty worktree; the official
  wrapper relies on the preceding matrix clean-worktree check.
- Floating-point, SciPy interpolation, and multiprocessing details can produce
  platform-dependent differences.
- An internal release-tier `PASS` is not an operational acceptance, safety
  case, regulatory approval, real-world validation, or certification.
- Navigation-health flags and guidance holds are software diagnostics, not a
  complete safety mechanism.

Any reported result must identify the artifact directory, source revision,
tier, scenario or tile, seeds, run counts, worker count, code modifications,
and these limitations.

## Remote GPU validation (optional)

For optional NN matcher retraining on cloud GPUs, see
[`REMOTE_VALIDATION.md`](REMOTE_VALIDATION.md). Release-tier CPU gates do not
require additional GPU spend. Verify a local pull with:

```bash
bash scripts/pod/verify_release_cpu.sh
```

An optional full profile also checks GPU training completion and regional GEBCO
characterization when a remote instance is active.
