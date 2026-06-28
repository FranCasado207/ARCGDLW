import json
from pathlib import Path

_FILE = Path(__file__).parent / "app_settings.json"


def _load() -> dict:
    if not _FILE.exists():
        return {}
    try:
        return json.loads(_FILE.read_text())
    except Exception:
        return {}


def get(key: str, default=None):
    return _load().get(key, default)


def set_value(key: str, value) -> None:
    data = _load()
    data[key] = value
    _FILE.write_text(json.dumps(data, indent=2))
