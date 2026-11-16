"""Animated word-by-word captions (ASS format, burned in by FFmpeg/libass)."""
from pathlib import Path

W, H = 1080, 1920


def _c(rgb_hex: str) -> str:            # "#RRGGBB" -> ASS "&H00BBGGRR"
    h = rgb_hex.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


STYLES = {
    "Bold Pop":     dict(font="Arial Black", size=92, color="#FFFFFF", hl="#FFE600", outline=7,
                         shadow=3, upper=True, pop=118, words=3, box=False),
    "Karaoke Green":dict(font="Arial Black", size=88, color="#FFFFFF", hl="#3CFF5A", outline=7,
                         shadow=2, upper=True, pop=112, words=3, box=False),
    "Neon":         dict(font="Arial Black", size=86, color="#FFFFFF", hl="#00F0FF", outline=5,
                         shadow=0, upper=True, pop=115, words=3, box=False, outline_col="#7B00FF"),
    "Clean":        dict(font="Arial", size=72, color="#FFFFFF", hl="#FFFFFF", outline=4,
                         shadow=2, upper=False, pop=100, words=5, box=False),
    "Boxed":        dict(font="Arial", size=70, color="#FFFFFF", hl="#FFD000", outline=14,
                         shadow=0, upper=False, pop=100, words=4, box=True),
}
STYLE_NAMES = list(STYLES)


def _t(s: float) -> str:
    s = max(0.0, s)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def _esc(t: str) -> str:
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def _chunks(words, max_words):
    chunk = []
    for w in words:
        chunk.append(w)
        end_sent = w.text.endswith((".", "!", "?", ","))
        if len(chunk) >= max_words or end_sent or sum(len(x.text) for x in chunk) > 18:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def write_ass(words, clip_start: float, clip_end: float, out: Path, style="Bold Pop",
              margin_v=560) -> Path:
    st = STYLES.get(style, STYLES["Bold Pop"])
    outline_col = _c(st.get("outline_col", "#000000"))
    back = "&H80000000" if st["box"] else "&H00000000"
    border_style = 3 if st["box"] else 1
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['size']},{_c(st['color'])},&H000000FF,{outline_col if not st['box'] else back},{back},-1,0,0,0,100,100,2,0,{border_style},{st['outline']},{st['shadow']},2,70,70,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    ws = [w for w in words if w.end > clip_start and w.start < clip_end]
    hl = _c(st["hl"])
    chunks = list(_chunks(ws, st["words"]))
    for ci, chunk in enumerate(chunks):
        nxt = chunks[ci + 1][0].start if ci + 1 < len(chunks) else 1e9
        texts = [_esc(w.text.upper() if st["upper"] else w.text) for w in chunk]
        for i, w in enumerate(chunk):
            a = w.start - clip_start
            b = (chunk[i + 1].start if i + 1 < len(chunk) else min(w.end + 0.25, nxt)) - clip_start
            b = min(b, clip_end - clip_start)
            parts = []
            for j, t in enumerate(texts):
                if j == i:
                    pop = (f"\\fscx{st['pop']}\\fscy{st['pop']}\\t(0,90,\\fscx100\\fscy100)"
                           if st["pop"] != 100 else "")
                    parts.append(f"{{\\c{hl}{pop}}}{t}{{\\r}}")
                else:
                    parts.append(t)
            if b > a:
                lines.append(f"Dialogue: 0,{_t(a)},{_t(b)},Cap,,0,0,0,,{' '.join(parts)}")
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out
