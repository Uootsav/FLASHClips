"""Built-in local AI (llama.cpp). Downloads a small free model once, then works offline.
No Ollama, no account, no API key."""
import json
import os
import threading
from pathlib import Path

from flashclips.config import app_dir

MODELS = {
    # name: (url, approx size GB, min RAM GB)
    "qwen2.5-3b": ("https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/"
                   "qwen2.5-3b-instruct-q4_k_m.gguf", 2.1, 8),
    "qwen2.5-1.5b": ("https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
                     "qwen2.5-1.5b-instruct-q4_k_m.gguf", 1.1, 4),
}


def models_dir() -> Path:
    d = app_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        return 8.0


def recommended_model() -> str:
    return "qwen2.5-3b" if ram_gb() >= 11 else "qwen2.5-1.5b"


def model_path(name: str) -> Path:
    return models_dir() / MODELS[name][0].rsplit("/", 1)[1]


def installed_model():
    for name in MODELS:
        if model_path(name).exists():
            return name
    return None


def available() -> bool:
    try:
        import llama_cpp  # noqa: F401
        return installed_model() is not None
    except Exception:
        return False


def download(name: str, progress=lambda done, total: None, cancelled=lambda: False) -> Path:
    """Resumable download to models dir."""
    import requests
    url = MODELS[name][0]
    dest = model_path(name)
    part = dest.with_suffix(".part")
    pos = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={pos}-"} if pos else {}
    with requests.get(url, stream=True, headers=headers, timeout=30) as r:
        if r.status_code == 200:
            pos = 0
        r.raise_for_status()
        total = pos + int(r.headers.get("content-length", 0))
        with open(part, "ab" if pos else "wb") as f:
            for chunk in r.iter_content(1 << 20):
                if cancelled():
                    raise InterruptedError("cancelled")
                f.write(chunk)
                pos += len(chunk)
                progress(pos, total)
    os.replace(part, dest)
    return dest


_llm = None
_lock = threading.Lock()


def _get():
    global _llm
    with _lock:
        if _llm is None:
            from llama_cpp import Llama
            _llm = Llama(model_path=str(model_path(installed_model())), n_ctx=4096,
                         n_threads=max(2, (os.cpu_count() or 4) - 1), n_gpu_layers=-1,
                         verbose=False)
        return _llm


def chat_json(prompt: str, max_tokens=200) -> dict:
    out = _get().create_chat_completion(
        messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=max_tokens,
        response_format={"type": "json_object"})
    return json.loads(out["choices"][0]["message"]["content"])
