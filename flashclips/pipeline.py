"""Link -> best moments -> 9:16 clips with captions, titles & hashtags."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from flashclips import analyzer, downloader, reframer, subtitles, transcriber
from flashclips.config import Settings
from flashclips.utils import extract_audio, safe_name

STAGES = [("download", 0.15), ("transcribe", 0.35), ("analyze", 0.15), ("render", 0.35)]


class Cancelled(Exception):
    pass


class Pipeline:
    def __init__(self, settings: Settings, log=print, progress=lambda p, stage: None,
                 is_cancelled=lambda: False):
        self.s, self.log, self._progress, self.cancelled = settings, log, progress, is_cancelled

    def _stage(self, name):
        base = 0.0
        for n, w in STAGES:
            if n == name:
                weight = w
                break
            base += w

        def f(p):
            if self.cancelled():
                raise Cancelled()
            self._progress(base + weight * max(0.0, min(p, 1.0)), name)
        return f

    def run(self, source: str):
        s = self.s
        key = hashlib.md5(source.strip().encode()).hexdigest()[:10]
        work = Path(s.output_dir) / ".work" / key
        work.mkdir(parents=True, exist_ok=True)

        p = self._stage("download"); p(0)
        src = downloader.fetch(source, work, s.use_comments, s.browser_cookies, self.log, p)
        p(1)

        p = self._stage("transcribe"); p(0)
        cache = work / "transcript.json"
        wav = extract_audio(src.path, work / "audio.wav")
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            segs = [transcriber.Segment(d["start"], d["end"], d["text"],
                                        [transcriber.Word(**w) for w in d["words"]]) for d in data["segs"]]
            lang = data["lang"]
            self.log("Using cached transcript.")
        else:
            self.log("Transcribing speech…")
            segs, lang = transcriber.transcribe(wav, s.whisper_model, s.device, s.language,
                                                self.log, p, src.duration)
            cache.write_text(json.dumps({"lang": lang, "segs": [asdict(x) for x in segs]}),
                             encoding="utf-8")
        p(1)

        p = self._stage("analyze"); p(0)
        self.log("Finding the best moments…")
        clips = analyzer.find_best(segs, wav, src, s, lang, self.log, p)
        p(1)

        out_dir = Path(s.output_dir) / safe_name(src.title)
        out_dir.mkdir(parents=True, exist_ok=True)
        p = self._stage("render")
        all_words = [w for sg in segs for w in sg.words]
        for i, c in enumerate(clips, 1):
            p((i - 1) / len(clips))
            self.log(f"Rendering clip {i}/{len(clips)}  (score {c.score:.0f}) – {c.title}")
            self.render_clip(c, src.path, all_words, out_dir, i)
        p(1)

        meta = {"source": source, "title": src.title, "video": str(src.path), "language": lang,
                "clips": [{k: v for k, v in asdict(c).items() if k != "words"} for c in clips]}
        (out_dir / "clips.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
        (out_dir / "captions_and_hashtags.txt").write_text("\n\n".join(
            f"#{i} [{c.score:.0f}] {c.title}\n{' '.join(c.hashtags)}\n{Path(c.file).name}"
            for i, c in enumerate(clips, 1)), encoding="utf-8")
        self.log(f"Done! {len(clips)} clips saved to {out_dir}")
        return out_dir, clips, src, all_words

    def render_clip(self, clip, video: Path, all_words, out_dir: Path, idx: int, style=None):
        name = f"{idx:02d}_{safe_name(clip.title, 40) or 'clip'}"
        ass = out_dir / f"{name}.ass"
        subtitles.write_ass(all_words, clip.start, clip.end, ass, style or self.s.caption_style)
        out = out_dir / f"{name}.mp4"
        layout = reframer.render(Path(video), clip.start, clip.end, ass, out, self.s.layout, self.log)
        ass.unlink(missing_ok=True)
        clip.file = str(out)
        clip.signals["layout"] = layout
        return out
