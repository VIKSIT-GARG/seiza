"""Screen color picker, region selector, OCR bridge, and screen recording helper."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple


def _capture_full_screen() -> Path:
    tmp = Path(tempfile.mkstemp(prefix="seiza_screen_", suffix=".png")[1])
    subprocess.run(["grim", str(tmp)], check=True)
    return tmp


def _notify(summary: str, body: str) -> None:
    if shutil.which("noctalia"):
        subprocess.run(["noctalia", "msg", "notification-show", summary, body], capture_output=True)


def pick_screen_color() -> Optional[str]:
    """Freeze screen with grim and let user pick any pixel in a PyQt6 overlay."""
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
    from PyQt6.QtWidgets import QApplication, QWidget

    snap_path = _capture_full_screen()
    try:
        app = QApplication.instance() or QApplication(["seiza-color"])
        pixmap = QPixmap(str(snap_path))
        img = pixmap.toImage()
        chosen: Dict[str, Optional[str]] = {"hex": None}

        class ColorOverlay(QWidget):
            def __init__(self) -> None:
                super().__init__()
                self.pos_cur = QPoint(pixmap.width() // 2, pixmap.height() // 2)
                self.cur_color = QColor("#C4B5FD")
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.WindowStaysOnTopHint
                    | Qt.WindowType.Tool
                )
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.setMouseTracking(True)
                self.setGeometry(app.primaryScreen().geometry())

            def mouseMoveEvent(self, ev) -> None:
                self.pos_cur = ev.position().toPoint()
                sx = max(0, min(img.width() - 1, round(self.pos_cur.x() * pixmap.width() / max(1, self.width()))))
                sy = max(0, min(img.height() - 1, round(self.pos_cur.y() * pixmap.height() / max(1, self.height()))))
                self.cur_color = img.pixelColor(sx, sy)
                self.update()

            def mousePressEvent(self, ev) -> None:
                if ev.button() == Qt.MouseButton.LeftButton:
                    self.mouseMoveEvent(ev)
                    chosen["hex"] = self.cur_color.name().upper()
                self.close()

            def keyPressEvent(self, ev) -> None:
                if ev.key() == Qt.Key.Key_Escape:
                    self.close()

            def paintEvent(self, _ev) -> None:
                p = QPainter(self)
                p.drawPixmap(self.rect(), pixmap)
                # Subtle floating color pill near cursor
                hx = self.cur_color.name().upper()
                rgb = f"rgb({self.cur_color.red()}, {self.cur_color.green()}, {self.cur_color.blue()})"
                bx = min(self.width() - 210, self.pos_cur.x() + 18)
                by = min(self.height() - 62, self.pos_cur.y() + 18)
                p.setBrush(QColor(13, 16, 29, 232))
                p.setPen(QPen(QColor("#C4B5FD"), 1.5))
                p.drawRoundedRect(bx, by, 196, 52, 10, 10)
                p.setBrush(self.cur_color)
                p.setPen(QPen(QColor("#EEF1FA"), 1))
                p.drawRoundedRect(bx + 10, by + 11, 30, 30, 6, 6)
                p.setPen(QColor("#EEF1FA"))
                p.drawText(bx + 50, by + 23, f"{hx}  (Click to copy)")
                p.setPen(QColor("#A6B0D0"))
                p.drawText(bx + 50, by + 40, rgb)

        w = ColorOverlay()
        w.showFullScreen()
        app.exec()

        if chosen["hex"]:
            subprocess.run(["wl-copy"], input=chosen["hex"], text=True, check=True)
            _notify("seiza. Color Picker", f"Copied {chosen['hex']} to clipboard")
        return chosen["hex"]
    finally:
        snap_path.unlink(missing_ok=True)


def select_region_image() -> Optional[Path]:
    """Capture screen and allow drag selection to cropped temporary PNG."""
    from PyQt6.QtCore import QPoint, QRect, Qt
    from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
    from PyQt6.QtWidgets import QApplication, QWidget

    snap_path = _capture_full_screen()
    app = QApplication.instance() or QApplication(["seiza-region"])
    pixmap = QPixmap(str(snap_path))
    rect_out: Dict[str, Optional[QRect]] = {"rect": None}

    class RegionOverlay(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.start: Optional[QPoint] = None
            self.end: Optional[QPoint] = None
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
            )
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setGeometry(app.primaryScreen().geometry())

        def mousePressEvent(self, ev) -> None:
            if ev.button() == Qt.MouseButton.LeftButton:
                self.start = ev.position().toPoint()
                self.end = self.start
                self.update()
            elif ev.button() == Qt.MouseButton.RightButton:
                self.close()

        def mouseMoveEvent(self, ev) -> None:
            if self.start is not None:
                self.end = ev.position().toPoint()
                self.update()

        def mouseReleaseEvent(self, ev) -> None:
            if self.start is not None and ev.button() == Qt.MouseButton.LeftButton:
                self.end = ev.position().toPoint()
                r = QRect(self.start, self.end).normalized()
                if r.width() >= 8 and r.height() >= 8:
                    rect_out["rect"] = r
                self.close()

        def keyPressEvent(self, ev) -> None:
            if ev.key() == Qt.Key.Key_Escape:
                self.close()

        def paintEvent(self, _ev) -> None:
            p = QPainter(self)
            p.drawPixmap(self.rect(), pixmap)
            p.fillRect(self.rect(), QColor(9, 11, 21, 125))
            if self.start and self.end:
                r = QRect(self.start, self.end).normalized()
                sx = pixmap.width() / max(1, self.width())
                sy = pixmap.height() / max(1, self.height())
                src = QRect(int(r.x() * sx), int(r.y() * sy), int(r.width() * sx), int(r.height() * sy))
                p.drawPixmap(r, pixmap, src)
                p.setPen(QPen(QColor("#C4B5FD"), 2))
                p.drawRect(r)
                p.setBrush(QColor(13, 16, 29, 220))
                p.drawRoundedRect(r.x(), max(8, r.y() - 28), 160, 22, 6, 6)
                p.setPen(QColor("#EEF1FA"))
                p.drawText(r.x() + 8, max(23, r.y() - 12), f"{r.width()}×{r.height()} · OCR/Select")
            else:
                p.setBrush(QColor(13, 16, 29, 220))
                p.setPen(QPen(QColor("#28304D"), 1))
                p.drawRoundedRect(24, 24, 340, 34, 10, 10)
                p.setPen(QColor("#EEF1FA"))
                p.drawText(38, 46, "seiza. · Drag a region (Esc to cancel)")

    try:
        w = RegionOverlay()
        w.showFullScreen()
        app.exec()
        r = rect_out["rect"]
        if not r:
            return None
        sx = pixmap.width() / max(1, w.width())
        sy = pixmap.height() / max(1, w.height())
        cropped = pixmap.copy(int(r.x() * sx), int(r.y() * sy), int(r.width() * sx), int(r.height() * sy))
        out_path = Path(tempfile.mkstemp(prefix="seiza_crop_", suffix=".png")[1])
        cropped.save(str(out_path), "PNG")
        return out_path
    finally:
        snap_path.unlink(missing_ok=True)


def run_ocr(image_path: Optional[Path] = None) -> Tuple[bool, str]:
    created_temp = False
    target = image_path
    if target is None:
        target = select_region_image()
        created_temp = True
        if target is None:
            return False, "Selection cancelled."

    try:
        if shutil.which("tesseract"):
            res = subprocess.run(
                ["tesseract", str(target), "stdout", "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=15.0,
            )
            txt = res.stdout.strip()
            if txt:
                subprocess.run(["wl-copy"], input=txt, text=True, check=True)
                _notify("seiza. OCR", f"Copied {len(txt)} characters to clipboard")
                return True, txt
            _notify("seiza. OCR", "No text recognized in selected region.")
            return False, "No text recognized in selected region."

        # Copy cropped region PNG to clipboard gracefully and inform clearly about missing tesseract
        raw = target.read_bytes()
        subprocess.run(["wl-copy", "--type", "image/png"], input=raw, check=False)
        msg = (
            "Local OCR engine (tesseract) is not installed yet.\n"
            "Selected region image was copied to clipboard instead.\n"
            "Enable full text OCR anytime with:\n"
            "  sudo pacman -S tesseract tesseract-data-eng"
        )
        _notify("seiza. OCR Engine Missing", "Copied region image. Install: sudo pacman -S tesseract tesseract-data-eng")
        return False, msg
    finally:
        if created_temp and target is not None:
            target.unlink(missing_ok=True)


def toggle_recording(action: str = "toggle") -> str:
    if not shutil.which("noctalia"):
        return "Noctalia shell IPC unavailable"
    cmd_map = {
        "toggle": "toggle",
        "replay": "replay-toggle",
        "save-replay": "save-replay",
    }
    ev = cmd_map.get(action, "toggle")
    # Try official Noctalia screen_recorder plugin channel
    r = subprocess.run(
        ["noctalia", "msg", "plugin", "noctalia/screen_recorder:recorder", ev],
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return f"Screen recorder triggered ({ev})"
    # Fallback launch via shortcut/panel or gpu-screen-recorder check
    if shutil.which("gpu-screen-recorder"):
        if subprocess.run(["pgrep", "-x", "gpu-screen-recorder"], capture_output=True).returncode == 0:
            subprocess.run(["pkill", "-SIGINT", "-x", "gpu-screen-recorder"], capture_output=True)
            _notify("seiza. Screen Recorder", "Stopped recording")
            return "Stopped gpu-screen-recorder"
        rec_dir = Path.home() / "Videos/Recordings"
        rec_dir.mkdir(parents=True, exist_ok=True)
        _notify("seiza. Screen Recorder", "Use Noctalia Control Center 'Record Screen' shortcut for portal capture")
        return "Triggered Noctalia Control Center screen recorder hint"
    return "gpu-screen-recorder not installed"
