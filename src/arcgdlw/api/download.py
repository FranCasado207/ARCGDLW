import asyncio
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from arcgdlw import app_settings
from arcgdlw.api import hub
from arcgdlw.api.auth import require_token, require_token_ws
from arcgdlw.models.downloader.downloader import Downloader

router = APIRouter()
_auth = Depends(require_token)

_jobs: dict[str, dict] = {}


class DownloadIn(BaseModel):
    urls: list[str]
    output_folder: str
    target_format: str
    override_format: bool = False
    archive_format: str | None = None


@router.post("", status_code=202, dependencies=[_auth])
async def start_download(body: DownloadIn):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running"}
    _schedule(job_id, body)
    return {"job_id": job_id}


def _schedule(job_id: str, body: DownloadIn) -> None:
    async def job() -> None:
        loop = asyncio.get_running_loop()

        def on_log(msg: str) -> None:
            hub.broadcast(job_id, {"type": "log", "line": msg})

        def blocking() -> tuple[bool, str]:
            try:
                downloader = Downloader(
                    outputFolder=body.output_folder,
                    urls=body.urls,
                    targetFormat=body.target_format,
                    overrideFormat=body.override_format,
                    archiveFormat=body.archive_format,
                    configFile=app_settings.get("gallery_dl_config"),
                )
                downloader.download(log_callback=on_log)
                return True, ""
            except Exception as e:
                return False, str(e)

        success, error = await loop.run_in_executor(None, blocking)
        _jobs[job_id] = {"status": "completed" if success else "error", "error": error}
        hub.broadcast(job_id, {"type": "finished", "success": success, "error_message": error})

    asyncio.create_task(job())


@router.websocket("/{job_id}/stream")
async def download_stream(websocket: WebSocket, job_id: str, token: str | None = Query(default=None)):
    if not await require_token_ws(websocket, token):
        return
    await websocket.accept()
    hub.register(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(job_id, websocket)
