"""FLASHClips desktop app (PySide6)."""
import sys
import traceback
from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap, QIcon, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from flashclips import APP_NAME, __version__
from flashclips.config import GITHUB_URL, SUPPORT_URL, Settings
from flashclips.pipeline import Cancelled, Pipeline
from flashclips.subtitles import STYLE_NAMES
from flashclips.utils import fmt_time

ACCENT = "#FFD000"
QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 14px; color: #EDEDED; }}
QMainWindow, QDialog, QScrollArea, #root {{ background: #0F0F13; }}
QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox {{ background: #1B1B22; border: 1px solid #2C2C36;
    border-radius: 8px; padding: 8px; }}
QPushButton {{ background: #24242D; border: 1px solid #33333F; border-radius: 8px; padding: 8px 14px; }}
QPushButton:hover {{ background: #2F2F3A; }}
QPushButton#primary {{ background: {ACCENT}; color: #111; font-weight: 700; font-size: 16px;
    padding: 12px 28px; border: none; }}
QPushButton#primary:disabled {{ background: #6b5e14; }}
QPushButton#coffee {{ background: #FF813F; color: #111; font-weight: 700; border: none; }}
QProgressBar {{ background: #1B1B22; border-radius: 6px; height: 14px; text-align: center; color:#111; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
#card {{ background: #17171E; border: 1px solid #2A2A34; border-radius: 12px; }}
#score {{ color: {ACCENT}; font-size: 18px; font-weight: 800; }}
#title {{ font-weight: 700; }}
#muted {{ color: #9A9AA8; font-size: 12px; }}
#logo {{ font-size: 26px; font-weight: 900; color: {ACCENT}; }}
"""

LENGTHS = {"Auto (20–60s)": (20, 60), "Short (15–30s)": (15, 30),
           "Medium (30–60s)": (30, 60), "Long (60–90s)": (60, 90)}
LANGS = {"Auto-detect": "auto", "English": "en", "Hindi": "hi", "Gujarati": "gu", "Spanish": "es",
         "French": "fr", "German": "de", "Portuguese": "pt", "Arabic": "ar", "Swedish": "sv"}


# ------------------------------------------------------------------ worker
class Worker(QThread):
    log = Signal(str)
    progress = Signal(float, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, settings, sources=None, job=None):
        super().__init__()
        self.s, self.sources, self.job, self._cancel = settings, sources or [], job, False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            pl = Pipeline(self.s, log=self.log.emit, progress=self.progress.emit,
                          is_cancelled=lambda: self._cancel)
            if self.job:                                    # re-render one edited clip
                clip, video, words, out_dir, idx, style = self.job
                pl.render_clip(clip, video, words, out_dir, idx, style)
                self.done.emit([("edit", clip)])
                return
            from flashclips.downloader import try_update_ytdlp
            try_update_ytdlp(self.log.emit)
            results = []
            for i, src in enumerate(self.sources, 1):
                if len(self.sources) > 1:
                    self.log.emit(f"=== Video {i}/{len(self.sources)} ===")
                results.append(pl.run(src))
            self.done.emit(results)
        except Cancelled:
            self.failed.emit("Cancelled.")
        except Exception as e:
            self.log.emit(traceback.format_exc())
            self.failed.emit(_friendly(e))


def _friendly(e):
    m = str(e)
    if "Sign in to confirm" in m or "age" in m.lower():
        return ("YouTube requires sign-in for this video. Open Settings → 'Use browser login' "
                "and choose the browser where you're logged in to YouTube.")
    if "Private video" in m or "unavailable" in m.lower():
        return "This video is private or unavailable."
    return m[:600]


# ------------------------------------------------------------------ clip card
def _thumb(path, w=216):
    cap = cv2.VideoCapture(path)
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n * 0.3))
    ok, f = cap.read()
    cap.release()
    if not ok:
        return QPixmap()
    f = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
    h, wd = f.shape[:2]
    img = QImage(f.data, wd, h, 3 * wd, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(img).scaledToWidth(w, Qt.SmoothTransformation)


class ClipCard(QFrame):
    def __init__(self, clip, ctx, on_edit):
        super().__init__()
        self.setObjectName("card")
        self.setFixedWidth(240)
        self.clip, self.ctx = clip, ctx
        v = QVBoxLayout(self)
        self.img = QLabel(alignment=Qt.AlignCenter)
        self.img.setCursor(Qt.PointingHandCursor)
        self.img.mousePressEvent = lambda e: self.play()
        v.addWidget(self.img)
        self.score = QLabel(objectName="score")
        self.title = QLabel(objectName="title", wordWrap=True)
        self.meta = QLabel(objectName="muted", wordWrap=True)
        self.tags = QLabel(objectName="muted", wordWrap=True)
        for w in (self.score, self.title, self.meta, self.tags):
            v.addWidget(w)
        row = QHBoxLayout()
        for text, fn in [("▶ Play", self.play), ("✎ Edit", lambda: on_edit(self)),
                         ("📋 Caption", self.copy)]:
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row)
        b = QPushButton("📂 Show in folder"); b.clicked.connect(self.folder); v.addWidget(b)
        self.refresh()

    def refresh(self):
        c = self.clip
        self.img.setPixmap(_thumb(c.file))
        self.score.setText(f"🔥 {c.score:.0f}  ·  {fmt_time(c.duration)}")
        self.title.setText(c.title)
        self.meta.setText(f"{fmt_time(c.start)}–{fmt_time(c.end)} · {c.reason}")
        self.tags.setText(" ".join(c.hashtags))

    def play(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.clip.file))

    def folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.clip.file).parent)))

    def copy(self):
        QGuiApplication.clipboard().setText(f"{self.clip.title}\n\n{' '.join(self.clip.hashtags)}")


# ------------------------------------------------------------------ dialogs
class EditDialog(QDialog):
    def __init__(self, clip, video_dur, style, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit clip")
        f = QFormLayout(self)
        self.start = QDoubleSpinBox(maximum=video_dur or 1e6, decimals=1, singleStep=0.5, value=clip.start)
        self.end = QDoubleSpinBox(maximum=video_dur or 1e6, decimals=1, singleStep=0.5, value=clip.end)
        self.title = QLineEdit(clip.title)
        self.tags = QLineEdit(" ".join(clip.hashtags))
        self.style = QComboBox(); self.style.addItems(STYLE_NAMES); self.style.setCurrentText(style)
        f.addRow("Start (sec)", self.start); f.addRow("End (sec)", self.end)
        f.addRow("Title", self.title); f.addRow("Hashtags", self.tags); f.addRow("Caption style", self.style)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Re-render")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        f.addRow(bb)


class SettingsDialog(QDialog):
    def __init__(self, s: Settings, parent=None):
        super().__init__(parent)
        self.s = s
        self.setWindowTitle("Settings")
        f = QFormLayout(self)
        self.out = QLineEdit(s.output_dir)
        pick = QPushButton("Browse…"); pick.clicked.connect(self._pick)
        r = QHBoxLayout(); r.addWidget(self.out); r.addWidget(pick)
        self.model = QComboBox(); self.model.addItems(["auto", "tiny", "base", "small", "medium", "large-v3"])
        self.model.setCurrentText(s.whisper_model)
        self.device = QComboBox(); self.device.addItems(["auto", "cpu", "cuda"]); self.device.setCurrentText(s.device)
        self.layout_ = QComboBox(); self.layout_.addItems(["auto", "track", "fit"]); self.layout_.setCurrentText(s.layout)
        self.ai = QCheckBox("Use built-in AI for smarter moments, titles & hashtags"); self.ai.setChecked(s.use_ai)
        self.ollama = QLineEdit(s.ollama_model)
        self.comments = QCheckBox("Read timestamped YouTube comments"); self.comments.setChecked(s.use_comments)
        self.cookies = QComboBox(); self.cookies.addItems(["", "chrome", "edge", "firefox", "brave", "opera"])
        self.cookies.setCurrentText(s.browser_cookies)
        f.addRow("Output folder", r)
        f.addRow("Speech model", self.model)
        f.addRow("Device", self.device)
        f.addRow("Framing", self.layout_)
        f.addRow(self.ai)
        f.addRow("Ollama model", self.ollama)
        f.addRow(self.comments)
        f.addRow("Use browser login\n(age-restricted videos)", self.cookies)
        from flashclips import llm
        st = llm.installed_model()
        self.ai_status = QLabel(f"AI brain: ✅ {st} installed" if st else "AI brain: not installed",
                                objectName="muted")
        f.addRow(self.ai_status)
        hint = QLabel("'auto' picks the best speech model for your PC. "
                      "(Advanced: 'Ollama model' is only used if you run Ollama yourself.)",
                      objectName="muted", wordWrap=True)
        f.addRow(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._save); bb.rejected.connect(self.reject)
        f.addRow(bb)

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.out.text())
        if d:
            self.out.setText(d)

    def _save(self):
        s = self.s
        s.output_dir, s.whisper_model, s.device = self.out.text(), self.model.currentText(), self.device.currentText()
        s.layout, s.use_ai, s.ollama_model = self.layout_.currentText(), self.ai.isChecked(), self.ollama.text().strip()
        s.use_comments, s.browser_cookies = self.comments.isChecked(), self.cookies.currentText()
        s.save()
        self.accept()


# ------------------------------------------------------------------ first-run setup
class SetupWorker(QThread):
    status = Signal(str)
    progress = Signal(int)          # -1 = busy/indeterminate, 0..1000
    finished_ok = Signal(bool)

    def __init__(self, with_ai=True):
        super().__init__()
        self.with_ai, self._cancel = with_ai, False

    def run(self):
        from flashclips import llm, transcriber, updater
        ok = True
        try:
            self.status.emit("Step 1/3 · Updating YouTube downloader…"); self.progress.emit(-1)
            updater.update(lambda m: None)
            self.status.emit("Step 2/3 · Downloading speech recognition model…")
            transcriber.download_model("auto")
            if self.with_ai and not llm.installed_model():
                name = llm.recommended_model()
                gb = llm.MODELS[name][1]
                self.status.emit(f"Step 3/3 · Downloading AI brain (~{gb} GB, one time only)…")
                llm.download(name, lambda d, t: self.progress.emit(int(d / max(t, 1) * 1000)),
                             lambda: self._cancel)
        except Exception as e:
            ok = False
            self.status.emit(f"Setup could not finish ({type(e).__name__}). It will retry next time.")
        self.finished_ok.emit(ok)


class SetupDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle("Welcome to FLASHClips")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self); v.setSpacing(14)
        v.addWidget(QLabel("⚡ Welcome to FLASHClips!", objectName="logo"))
        v.addWidget(QLabel("FLASHClips is getting ready. This happens only once and needs an internet "
                           "connection. After this, everything runs on your computer.", wordWrap=True))
        self.msg = QLabel("Starting…", objectName="muted", wordWrap=True)
        self.bar = QProgressBar(); self.bar.setRange(0, 1000)
        v.addWidget(self.msg); v.addWidget(self.bar)
        self.btn = QPushButton("Please wait…", objectName="primary"); self.btn.setEnabled(False)
        self.btn.clicked.connect(self.accept)
        v.addWidget(self.btn)
        self.w = SetupWorker(with_ai=True)
        self.w.status.connect(self.msg.setText)
        self.w.progress.connect(self._prog)
        self.w.finished_ok.connect(self._done)
        self.w.start()

    def _prog(self, p):
        if p < 0:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, 1000); self.bar.setValue(p)

    def _done(self, ok):
        self.bar.setRange(0, 1000); self.bar.setValue(1000 if ok else 0)
        if ok:
            self.s.setup_done = True; self.s.save()
            self.msg.setText("✅ All set! Paste a YouTube link and press Generate.")
        self.btn.setText("Start using FLASHClips"); self.btn.setEnabled(True)

    def closeEvent(self, e):
        self.w._cancel = True
        self.w.wait(3000)
        super().closeEvent(e)

    def reject(self):
        self.w._cancel = True
        self.w.wait(3000)
        super().reject()


# ------------------------------------------------------------------ main window
class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.s = Settings.load()
        self.worker = None
        self.cards = []
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1180, 820)
        self.setAcceptDrops(True)
        icon = Path(__file__).resolve().parents[2] / "assets" / "icon.png"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))

        root = QWidget(objectName="root"); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(24, 18, 24, 18); v.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(QLabel("⚡ FLASHClips", objectName="logo"))
        top.addWidget(QLabel("Free AI shorts maker · no watermark · no limits", objectName="muted"))
        top.addStretch()
        for text, fn, name in [("⚙ Settings", self.open_settings, ""),
                               ("★ GitHub", lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)), ""),
                               ("☕ Buy me a coffee", lambda: QDesktopServices.openUrl(QUrl(SUPPORT_URL)), "coffee")]:
            b = QPushButton(text, objectName=name); b.clicked.connect(fn); top.addWidget(b)
        v.addLayout(top)

        self.inp = QPlainTextEdit(placeholderText="Paste a YouTube (or any) video link here — one per line "
                                                  "for batch mode.  You can also drop video files here.")
        self.inp.setFixedHeight(90)
        v.addWidget(self.inp)

        opts = QHBoxLayout()
        self.n = QComboBox(); self.n.addItems(["Auto"] + [str(i) for i in range(1, 16)])
        self.len = QComboBox(); self.len.addItems(LENGTHS)
        self.style = QComboBox(); self.style.addItems(STYLE_NAMES); self.style.setCurrentText(self.s.caption_style)
        self.lang = QComboBox(); self.lang.addItems(LANGS)
        add = QPushButton("＋ Add file"); add.clicked.connect(self.add_file)
        for lbl, w in [("Clips", self.n), ("Length", self.len), ("Captions", self.style), ("Language", self.lang)]:
            opts.addWidget(QLabel(lbl, objectName="muted")); opts.addWidget(w)
        opts.addWidget(add); opts.addStretch()
        self.go = QPushButton("⚡ Generate Clips", objectName="primary"); self.go.clicked.connect(self.start)
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.clicked.connect(self.cancel); self.cancel_btn.hide()
        opts.addWidget(self.cancel_btn); opts.addWidget(self.go)
        v.addLayout(opts)

        self.bar = QProgressBar(); self.bar.setRange(0, 1000); self.bar.hide()
        self.stage = QLabel(objectName="muted")
        v.addWidget(self.bar); v.addWidget(self.stage)

        self.scroll = QScrollArea(widgetResizable=True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.grid_host = QWidget(); self.grid = QGridLayout(self.grid_host)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.grid.setSpacing(14)
        self.empty = QLabel("Your clips will appear here.", objectName="muted", alignment=Qt.AlignCenter)
        self.grid.addWidget(self.empty, 0, 0)
        self.scroll.setWidget(self.grid_host)
        v.addWidget(self.scroll, 1)

        logrow = QHBoxLayout()
        self.toggle_log = QPushButton("Show log"); self.toggle_log.clicked.connect(self._toggle_log)
        logrow.addWidget(self.toggle_log)
        self.open_out = QPushButton("📂 Open output folder"); self.open_out.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.s.output_dir)))
        logrow.addWidget(self.open_out); logrow.addStretch()
        logrow.addWidget(QLabel("Only clip videos you own or have permission to use.", objectName="muted"))
        v.addLayout(logrow)
        self.log = QPlainTextEdit(readOnly=True); self.log.setFixedHeight(150); self.log.hide()
        v.addWidget(self.log)

    # --- drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            self.inp.appendPlainText(u.toLocalFile() if u.isLocalFile() else u.toString())

    def add_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose videos", "",
                                                "Videos (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)")
        for f in files:
            self.inp.appendPlainText(f)

    def _toggle_log(self):
        self.log.setVisible(not self.log.isVisible())
        self.toggle_log.setText("Hide log" if self.log.isVisible() else "Show log")

    def open_settings(self):
        SettingsDialog(self.s, self).exec()

    # --- run
    def start(self):
        sources = [l.strip() for l in self.inp.toPlainText().splitlines() if l.strip()]
        if not sources:
            QMessageBox.information(self, APP_NAME, "Paste a video link first.")
            return
        s = self.s
        s.num_clips = 0 if self.n.currentText() == "Auto" else int(self.n.currentText())
        s.min_len, s.max_len = LENGTHS[self.len.currentText()]
        s.caption_style = self.style.currentText()
        s.language = LANGS[self.lang.currentText()]
        s.save()
        self._clear()
        self._busy(True)
        self.worker = Worker(s, sources)
        self._wire(self.worker, self.show_results)
        self.worker.start()

    def _wire(self, w, on_done):
        w.log.connect(self.log.appendPlainText)
        w.log.connect(lambda m: self.stage.setText(m.splitlines()[0][:140]) if m.strip() else None)
        w.progress.connect(lambda p, st: self.bar.setValue(int(p * 1000)))
        w.done.connect(on_done)
        w.failed.connect(self.on_fail)

    def cancel(self):
        if self.worker:
            self.worker.cancel()
            self.stage.setText("Cancelling…")

    def _busy(self, b):
        self.go.setEnabled(not b); self.cancel_btn.setVisible(b); self.bar.setVisible(b)
        if b:
            self.bar.setValue(0)

    def _clear(self):
        for c in self.cards:
            c.deleteLater()
        self.cards = []
        self.empty.show()

    def show_results(self, results):
        self._busy(False)
        self.empty.hide()
        cols = max(1, (self.scroll.width() - 20) // 256)
        for out_dir, clips, src, words in results:
            for c in clips:
                card = ClipCard(c, (src, words, out_dir), self.edit_clip)
                i = len(self.cards)
                self.grid.addWidget(card, i // cols, i % cols)
                self.cards.append(card)
        total = len(self.cards)
        self.stage.setText(f"✅ {total} clips ready. Click a thumbnail to play.")

    def on_fail(self, msg):
        self._busy(False)
        self.stage.setText("❌ " + msg.splitlines()[0][:160])
        if msg != "Cancelled.":
            QMessageBox.warning(self, APP_NAME, msg)

    def edit_clip(self, card):
        src, words, out_dir = card.ctx
        d = EditDialog(card.clip, src.duration, self.s.caption_style, self)
        if not d.exec():
            return
        c = card.clip
        if d.end.value() - d.start.value() < 3:
            QMessageBox.warning(self, APP_NAME, "Clip must be at least 3 seconds.")
            return
        old = Path(c.file)
        c.start, c.end = d.start.value(), d.end.value()
        c.title, c.hashtags = d.title.text().strip() or c.title, d.tags.text().split()
        idx = int(old.name[:2]) if old.name[:2].isdigit() else self.cards.index(card) + 1
        old.unlink(missing_ok=True)
        self._busy(True)
        self.worker = Worker(self.s, job=(c, src.path, words, out_dir, idx, d.style.currentText()))
        self._wire(self.worker, lambda _: (self._busy(False), card.refresh(),
                                           self.stage.setText("✅ Clip updated.")))
        self.worker.start()


class UpdateCheck(QThread):
    found = Signal(str)

    def run(self):
        try:
            import requests
            api = GITHUB_URL.replace("github.com", "api.github.com/repos") + "/releases/latest"
            tag = requests.get(api, timeout=5).json().get("tag_name", "").lstrip("v")
            if tag and tuple(map(int, tag.split("."))) > tuple(map(int, __version__.split("."))):
                self.found.emit(tag)
        except Exception:
            pass


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FLASHClips.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(QSS)
    from flashclips.utils import setup_bundled_tools
    setup_bundled_tools()
    w = Main(); w.show()
    from flashclips import llm
    if not w.s.setup_done or (w.s.use_ai and not llm.installed_model()):
        SetupDialog(w.s, w).exec()
    upd = UpdateCheck()
    upd.found.connect(lambda tag: QMessageBox.information(
        w, APP_NAME, f"FLASHClips {tag} is available (keeps YouTube downloads working).\n"
                     f"Download it from GitHub → Releases.") or
        QDesktopServices.openUrl(QUrl(GITHUB_URL + "/releases/latest")))
    upd.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
