import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List


class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class Task:
    def __init__(
        self,
        name: str,
        urls: List[str],
        output_folder: str,
        target_format: str,
        override_format: bool = False,
        archive_format: str | None = None,
        cookies_file: str | None = None,
        create_subfolder: bool = False,
        start_automatically: bool = False,
        task_id: str | None = None,
        status: TaskStatus = TaskStatus.PENDING,
        preview_image: Path | str | None = None,
        error_message: str | None = None,
        created_at: datetime | None = None,
        output_files: List[str] | None = None,
    ):
        self.id = task_id or str(uuid.uuid4())
        self.name = name
        self.urls = urls
        self.output_folder = output_folder
        self.target_format = target_format
        self.override_format = override_format
        self.archive_format = archive_format
        self.cookies_file = cookies_file
        self.create_subfolder = create_subfolder
        self.start_automatically = start_automatically
        self.status = status
        self.preview_image = Path(preview_image) if preview_image else None
        self.error_message = error_message
        self.created_at = created_at or datetime.now()
        self.output_files = output_files or []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "urls": self.urls,
            "output_folder": self.output_folder,
            "target_format": self.target_format,
            "override_format": self.override_format,
            "archive_format": self.archive_format,
            "cookies_file": self.cookies_file,
            "create_subfolder": self.create_subfolder,
            "start_automatically": self.start_automatically,
            "status": self.status.value,
            "preview_image": str(self.preview_image) if self.preview_image else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "output_files": self.output_files,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            task_id=data["id"],
            name=data["name"],
            urls=data["urls"],
            output_folder=data["output_folder"],
            target_format=data["target_format"],
            override_format=data["override_format"],
            archive_format=data.get("archive_format"),
            cookies_file=data.get("cookies_file"),
            create_subfolder=data.get("create_subfolder", False),
            start_automatically=data.get("start_automatically", False),
            status=TaskStatus(data["status"]),
            preview_image=data.get("preview_image"),
            error_message=data.get("error_message"),
            created_at=datetime.fromisoformat(data["created_at"]),
            output_files=data.get("output_files"),
        )
