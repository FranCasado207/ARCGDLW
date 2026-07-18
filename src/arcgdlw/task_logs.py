import time
from pathlib import Path

from arcgdlw.paths import get_app_data_dir

LOGS_DIR = get_app_data_dir() / "logs"
_MAX_BYTES = 512 * 1024  # rotate a task's log once it grows past this size


def log_path(task_id: str) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / f"{task_id}.log"


def _backup_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.log.1")


def _rotate_if_needed(path: Path) -> None:
    if path.exists() and path.stat().st_size > _MAX_BYTES:
        backup = _backup_path(path)
        backup.unlink(missing_ok=True)
        path.rename(backup)


def start_run(task_id: str) -> None:
    """Call once when a task starts a run: rotates the log if it has grown
    too large, then writes a run-start header."""
    path = log_path(task_id)
    _rotate_if_needed(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n===== Run started: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")


def append(task_id: str, message: str) -> None:
    with open(log_path(task_id), "a", encoding="utf-8") as f:
        f.write(message + "\n")


def read(task_id: str) -> str:
    path = log_path(task_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def clear(task_id: str) -> None:
    log_path(task_id).unlink(missing_ok=True)
    _backup_path(log_path(task_id)).unlink(missing_ok=True)
