import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from arcgdlw import app_settings, task_logs
from arcgdlw.api import hub
from arcgdlw.api.auth import require_token, require_token_ws
from arcgdlw.models.downloader.downloader import Downloader
from arcgdlw.models.task.task import Task, TaskStatus
from arcgdlw.models.task.task_manager import TaskManager

# The WebSocket route authenticates itself via require_token_ws (query-param
# token, clean close on failure) instead of this dependency: raising
# HTTPException from a router-level dependency doesn't close a WebSocket
# handshake as cleanly, so it's applied per-route to the HTTP endpoints only.
router = APIRouter()
_auth = Depends(require_token)

_manager = TaskManager()
_run_tasks: dict[str, asyncio.Task] = {}
_preview_tasks: dict[str, asyncio.Task] = {}


class TaskIn(BaseModel):
    name: str
    urls: list[str]
    output_folder: str
    target_format: str
    override_format: bool = False
    archive_format: str | None = None
    cookies_file: str | None = None
    create_subfolder: bool = False
    start_automatically: bool = False


def _task_to_out(task: Task) -> dict:
    data = task.to_dict()
    data["preview_url"] = (
        f"/api/previews/{task.preview_image.name}"
        if task.preview_image and task.preview_image.exists()
        else None
    )
    data["is_running"] = task.id in _run_tasks
    return data


@router.get("", dependencies=[_auth])
def list_tasks():
    return [_task_to_out(t) for t in _manager.tasks]


@router.post("", status_code=201, dependencies=[_auth])
async def create_task(body: TaskIn):
    task = Task(**body.model_dump())
    _manager.create(task)
    _schedule_preview_fetch(task.id)
    if task.start_automatically:
        _schedule_run(task.id)
    return _task_to_out(task)


@router.put("/{task_id}", dependencies=[_auth])
async def update_task(task_id: str, body: TaskIn):
    task = _manager.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task_id in _run_tasks:
        raise HTTPException(409, "Cannot edit a running task")

    urls_changed = body.urls != task.urls
    for field, value in body.model_dump().items():
        setattr(task, field, value)
    if task.status == TaskStatus.ERROR:
        task.status = TaskStatus.PENDING
        task.error_message = None
    if urls_changed:
        task.preview_image = None
    _manager.update(task)

    if urls_changed:
        _schedule_preview_fetch(task_id)
    return _task_to_out(task)


@router.delete("/{task_id}", dependencies=[_auth])
def delete_task(task_id: str, delete_files: bool = False):
    if not _manager.get(task_id):
        raise HTTPException(404, "Task not found")
    if task_id in _run_tasks:
        raise HTTPException(409, "Cannot delete a running task")
    _manager.delete(task_id, delete_files=delete_files)
    return Response(status_code=204)


@router.post("/{task_id}/run", status_code=202, dependencies=[_auth])
async def run_task(task_id: str):
    task = _manager.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task_id in _run_tasks:
        raise HTTPException(409, "Task is already running")
    _schedule_run(task_id)
    return {"status": "started"}


def _schedule_preview_fetch(task_id: str) -> None:
    async def job() -> None:
        loop = asyncio.get_running_loop()
        task = _manager.get(task_id)
        if not task:
            return
        preview = await loop.run_in_executor(None, _manager.fetch_preview, task)
        if preview:
            # Re-fetch: the task may have been edited while the preview was downloading.
            task = _manager.get(task_id)
            if task:
                task.preview_image = preview
                _manager.update(task)
                hub.broadcast(task_id, {"type": "task_updated", "task": _task_to_out(task)})
        _preview_tasks.pop(task_id, None)

    _preview_tasks[task_id] = asyncio.create_task(job())


def _schedule_run(task_id: str) -> None:
    async def job() -> None:
        loop = asyncio.get_running_loop()
        task = _manager.get(task_id)
        if not task:
            return

        task.status = TaskStatus.RUNNING
        task.error_message = None
        _manager.update(task)
        hub.broadcast(task_id, {"type": "task_updated", "task": _task_to_out(task)})

        task_logs.start_run(task_id)
        start_msg = f"⏳ Starting task: {task.name}"
        task_logs.append(task_id, start_msg)
        hub.broadcast(task_id, {"type": "log", "line": start_msg})

        def on_log(msg: str) -> None:
            task_logs.append(task_id, msg)
            hub.broadcast(task_id, {"type": "log", "line": msg})

        def on_progress(current: int, total: int) -> None:
            hub.broadcast(task_id, {"type": "progress", "current": current, "total": total})

        def blocking() -> tuple[bool, str, list[str]]:
            try:
                downloader = Downloader(
                    outputFolder=task.output_folder,
                    urls=task.urls,
                    targetFormat=task.target_format,
                    overrideFormat=task.override_format,
                    archiveFormat=task.archive_format,
                    configFile=app_settings.get("gallery_dl_config"),
                    cookiesFile=task.cookies_file or None,
                    createSubfolder=task.create_subfolder,
                    archiveName=task.name,
                )
                files = downloader.download(log_callback=on_log, progress_callback=on_progress)
                return True, "", [str(p) for p in files]
            except Exception as e:
                return False, str(e), []

        success, error_msg, output_files = await loop.run_in_executor(None, blocking)

        task = _manager.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED if success else TaskStatus.ERROR
            task.error_message = error_msg if not success else None
            if success:
                task.output_files = output_files
            _manager.update(task)

        final_msg = "\n✅ Task completed!" if success else f"\n❌ Task failed: {error_msg}"
        task_logs.append(task_id, final_msg)
        hub.broadcast(task_id, {"type": "log", "line": final_msg})
        hub.broadcast(
            task_id,
            {
                "type": "finished",
                "success": success,
                "error_message": error_msg,
                "task": _task_to_out(task) if task else None,
            },
        )
        _run_tasks.pop(task_id, None)

    _run_tasks[task_id] = asyncio.create_task(job())


@router.websocket("/{task_id}/stream")
async def task_stream(websocket: WebSocket, task_id: str, token: str | None = Query(default=None)):
    if not await require_token_ws(websocket, token):
        return
    await websocket.accept()
    hub.register(task_id, websocket)
    try:
        history = task_logs.read(task_id)
        if history:
            await websocket.send_json({"type": "history", "content": history})
        task = _manager.get(task_id)
        if task:
            await websocket.send_json({"type": "task_updated", "task": _task_to_out(task)})
        while True:
            # No messages are expected from the client; this just keeps the
            # socket open so the hub can push updates until it disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(task_id, websocket)
