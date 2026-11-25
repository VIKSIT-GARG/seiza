"""seiza. Focus Studio — Quick Notes, Pomodoro Timer, Snippets & Keybind Explorer."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from typing import Dict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import productivity
from .theme import PAL, build_qt_qss


class FocusStudioWindow(QMainWindow):
    def __init__(self, initial_tab: str = "notes") -> None:
        super().__init__()
        self.setWindowTitle("seiza. // Focus Studio")
        self.resize(940, 640)

        self.pomo_total = 25 * 60
        self.pomo_rem = 25 * 60
        self.pomo_mode = "Focus Session"
        self.pomo_running = False
        self.pomo_timer = QTimer(self)
        self.pomo_timer.setInterval(1000)
        self.pomo_timer.timeout.connect(self._pomo_tick)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        hdr = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("✦ seiza.  //  Focus Studio")
        t.setObjectName("BrandTitle")
        s = QLabel("Quick Notes, Pomodoro Timer, Sensitive-Safe Clipboard Snippets & Keybind Explorer")
        s.setObjectName("BrandTagline")
        col.addWidget(t)
        col.addWidget(s)
        hdr.addLayout(col)
        hdr.addStretch()

        self.tabs_map = {"notes": 0, "pomodoro": 1, "snippets": 2, "keys": 3}
        self.tab_btns: Dict[int, QPushButton] = {}
        for idx, label in [(0, "Notes"), (1, "Pomodoro"), (2, "Snippets && Clipboard"), (3, "Keybinds")]:
            b = QPushButton(label)
            b.setObjectName("NavTab")
            b.clicked.connect(lambda _c=False, i=idx: self._switch_tab(i))
            self.tab_btns[idx] = b
            hdr.addWidget(b)
        outer.addLayout(hdr)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_notes_tab())
        self.stack.addWidget(self._build_pomodoro_tab())
        self.stack.addWidget(self._build_snippets_tab())
        self.stack.addWidget(self._build_keys_tab())

        QShortcut(QKeySequence("Ctrl+S"), self, self._save_notes)
        self._switch_tab(self.tabs_map.get(initial_tab, 0))

    def _switch_tab(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        for i, b in self.tab_btns.items():
            b.setProperty("active", "true" if i == idx else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    # ── Notes ──
    def _build_notes_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        top = QHBoxLayout()
        self.lbl_note_status = QLabel("Saved locally to ~/.local/state/seiza/notes.md (Ctrl+S)")
        self.lbl_note_status.setStyleSheet(f"color: {PAL['muted']};")
        btn_ts = QPushButton("Insert Timestamp")
        btn_ts.clicked.connect(self._insert_timestamp)
        btn_save = QPushButton("Save Notes")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self._save_notes)
        top.addWidget(self.lbl_note_status)
        top.addStretch()
        top.addWidget(btn_ts)
        top.addWidget(btn_save)
        lay.addLayout(top)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(productivity.load_notes())
        self.editor.setStyleSheet("font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 13px; padding: 12px;")
        lay.addWidget(self.editor, 1)
        return w

    def _insert_timestamp(self) -> None:
        self.editor.insertPlainText(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n- ")

    def _save_notes(self) -> None:
        productivity.save_notes(self.editor.toPlainText())
        self.lbl_note_status.setText(f"Saved at {datetime.now().strftime('%H:%M:%S')} -> ~/.local/state/seiza/notes.md")

    def closeEvent(self, event) -> None:
        productivity.save_notes(self.editor.toPlainText())
        self.pomo_timer.stop()
        super().closeEvent(event)

    # ── Pomodoro ──
    def _build_pomodoro_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(14)

        self.lbl_pomo_mode = QLabel("Focus Session")
        self.lbl_pomo_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pomo_mode.setStyleSheet(f"color: {PAL['primary']}; font-size: 15px; font-weight: 700;")

        self.lbl_pomo_clock = QLabel("25:00")
        self.lbl_pomo_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pomo_clock.setStyleSheet("font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 56px; font-weight: 700;")

        self.bar_pomo = QProgressBar()
        self.bar_pomo.setValue(0)

        presets = QHBoxLayout()
        for name, mins in [("Focus 25m", 25), ("Deep Work 50m", 50), ("Break 5m", 5), ("Long Break 15m", 15)]:
            b = QPushButton(name)
            b.clicked.connect(lambda _c=False, n=name, m=mins: self._set_pomo(n, m * 60))
            presets.addWidget(b)

        ctrl = QHBoxLayout()
        self.btn_pomo_toggle = QPushButton("Start")
        self.btn_pomo_toggle.setObjectName("PrimaryBtn")
        self.btn_pomo_toggle.clicked.connect(self._toggle_pomo)
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(lambda: self._set_pomo(self.pomo_mode, self.pomo_total))
        self.chk_dnd = QCheckBox("Enable Noctalia Do Not Disturb while running")
        ctrl.addWidget(self.btn_pomo_toggle)
        ctrl.addWidget(btn_reset)
        ctrl.addStretch()
        ctrl.addWidget(self.chk_dnd)

        cl.addWidget(self.lbl_pomo_mode)
        cl.addWidget(self.lbl_pomo_clock)
        cl.addWidget(self.bar_pomo)
        cl.addLayout(presets)
        cl.addLayout(ctrl)
        lay.addWidget(card)
        lay.addStretch()
        return w

    def _set_pomo(self, mode: str, secs: int) -> None:
        self.pomo_timer.stop()
        self.pomo_running = False
        self.btn_pomo_toggle.setText("Start")
        self.pomo_mode = mode
        self.pomo_total = secs
        self.pomo_rem = secs
        self.lbl_pomo_mode.setText(mode)
        self._render_pomo()

    def _toggle_pomo(self) -> None:
        self.pomo_running = not self.pomo_running
        if self.pomo_running:
            self.btn_pomo_toggle.setText("Pause")
            if self.chk_dnd.isChecked() and shutil.which("noctalia"):
                subprocess.run(["noctalia", "msg", "notification-dnd-set", "true"], capture_output=True)
            self.pomo_timer.start()
        else:
            self.btn_pomo_toggle.setText("Resume")
            self.pomo_timer.stop()

    def _render_pomo(self) -> None:
        mins, secs = divmod(self.pomo_rem, 60)
        self.lbl_pomo_clock.setText(f"{mins:02d}:{secs:02d}")
        done = max(0, self.pomo_total - self.pomo_rem)
        self.bar_pomo.setValue(int(round(done * 100 / max(1, self.pomo_total))))

    def _pomo_tick(self) -> None:
        self.pomo_rem -= 1
        self._render_pomo()
        if self.pomo_rem <= 0:
            self.pomo_timer.stop()
            self.pomo_running = False
            self.btn_pomo_toggle.setText("Start")
            if self.chk_dnd.isChecked() and shutil.which("noctalia"):
                subprocess.run(["noctalia", "msg", "notification-dnd-set", "false"], capture_output=True)
            if shutil.which("noctalia"):
                subprocess.run(["noctalia", "msg", "notification-show", "seiza. Pomodoro Complete", f"{self.pomo_mode} finished."], capture_output=True)

    # ── Snippets & Clipboard ──
    def _build_snippets_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        bar = QHBoxLayout()
        btn_add = QPushButton("+ Pin New Snippet")
        btn_add.setObjectName("PrimaryBtn")
        btn_add.clicked.connect(self._add_snippet_dialog)
        btn_del = QPushButton("Delete Selected Pin")
        btn_del.clicked.connect(self._delete_snippet)
        btn_clear_hist = QPushButton("Clear Clipboard History")
        btn_clear_hist.setObjectName("DangerBtn")
        btn_clear_hist.clicked.connect(self._clear_clip_hist)
        self.chk_mask = QCheckBox("Mask sensitive tokens / API keys")
        self.chk_mask.setChecked(True)
        self.chk_mask.stateChanged.connect(self._refresh_clipboard)
        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        bar.addWidget(self.chk_mask)
        bar.addStretch()
        bar.addWidget(btn_clear_hist)
        lay.addLayout(bar)

        cols = QHBoxLayout()
        cols.setSpacing(12)

        left = QFrame()
        left.setObjectName("Card")
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("PINNED SNIPPETS (Double-click copies)"))
        self.list_snips = QListWidget()
        self.list_snips.itemDoubleClicked.connect(self._copy_selected_snippet)
        ll.addWidget(self.list_snips, 1)

        right = QFrame()
        right.setObjectName("Card")
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel("RECENT CLIPHIST (Double-click copies)"))
        self.list_clip = QListWidget()
        self.list_clip.itemDoubleClicked.connect(self._copy_selected_cliphist)
        rl.addWidget(self.list_clip, 1)

        cols.addWidget(left, 1)
        cols.addWidget(right, 1)
        lay.addLayout(cols, 1)
        self._refresh_clipboard()
        return w

    def _refresh_clipboard(self) -> None:
        self._snippets = productivity.load_snippets()
        self._cliphist = productivity.list_cliphist(limit=30)
        mask = self.chk_mask.isChecked()
        self.list_snips.clear()
        for s in self._snippets:
            preview = productivity.mask_preview(s["text"], s.get("sensitive", False)) if mask else " ".join(s["text"].splitlines())[:100]
            self.list_snips.addItem(f"{s['title']}  ·  {preview}")
        self.list_clip.clear()
        for c in self._cliphist:
            txt = c["display"] if mask or c["type"] == "image" else c["raw_preview"][:100]
            self.list_clip.addItem(f"#{c['id']}  {txt}")

    def _add_snippet_dialog(self) -> None:
        title, ok1 = QInputDialog.getText(self, "Pin Snippet", "Snippet title:")
        if not ok1 or not title.strip():
            return
        text, ok2 = QInputDialog.getMultiLineText(self, "Pin Snippet", "Content:")
        if not ok2 or not text:
            return
        try:
            productivity.add_snippet(title, text)
        except ValueError as e:
            QMessageBox.warning(self, "Sensitive Data Blocked", str(e))
            return
        self._refresh_clipboard()

    def _delete_snippet(self) -> None:
        r = self.list_snips.currentRow()
        if 0 <= r < len(self._snippets):
            self._snippets.pop(r)
            productivity.save_snippets(self._snippets)
            self._refresh_clipboard()

    def _copy_selected_snippet(self) -> None:
        r = self.list_snips.currentRow()
        if 0 <= r < len(self._snippets):
            productivity.copy_text(self._snippets[r]["text"])

    def _copy_selected_cliphist(self) -> None:
        r = self.list_clip.currentRow()
        if 0 <= r < len(self._cliphist):
            cid = self._cliphist[r]["id"]
            raw = subprocess.check_output(["cliphist", "decode", cid])
            subprocess.run(["wl-copy"], input=raw, check=False)

    def _clear_clip_hist(self) -> None:
        productivity.clear_clipboard_history()
        self._refresh_clipboard()

    # ── Keybinds ──
    def _build_keys_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.keys_search = QLineEdit()
        self.keys_search.setPlaceholderText("Filter keyboard shortcuts (e.g. screenshot, scratchpad, workspace, palette)...")
        self.keys_search.textChanged.connect(self._filter_keys)
        lay.addWidget(self.keys_search)

        self.tbl_keys = QTableWidget(0, 3)
        self.tbl_keys.setHorizontalHeaderLabels(["Section", "Shortcut", "Action"])
        self.tbl_keys.horizontalHeader().setStretchLastSection(True)
        self.tbl_keys.verticalHeader().setVisible(False)
        self.tbl_keys.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.tbl_keys, 1)

        self._all_keys = productivity.parse_keybinds()
        self._filter_keys("")
        return w

    def _filter_keys(self, q: str) -> None:
        ql = q.strip().lower()
        rows = [
            k
            for k in self._all_keys
            if not ql or ql in k["chord"].lower() or ql in k["description"].lower() or ql in k["section"].lower()
        ]
        self.tbl_keys.setRowCount(len(rows))
        for i, k in enumerate(rows):
            self.tbl_keys.setItem(i, 0, QTableWidgetItem(k["section"]))
            it_chord = QTableWidgetItem(k["chord"])
            it_chord.setForeground(Qt.GlobalColor.white)
            self.tbl_keys.setItem(i, 1, it_chord)
            self.tbl_keys.setItem(i, 2, QTableWidgetItem(k["description"]))
        self.tbl_keys.resizeColumnsToContents()


def launch_studio_gui(initial_tab: str = "notes") -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setDesktopFileName("seiza-studio")
    app.setStyleSheet(build_qt_qss())
    win = FocusStudioWindow(initial_tab=initial_tab)
    win.show()
    return app.exec()
