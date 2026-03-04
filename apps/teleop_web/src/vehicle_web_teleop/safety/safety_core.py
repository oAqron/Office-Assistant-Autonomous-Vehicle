"""Safety core: deadman watchdog, velocity clamping, mode arbitration.

Design rules
------------
* Only ONE asyncio task (``_watchdog``) reads ``_last_cmd_time``.
* ``submit()`` is the sole write path for incoming commands.
* ``emergency_stop()`` sets ESTOP mode; only ``clear_estop()`` can lift it.
* Motor bridge is injected so this module has zero import-time side-effects
  (easy to unit-test and to swap in a ROS 2 node later).

ROS 2 integration point
-----------------------
Create a SafetyCore in the ROS 2 node constructor, subscribe to /cmd_vel and
call ``asyncio.run_coroutine_threadsafe(core.submit(cmd), loop)`` from the
subscription callback.  Nothing else needs to change.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from .types import STOP_COMMAND, DriveMode, TwistCommand

if TYPE_CHECKING:
    from ..motor.bridge import MotorBridge

logger = logging.getLogger(__name__)

_DEFAULT_DEADMAN_S = 0.5


class SafetyCore:
    """Enforces deadman timeout, velocity clamping, and mode arbitration.

    Usage::

        core = SafetyCore(bridge, deadman_s=0.5)
        await core.start()          # begins background watchdog
        await core.submit(cmd)      # call from ws_server on each message
        await core.stop()           # clean shutdown
    """

    def __init__(self, bridge: MotorBridge, deadman_s: float = _DEFAULT_DEADMAN_S) -> None:
        self._bridge = bridge
        self._deadman_s = deadman_s
        self._last_cmd_time: float = 0.0
        self._mode: DriveMode = DriveMode.IDLE
        self._watchdog_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background deadman watchdog."""
        self._running = True
        self._watchdog_task = asyncio.create_task(self._watchdog(), name="safety-watchdog")
        logger.info("SafetyCore started (deadman=%.3f s)", self._deadman_s)

    async def stop(self) -> None:
        """Halt motors and cancel the watchdog."""
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        await self._bridge.send_stop()
        logger.info("SafetyCore stopped")

    # ------------------------------------------------------------------
    # Command path
    # ------------------------------------------------------------------

    async def submit(self, cmd: TwistCommand, mode: DriveMode = DriveMode.WEB) -> bool:
        """Accept a TwistCommand if the mode is allowed.

        Returns True if the command was forwarded to the bridge, False if it
        was suppressed (wrong mode or ESTOP active).
        """
        async with self._lock:
            if self._mode is DriveMode.ESTOP:
                logger.debug("submit() rejected – ESTOP active")
                return False

            # Mode arbitration: only allow if incoming mode >= current mode,
            # or if transitioning from IDLE.
            if mode.value < self._mode.value and self._mode is not DriveMode.IDLE:
                logger.debug(
                    "submit() rejected – mode %s < active mode %s", mode, self._mode
                )
                return False

            self._mode = mode
            self._last_cmd_time = time.monotonic()

        clamped = _clamp_twist(cmd)
        await self._bridge.send_twist(clamped)
        return True

    async def emergency_stop(self) -> None:
        """Immediately halt motors and lock out all commands."""
        async with self._lock:
            self._mode = DriveMode.ESTOP
        await self._bridge.send_stop()
        logger.warning("ESTOP activated")

    async def clear_estop(self) -> None:
        """Release ESTOP and return to IDLE (ready for new commands)."""
        async with self._lock:
            if self._mode is DriveMode.ESTOP:
                self._mode = DriveMode.IDLE
                self._last_cmd_time = 0.0
        logger.info("ESTOP cleared")

    async def release_mode(self, mode: DriveMode) -> None:
        """Called when a controller (e.g. WebSocket client) disconnects."""
        async with self._lock:
            if self._mode is mode:
                self._mode = DriveMode.IDLE
                self._last_cmd_time = 0.0
        await self._bridge.send_stop()

    @property
    def mode(self) -> DriveMode:
        return self._mode

    # ------------------------------------------------------------------
    # Background watchdog
    # ------------------------------------------------------------------

    async def _watchdog(self) -> None:
        """Polls at half the deadman period; stops motors on timeout."""
        poll_s = self._deadman_s / 2.0
        while self._running:
            await asyncio.sleep(poll_s)
            async with self._lock:
                if self._mode not in (DriveMode.IDLE, DriveMode.ESTOP):
                    age = time.monotonic() - self._last_cmd_time
                    if age > self._deadman_s:
                        logger.warning(
                            "Deadman triggered after %.3f s – stopping motors", age
                        )
                        self._mode = DriveMode.IDLE
                        self._last_cmd_time = 0.0
                        # Schedule stop outside the lock to avoid blocking.
                        asyncio.create_task(self._bridge.send_stop())


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _clamp_twist(cmd: TwistCommand) -> TwistCommand:
    return TwistCommand(
        linear_x=_clamp(cmd.linear_x),
        linear_y=_clamp(cmd.linear_y),
        angular_z=_clamp(cmd.angular_z),
        timestamp=cmd.timestamp,
    )
