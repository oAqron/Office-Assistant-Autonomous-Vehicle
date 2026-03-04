"""Async wrapper around a serial port (UART / RS485 / USB-serial).

Uses pyserial in a thread-pool executor so the asyncio event loop is never
blocked by serial I/O.  An asyncio.Lock serialises concurrent writes so that
back-to-back packets are never interleaved.

Default configuration matches the existing keyboard teleop script:
    port    = /dev/ttyTHS1   (Jetson Orin Nano hardware UART)
    baud    = 115200

Reconnect strategy
------------------
If the port disappears the next write attempt will try to reopen it once.
If that also fails the exception propagates to MotorBridge, which logs the
error and continues; the deadman watchdog will stop the motors within one
timeout period.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import serial

logger = logging.getLogger(__name__)

_BAUD_DEFAULT = 115_200
_TIMEOUT_S = 0.05          # read timeout (not used for writes, but needed by Serial ctor)


class RS485Port:
    """Async serial port with exclusive-access locking.

    Parameters
    ----------
    port:
        Device path, e.g. ``/dev/ttyUSB0`` or ``/dev/ttyTHS0``.
    baudrate:
        Should match Dynamixel firmware setting (default 3 Mbps as in the
        existing ``basic_packet.ino`` / ``Dynamixel_motor_packet.cpp``).
    """

    def __init__(
        self,
        port: str,
        baudrate: int = _BAUD_DEFAULT,
        timeout: float = _TIMEOUT_S,
    ) -> None:
        self._port_name = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._ser: Optional[serial.Serial] = None
        # asyncio.Lock: only one coroutine in write() at a time.
        self._bus_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        """Open the serial port (non-blocking via executor)."""
        loop = asyncio.get_running_loop()
        async with self._bus_lock:
            await loop.run_in_executor(None, self._open_sync)

    def _open_sync(self) -> None:
        if self._ser and self._ser.is_open:
            return
        self._ser = serial.Serial(
            port=self._port_name,
            baudrate=self._baudrate,
            timeout=self._timeout,
            write_timeout=0.1,
        )
        logger.info(
            "RS485 port %s opened at %d bps", self._port_name, self._baudrate
        )

    async def close(self) -> None:
        """Flush and close the port."""
        async with self._bus_lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
                logger.info("RS485 port %s closed", self._port_name)

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    async def write(self, data: bytes) -> None:
        """Write *data* to the bus; reconnects once on SerialException."""
        loop = asyncio.get_running_loop()
        async with self._bus_lock:
            await loop.run_in_executor(None, self._write_sync, data)

    def _write_sync(self, data: bytes) -> None:
        try:
            if not (self._ser and self._ser.is_open):
                logger.warning("Port not open; attempting reconnect")
                self._open_sync()
            self._ser.write(data)  # type: ignore[union-attr]
        except serial.SerialException:
            logger.exception("Serial write failed; attempting one reconnect")
            self._open_sync()
            self._ser.write(data)  # type: ignore[union-attr]

    async def read(self, n: int) -> bytes:
        """Read up to *n* bytes (subject to timeout)."""
        loop = asyncio.get_running_loop()
        async with self._bus_lock:
            return await loop.run_in_executor(None, self._ser.read, n)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return bool(self._ser and self._ser.is_open)

    @property
    def port_name(self) -> str:
        return self._port_name
