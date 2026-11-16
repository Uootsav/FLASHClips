"""Smart 9:16 reframing: face tracking, two-speaker split screen, or blurred-fit fallback."""
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from flashclips.utils import ffmpeg_exe, run_check

OUT_W, OUT_H = 1080, 1920
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_cascade = None


def _detector():
    global _cascade
    if _cascade is None:
        base = Path(cv2.data.haarcascades) if hasattr(cv2, "data") else Path(".")
        _cascade = cv2.CascadeClassifier(str(base / "haarcascade_frontalface_default.xml"))
    return _cascade


def _faces(frame):
    h, w = frame.shape[:2]
    scale = 480 / w
    small = cv2.cvtColor(cv2.resize(frame, (480, int(h * scale))), cv2.COLOR_BGR2GRAY)
    small = cv2.equalizeHist(small)
    found = _detector().detectMultiScale(small, 1.15, 6, minSize=(28, 28))
    return [(x / scale, y / scale, fw / scale, fh / scale) for (x, y, fw, fh) in found]


def analyze(video: Path, start: float, end: float, sample_fps=3.0):
    """Return (layout, centers_track, (cxA, cxB) for split) based on face statistics."""
    cap = cv2.VideoCapture(str(video))
    vw, vh = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    times, centers, two = [], [], []
    hits = 0
    t = start
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        fs = sorted(_faces(frame), key=lambda f: -f[2] * f[3])
        if fs:
            hits += 1
            centers.append(fs[0][0] + fs[0][2] / 2)
            if len(fs) >= 2 and fs[1][2] > fs[0][2] * 0.6:
                a, b = sorted([fs[0][0] + fs[0][2] / 2, fs[1][0] + fs[1][2] / 2])
                two.append((a, b))
        else:
            centers.append(None)
        times.append(t - start)
        t += 1 / sample_fps
    cap.release()
    n = max(len(times), 1)
    crop_w = vh * 9 / 16
    info = {"vw": vw, "vh": vh, "times": times, "centers": centers}
    if vw / max(vh, 1) <= 9 / 16 + 0.02:
        return "vertical", info
    if len(two) / n > 0.5:
        a = np.median([p[0] for p in two]); b = np.median([p[1] for p in two])
        if b - a > crop_w * 0.8:
            info["split"] = (a, b)
            return "split", info
    if hits / n >= 0.35:
        return "track", info
    return "fit", info


def _smooth_track(info, fps, n_frames):
    vw, vh = info["vw"], info["vh"]
    crop_w = vh * 9 / 16
    cs, ts = info["centers"], info["times"]
    last = vw / 2
    filled = []
    for c in cs:
        last = c if c is not None else last
        filled.append(last)
    if not filled:
        filled, ts = [vw / 2], [0.0]
    ft = np.arange(n_frames) / fps
    raw = np.interp(ft, ts, filled)
    # dead-zone + exponential smoothing = calm, "camera operator" style motion
    out, cur = np.empty_like(raw), raw[0]
    dead = crop_w * 0.08
    for i, x in enumerate(raw):
        if abs(x - cur) > dead:
            cur += (x - cur) * 0.06
        out[i] = cur
    return np.clip(out - crop_w / 2, 0, vw - crop_w)


def render(video: Path, start: float, end: float, ass_file: Path, out: Path, layout="auto",
           log=print):
    """Render a 1080x1920 clip with burned-in captions. Returns the layout used."""
    det, info = analyze(video, start, end)
    if layout in ("track", "fit") and det != "vertical":
        det = layout if not (layout == "track" and det == "split") else det
    ff = ffmpeg_exe()
    dur = end - start
    cwd = str(ass_file.parent)
    ass = ass_file.name
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest"]

    if det in ("fit", "vertical"):
        if det == "vertical":
            vf = (f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease,"
                  f"pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2,ass={ass}")
            fc = ["-vf", vf]
        else:
            fc = ["-filter_complex",
                  f"[0:v]split[a][b];[a]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
                  f"crop={OUT_W}:{OUT_H},boxblur=25:5,eq=brightness=-0.08[bg];"
                  f"[b]scale={OUT_W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,ass={ass}[v]",
                  "-map", "[v]", "-map", "0:a?"]
        run_check([ff, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video.resolve()),
                   *fc, *enc, str(out.resolve())], cwd=cwd)
        return det

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n_frames = int(dur * fps)
    vw, vh = int(info["vw"]), int(info["vh"])
    crop_w = int(vh * 9 / 16)
    xs = _smooth_track(info, fps, n_frames) if det == "track" else None

    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OUT_W}x{OUT_H}",
           "-r", f"{fps:.3f}", "-i", "-", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
           "-i", str(video.resolve()), "-map", "0:v", "-map", "1:a?", "-vf", f"ass={ass}",
           *enc, str(out.resolve())]
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, creationflags=_NO_WINDOW)
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    if det == "split":
        a, b = info["split"]
        half_h = OUT_H // 2
        cw2 = int(vh * OUT_W / half_h)          # crop width for a 1080x960 panel
        cw2 = min(cw2, vw)
        xa = int(np.clip(a - cw2 / 2, 0, vw - cw2)); xb = int(np.clip(b - cw2 / 2, 0, vw - cw2))
    try:
        for i in range(n_frames):
            ok, frame = cap.read()
            if not ok:
                break
            if det == "track":
                x = int(xs[i])
                out_f = cv2.resize(frame[:, x:x + crop_w], (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR)
            else:
                top = cv2.resize(frame[:, xa:xa + cw2], (OUT_W, half_h))
                bot = cv2.resize(frame[:, xb:xb + cw2], (OUT_W, OUT_H - half_h))
                out_f = np.vstack([top, bot])
            proc.stdin.write(out_f.tobytes())
    except BrokenPipeError:
        pass
    finally:
        cap.release()
        try:
            proc.stdin.close()
        except Exception:
            pass
        err = proc.stderr.read().decode(errors="ignore")
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{err[-1500:]}")
    return det
