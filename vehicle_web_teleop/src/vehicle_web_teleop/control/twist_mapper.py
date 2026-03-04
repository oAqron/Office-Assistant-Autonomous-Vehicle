"""Twist pass-through / scaler for a holonomic (omnidirectional) platform.

The robot accepts independent vx / vy / vz commands directly, so no
differential-drive wheel splitting is needed.  TwistMapper exists as a
configurable scaling hook between the normalised [-1, 1] TwistCommand values
and the final floats forwarded to MotorBridge.

Scale factors default to 1.0 (identity); the per-axis gain applied at the
motor bridge level (vx_scale / vy_scale / vz_scale) handles unit conversion.

ROS 2 note: a ROS 2 node can set speed_scale < 1 here to apply a soft speed
cap before calling submit(), independent of the motor bridge's unit mapping.
"""

from __future__ import annotations

from ..safety.types import TwistCommand


class TwistMapper:
    """Scales all three TwistCommand axes by a single speed multiplier.

    Parameters
    ----------
    speed_scale:
        Global multiplier applied to all axes (0.0 – 1.0).  This acts as a
        soft speed cap layered on top of the safety-core clamp.  The web UI
        applies its own multiplier before sending, so this defaults to 1.0.
    """

    def __init__(self, speed_scale: float = 1.0) -> None:
        if not (0.0 < speed_scale <= 1.0):
            raise ValueError("speed_scale must be in (0.0, 1.0]")
        self._scale = speed_scale

    def map(self, cmd: TwistCommand) -> tuple[float, float, float]:
        """Return (vx, vy, vz) scaled to [-speed_scale, +speed_scale].

        Parameters
        ----------
        cmd:
            TwistCommand with all axes normalised to [-1.0, 1.0].

        Returns
        -------
        tuple[float, float, float]
            (linear_x, linear_y, angular_z) each in [-speed_scale, +speed_scale].
        """
        return (
            cmd.linear_x  * self._scale,
            cmd.linear_y  * self._scale,
            cmd.angular_z * self._scale,
        )

    @property
    def speed_scale(self) -> float:
        return self._scale

    @speed_scale.setter
    def speed_scale(self, value: float) -> None:
        if not (0.0 < value <= 1.0):
            raise ValueError("speed_scale must be in (0.0, 1.0]")
        self._scale = value
