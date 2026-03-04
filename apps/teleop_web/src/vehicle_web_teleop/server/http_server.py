"""Static HTTP server that serves the web/ UI directory.

The ``/ws`` path is reserved for the WebSocket handler; all other GET requests
are resolved against the ``web_root`` directory.  ``index.html`` is served for
bare ``/`` requests.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

logger = logging.getLogger(__name__)


def add_static_routes(app: web.Application, web_root: Path) -> None:
    """Register static-file routes on *app*.

    Parameters
    ----------
    app:
        The aiohttp Application instance.
    web_root:
        Absolute path to the directory containing ``index.html``, ``app.js``,
        ``style.css``, etc.
    """
    if not web_root.is_dir():
        raise FileNotFoundError(f"web_root not found: {web_root}")

    async def index(_request: web.Request) -> web.FileResponse:
        return web.FileResponse(web_root / "index.html")

    # Serve index.html for the bare root.
    app.router.add_get("/", index)

    # Serve everything else under /static/ mapped to web_root.
    # Also add a catch-all so that assets can be referenced without the
    # /static/ prefix (e.g. <script src="app.js"> works from index.html).
    app.router.add_static("/static", web_root, name="static")
    app.router.add_static("/", web_root, name="web_root")

    logger.info("Static files served from %s", web_root)
