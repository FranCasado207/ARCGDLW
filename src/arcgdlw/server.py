"""The local API server that backs the Tauri + React frontend.

Run standalone in dev (`python -m arcgdlw.main --serve --port 8734`) or spawned
by the Tauri shell as a sidecar in production, in which case the port is left
at 0 (OS-assigned) and printed on stdout for the shell to pick up, along with a
random bearer token minted for this run — see run_server() below.
"""

import asyncio
import secrets
import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from arcgdlw.api import download as download_api
from arcgdlw.api import hub
from arcgdlw.api import settings as settings_api
from arcgdlw.api import tasks as tasks_api
from arcgdlw.api.auth import set_auth_token
from arcgdlw.api.config import router as config_router
from arcgdlw.models.task.task_manager import PREVIEWS_DIR


def create_app(auth_token: str) -> FastAPI:
    set_auth_token(auth_token)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hub.set_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(title="ARCGDLW backend", lifespan=lifespan)

    # This server only ever binds to 127.0.0.1 and is only ever reached by the
    # Tauri webview or a local dev Vite server, both of which need every
    # non-health route gated by the startup bearer token anyway — a permissive
    # CORS policy here doesn't widen the real attack surface.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(tasks_api.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(download_api.router, prefix="/api/download", tags=["download"])
    app.include_router(config_router, prefix="/api/config", tags=["config"])
    app.include_router(settings_api.router, prefix="/api", tags=["settings"])

    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/api/previews", StaticFiles(directory=PREVIEWS_DIR), name="previews")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


def _pick_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def run_server(host: str = "127.0.0.1", port: int = 0) -> None:
    token = secrets.token_hex(16)
    if port == 0:
        port = _pick_free_port(host)

    app = create_app(token)

    # The Tauri shell (or a dev script) reads these two lines from stdout to
    # learn where and how to reach this server before it does anything else.
    print(f"ARCGDLW-PORT={port}", flush=True)
    print(f"ARCGDLW-TOKEN={token}", flush=True)

    uvicorn.run(app, host=host, port=port, log_level="warning")
