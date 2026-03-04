"""Entry point: assembles all components and starts the aiohttp server.

Configuration is read from environment variables (see README.md for the full
table).  All defaults are chosen so that ``python -m vehicle_web_teleop.main``
works out-of-the-box for local development without a real serial port
(serial errors are logged but the server still starts).

Startup order
-------------
1. Parse config from environment.
2. Open RS485 port (best-effort; continues if unavailable).
3. Build MotorBridge → SafetyCore.
4. Build ControllerSession + WebSocketHandler.
5. Register routes (WS + static HTTP).
6. Start background tasks (safety watchdog, session heartbeat watchdog).
7. Run aiohttp runner until SIGINT/SIGTERM.
8. Graceful shutdown: stop SafetyCore (halts motors), close serial port.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

from aiohttp import web

from .motor.bridge import MotorBridge
from .motor.rs485_port import RS485Port
from .safety.safety_core import SafetyCore
from .server.http_server import add_static_routes
from .server.session import ControllerSession
from .server.ws_server import WebSocketHandler

logger = logging.getLogger(__name__)

# ── Web/ directory is two levels up from this file (src/vehicle_web_teleop/) ─
SUBPROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../apps/teleop_web
_WEB_ROOT = SUBPROJECT_ROOT / "web"

def _cfg(key: str, default: str) -> str:
    return os.environ.get(key, default)


def build_app() -> tuple[web.Application, SafetyCore, RS485Port]:
    """Construct and wire all components; return (app, safety, port)."""

    # ── Config ────────────────────────────────────────────────────────────────
    # Defaults match the existing keyboard teleop script:
    #   port=/dev/ttyTHS1 @ 115200, vx/vy scale=100, vz scale=500
    serial_port = _cfg("VWT_SERIAL_PORT", "/dev/ttyTHS1")
    baudrate    = int(_cfg("VWT_BAUD",        "115200"))
    deadman_ms  = int(_cfg("VWT_DEADMAN_MS",  "500"))
    hb_timeout  = float(_cfg("VWT_HB_TIMEOUT_S", "5.0"))
    vx_scale    = float(_cfg("VWT_VX_SCALE",  "100"))   # forward/reverse
    vy_scale    = float(_cfg("VWT_VY_SCALE",  "100"))   # strafe
    vz_scale    = float(_cfg("VWT_VZ_SCALE",  "500"))   # yaw (5× factor)

    # ── Motor stack ──────────────────────────────────────────────────────────
    port   = RS485Port(serial_port, baudrate=baudrate)
    bridge = MotorBridge(port, vx_scale=vx_scale, vy_scale=vy_scale, vz_scale=vz_scale)
    safety = SafetyCore(bridge, deadman_s=deadman_ms / 1000.0)

    # ── Session + WebSocket ───────────────────────────────────────────────────
    session    = ControllerSession(heartbeat_timeout_s=hb_timeout)
    ws_handler = WebSocketHandler(safety, session)

    # ── aiohttp application ───────────────────────────────────────────────────
    app = web.Application()
    app["ws_handler"] = ws_handler
    app["safety"]     = safety
    app["port"]       = port

    app.router.add_get("/ws", ws_handler.handle)
    add_static_routes(app, _WEB_ROOT)

    # ── Startup / shutdown hooks ──────────────────────────────────────────────
    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)

    return app, safety, port


# ── aiohttp lifecycle hooks ────────────────────────────────────────────────────

async def _on_startup(app: web.Application) -> None:
    port: RS485Port    = app["port"]
    safety: SafetyCore = app["safety"]
    ws_handler: WebSocketHandler = app["ws_handler"]

    # Open serial port (non-fatal if the adapter isn't present yet).
    try:
        await port.open()
    except Exception as exc:
        logger.warning("Could not open RS485 port: %s – running without motors", exc)

    await safety.start()

    # Heartbeat watchdog runs independently.
    app["hb_task"] = asyncio.create_task(
        ws_handler.run_heartbeat_watchdog(), name="hb-watchdog"
    )
    logger.info("vehicle_web_teleop started")


async def _on_shutdown(app: web.Application) -> None:
    safety: SafetyCore = app["safety"]
    port: RS485Port    = app["port"]

    app["hb_task"].cancel()
    try:
        await app["hb_task"]
    except asyncio.CancelledError:
        pass

    await safety.stop()
    await port.close()
    logger.info("vehicle_web_teleop shut down cleanly")


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    host = _cfg("VWT_HOST", "0.0.0.0")
    port = int(_cfg("VWT_PORT", "8080"))

    app, _, _ = build_app()

    # Graceful shutdown on SIGINT / SIGTERM.
    loop = asyncio.new_event_loop()

    def _shutdown_handler() -> None:
        logger.info("Shutdown signal received")
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown_handler)
        except NotImplementedError:
            # Windows does not support add_signal_handler for all signals.
            pass

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, host, port)
    loop.run_until_complete(site.start())
    logger.info("Listening on http://%s:%d  (ws://%s:%d/ws)", host, port, host, port)

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(runner.cleanup())
        loop.close()


if __name__ == "__main__":
    main()
