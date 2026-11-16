"""Find the best moments. Combines 5 signals into one viral score (0-100):
  1. YouTube 'Most Replayed' heatmap      (real viewer behaviour)
  2. Transcript AI score via local LLM     (hooks, emotion, punchlines, standalone value)
     -> falls back to a keyword/heuristic scorer if no LLM is available
  3. Audio energy & speech pace            (laughter, excitement, raised voices)
  4. Timestamped comments                  ("3:45 😂😂")
  5. Structure                             (starts/ends on sentence boundaries, good length)
"""
import json
import re
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Clip:
    start: float
    end: float
    text: str
    words: list
    score: float = 0.0
    signals: dict = field(default_factory=dict)
    title: str = ""
    hashtags: list = field(default_factory=list)
    reason: str = ""
    file: str = ""

    @property
    def duration(self):
        return self.end - self.start


# ---------------------------------------------------------------- sentences & candidates
def sentences_from(segments):
    words = [w for s in segments for w in s.words]
    sents, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?…]$", w.text) or (cur and w.end - cur[0].start > 14):
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    return sents


def build_candidates(segments, min_len=20, max_len=60):
    sents = sentences_from(segments)
    cands = []
    for i in range(len(sents)):
        start = sents[i][0].start
        words = []
        for j in range(i, len(sents)):
            words = words + sents[j]
            dur = sents[j][-1].end - start
            if dur > max_len:
                break
            if dur >= min_len:
                cands.append(Clip(start=max(0, start - 0.15), end=sents[j][-1].end + 0.35,
                                  text=" ".join(w.text for w in words), words=list(words)))
    return cands


# ---------------------------------------------------------------- signals
def audio_energy(wav_path: Path, hop=0.5):
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)
    n = int(sr * hop)
    if len(data) < n:
        return np.zeros(1), hop
    frames = data[: len(data) // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-9)
    db = 20 * np.log10(rms + 1e-9)
    z = (db - db.mean()) / (db.std() + 1e-6)
    return z, hop


def _range_mean(arr, hop, a, b):
    i, j = int(a / hop), max(int(b / hop), int(a / hop) + 1)
    seg = arr[i:j]
    return float(seg.mean()) if len(seg) else 0.0


def heat_score(heatmap, a, b):
    if not heatmap:
        return None
    vals = [h["value"] for h in heatmap if h["end_time"] > a and h["start_time"] < b]
    if not vals:
        return 0.0
    allv = np.array([h["value"] for h in heatmap])
    pct = (np.mean(vals) - allv.mean()) / (allv.std() + 1e-6)
    return float(np.clip(0.5 + pct / 4, 0, 1))


HOOKS = r"\b(secret|never|nobody|everyone|mistake|truth|actually|crazy|insane|biggest|worst|best|" \
        r"how to|why|what if|stop|imagine|the reason|here's|here is|you need|don't|million|" \
        r"billion|money|shocking|honestly|literally|changed my life|i quit|i was|story|" \
        r"lesson|tip|hack|problem|wrong|fail|rich|broke|love|hate|scared|died|first time)\b"
EMO = r"\b(haha|lol|wow|omg|oh my god|amazing|unbelievable|hilarious|funny|crying|angry|" \
      r"damn|wild|no way|seriously)\b|!|\[laugh"


def text_heuristic(text, first_words):
    t = text.lower()
    s = 0.3
    s += min(len(re.findall(HOOKS, t)) * 0.06, 0.3)
    s += min(len(re.findall(EMO, t)) * 0.05, 0.2)
    s += 0.05 * min(len(re.findall(r"\d+", t)), 3)
    s += 0.08 if "?" in text else 0
    head = first_words.lower()
    if re.search(HOOKS, head) or "?" in head:
        s += 0.15                                   # strong opening hook
    if re.match(r"^(and|but|so|because|which|or|um|uh)\b", head):
        s -= 0.15                                   # starts mid-thought
    return float(np.clip(s, 0, 1))


def comment_score(times, a, b):
    if not times:
        return None
    hits = sum(1 for t in times if a - 5 <= t <= b)
    return float(min(hits / 3, 1.0))


# ---------------------------------------------------------------- LLM (Ollama)
def ollama_ok(url):
    try:
        import requests
        return requests.get(url + "/api/tags", timeout=2).ok
    except Exception:
        return False


LLM_PROMPT = """You are an expert short-form video editor (TikTok, Reels, YouTube Shorts).
Rate this transcript excerpt as a standalone viral short clip.
Consider: strong hook in the first sentence, emotion, humor, surprise, controversy,
useful insight, and whether it makes sense WITHOUT the rest of the video.
Language of transcript: {lang}. Write title and hashtags in the same language.

Transcript:
\"\"\"{text}\"\"\"

Reply ONLY with JSON: {{"score": 0-100, "title": "catchy title max 60 chars",
"hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"], "reason": "max 12 words"}}"""


def llm_rate(clip, backend, url, model, lang="en"):
    prompt = LLM_PROMPT.format(text=clip.text[:2000], lang=lang)
    if backend == "builtin":
        from flashclips import llm
        data = llm.chat_json(prompt)
    else:                                                   # optional: Ollama for power users
        import requests
        r = requests.post(url + "/api/generate", timeout=180, json={
            "model": model, "prompt": prompt, "stream": False, "format": "json",
            "options": {"temperature": 0.3}})
        r.raise_for_status()
        data = json.loads(r.json().get("response", "{}"))
    return (float(data.get("score", 50)) / 100, str(data.get("title", ""))[:80],
            [h if h.startswith("#") else "#" + h for h in data.get("hashtags", [])][:6],
            str(data.get("reason", "")))


# ---------------------------------------------------------------- titles fallback
STOP = set("the a an and or but so to of in on for with is are was were be been it this that i you "
           "we they he she my your our just like really very have has had do does did not no "
           "yeah okay um uh what when where who how about from at as by if then there their".split())


def fallback_title(text):
    first = re.split(r"(?<=[.!?])\s", text.strip())[0]
    title = first if len(first) <= 60 else first[:57].rsplit(" ", 1)[0] + "…"
    words = [w.strip(".,!?\"'").lower() for w in text.split()]
    freq = {}
    for w in words:
        if len(w) > 3 and w not in STOP and w.isalpha():
            freq[w] = freq.get(w, 0) + 1
    tags = ["#" + w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:3]]
    return title, tags + ["#shorts", "#viral"]


# ---------------------------------------------------------------- main
def find_best(segments, wav_path, source, settings, lang="en", log=print, progress=lambda p: None):
    cands = build_candidates(segments, settings.min_len, settings.max_len)
    if not cands:
        raise RuntimeError("No speech found - cannot pick moments from this video.")
    log(f"Evaluating {len(cands)} candidate clips…")
    energy, hop = audio_energy(wav_path)

    for c in cands:
        txt = text_heuristic(c.text, " ".join(w.text for w in c.words[:12]))
        en = float(np.clip(0.5 + _range_mean(energy, hop, c.start, c.end) / 3, 0, 1))
        pace = len(c.words) / max(c.duration, 1)
        pace_s = float(np.clip((pace - 1.8) / 2.0, 0, 1))
        heat = heat_score(source.heatmap, c.start, c.end)
        com = comment_score(source.comment_times, c.start, c.end)
        length_s = 1 - abs(c.duration - 40) / 60
        c.signals = {"text": txt, "energy": en, "pace": pace_s, "heat": heat,
                     "comments": com, "length": length_s}
        c.score = _combine(c.signals)

    cands.sort(key=lambda c: -c.score)
    n_target = settings.num_clips or int(np.clip(source.duration / 300, 3, 10))
    shortlist = _non_overlapping(cands, n_target * 3)

    backend = None
    if settings.use_ai:
        from flashclips import llm
        if llm.available():
            backend = "builtin"
        elif ollama_ok(settings.ollama_url):
            backend = "ollama"
        else:
            log("AI model not installed → using built-in smart scoring.")
    use_llm = backend is not None
    if use_llm:
        log("AI is reading the best moments…")
        shortlist = shortlist[: n_target * 2]
    import time
    t0 = time.time()
    for i, c in enumerate(shortlist):
        if use_llm and time.time() - t0 > 600:
            log("AI is slow on this PC – finishing remaining clips with smart scoring.")
            use_llm = False
        if use_llm:
            try:
                ai, title, tags, reason = llm_rate(c, backend, settings.ollama_url,
                                                   settings.ollama_model, lang)
                c.signals["ai"] = ai
                c.title, c.hashtags, c.reason = title, tags, reason
                c.score = _combine(c.signals)
            except Exception as e:
                log(f"AI scoring failed on one clip ({e}); using fallback.")
                use_llm = False
        if not c.title:
            c.title, c.hashtags = fallback_title(c.text)
        if not c.reason:
            c.reason = _reason(c.signals)
        progress((i + 1) / len(shortlist))

    shortlist.sort(key=lambda c: -c.score)
    best = shortlist[:n_target]
    for c in best:
        c.score = round(min(99, 40 + c.score * 60), 0)
    best.sort(key=lambda c: -c.score)
    return best


def _combine(s):
    w = {"text": 0.22, "energy": 0.12, "pace": 0.06, "length": 0.05,
         "heat": 0.25, "comments": 0.10, "ai": 0.40}
    tot = val = 0.0
    for k, wt in w.items():
        if s.get(k) is not None:
            val += wt * s[k]
            tot += wt
    return val / tot if tot else 0.0


def _reason(s):
    parts = []
    if (s.get("heat") or 0) > 0.65: parts.append("most replayed section")
    if (s.get("comments") or 0) > 0.3: parts.append("viewers mention it in comments")
    if s.get("text", 0) > 0.6: parts.append("strong hook")
    if s.get("energy", 0) > 0.65: parts.append("high energy")
    return " + ".join(parts) or "good standalone moment"


def _non_overlapping(cands, n):
    chosen = []
    for c in cands:
        if all(c.end <= o.start + 2 or c.start >= o.end - 2 for o in chosen):
            chosen.append(c)
        if len(chosen) >= n:
            break
    return chosen
