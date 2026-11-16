<p align="center"><img src="assets/icon.png" width="120"></p>
<h1 align="center">⚡ FLASHClips</h1>
<p align="center"><b>Free, open-source AI clip maker.</b> Paste a YouTube link → get viral 9:16 shorts with animated subtitles.<br>
For TikTok, Instagram Reels, YouTube Shorts &amp; Facebook. No account. No watermark. No limits. Free forever.</p>
<p align="center"><a href="https://www.buymeacoffee.com/YOUR_NAME">☕ Buy me a coffee</a> if FLASHClips saves you time!</p>

---

## ✨ Features
- 🔗 **Paste any link**: YouTube, Twitch VODs, Vimeo, X and 1000+ sites (via yt-dlp), or drop local files
- 🧠 **Finds the best moments** with 5 signals:
  YouTube *Most Replayed* heatmap · local AI transcript scoring · audio energy · timestamped comments · clean sentence boundaries
- 📱 **Smart 9:16 reframing**: face tracking, two-speaker split screen, or blurred-background fit
- 💬 **Animated word-by-word captions**: 5 styles (Bold Pop, Karaoke Green, Neon, Clean, Boxed)
- 🌍 **~100 languages** (Whisper), including Hindi, Gujarati and Spanish
- 🏷 **Auto titles + hashtags** for every clip
- 📦 **Batch mode**: paste several links, one per line
- ✎ **Quick editor**: adjust start/end, title and caption style, then re-render
- 🔒 **100% local & private**: your videos never leave your PC

## 📥 Download (Windows)
Go to **[Releases](../../releases/latest)** and download **FLASHClips-Setup.exe** (installer) or the portable `.zip`.

**Everything is included.** No Python, FFmpeg, Ollama or anything else to install.
On first launch, FLASHClips runs a one-time automatic setup: it downloads the speech model and the
built-in AI brain (about 1–2 GB, picked automatically for your PC's memory). After that it works offline.
The YouTube downloader updates itself silently, so links keep working.

> An NVIDIA GPU makes transcription much faster, but any normal PC works.

## 🧑‍💻 Run from source (Windows / macOS / Linux)
```bash
git clone https://github.com/YOUR_USERNAME/FLASHClips.git
cd FLASHClips
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_flashclips.py                              # desktop app
python run_flashclips.py "https://youtu.be/VIDEO" -n 5 --style "Neon"   # command line
```
Requires Python 3.10+ and FFmpeg with libass (bundled in the Windows release).

## ⚙️ How it picks moments
| Signal | Weight | What it captures |
|---|---|---|
| Built-in AI (Qwen 2.5, llama.cpp) | high | hook, emotion, humour, surprise, standalone value |
| Most Replayed heatmap | high | parts real viewers rewatch |
| Comments with timestamps | medium | moments viewers talk about |
| Transcript heuristics | medium | hook words, questions, numbers, avoids starting mid-thought |
| Audio energy & pace | low | laughter, excitement, raised voices |

## ⚖️ Responsible use
Only clip videos you own or have permission to use. Respect creators and platform terms of service.

## ❤️ Support
FLASHClips is and always will be free. If it helps you, consider [buying me a coffee](https://www.buymeacoffee.com/YOUR_NAME) ☕

## 📄 License
MIT © Utsav Patel
