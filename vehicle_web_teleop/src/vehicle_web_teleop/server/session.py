"""Controller session: exclusive lock + heartbeat tracking.

Only one WebSocket client at a time may hold the controller lock.  All other
clients can connect and observe status messages, but their cmd_vel packets are
silently ignored by ws_server.py.

Lock lifetime
-------------
* Acquired explicitly via ``{"type": "acquire_lock"}``
* Released explicitly via ``{"type": "release_lock"}``
* Auto-released after ``heartbeat_timeout_s`` without a ``{"type": "ping"}``
* Auto-released on WebSocket disconnect (ws_server calls ``release()``)

This means a client that crashes hard (network loss) will drop its lock within
``heartbeat_timeout_s`` seconds, allowing another client to take over.

Thread / task safety
--------------------
All public methods are synchronous and guarded by a threading.Lock so they are
safe to call from any asyncio task or from the aiohttp request handler directly.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_HEARTBEAT_TIMEOUT_S = 5.0


class ControllerSession:
    """Manages the exclusive controller lock.

    Parameters
    ----------
    heartbeat_timeout_s:
        If the lock holder does not send a ``ping`` within this window the lock
        is force-released on the next ``is_expired()`` check (polled by the
        watchdog in ``ws_server.py``).
    """

    def __init__(self, heartbeat_timeout_s: float = _DEFAULT_HEARTBEAT_TIMEOUT_S) -> None:
        self._timeout = heartbeat_timeout_s
        self._client_id: Optional[str] = None
        self._last_heartbeat: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lock management
    # ------------------------------------------------------------------

    def try_acquire(self, client_id: str) -> bool:
        """Attempt to acquire the lock for *client_id*.

        Returns True on success; False if another client already holds it.
        """
        with self._lock:
            if self._client_id is not None and self._client_id != client_id:
                logger.debug(
                    "Lock denied for %s – already held by %s", client_id, self._client_id
                )
                return False
            self._client_id = client_id
            self._last_heartbeat = time.monotonic()
            logger.info("Lock acquired by %s", client_id)
            return True

    def release(self, client_id: str) -> bool:
        """Release the lock if *client_id* currently holds it.

        Returns True if the lock was actually released.
        """
        with self._lock:
            if self._client_id != client_id:
                return False
            self._client_id = None
            self._last_heartbeat = 0.0
            logger.info("Lock released by %s", client_id)
            return True

    def force_release(self) -> Optional[str]:
        """Unconditionally release the lock.

        Returns the client_id that was evicted, or None if no lock was held.
        """
        with self._lock:
            evicted = self._client_id
            self._client_id = None
            self._last_heartbeat = 0.0
            if evicted:
                logger.warning("Lock force-released (was held by %s)", evicted)
            return evicted

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def refresh_heartbeat(self, client_id: str) -> bool:
        """Reset the heartbeat timer for *client_id*.

        Returns True if client is the current lock holder (heartbeat accepted),
        False otherwise.
        """
        with self._lock:
            if self._client_id != client_id:
                return False
            self._last_heartbeat = time.monotonic()
            return True

    def is_expired(self) -> bool:
        """Return True if the lock holder has not pinged within the timeout."""
        with self._lock:
            if self._client_id is None:
                return False
            return (time.monotonic() - self._last_heartbeat) > self._timeout

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_controller(self, client_id: str) -> bool:
        with self._lock:
            return self._client_id == client_id

    @property
    def controller_id(self) -> Optional[str]:
        with self._lock:
            return self._client_id

    @property
    def is_locked(self) -> bool:
        with self._lock:
            return self._client_id is not None

    def status_dict(self) -> dict:
        """Serialisable snapshot for broadcasting to all clients."""
        with self._lock:
            return {
                "type": "lock_status",
                "locked": self._client_id is not None,
                "controller_id": self._client_id,
            }

    # ------------------------------------------------------------------
    # Client ID factory
    # ------------------------------------------------------------------

    @staticmethod
    def new_client_id() -> str:
        return str(uuid.uuid4())
