"""Speech-to-text with word-level timestamps (faster-whisper, runs locally)."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list


def _pick_device(device: str):
    if device != "auto":
        return device, ("float16" if device == "cuda" else "int8")
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def whisper_dir():
    from flashclips.config import app_dir
    d = app_dir() / "models" / "whisper"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def auto_size(model_size: str) -> str:
    if model_size != "auto":
        return model_size
    if _pick_device("auto")[0] == "cuda":
        return "medium"
    try:
        import psutil
        return "small" if psutil.virtual_memory().total / 1024 ** 3 >= 6 else "base"
    except Exception:
        return "small"


def download_model(model_size="auto"):
    from faster_whisper.utils import download_model as dl
    return dl(auto_size(model_size), cache_dir=whisper_dir())


def transcribe(audio: Path, model_size="auto", device="auto", language="auto",
               log=print, progress=lambda p: None, duration=0.0):
    model_size = auto_size(model_size)
    dev, _ = _pick_device(device)
    if dev == "cuda":
        try:
            return _transcribe(audio, model_size, "cuda", "float16", language, log, progress, duration)
        except Exception as e:                       # missing CUDA libraries etc. -> CPU
            log(f"GPU not usable ({type(e).__name__}); switching to CPU.")
            if model_size in ("medium", "large-v3") and device == "auto":
                model_size = "small"
    return _transcribe(audio, model_size, "cpu", "int8", language, log, progress, duration)


def _transcribe(audio, model_size, dev, ctype, language, log, progress, duration):
    from faster_whisper import WhisperModel
    log(f"Loading speech model '{model_size}' on {dev.upper()} (first run downloads it)…")
    model = WhisperModel(model_size, device=dev, compute_type=ctype, download_root=whisper_dir())
    segs_iter, info = model.transcribe(str(audio), word_timestamps=True, vad_filter=True,
                                       language=None if language == "auto" else language)
    log(f"Detected language: {info.language}")
    total = duration or info.duration or 1
    segments = []
    for s in segs_iter:
        words = [Word(w.start, w.end, w.word.strip()) for w in (s.words or []) if w.word.strip()]
        segments.append(Segment(s.start, s.end, s.text.strip(), words))
        progress(min(s.end / total, 1.0))
    return segments, info.language
