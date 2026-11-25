"""seiza. Wayland / Niri Display Manager with visual layout, wl-mirror & 15s auto-revert."""

from __future__ import annotations

import sys
from typing import Dict, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import displays
from .theme import PAL, build_qt_qss


class MonitorCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.outputs: List[Dict] = []
        self.selected_name: str = "eDP-1"
        self.setMinimumHeight(185)

    def set_outputs(self, outputs: List[Dict], selected: str) -> None:
        self.outputs = outputs
        self.selected_name = selected
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(PAL["surface_sunken"]))
        p.setPen(QPen(QColor(PAL["border"]), 1))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

        enabled = [o for o in self.outputs if o.get("enabled")]
        if not enabled:
            p.setPen(QColor(PAL["muted"]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No enabled displays detected")
            return

        min_x = min(o["x"] for o in enabled)
        min_y = min(o["y"] for o in enabled)
        max_x = max(o["x"] + max(640, o["width"]) for o in enabled)
        max_y = max(o["y"] + max(480, o["height"]) for o in enabled)
        span_w = max(1, max_x - min_x)
        span_h = max(1, max_y - min_y)

        pad = 24
        avail_w = max(100, self.width() - pad * 2)
        avail_h = max(80, self.height() - pad * 2)
        scale = min(avail_w / span_w, avail_h / span_h)
        ox = pad + (avail_w - span_w * scale) / 2
        oy = pad + (avail_h - span_h * scale) / 2

        for o in enabled:
            rx = int(ox + (o["x"] - min_x) * scale)
            ry = int(oy + (o["y"] - min_y) * scale)
            rw = int(max(90, o["width"] * scale))
            rh = int(max(60, o["height"] * scale))
            sel = o["name"] == self.selected_name
            fill = QColor(30, 36, 64) if sel else QColor(21, 25, 46)
            stroke = QColor(PAL["primary"] if sel else PAL["secondary"])
            p.setBrush(fill)
            p.setPen(QPen(stroke, 2 if sel else 1.2))
            p.drawRoundedRect(rx, ry, rw, rh, 8, 8)
            p.setPen(QColor(PAL["text"]))
            p.drawText(rx + 10, ry + 24, f"{o['name']}")
            p.setPen(QColor(PAL["muted"]))
            p.drawText(rx + 10, ry + 42, f"{o['current_mode']}")
            p.drawText(rx + 10, ry + 58, f"scale {o['scale']} · ({o['x']},{o['y']})")


class ConfirmRevertDialog(QDialog):
    def __init__(self, summary: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keep Display Layout?")
        self.setModal(True)
        self.seconds = 15
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lbl = QLabel(f"Applied: {summary}")
        lbl.setStyleSheet("font-weight: 700;")
        self.lbl_count = QLabel(f"Reverting automatically to previous layout in {self.seconds}s...")
        self.lbl_count.setStyleSheet(f"color: {PAL['amber']};")
        lay.addWidget(lbl)
        lay.addWidget(self.lbl_count)

        btns = QHBoxLayout()
        btn_keep = QPushButton("Keep Changes")
        btn_keep.setObjectName("PrimaryBtn")
        btn_revert = QPushButton("Revert Now")
        btn_revert.setObjectName("DangerBtn")
        btn_keep.clicked.connect(self.accept)
        btn_revert.clicked.connect(self.reject)
        btns.addWidget(btn_revert)
        btns.addWidget(btn_keep)
        lay.addLayout(btns)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self) -> None:
        self.seconds -= 1
        if self.seconds <= 0:
            self.timer.stop()
            self.reject()
            return
        self.lbl_count.setText(f"Reverting automatically to previous layout in {self.seconds}s...")


class DisplayWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("seiza. // Display Manager")
        self.resize(860, 620)
        self.outputs: List[Dict] = []

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        hdr = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("✦ seiza.  //  Display Studio")
        t.setObjectName("BrandTitle")
        s = QLabel("Niri Wayland multi-monitor layout, scaling, wl-mirror & safe 15s auto-revert")
        s.setObjectName("BrandTagline")
        col.addWidget(t)
        col.addWidget(s)
        hdr.addLayout(col)
        hdr.addStretch()
        btn_ref = QPushButton("Detect Outputs")
        btn_ref.clicked.connect(self.refresh)
        hdr.addWidget(btn_ref)
        lay.addLayout(hdr)

        self.canvas = MonitorCanvas()
        lay.addWidget(self.canvas)

        # Quick Modes card
        quick = QFrame()
        quick.setObjectName("Card")
        ql = QVBoxLayout(quick)
        ql.setContentsMargins(14, 12, 14, 12)
        ql.addWidget(QLabel("QUICK TOPOLOGY PRESETS"))
        qrow = QHBoxLayout()
        for label, fn in [
            ("Internal Only", self._act_internal),
            ("Extend Right", lambda: self._act_extend("right")),
            ("Extend Above", lambda: self._act_extend("above")),
            ("Mirror (wl-mirror)", self._act_mirror),
            ("Presentation", self._act_presentation),
        ]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            qrow.addWidget(b)
        ql.addLayout(qrow)
        lay.addWidget(quick)

        # Per-output controls + profiles
        bot = QHBoxLayout()
        bot.setSpacing(12)

        cfg = QFrame()
        cfg.setObjectName("Card")
        cl = QGridLayout(cfg)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.addWidget(QLabel("Output"), 0, 0)
        self.cmb_out = QComboBox()
        self.cmb_out.currentTextChanged.connect(self._on_select_output)
        cl.addWidget(self.cmb_out, 0, 1)

        cl.addWidget(QLabel("Mode / Hz"), 1, 0)
        self.cmb_mode = QComboBox()
        cl.addWidget(self.cmb_mode, 1, 1)

        cl.addWidget(QLabel("Scale"), 2, 0)
        self.cmb_scale = QComboBox()
        for sc in ("1.0", "1.25", "1.5", "1.75", "2.0"):
            self.cmb_scale.addItem(sc)
        cl.addWidget(self.cmb_scale, 2, 1)

        btn_apply_out = QPushButton("Apply Mode && Scale (Safe Confirm)")
        btn_apply_out.setObjectName("PrimaryBtn")
        btn_apply_out.clicked.connect(self._act_apply_selected)
        cl.addWidget(btn_apply_out, 3, 0, 1, 2)
        bot.addWidget(cfg, 1)

        prof = QFrame()
        prof.setObjectName("Card")
        pl = QVBoxLayout(prof)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.addWidget(QLabel("PROFILES & PERSISTENCE"))
        self.cmb_prof = QComboBox()
        pl.addWidget(self.cmb_prof)
        prow = QHBoxLayout()
        btn_save_p = QPushButton("Save Profile")
        btn_save_p.clicked.connect(self._save_profile)
        btn_apply_p = QPushButton("Apply Profile")
        btn_apply_p.clicked.connect(self._apply_profile)
        prow.addWidget(btn_save_p)
        prow.addWidget(btn_apply_p)
        pl.addLayout(prow)
        btn_persist = QPushButton("Save Current Layout to ~/.config/niri/cfg/display.kdl")
        btn_persist.clicked.connect(self._save_display_kdl)
        pl.addWidget(btn_persist)
        bot.addWidget(prof, 1)

        lay.addLayout(bot)
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet(f"color: {PAL['muted']};")
        lay.addWidget(self.lbl_status)

        self.refresh()

    def refresh(self) -> None:
        self.outputs = displays.get_outputs()
        cur = self.cmb_out.currentText()
        self.cmb_out.blockSignals(True)
        self.cmb_out.clear()
        for o in self.outputs:
            self.cmb_out.addItem(o["name"])
        if cur and any(o["name"] == cur for o in self.outputs):
            self.cmb_out.setCurrentText(cur)
        self.cmb_out.blockSignals(False)
        self._on_select_output(self.cmb_out.currentText())

        self.cmb_prof.clear()
        self.cmb_prof.addItems(sorted(displays.load_profiles().keys()))
        self.lbl_status.setText(f"Detected {len(self.outputs)} display connector(s).")

    def _on_select_output(self, name: str) -> None:
        self.canvas.set_outputs(self.outputs, name)
        out = next((o for o in self.outputs if o["name"] == name), None)
        if not out:
            return
        self.cmb_mode.clear()
        self.cmb_mode.addItems(out["modes"] or [out["current_mode"] or ""])
        if out["current_mode"]:
            self.cmb_mode.setCurrentText(out["current_mode"])
        self.cmb_scale.setCurrentText(str(out["scale"]))

    def _safe_run(self, fn, label: str) -> None:
        snap = displays.snapshot_state()
        try:
            msg = fn()
        except Exception as e:
            QMessageBox.warning(self, "Display Action", str(e))
            return
        self.refresh()
        dlg = ConfirmRevertDialog(msg, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            displays.restore_snapshot(snap)
            self.refresh()
            self.lbl_status.setText(f"Reverted changes ({label}).")
        else:
            self.lbl_status.setText(f"Confirmed: {msg}")

    def _external_name(self) -> str:
        prim = displays.primary_output_name()
        ext = next((o["name"] for o in self.outputs if o["name"] != prim), None)
        if not ext:
            raise RuntimeError("No external monitor detected via Niri outputs.")
        return ext

    def _act_internal(self) -> None:
        self._safe_run(displays.set_internal_only, "Internal Only")

    def _act_extend(self, side: str) -> None:
        self._safe_run(lambda: displays.set_extend(displays.primary_output_name(), self._external_name(), side), f"Extend {side}")

    def _act_mirror(self) -> None:
        self._safe_run(lambda: displays.start_mirror(displays.primary_output_name(), self._external_name()), "Mirror")

    def _act_presentation(self) -> None:
        self._safe_run(displays.set_presentation, "Presentation")

    def _act_apply_selected(self) -> None:
        name = self.cmb_out.currentText()
        mode = self.cmb_mode.currentText()
        scale = self.cmb_scale.currentText()
        if not name:
            return

        def _apply() -> str:
            displays.run_niri_output([name, "on"])
            if mode:
                displays.run_niri_output([name, "mode", mode])
            displays.run_niri_output([name, "scale", scale])
            return f"{name} -> {mode} @ {scale}x"

        self._safe_run(_apply, f"{name} mode/scale")

    def _save_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Display Profile", "Profile name (e.g. desk-dual):")
        if ok and name.strip():
            displays.save_profile(name.strip())
            self.refresh()
            self.lbl_status.setText(f"Saved display profile '{name.strip()}'.")

    def _apply_profile(self) -> None:
        name = self.cmb_prof.currentText()
        if name:
            self._safe_run(lambda: displays.apply_profile(name), f"Profile {name}")

    def _save_display_kdl(self) -> None:
        p = displays.write_persistent_display_kdl()
        self.lbl_status.setText(f"Persisted configuration to {p}")


def launch_display_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setDesktopFileName("seiza-display")
    app.setStyleSheet(build_qt_qss())
    win = DisplayWindow()
    win.show()
    return app.exec()
