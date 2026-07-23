from fastapi import APIRouter, Depends
from pydantic import BaseModel

from arcgdlw import app_settings
from arcgdlw.api.auth import require_token
from arcgdlw.api.config import resolve_config_path
from arcgdlw.paths import get_app_data_dir, get_default_output_dir

router = APIRouter(dependencies=[Depends(require_token)])


@router.get("/settings")
def get_settings():
    return {"gallery_dl_config": app_settings.get("gallery_dl_config")}


class SettingsIn(BaseModel):
    gallery_dl_config: str | None = None


@router.put("/settings")
def update_settings(body: SettingsIn):
    app_settings.set_value("gallery_dl_config", body.gallery_dl_config)
    return get_settings()


@router.get("/paths")
def get_paths():
    config_path = resolve_config_path()
    return {
        "app_data_dir": str(get_app_data_dir()),
        "config_dir": str(config_path.parent) if config_path else None,
        "default_output_dir": str(get_default_output_dir()),
    }
