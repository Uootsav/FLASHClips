"""Command line: python -m flashclips <link-or-file> [more links…]"""
import argparse

from flashclips import __version__
from flashclips.config import Settings
from flashclips.downloader import try_update_ytdlp
from flashclips.pipeline import Pipeline
from flashclips.subtitles import STYLE_NAMES


def main():
    ap = argparse.ArgumentParser(prog="flashclips", description="FLASHClips – free AI shorts maker")
    ap.add_argument("sources", nargs="+", help="YouTube/any video links or local files")
    ap.add_argument("-n", "--clips", type=int, help="number of clips (default auto)")
    ap.add_argument("--style", choices=STYLE_NAMES)
    ap.add_argument("--model", help="whisper model: tiny/base/small/medium/large-v3")
    ap.add_argument("--layout", choices=["auto", "track", "fit"])
    ap.add_argument("--out", help="output folder")
    ap.add_argument("--min", type=int); ap.add_argument("--max", type=int)
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args()
    s = Settings.load()
    for attr, val in [("num_clips", a.clips), ("caption_style", a.style), ("whisper_model", a.model),
                      ("layout", a.layout), ("output_dir", a.out), ("min_len", a.min), ("max_len", a.max)]:
        if val is not None:
            setattr(s, attr, val)
    if a.no_ai:
        s.use_ai = False
    try_update_ytdlp()
    last = [-1]

    def prog(p, stage):
        pct = int(p * 100)
        if pct != last[0]:
            last[0] = pct
            print(f"\r[{('#' * (pct // 4)).ljust(25)}] {pct:3d}% {stage:<10}", end="", flush=True)

    for src in a.sources:
        out, clips, *_ = Pipeline(s, log=lambda m: print("\n" + m), progress=prog).run(src)
        print()
        for c in clips:
            print(f"  🔥 {c.score:.0f}  {c.title}  →  {c.file}")
