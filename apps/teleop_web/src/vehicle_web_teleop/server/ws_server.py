"""WebSocket endpoint: receives Twist commands, enforces session lock.

Message protocol (client → server, JSON)
-----------------------------------------
    {"type": "acquire_lock"}
        Request the exclusive controller lock.

    {"type": "release_lock"}
        Voluntarily release the lock.

    {"type": "cmd_vel", "linear_x": <float>, "linear_y": <float>, "angular_z": <float>}
        Velocity command; only processed for the lock holder.
        All axes normalised to [-1.0, 1.0].  Resets the deadman timer.
        linear_x  : forward / reverse
        linear_y  : strafe right (+) / left (-)
        angular_z : rotate CW (+) / CCW (-)

    {"type": "ping"}
        Heartbeat; resets the session heartbeat timer (keeps lock alive).

    {"type": "estop"}
        Emergency stop; any client may send this regardless of lock.

    {"type": "clear_estop"}
        Clear ESTOP; only the lock holder may do this.

Message protocol (server → client, JSON)
-----------------------------------------
    {"type": "assigned_id", "client_id": "<uuid>"}
        Sent once on connect.

    {"type": "lock_status", "locked": <bool>, "controller_id": "<uuid>|null>"}
        Broadcast to ALL clients on any lock-state change.

    {"type": "lock_acquired", "client_id": "<uuid>"}
        Sent to the client that just acquired the lock.

    {"type": "lock_denied", "reason": "<string>"}
        Sent to the client whose acquire_lock was rejected.

    {"type": "lock_released", "client_id": "<uuid>"}
        Broadcast when the lock is released (voluntarily or by timeout).

    {"type": "pong"}
        Response to a ping.

    {"type": "estop_activated"}
        Broadcast to all clients.

    {"type": "error", "message": "<string>"}
        Malformed message or internal error.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from aiohttp import WSMsgType, web

from ..safety.types import DriveMode, TwistCommand

if TYPE_CHECKING:
    from ..safety.safety_core import SafetyCore
    from .session import ControllerSession

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """aiohttp WebSocket handler (not a class-based view, just a callable).

    Attach with::

        app.router.add_get("/ws", ws_handler.handle)
    """

    def __init__(self, safety: SafetyCore, session: ControllerSession) -> None:
        self._safety = safety
        self._session = session
        # Active WebSocket connections keyed by client_id.
        self._connections: dict[str, web.WebSocketResponse] = {}
        self._conn_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # aiohttp request handler
    # ------------------------------------------------------------------

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=10.0)
        await ws.prepare(request)

        client_id = self._session.new_client_id()
        async with self._conn_lock:
            self._connections[client_id] = ws

        logger.info("WebSocket connected: %s  (%s)", client_id, request.remote)

        # Identify the new client and broadcast current lock state.
        await ws.send_json({"type": "assigned_id", "client_id": client_id})
        await ws.send_json(self._session.status_dict())

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._dispatch(client_id, ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.warning("WS error from %s: %s", client_id, ws.exception())
                    break
        finally:
            await self._on_disconnect(client_id)

        return ws

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, client_id: str, ws: web.WebSocketResponse, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send_json({"type": "error", "message": "invalid JSON"})
            return

        msg_type = msg.get("type", "")

        if msg_type == "acquire_lock":
            await self._handle_acquire(client_id, ws)

        elif msg_type == "release_lock":
            await self._handle_release(client_id)

        elif msg_type == "cmd_vel":
            await self._handle_cmd_vel(client_id, msg)

        elif msg_type == "ping":
            self._session.refresh_heartbeat(client_id)
            await ws.send_json({"type": "pong"})

        elif msg_type == "estop":
            await self._safety.emergency_stop()
            await self._broadcast({"type": "estop_activated", "triggered_by": client_id})
            logger.warning("ESTOP triggered by client %s", client_id)

        elif msg_type == "clear_estop":
            if self._session.is_controller(client_id):
                await self._safety.clear_estop()
                await self._broadcast({"type": "estop_cleared", "cleared_by": client_id})
            else:
                await ws.send_json({"type": "error", "message": "only lock holder can clear ESTOP"})

        else:
            await ws.send_json({"type": "error", "message": f"unknown type: {msg_type!r}"})

    # ------------------------------------------------------------------
    # Lock handlers
    # ------------------------------------------------------------------

    async def _handle_acquire(self, client_id: str, ws: web.WebSocketResponse) -> None:
        if self._session.try_acquire(client_id):
            await ws.send_json({"type": "lock_acquired", "client_id": client_id})
            await self._broadcast(self._session.status_dict())
        else:
            await ws.send_json({
                "type": "lock_denied",
                "reason": f"locked by {self._session.controller_id}",
            })

    async def _handle_release(self, client_id: str) -> None:
        released = self._session.release(client_id)
        if released:
            await self._safety.release_mode(DriveMode.WEB)
            await self._broadcast({
                "type": "lock_released",
                "client_id": client_id,
            })
            await self._broadcast(self._session.status_dict())

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    async def _handle_cmd_vel(self, client_id: str, msg: dict) -> None:
        if not self._session.is_controller(client_id):
            return  # silently ignore non-controller commands

        try:
            cmd = TwistCommand(
                linear_x=float(msg["linear_x"]),
                linear_y=float(msg.get("linear_y", 0.0)),
                angular_z=float(msg.get("angular_z", 0.0)),
            )
        except (KeyError, TypeError, ValueError):
            ws = self._connections.get(client_id)
            if ws:
                await ws.send_json({"type": "error", "message": "malformed cmd_vel"})
            return

        await self._safety.submit(cmd, DriveMode.WEB)

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    async def _on_disconnect(self, client_id: str) -> None:
        async with self._conn_lock:
            self._connections.pop(client_id, None)

        was_controller = self._session.release(client_id)
        if was_controller:
            # Stop-on-drop: immediately halt motors when lock holder disconnects.
            await self._safety.release_mode(DriveMode.WEB)
            await self._broadcast({
                "type": "lock_released",
                "client_id": client_id,
                "reason": "disconnect",
            })
            await self._broadcast(self._session.status_dict())
            logger.info("Lock holder %s disconnected – motors stopped", client_id)
        else:
            logger.info("Observer %s disconnected", client_id)

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    async def _broadcast(self, payload: dict) -> None:
        """Send *payload* to every connected client."""
        text = json.dumps(payload)
        async with self._conn_lock:
            targets = list(self._connections.values())
        for ws in targets:
            try:
                await ws.send_str(text)
            except Exception:
                pass  # ignore closed connections; they'll clean up in _on_disconnect

    # ------------------------------------------------------------------
    # Heartbeat watchdog (polled by main.py)
    # ------------------------------------------------------------------

    async def run_heartbeat_watchdog(self, poll_s: float = 2.0) -> None:
        """Background task: force-release expired locks."""
        while True:
            await asyncio.sleep(poll_s)
            if self._session.is_expired():
                evicted = self._session.force_release()
                if evicted:
                    await self._safety.release_mode(DriveMode.WEB)
                    await self._broadcast({
                        "type": "lock_released",
                        "client_id": evicted,
                        "reason": "heartbeat_timeout",
                    })
                    await self._broadcast(self._session.status_dict())
                    logger.warning("Session %s evicted due to heartbeat timeout", evicted)
