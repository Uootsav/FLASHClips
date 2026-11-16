"""Silent auto-update of the YouTube downloader (yt-dlp + yt-dlp-ejs).

Both are pure-Python wheels, so we download the newest wheels from PyPI into the
user's app-data folder and put them first on sys.path. This works even inside the
frozen .exe - users never need to reinstall FLASHClips when YouTube changes.
"""
import re
import sys
from pathlib import Path

from flashclips.config import app_dir

PKGS = ["yt-dlp", "yt-dlp-ejs"]
_activated = False


def _dir() -> Path:
    d = app_dir() / "ytdlp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ver(name: str):
    m = re.search(r"-(\d+(?:\.\d+)*)-", name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def _latest_local(pkg: str):
    norm = pkg.replace("-", "_")
    wheels = sorted(_dir().glob(f"{norm}-*.whl"), key=lambda p: _ver(p.name))
    return wheels[-1] if wheels else None


def _installed_version(pkg: str):
    try:
        from importlib.metadata import version
        return tuple(int(x) for x in re.findall(r"\d+", version(pkg)))
    except Exception:
        return (0,)


def activate() -> None:
    """Put downloaded wheels on sys.path (call before importing yt_dlp)."""
    global _activated
    if _activated or "yt_dlp" in sys.modules:
        return
    for pkg in PKGS:
        w = _latest_local(pkg)
        if w and _ver(w.name) > _installed_version(pkg):
            sys.path.insert(0, str(w))
    _activated = True


def update(log=print) -> None:
    """Download newer wheels if available, then activate. Never raises."""
    try:
        import requests
        for pkg in PKGS:
            info = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=8).json()
            latest = info["info"]["version"]
            lv = tuple(int(x) for x in re.findall(r"\d+", latest))
            local = _latest_local(pkg)
            have = max(_installed_version(pkg), _ver(local.name) if local else (0,))
            if lv <= have:
                continue
            wheel = next((f for f in info["urls"] if f["filename"].endswith("py3-none-any.whl")), None)
            if not wheel:
                continue
            dest = _dir() / wheel["filename"]
            data = requests.get(wheel["url"], timeout=60).content
            dest.write_bytes(data)
            for old in _dir().glob(f"{pkg.replace('-', '_')}-*.whl"):
                if old != dest:
                    old.unlink(missing_ok=True)
            log(f"Updated {pkg} to {latest} (keeps YouTube working).")
    except Exception as e:
        log(f"Downloader update check skipped ({type(e).__name__}).")
    activate()
