"""Fan-out of log/progress/status events to WebSocket subscribers, keyed by
task id or download-job id. Downloads run in a thread pool executor, so
broadcast() must be safe to call from a non-event-loop thread."""

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

_loop: asyncio.AbstractEventLoop | None = None
_conns: dict[str, set[WebSocket]] = defaultdict(set)


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def register(key: str, ws: WebSocket) -> None:
    _conns[key].add(ws)


def unregister(key: str, ws: WebSocket) -> None:
    _conns[key].discard(ws)


async def _broadcast(key: str, message: dict[str, Any]) -> None:
    dead = []
    for ws in list(_conns.get(key, ())):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _conns[key].discard(ws)


def broadcast(key: str, message: dict[str, Any]) -> None:
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_broadcast(key, message), _loop)
