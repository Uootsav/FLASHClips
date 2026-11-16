"""User settings, stored as JSON in the user's app-data folder."""
import json
import os
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path

from flashclips import APP_NAME

# >>> Put YOUR support link here <<<
SUPPORT_URL = "https://www.buymeacoffee.com/YOUR_NAME"
GITHUB_URL = "https://github.com/YOUR_USERNAME/FLASHClips"


def app_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Settings:
    output_dir: str = str(Path.home() / "Videos" / APP_NAME)
    whisper_model: str = "auto"           # auto / tiny / base / small / medium / large-v3
    device: str = "auto"                  # auto / cpu / cuda
    language: str = "auto"
    num_clips: int = 0                    # 0 = auto
    min_len: int = 20
    max_len: int = 60
    caption_style: str = "Bold Pop"
    layout: str = "auto"                  # auto / track / fit
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    use_ai: bool = True
    use_comments: bool = True
    browser_cookies: str = ""             # e.g. "chrome" for age-restricted videos
    setup_done: bool = False
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        p = app_dir() / "settings.json"
        s = cls()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
            except Exception:
                pass
        return s

    def save(self) -> None:
        (app_dir() / "settings.json").write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
