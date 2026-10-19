# Legacy terrain-aided navigation (regression stack)

This package contains Charybdis's original GPS-denied **terrain-aided navigation**
research stack: TERCOM, EKF, particle-filter, point-mass-filter, and
coordination logic. It uses a **synthetic altimeter chain** (barometric MSL +
radar AGL over a terrain DEM) for simulation and filter comparison.

It is **not** the product architecture for surface/submerged UUV work. That path
is [`charybdis.hybrid`](../hybrid/) with bathymetry maps, depth/DVL aiding, and
patrol guidance.

The code remains maintained for backward compatibility, regression testing, and
Monte Carlo evaluation. Do not describe this stack as a weapon or interceptor
system; it is offline navigation research software.

See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) for stack comparison,
state definitions, and import guidance.
