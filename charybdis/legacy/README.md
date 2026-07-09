# Legacy Interceptor Navigation

This package contains Charybdis's original GPS-denied interceptor navigation
stack: TERCOM, EKF, particle-filter, point-mass-filter, and coordination logic.

The code remains maintained for backward compatibility, regression testing, and
Monte Carlo evaluation. It is not the active development path for harbor UUV
navigation.

Use [`charybdis.hybrid`](../hybrid/) for new surface/submerged UUV fusion and
patrol work.

See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) for the stack comparison,
state definitions, and import guidance.
