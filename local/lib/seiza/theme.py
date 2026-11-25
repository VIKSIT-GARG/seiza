"""Shared theme tokens, Rich console styles, and PyQt6 Celestia/seiza QSS."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.theme import Theme

APP_NAME = "seiza."
TAGLINE = "A system of my own."

DEFAULT_PALETTE: Dict[str, str] = {
    "bg": "#0D101D",
    "surface": "#15192E",
    "surface_sunken": "#090B15",
    "hover": "#1E2440",
    "selection": "#272F52",
    "border": "#28304D",
    "primary": "#C4B5FD",
    "secondary": "#9CC9FF",
    "tertiary": "#F2B8D4",
    "mint": "#9CE0C2",
    "amber": "#F5D6A8",
    "error": "#F28FAD",
    "text": "#EEF1FA",
    "muted": "#A6B0D0",
    "dim": "#6C7699",
}


def load_palette() -> Dict[str, str]:
    pal = dict(DEFAULT_PALETTE)
    for candidate in (
        Path.home() / ".config/noctalia/palettes/seiza.json",
        Path.home() / ".config/noctalia/palettes/Celestia.json",
    ):
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text())
                dark = data.get("dark", {})
                if dark:
                    pal["bg"] = dark.get("surface", pal["bg"])
                    pal["surface"] = dark.get("surface_container", pal["surface"])
                    pal["hover"] = dark.get("hover", pal["hover"])
                    pal["border"] = dark.get("outline_variant", pal["border"])
                    pal["primary"] = dark.get("primary", pal["primary"])
                    pal["secondary"] = dark.get("secondary", pal["secondary"])
                    pal["tertiary"] = dark.get("tertiary", pal["tertiary"])
                    pal["error"] = dark.get("error", pal["error"])
                    pal["text"] = dark.get("on_surface", pal["text"])
                    pal["muted"] = dark.get("on_surface_variant", pal["muted"])
                break
            except Exception:
                pass
    return pal


PAL = load_palette()

RICH_THEME = Theme(
    {
        "brand": f"bold {PAL['primary']}",
        "accent": PAL["secondary"],
        "pink": PAL["tertiary"],
        "ok": f"bold {PAL['mint']}",
        "warn": f"bold {PAL['amber']}",
        "err": f"bold {PAL['error']}",
        "muted": PAL["muted"],
        "dim": PAL["dim"],
        "key": f"bold {PAL['primary']}",
        "val": PAL["text"],
    }
)

console = Console(theme=RICH_THEME)


def print_header(title: str, subtitle: str = TAGLINE) -> None:
    console.print(
        f"[brand]✦ {APP_NAME}[/] [dim]//[/] [bold {PAL['text']}]{title}[/]  "
        f"[dim]· {subtitle}[/]"
    )
    console.print(f"[{PAL['border']}]{'─' * 68}[/]")


def build_qt_qss(pal: Dict[str, str] | None = None) -> str:
    p = pal or PAL
    return f"""
QWidget {{
    background-color: {p['bg']};
    color: {p['text']};
    font-family: "Adwaita Sans", "Inter", sans-serif;
    font-size: 13px;
    selection-background-color: {p['selection']};
    selection-color: {p['text']};
}}
QMainWindow, QDialog {{
    background-color: {p['bg']};
}}
QFrame#Card, QWidget#Card {{
    background-color: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 14px;
}}
QFrame#SubCard {{
    background-color: {p['surface_sunken']};
    border: 1px solid {p['border']};
    border-radius: 10px;
}}
QLabel#BrandTitle {{
    font-size: 19px;
    font-weight: 700;
    color: {p['text']};
    background: transparent;
}}
QLabel#BrandTagline {{
    font-size: 12px;
    color: {p['muted']};
    background: transparent;
}}
QLabel#SectionTitle {{
    font-size: 12px;
    font-weight: 700;
    color: {p['primary']};
    letter-spacing: 0.6px;
    background: transparent;
}}
QLabel#MetricValue {{
    font-family: "JetBrainsMono Nerd Font", monospace;
    font-size: 20px;
    font-weight: 700;
    color: {p['text']};
    background: transparent;
}}
QLabel#Mono {{
    font-family: "JetBrainsMono Nerd Font", monospace;
    background: transparent;
}}
QLabel {{
    background: transparent;
}}
QPushButton {{
    background-color: {p['hover']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {p['primary']};
    background-color: {p['selection']};
}}
QPushButton:pressed {{
    background-color: {p['surface']};
}}
QPushButton#PrimaryBtn {{
    background-color: {p['primary']};
    color: {p['bg']};
    border: 1px solid {p['primary']};
}}
QPushButton#PrimaryBtn:hover {{
    background-color: {p['secondary']};
    border-color: {p['secondary']};
}}
QPushButton#DangerBtn {{
    background-color: rgba(242, 143, 173, 0.16);
    color: {p['error']};
    border: 1px solid {p['error']};
}}
QPushButton#NavTab {{
    background-color: transparent;
    color: {p['muted']};
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 7px 14px;
}}
QPushButton#NavTab:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QPushButton#NavTab[active="true"] {{
    background-color: rgba(196, 181, 253, 0.18);
    color: {p['primary']};
    border: 1px solid rgba(196, 181, 253, 0.45);
}}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {p['surface_sunken']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 7px 11px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {p['primary']};
}}
QComboBox QAbstractItemView {{
    background-color: {p['surface']};
    color: {p['text']};
    border: 1px solid {p['border']};
    selection-background-color: {p['selection']};
}}
QListWidget, QTableWidget, QTreeWidget {{
    background-color: {p['surface_sunken']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 8px;
    margin: 2px 4px;
}}
QListWidget::item:selected {{
    background-color: rgba(196, 181, 253, 0.20);
    color: {p['text']};
    border: 1px solid rgba(196, 181, 253, 0.45);
}}
QListWidget::item:hover {{
    background-color: {p['hover']};
}}
QHeaderView::section {{
    background-color: {p['surface']};
    color: {p['muted']};
    border: none;
    border-bottom: 1px solid {p['border']};
    padding: 6px 8px;
    font-weight: 600;
}}
QProgressBar {{
    background-color: {p['surface_sunken']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    height: 10px;
    text-align: center;
    font-size: 10px;
}}
QProgressBar::chunk {{
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['primary']}, stop:1 {p['secondary']});
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: {p['border']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p['dim']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
