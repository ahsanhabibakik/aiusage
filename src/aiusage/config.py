"""Cross-platform path + settings helpers."""
import json
import os
from pathlib import Path

DEFAULT_PORT = 8737


def claude_config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def claude_credentials_path() -> Path:
    return claude_config_dir() / ".credentials.json"


def claude_projects_dir() -> Path:
    return claude_config_dir() / "projects"


def codex_home_dir() -> Path:
    override = os.environ.get("CODEX_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex"


def app_config_dir() -> Path:
    """Where aiusage keeps its own settings (port, enabled providers)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home()))
        return Path(base) / "aiusage"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "aiusage"


def load_settings() -> dict:
    path = app_config_dir() / "config.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def save_settings(settings: dict) -> None:
    d = app_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(settings, indent=2))
