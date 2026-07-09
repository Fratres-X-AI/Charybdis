"""Audited integration loop for hybrid state estimation and patrol guidance."""

from __future__ import annotations

from dataclasses import dataclass

from numpy.typing import ArrayLike

from .fusion import HybridNavState, HybridSensorFusion
from .patrol import PatrolCommand, PatrolExecutor
from .sensors import SensorPacket


@dataclass(frozen=True)
class HybridStepResult:
    """Navigation estimate and guidance command produced by one sensor cycle."""

    state: HybridNavState
    command: PatrolCommand


class HybridNavigator:
    """Compose hybrid fusion and patrol in one deterministic integration point.

    The ordering is always sensor fusion first, then guidance from the resulting
    immutable navigation snapshot. This class intentionally does not implement
    mission planning, vehicle control, or a general autonomy state machine.
    """

    def __init__(
        self,
        fusion: HybridSensorFusion,
        patrol: PatrolExecutor,
    ) -> None:
        if not isinstance(fusion, HybridSensorFusion):
            raise TypeError("fusion must be HybridSensorFusion")
        if not isinstance(patrol, PatrolExecutor):
            raise TypeError("patrol must be PatrolExecutor")
        self._fusion = fusion
        self._patrol = patrol
        self._last_result: HybridStepResult | None = None

    @property
    def fusion(self) -> HybridSensorFusion:
        """Return the owned fusion component."""
        return self._fusion

    @property
    def patrol(self) -> PatrolExecutor:
        """Return the owned patrol component."""
        return self._patrol

    @property
    def last_result(self) -> HybridStepResult | None:
        """Return the most recent completed cycle."""
        return self._last_result

    def step(self, packet: SensorPacket) -> HybridStepResult:
        """Fuse one packet and generate guidance from the updated state."""
        state = self._fusion.step(packet)
        command = self._patrol.update(state)
        result = HybridStepResult(state=state, command=command)
        self._last_result = result
        return result

    def resume(
        self,
        pos: ArrayLike,
        *,
        vel: ArrayLike | None = None,
        pos_cov: ArrayLike | None = None,
        depth_m: float | None = None,
    ) -> HybridStepResult:
        """Re-anchor navigation and resume at the nearest route waypoint."""
        state = self._fusion.reset(
            pos,
            vel=vel,
            pos_cov=pos_cov,
            depth_m=depth_m,
        )
        self._patrol.resume(state.pos)
        command = self._patrol.update(state)
        result = HybridStepResult(state=state, command=command)
        self._last_result = result
        return result


__all__ = ["HybridNavigator", "HybridStepResult"]
