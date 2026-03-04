"""Motor bridge: translates TwistCommand into the robot's native serial packet.

Packet format — mirrors the existing keyboard teleop script exactly:

    Header  : 3E 01 09         (3 bytes, fixed)
    vx      : struct.pack('>h', int(linear_x  * vx_scale))   (2 bytes, big-endian int16)
    vy      : struct.pack('>h', int(linear_y  * vy_scale))   (2 bytes, big-endian int16)
    vz      : struct.pack('>h', int(angular_z * vz_scale))   (2 bytes, big-endian int16)
    Total   : 9 bytes

Default scale factors (matching the original script at gain g = 1.0):
    vx_scale = 100   ← original:  1.0  * g * 100
    vy_scale = 100   ← original:  1.0  * g * 100
    vz_scale = 500   ← original:  5.0  * g * 100  (5× multiplier for yaw)

Keyword convention (from sample code):
    'w'/'s' → ±vx  (forward / reverse)
    'a'/'d' → ∓vy  (strafe: 'a' = vy negative, 'd' = vy positive)
    'q'/'e' → ∓vz  (yaw:    'q' = vz negative, 'e' = vz positive)
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from ..safety.types import TwistCommand

if TYPE_CHECKING:
    from .rs485_port import RS485Port

logger = logging.getLogger(__name__)

# ── Packet constants ──────────────────────────────────────────────────────────
_HEADER = bytes.fromhex('3E0109')

# ── Default scale factors ─────────────────────────────────────────────────────
_VX_SCALE_DEFAULT = 100    # linear forward/reverse
_VY_SCALE_DEFAULT = 100    # linear strafe
_VZ_SCALE_DEFAULT = 500    # angular yaw (5× factor from original script)

# ── int16 clamp bounds ────────────────────────────────────────────────────────
_INT16_MAX =  32767
_INT16_MIN = -32768


class MotorBridge:
    """Translates TwistCommand floats into the robot's 9-byte velocity packet.

    Parameters
    ----------
    port:
        An open :class:`RS485Port` instance.
    vx_scale:
        Multiplier applied to ``TwistCommand.linear_x`` before int16 packing.
        Default 100 matches the original script at gain g = 1.0.
    vy_scale:
        Multiplier applied to ``TwistCommand.linear_y`` (strafe).
    vz_scale:
        Multiplier applied to ``TwistCommand.angular_z`` (yaw).
        Default 500 (= 5 × 100) matches the original q/e rotation multiplier.
    """

    def __init__(
        self,
        port: RS485Port,
        vx_scale: float = _VX_SCALE_DEFAULT,
        vy_scale: float = _VY_SCALE_DEFAULT,
        vz_scale: float = _VZ_SCALE_DEFAULT,
    ) -> None:
        self._port = port
        self._vx_scale = vx_scale
        self._vy_scale = vy_scale
        self._vz_scale = vz_scale

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_twist(self, cmd: TwistCommand) -> None:
        """Pack and send a single velocity packet for all three axes."""
        packet = _assemble_packet(
            int(_clamp_int16(cmd.linear_x  * self._vx_scale)),
            int(_clamp_int16(cmd.linear_y  * self._vy_scale)),
            int(_clamp_int16(cmd.angular_z * self._vz_scale)),
        )
        logger.debug(
            "send_twist  lx=%.3f ly=%.3f az=%.3f  → %s",
            cmd.linear_x, cmd.linear_y, cmd.angular_z, packet.hex(),
        )
        await self._port.write(packet)

    async def send_stop(self) -> None:
        """Send zero velocity on all axes (immediate halt)."""
        packet = _assemble_packet(0, 0, 0)
        await self._port.write(packet)
        logger.debug("send_stop: %s", packet.hex())


# ── Module-level pure functions (easy to unit-test) ───────────────────────────

def _assemble_packet(vx: int, vy: int, vz: int) -> bytes:
    """Build the 9-byte velocity packet.

    Directly mirrors the original script::

        packet = bytearray.fromhex('3E 01 09')
        packet.extend(struct.pack('>h', vx))
        packet.extend(struct.pack('>h', vy))
        packet.extend(struct.pack('>h', vz))
    """
    return _HEADER + struct.pack('>hhh', vx, vy, vz)


def _clamp_int16(value: float) -> float:
    """Clamp to signed int16 range before struct.pack (avoids OverflowError)."""
    return max(_INT16_MIN, min(_INT16_MAX, value))
