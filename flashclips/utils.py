import re
import shutil
import subprocess
import sys
from pathlib import Path

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def bundle_dir() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def setup_bundled_tools() -> None:
    """Put bundled bin/ (ffmpeg, deno) on PATH so yt-dlp finds the JS runtime for YouTube."""
    import os
    for d in (bundle_dir() / "bin", bundle_dir() / "_internal" / "bin"):
        if d.exists():
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


def ffmpeg_exe() -> str:
    """ffmpeg bundled next to the app (.exe build) > system ffmpeg > imageio-ffmpeg."""
    here = bundle_dir()
    for cand in (here / "bin" / "ffmpeg.exe", here / "bin" / "ffmpeg", here / "ffmpeg.exe"):
        if cand.exists():
            return str(cand)
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError("FFmpeg not found. Install it or `pip install imageio-ffmpeg`.")


def run(cmd, cwd=None, stdin=None):
    return subprocess.Popen(cmd, cwd=cwd, stdin=stdin, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, creationflags=_NO_WINDOW)


def run_check(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, creationflags=_NO_WINDOW)
    if p.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{p.stderr.decode(errors='ignore')[-1500:]}")
    return p


def safe_name(text: str, maxlen: int = 60) -> str:
    text = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", text).strip()
    return (text[:maxlen].rstrip() or "video")


def fmt_time(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 3600:d}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:d}:{t % 60:02d}"


def extract_audio(video: Path, out_wav: Path) -> Path:
    run_check([ffmpeg_exe(), "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
               "-c:a", "pcm_s16le", str(out_wav)])
    return out_wav
