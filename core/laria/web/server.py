"""Run the web API as a standalone process.

Used as the container entrypoint: ``python -m laria.web``. It builds the engine
from the environment and serves the JSON API on the configured host and port.
"""
from __future__ import annotations

import logging

from aiohttp import web

from ..app import build_engine
from ..config import get_settings
from ..storage import init_db
from .app import create_app


async def _on_startup(app: web.Application) -> None:
    """Create the database schema before the first request is served."""
    await init_db()


def serve() -> None:
    """Start the HTTP server and block until the process is stopped."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = create_app(build_engine(settings))
    app.on_startup.append(_on_startup)
    web.run_app(app, host=settings.web_host, port=settings.web_port)


if __name__ == "__main__":
    serve()
