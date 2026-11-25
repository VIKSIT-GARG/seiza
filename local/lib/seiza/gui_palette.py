"""seiza. Universal Command Centre — unified searchable launcher palette."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import indexers, productivity, workspaces
from .theme import PAL, build_qt_qss


def _spawn(cmd: List[str]) -> None:
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )


def _notify(title: str, body: str) -> None:
    if shutil.which("noctalia"):
        subprocess.run(["noctalia", "msg", "notification-show", title, body], capture_output=True)


class CommandPalette(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("seiza. // Command Centre")
        self.resize(800, 560)
        self.active_cat = "All"
        self.entries: List[Dict[str, Any]] = []
        self.filtered: List[Dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("✦ seiza.  //  Universal Command Centre")
        lbl.setObjectName("BrandTitle")
        hint = QLabel("Enter: Run   ·   Esc: Close   ·   Type math like 165*2560")
        hint.setStyleSheet(f"color: {PAL['dim']}; font-size: 12px;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(hint)
        root.addLayout(hdr)

        # Search bar
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search apps, files, calc (=), commands, workspaces, clips, keys, bookmarks...")
        self.search.setStyleSheet(
            f"font-size: 15px; padding: 11px 14px; border: 1.5px solid {PAL['primary']}; "
            f"background-color: {PAL['surface']}; border-radius: 12px;"
        )
        self.search.textChanged.connect(self._update_filter)
        self.search.returnPressed.connect(self._activate_current)
        self.search.installEventFilter(self)
        root.addWidget(self.search)

        # Category pills
        cats_row = QHBoxLayout()
        cats_row.setSpacing(6)
        self.cat_btns: Dict[str, QPushButton] = {}
        for cat in ("All", "Action", "Workspace", "Command", "App", "Clipboard", "Shortcut", "Bookmark", "File"):
            b = QPushButton(cat)
            b.setObjectName("NavTab")
            b.setProperty("active", "true" if cat == "All" else "false")
            b.setStyleSheet("padding: 4px 10px; font-size: 12px;")
            b.clicked.connect(lambda _c=False, c=cat: self._set_cat(c))
            self.cat_btns[cat] = b
            cats_row.addWidget(b)
        cats_row.addStretch()
        root.addLayout(cats_row)

        # Results list
        frame = QFrame()
        frame.setObjectName("Card")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(8, 8, 8, 8)
        self.results = QListWidget()
        self.results.setStyleSheet("QListWidget::item { padding: 3px 6px; border: 1px solid transparent; border-radius: 8px; margin: 2px 4px; }")
        self.results.itemActivated.connect(self._activate_item)
        fl.addWidget(self.results)
        root.addWidget(frame, 1)

        self._build_fast_index()
        self._update_filter("")
        self.search.setFocus()
        QTimer.singleShot(25, self._populate_extended_index)

    def eventFilter(self, obj, ev) -> bool:
        if obj is self.search and isinstance(ev, QKeyEvent) and ev.type() == QKeyEvent.Type.KeyPress:
            if ev.key() == Qt.Key.Key_Down:
                row = min(self.results.count() - 1, self.results.currentRow() + 1)
                if row >= 0:
                    self.results.setCurrentRow(row)
                return True
            if ev.key() == Qt.Key.Key_Up:
                row = max(0, self.results.currentRow() - 1)
                if row >= 0:
                    self.results.setCurrentRow(row)
                return True
            if ev.key() == Qt.Key.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, ev)

    def _set_cat(self, cat: str) -> None:
        self.active_cat = cat
        for k, b in self.cat_btns.items():
            b.setProperty("active", "true" if k == cat else "false")
            b.style().unpolish(b)
            b.style().polish(b)
        self._update_filter(self.search.text())

    def _build_fast_index(self) -> None:
        items: List[Dict[str, Any]] = []

        # Built-in seiza. Actions & System Tools
        actions = [
            ("AI, ML & Health Dashboard", "GPU VRAM telemetry, LLM fit estimator, health & receipts", ["seiza", "dashboard"]),
            ("Display Studio (Monitors)", "Extend, mirror (wl-mirror), scaling & 15s revert safety", ["seiza", "display"]),
            ("Focus Studio (Notes & Pomodoro)", "Markdown scratchpad, timer, clipboard snippets & shortcuts", ["seiza", "studio"]),
            ("Screen Color Picker", "Sample pixel HEX to clipboard", ["seiza", "color"]),
            ("Screen Region OCR", "Drag region to extract text or copy region", ["seiza", "ocr"]),
            ("Screenshot Region (Noctalia)", "Interactive region screenshot", ["noctalia", "msg", "screenshot-region"]),
            ("Screenshot Annotate (Noctalia)", "Freeze & annotate screen", ["noctalia", "msg", "screenshot-annotate"]),
            ("Screen Recorder Toggle", "Start/stop Noctalia screen recorder", ["seiza", "record", "toggle"]),
            ("System Doctor (Terminal)", "Validate configs, systemd units & NVIDIA health", ["alacritty", "-e", "fish", "-C", "seiza doctor"]),
            ("Safe System Clean Preview", "Inspect reclaimable caches & orphans", ["alacritty", "-e", "fish", "-C", "seiza clean --dry-run"]),
            ("Pacman Upgrade Receipts", "Inspect upgrade history & rollback snapshots", ["alacritty", "-e", "fish", "-C", "seiza update --receipts"]),
            ("Network Diagnostics", "Interfaces, Wi-Fi link, DNS, ping & ports", ["alacritty", "-e", "fish", "-C", "seiza network --ports"]),
            ("Lock Screen", "Lock Wayland session cleanly", ["noctalia", "msg", "session", "lock"]),
            ("Power & Session Menu", "Shutdown, reboot, suspend, logout", ["noctalia", "msg", "panel-open", "session"]),
            ("Power Profile: Performance", "Switch CPU/platform to performance", ["noctalia", "msg", "power-set", "performance"]),
            ("Power Profile: Balanced", "Switch CPU/platform to balanced", ["noctalia", "msg", "power-set", "balanced"]),
            ("Power Profile: Power Saver", "Switch CPU/platform to power-saver", ["noctalia", "msg", "power-set", "power-saver"]),
            ("Next Wallpaper & Theme Sync", "Advance wallpaper and re-sync seiza.", ["sh", "-c", "noctalia msg wallpaper-next && sleep 0.35 && theme-sync"]),
            ("Reload Niri & Noctalia", "Hot-reload compositor & shell configs", ["sh", "-c", "niri msg action load-config-file && noctalia msg config-reload"]),
        ]
        for title, sub, cmd in actions:
            items.append({"kind": "Action", "title": title, "subtitle": sub, "cmd": cmd})

        # Workspace Presets
        for p in workspaces.PRESETS.values():
            items.append(
                {
                    "kind": "Workspace",
                    "title": f"Workspace: {p.name}",
                    "subtitle": p.tagline,
                    "workspace": p.id,
                }
            )

        # Frequent Developer & System Commands
        freq_cmds = [
            ("seiza status", "Print workstation health overview in Alacritty"),
            ("seiza gpu --watch", "Live RTX 5060 VRAM/power monitor"),
            ("seiza update", "Run safe upgrade and generate Pacman receipt"),
            ("seiza backup", "Create timestamped config snapshot"),
            ("seiza welcome", "Show wide/compact SEIZA welcome card"),
            ("syscheck", "Full CachyOS health check"),
            ("opencode-dash", "OpenCode serving controller"),
        ]
        for cmd_str, desc in freq_cmds:
            items.append(
                {
                    "kind": "Command",
                    "title": cmd_str,
                    "subtitle": f"Run in terminal · {desc}",
                    "cmd": ["alacritty", "-e", "fish", "-C", cmd_str],
                }
            )

        # Pinned snippets & recent cliphist (masked safely!)
        for snip in productivity.load_snippets():
            items.append(
                {
                    "kind": "Clipboard",
                    "title": f"Pin: {snip['title']}",
                    "subtitle": productivity.mask_preview(snip["text"], snip.get("sensitive", False)),
                    "copy": snip["text"],
                }
            )
        for ch in productivity.list_cliphist(limit=20):
            if ch["type"] == "text":
                items.append(
                    {
                        "kind": "Clipboard",
                        "title": ch["display"],
                        "subtitle": f"Cliphist #{ch['id']} (Enter copies to clipboard)",
                        "cliphist_id": ch["id"],
                    }
                )

        # Keyboard shortcuts
        for kb in productivity.parse_keybinds():
            items.append(
                {
                    "kind": "Shortcut",
                    "title": f"{kb['chord']}  →  {kb['description']}",
                    "subtitle": f"Keybind · {kb['section']} · {kb['action']}",
                    "copy": kb["chord"],
                }
            )

        self.entries = items

    def _populate_extended_index(self) -> None:
        extra: List[Dict[str, Any]] = []
        for app in indexers.load_desktop_apps():
            extra.append(
                {
                    "kind": "App",
                    "title": app["title"],
                    "subtitle": f"App · {app['subtitle']}",
                    "exec_str": app["exec"],
                }
            )
        extra.extend(indexers.load_bookmarks())
        extra.extend(indexers.scan_home_files())
        self.entries.extend(extra)
        self._update_filter(self.search.text())

    def _update_filter(self, query: str) -> None:
        q = query.strip().lower()
        self.results.clear()
        self.filtered = []

        # Live Calculator check
        calc = indexers.eval_math(query)
        if calc is not None and self.active_cat in ("All", "Action"):
            self.filtered.append(
                {
                    "kind": "Calc",
                    "title": f"= {calc}",
                    "subtitle": f"Calculator: {query.strip()}  (Enter copies '{calc}' to clipboard)",
                    "copy": calc,
                }
            )

        tokens = [t for t in q.split() if t]
        for item in self.entries:
            if self.active_cat != "All" and item["kind"] != self.active_cat:
                continue
            hay = f"{item['kind']} {item['title']} {item.get('subtitle', '')}".lower()
            if all(tok in hay for tok in tokens):
                self.filtered.append(item)
                if len(self.filtered) >= 85:
                    break

        kind_colors = {
            "Calc": PAL["mint"],
            "Action": PAL["primary"],
            "Workspace": PAL["tertiary"],
            "Command": PAL["amber"],
            "App": PAL["secondary"],
            "Clipboard": PAL["mint"],
            "Shortcut": PAL["muted"],
            "Bookmark": PAL["secondary"],
            "File": PAL["text"],
            "Folder": PAL["primary"],
        }
        for item in self.filtered[:55]:
            kind = item["kind"]
            accent = kind_colors.get(kind, PAL["text"])
            lw = QListWidgetItem()
            lw.setSizeHint(QSize(0, 56))
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(6, 2, 6, 2)
            rl.setSpacing(10)

            badge = QLabel(kind.upper())
            badge.setFixedWidth(84)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"color: {accent}; background: rgba(196, 181, 253, 0.08); "
                f"border: 1px solid {PAL['border']}; border-radius: 6px; "
                f"font-size: 10px; font-weight: 700; padding: 3px 4px;"
            )
            rl.addWidget(badge)

            tcol = QVBoxLayout()
            tcol.setContentsMargins(0, 0, 0, 0)
            tcol.setSpacing(1)
            lbl_t = QLabel(item["title"])
            lbl_t.setStyleSheet(f"color: {PAL['text']}; font-weight: 600; font-size: 13px; background: transparent;")
            lbl_s = QLabel(item.get("subtitle", ""))
            lbl_s.setStyleSheet(f"color: {PAL['muted']}; font-size: 11px; background: transparent;")
            tcol.addWidget(lbl_t)
            tcol.addWidget(lbl_s)
            rl.addLayout(tcol, 1)

            self.results.addItem(lw)
            self.results.setItemWidget(lw, row_w)

        if self.results.count() > 0:
            self.results.setCurrentRow(0)

    def _activate_current(self) -> None:
        row = self.results.currentRow()
        if 0 <= row < len(self.filtered):
            self._run_entry(self.filtered[row])

    def _activate_item(self, item: QListWidgetItem) -> None:
        row = self.results.row(item)
        if 0 <= row < len(self.filtered):
            self._run_entry(self.filtered[row])

    def _run_entry(self, entry: Dict[str, Any]) -> None:
        if "cmd" in entry:
            _spawn(entry["cmd"])
        elif "workspace" in entry:
            workspaces.launch_preset(entry["workspace"])
        elif "exec_str" in entry:
            _spawn(shlex.split(entry["exec_str"]))
        elif "url" in entry:
            _spawn(["xdg-open", entry["url"]])
        elif "path" in entry:
            p = Path(entry["path"])
            _spawn(["nautilus", str(p)] if p.is_dir() else ["xdg-open", str(p)])
        elif "cliphist_id" in entry:
            raw = subprocess.check_output(["cliphist", "decode", entry["cliphist_id"]])
            subprocess.run(["wl-copy"], input=raw, check=False)
            _notify("seiza. Clipboard", "Copied entry to clipboard")
        elif "copy" in entry:
            productivity.copy_text(entry["copy"])
            _notify("seiza. Palette", f"Copied: {entry['copy'][:40]}")
        self.accept()


def launch_palette_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setDesktopFileName("seiza-palette")
    app.setStyleSheet(build_qt_qss())
    dlg = CommandPalette()
    dlg.show()
    return app.exec()
