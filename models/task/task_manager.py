import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from models.task.task import Task, TaskStatus
from paths import get_app_data_dir, subprocess_env

_DATA_DIR = get_app_data_dir()
TASKS_FILE = _DATA_DIR / "tasks.json"
PREVIEWS_DIR = _DATA_DIR / "previews"

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"}


class TaskManager:
    def __init__(self):
        self._tasks: List[Task] = []
        PREVIEWS_DIR.mkdir(exist_ok=True)
        self._load()

    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks)

    def get(self, task_id: str) -> Optional[Task]:
        return next((t for t in self._tasks if t.id == task_id), None)

    def create(self, task: Task) -> Task:
        self._tasks.append(task)
        self._save()
        return task

    def update(self, task: Task) -> None:
        for i, t in enumerate(self._tasks):
            if t.id == task.id:
                self._tasks[i] = task
                break
        self._save()

    def delete(self, task_id: str) -> None:
        task = self.get(task_id)
        if task and task.preview_image and task.preview_image.exists():
            task.preview_image.unlink(missing_ok=True)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        self._save()

    def fetch_preview(self, task: Task) -> Optional[Path]:
        """Download only the first file from the first URL to use as a thumbnail."""
        import app_settings
        if not task.urls:
            return None
        url = task.urls[0]
        config_file = app_settings.get("gallery_dl_config")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                cmd = ["gallery-dl", "-d", str(tmp_path), "--range", "1-1"]
                if config_file:
                    cmd += ["-c", str(config_file)]
                if task.cookies_file:
                    cmd += ["--cookies", str(task.cookies_file)]
                cmd.append(url)
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    timeout=60,
                    env=subprocess_env(),
                )
                all_files = sorted(f for f in tmp_path.rglob("*") if f.is_file())
                images = [f for f in all_files if f.suffix.lower() in _IMAGE_EXTS]
                candidates = images or all_files
                if not candidates:
                    return None
                src = candidates[0]
                dest = PREVIEWS_DIR / f"{task.id}_preview{src.suffix}"
                shutil.copy2(src, dest)
                return dest
            except Exception:
                return None

    def _load(self) -> None:
        if not TASKS_FILE.exists():
            return
        try:
            with open(TASKS_FILE) as f:
                data = json.load(f)
            self._tasks = [Task.from_dict(d) for d in data]
            # Tasks that were RUNNING when the app closed need to be reset
            for task in self._tasks:
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.PENDING
        except Exception:
            self._tasks = []

    def _save(self) -> None:
        with open(TASKS_FILE, "w") as f:
            json.dump([t.to_dict() for t in self._tasks], f, indent=2)
