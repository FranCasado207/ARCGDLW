import json
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from arcgdlw import app_settings
from arcgdlw.api.auth import require_token
from arcgdlw.paths import subprocess_env

router = APIRouter(dependencies=[Depends(require_token)])

# Default gallery-dl config file locations (Linux order; also checked as-is
# on Windows/macOS since gallery-dl itself falls back to the same names).
_DEFAULT_CONFIG_PATHS = [
    Path.home() / ".config" / "gallery-dl" / "config.json",
    Path.home() / ".gallery-dl.conf",
    Path("/etc/gallery-dl.conf"),
]


def find_default_config() -> Path | None:
    for p in _DEFAULT_CONFIG_PATHS:
        if p.exists():
            return p
    return None


def resolve_config_path() -> Path | None:
    custom = app_settings.get("gallery_dl_config")
    if custom:
        return Path(custom)
    return find_default_config()


@router.get("")
def get_config():
    path = resolve_config_path()
    if path and path.exists():
        try:
            content = path.read_text()
        except OSError as e:
            content = f"# Could not read file: {e}"
        return {"path": str(path), "exists": True, "content": content}
    return {
        "path": str(path) if path else None,
        "exists": False,
        "content": '{\n  "extractor": {},\n  "downloader": {},\n  "output": {}\n}\n',
    }


class ConfigIn(BaseModel):
    content: str


@router.put("")
def save_config(body: ConfigIn):
    path = resolve_config_path()
    if not path:
        raise HTTPException(400, "No config file path is set")
    try:
        json.loads(body.content)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content)
    return {"path": str(path)}


@router.post("/create-default")
def create_default_config():
    try:
        subprocess.run(
            ["gallery-dl", "--config-create"],
            capture_output=True, text=True, timeout=15,
            env=subprocess_env(),
        )
    except Exception as e:
        raise HTTPException(500, str(e))
    created = find_default_config()
    if not created:
        raise HTTPException(500, "gallery-dl did not create a config file")
    # Clear any custom override so the newly-created default is picked up.
    app_settings.set_value("gallery_dl_config", None)
    return {"path": str(created)}
