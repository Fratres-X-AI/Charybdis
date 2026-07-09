# Contributing

Charybdis is proprietary and confidential. Contributions are accepted only
from people authorized by Fratres-X-AI. Access to source code does not grant
permission to use or distribute it; see [`LICENSE`](LICENSE).

## Development setup

Use Python 3.11 or newer in an isolated environment:

```bash
python -m pip install -c requirements/ci.txt -e ".[dev]"
```

Keep generated caches, local artifacts, model experiments, credentials, and
large validation logs out of changes unless a maintainer explicitly requests
them.

## Architecture rules

- New surface/submerged work belongs in `charybdis.hybrid`.
- The package root exports only the curated hybrid API.
- Legacy interceptor work must remain under `charybdis.legacy`.
- Unstable NN, SLAM, and swarm work must remain under
  `charybdis.experimental`.
- `charybdis.hybrid` must not depend on legacy, experimental, console, or
  optional deep-learning code.
- The repository-level `console/` source must remain outside the wheel.
- Public integration boundaries should use immutable measurements, state
  snapshots, explicit covariance, and visible failure diagnostics.

Discuss an API-boundary or estimator-state change before implementing it.

## Change workflow

1. Start from the current integration branch and keep the change focused.
2. Add or update tests for nominal and failure behavior.
3. Update examples and maturity/validation documentation when contracts or
   evidence change.
4. Run the checks in [`docs/VALIDATION.md`](docs/VALIDATION.md).
5. Submit a reviewable change description covering intent, risk, test evidence,
   compatibility, and known limitations.

Do not weaken gates, suppress warnings, or broaden package exports merely to
make a check pass.

## Validation contributions

Record the source revision, complete seed set, scenario, configuration,
dependency or image identity, worker count, and artifact path. Standalone Monte
Carlo is limited to 31 workers and must not be nested under pytest-xdist.

Synthetic results must be labeled synthetic. Do not describe simulation,
fixed-seed regression, or internal testing as sea-trial evidence, operational
validation, certification, or a safety guarantee.

## Data and security

Do not commit secrets, private keys, access tokens, pod credentials, controlled
technical data, real mission details, or third-party datasets without explicit
authorization and provenance review. Use synthetic or approved sanitized data
in tests and examples.

Report suspected vulnerabilities privately as described in
[`SECURITY.md`](SECURITY.md).
