"""Keybind parser, quick notes, Pomodoro tracking & sensitive-aware clipboard snippets."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

KEYBINDS_FILE = Path.home() / ".config/niri/cfg/keybinds.kdl"
STATE_DIR = Path.home() / ".local/state/seiza"
NOTES_FILE = STATE_DIR / "notes.md"
SNIPPETS_FILE = STATE_DIR / "snippets.json"
POMODORO_FILE = STATE_DIR / "pomodoro.json"

SENSITIVE_PATTERNS = [
    ("OpenAI / API Token", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("GitHub Token", re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}\b")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{25,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private Key Block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Bearer / Auth Header", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{16,}")),
    ("JWT Token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)


def parse_keybinds() -> List[Dict[str, str]]:
    if not KEYBINDS_FILE.is_file():
        return []
    section = "General"
    entries: List[Dict[str, str]] = []
    bind_re = re.compile(
        r'^\s*([A-Za-z0-9_+]+)\s+(?:[^\{]*?hotkey-overlay-title="([^"]+)")?[^\{]*\{\s*([^;\}]+)'
    )
    sec_re = re.compile(r"//\s*───\s+([A-Za-z][^─\n]+?)\s+───")

    for line in KEYBINDS_FILE.read_text().splitlines():
        if sm := sec_re.search(line):
            section = sm.group(1).strip()
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("binds") or stripped == "}":
            continue
        if bm := bind_re.match(line):
            chord, title, action = bm.groups()
            action_clean = re.sub(r"\s+", " ", action.strip())
            if action_clean.startswith("spawn"):
                action_desc = title or action_clean
            else:
                action_desc = title or action_clean.replace("-", " ")
            entries.append(
                {
                    "section": section,
                    "chord": chord.replace("Mod", "Super"),
                    "action": action_clean,
                    "description": action_desc,
                }
            )
    return entries


def detect_sensitive(text: str) -> List[str]:
    hits = []
    for label, pat in SENSITIVE_PATTERNS:
        if pat.search(text):
            hits.append(label)
    return hits


def mask_preview(text: str, is_sensitive: bool = False) -> str:
    flat = " ".join(text.strip().splitlines())
    if is_sensitive or detect_sensitive(text):
        if len(flat) <= 8:
            return "••••••••"
        return f"{flat[:4]}••••••••{flat[-3:]} [sensitive masked]"
    return flat[:96] + ("…" if len(flat) > 96 else "")


def load_snippets() -> List[Dict[str, Any]]:
    _ensure_state_dir()
    if SNIPPETS_FILE.is_file():
        try:
            return json.loads(SNIPPETS_FILE.read_text())
        except Exception:
            pass
    # Seed default safe productivity snippets (non-sensitive developer helpers)
    defaults = [
        {"title": "seiza. CLI Help", "text": "seiza help", "sensitive": False, "created": "default"},
        {"title": "RTX 5060 GPU Watch", "text": "seiza gpu --watch", "sensitive": False, "created": "default"},
        {"title": "Check Pacman Receipts", "text": "seiza update --receipts", "sensitive": False, "created": "default"},
    ]
    save_snippets(defaults)
    return defaults


def save_snippets(items: List[Dict[str, Any]]) -> None:
    _ensure_state_dir()
    SNIPPETS_FILE.write_text(json.dumps(items, indent=2))
    os.chmod(SNIPPETS_FILE, 0o600)


def add_snippet(title: str, text: str, allow_sensitive: bool = False) -> Dict[str, Any]:
    hits = detect_sensitive(text)
    if hits and not allow_sensitive:
        raise ValueError(
            f"Refused to store plaintext sensitive data ({', '.join(hits)}) without --allow-sensitive."
        )
    items = load_snippets()
    rec = {
        "title": title.strip() or mask_preview(text, bool(hits))[:32],
        "text": text,
        "sensitive": bool(hits),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    items.insert(0, rec)
    save_snippets(items)
    return rec


def copy_text(text: str) -> None:
    subprocess.run(["wl-copy"], input=text, text=True, check=True)


def list_cliphist(limit: int = 30) -> List[Dict[str, str]]:
    try:
        raw = subprocess.check_output(["cliphist", "list"], text=True, timeout=2.0)
    except Exception:
        return []
    rows = []
    for line in raw.splitlines()[:limit]:
        if "\t" not in line:
            continue
        cid, preview = line.split("\t", 1)
        is_img = preview.startswith("[[ binary data")
        hits = [] if is_img else detect_sensitive(preview)
        rows.append(
            {
                "id": cid,
                "raw_preview": preview,
                "display": preview if is_img else mask_preview(preview, bool(hits)),
                "sensitive": "yes" if hits else "no",
                "type": "image" if is_img else "text",
            }
        )
    return rows


def clear_clipboard_history() -> None:
    subprocess.run(["cliphist", "wipe"], capture_output=True)
    subprocess.run(["noctalia", "msg", "clipboard-clear"], capture_output=True)


def load_notes() -> str:
    _ensure_state_dir()
    if NOTES_FILE.is_file():
        return NOTES_FILE.read_text()
    starter = (
        "# seiza. Quick Scratchpad\n\n"
        "- Press Ctrl+S or edit here — saved locally to ~/.local/state/seiza/notes.md\n"
    )
    NOTES_FILE.write_text(starter)
    return starter


def save_notes(content: str) -> None:
    _ensure_state_dir()
    NOTES_FILE.write_text(content)
