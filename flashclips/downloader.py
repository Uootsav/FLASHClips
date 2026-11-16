"""Download any video link with yt-dlp, plus YouTube 'Most Replayed' heatmap and comments."""
import re
from dataclasses import dataclass, field
from pathlib import Path

from flashclips.utils import ffmpeg_exe, safe_name


@dataclass
class VideoSource:
    path: Path
    title: str
    duration: float
    url: str = ""
    heatmap: list = field(default_factory=list)            # [{start_time,end_time,value}]
    comment_times: list = field(default_factory=list)      # [seconds, ...]


TS_RE = re.compile(r"(?<!\d)(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?!\d)")


def _comment_timestamps(comments, duration):
    times = []
    for c in comments or []:
        for h, m, s in TS_RE.findall(c.get("text", "")):
            t = int(h or 0) * 3600 + int(m) * 60 + int(s)
            if 0 < t < (duration or 1e9):
                times.append(float(t))
    return times


def try_update_ytdlp(log=print) -> None:
    from flashclips import updater
    updater.update(log)


def is_url(s: str) -> bool:
    return s.strip().lower().startswith(("http://", "https://", "www."))


def fetch(source: str, work_dir: Path, use_comments=True, cookies_browser="", log=print,
          progress=lambda p: None) -> VideoSource:
    work_dir.mkdir(parents=True, exist_ok=True)
    if not is_url(source):
        import cv2
        p = Path(source)
        cap = cv2.VideoCapture(str(p))
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
        cap.release()
        return VideoSource(path=p, title=p.stem, duration=dur)

    from flashclips import updater
    from flashclips.utils import setup_bundled_tools
    setup_bundled_tools()
    updater.activate()
    import yt_dlp

    def hook(d):
        if d.get("status") == "downloading":
            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if tot:
                progress(d.get("downloaded_bytes", 0) / tot)

    opts = {
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(work_dir / "source.%(ext)s"),
        "ffmpeg_location": ffmpeg_exe(),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "getcomments": bool(use_comments),
        "extractor_args": {"youtube": {"max_comments": ["400", "all", "0", "0"],
                                       "comment_sort": ["top"]}},
    }
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)

    log("Downloading video…")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source.strip(), download=True)
        path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
    if not path.exists():
        cands = sorted(work_dir.glob("source.*"))
        if not cands:
            raise RuntimeError("Download failed - no file produced.")
        path = cands[0]

    duration = float(info.get("duration") or 0)
    heat = info.get("heatmap") or []
    ctimes = _comment_timestamps(info.get("comments"), duration)
    log(f"Downloaded: {info.get('title')}  ({len(heat)} heatmap points, "
        f"{len(ctimes)} comment timestamps)")
    return VideoSource(path=path, title=safe_name(info.get("title") or "video"),
                       duration=duration, url=source, heatmap=heat, comment_times=ctimes)
