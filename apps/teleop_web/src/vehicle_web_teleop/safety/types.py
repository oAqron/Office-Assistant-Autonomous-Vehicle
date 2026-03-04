"""Shared data types for the vehicle teleop pipeline.

This robot is holonomic (omnidirectional) with three independent velocity axes,
matching the existing keyboard teleop convention:

    keyboard 'w'/'s' → vx (forward/back)
    keyboard 'a'/'d' → vy (strafe left/right)
    keyboard 'q'/'e' → vz (yaw CCW/CW)

ROS 2 note: TwistCommand maps to geometry_msgs/Twist with the convention
    linear_x  → Twist.linear.x   (multiply by physical max m/s)
    linear_y  → Twist.linear.y   (multiply by physical max m/s)
    angular_z → Twist.angular.z  (multiply by physical max rad/s)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto


@dataclass(frozen=True)
class TwistCommand:
    """Normalised velocity command in the vehicle body frame.

    All three axes are clamped to [-1.0, 1.0] by SafetyCore before being
    forwarded to the motor bridge.

    linear_x  : +1.0 = full forward,       -1.0 = full reverse
    linear_y  : +1.0 = full strafe-right,  -1.0 = full strafe-left
    angular_z : +1.0 = full rotate-CW,     -1.0 = full rotate-CCW
    timestamp : monotonic clock at creation (time.monotonic())
    """

    linear_x: float
    linear_y: float = 0.0
    angular_z: float = 0.0
    timestamp: float = field(default_factory=time.monotonic)

    def is_zero(self) -> bool:
        return self.linear_x == 0.0 and self.linear_y == 0.0 and self.angular_z == 0.0


# Singleton used by the safety watchdog to halt the vehicle.
STOP_COMMAND = TwistCommand(linear_x=0.0, linear_y=0.0, angular_z=0.0, timestamp=0.0)


class DriveMode(Enum):
    """Priority-ordered drive mode; higher value = higher priority."""
    IDLE = auto()       # no active controller
    WEB = auto()        # browser joystick (this package)
    ROS2 = auto()       # future: /cmd_vel subscriber
    ESTOP = auto()      # hard stop, overrides everything
