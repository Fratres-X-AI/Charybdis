# Experimental Modules

This package contains opt-in research prototypes with unstable APIs:

- `slam.py` — bathymetric submap alignment and pose-graph optimization
- `swarm.py` — cooperative navigation using acoustic range sharing
- `nn_matcher.py` — learned terrain matching; requires the `nn` extra (PyTorch)

These modules are not imported by the top-level `charybdis` API and must not be
used from production navigation paths. Import them explicitly:

```python
from charybdis.experimental import init_slam, run_swarm
from charybdis.experimental.nn_matcher import match_position
```

Promotion into the supported API requires stable interfaces, dedicated
validation, and documentation in the main architecture guide.
