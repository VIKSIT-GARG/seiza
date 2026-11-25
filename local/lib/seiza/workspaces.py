"""Curated developer workspace presets for seiza. on Niri (with portable fallbacks)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AppCandidate:
    label: str
    candidates: List[Tuple[str, List[str]]]
    desc: str


@dataclass(frozen=True)
class WorkspacePreset:
    id: str
    name: str
    icon: str
    tagline: str
    target_workspace: Optional[int]
    dnd: Optional[bool]
    power_profile: Optional[str]
    apps: List[AppCandidate]


def _pick(app: AppCandidate) -> Optional[Tuple[str, List[str]]]:
    for binary, cmd in app.candidates:
        if shutil.which(binary):
            return binary, cmd
    return None


PRESETS: Dict[str, WorkspacePreset] = {
    "development": WorkspacePreset(
        id="development",
        name="Development",
        icon="󰨞",
        tagline="Code editor, terminal workstation & local shell",
        target_workspace=2,
        dnd=None,
        power_profile="balanced",
        apps=[
            AppCandidate("Alacritty Terminal", [("alacritty", ["alacritty"])], "Fast GPU terminal"),
            AppCandidate(
                "Primary IDE",
                [("codium", ["codium"]), ("code", ["code"]), ("zed", ["zed"]), ("nvim", ["alacritty", "-e", "nvim"])],
                "VSCodium / Code / Zed / Neovim",
            ),
        ],
    ),
    "ai-research": WorkspacePreset(
        id="ai-research",
        name="AI Research",
        icon="󰚩",
        tagline="GPU telemetry dashboard, ML terminal, browser & notes",
        target_workspace=3,
        dnd=None,
        power_profile="performance",
        apps=[
            AppCandidate("seiza. AI & GPU Dashboard", [("seiza", ["seiza", "dashboard"])], "Live GPU & VRAM estimator"),
            AppCandidate("Alacritty ML Shell", [("alacritty", ["alacritty", "-e", "fish", "-C", "seiza gpu"])], "Terminal initialized with GPU check"),
            AppCandidate(
                "Web Browser",
                [("zen-browser", ["zen-browser"]), ("firefox", ["firefox"]), ("chromium", ["chromium"]), ("brave", ["brave"])],
                "Papers & documentation",
            ),
        ],
    ),
    "electronics": WorkspacePreset(
        id="electronics",
        name="Electronics & Embedded",
        icon="󰐮",
        tagline="Arduino IDE + serial/PlatformIO probe terminal",
        target_workspace=4,
        dnd=None,
        power_profile="balanced",
        apps=[
            AppCandidate("Arduino IDE v2", [("arduino-ide", ["arduino-ide"]), ("kicad", ["kicad"])], "Embedded IDE"),
            AppCandidate(
                "Embedded Lab Shell",
                [(
                    "alacritty",
                    [
                        "alacritty",
                        "-e",
                        "fish",
                        "-C",
                        "echo 'Serial ports:' && ls -1 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo 'No USB serial adapter detected'; pio --version 2>/dev/null; arduino-cli version 2>/dev/null",
                    ],
                )],
                "PlatformIO & arduino-cli shell",
            ),
        ],
    ),
    "focus": WorkspacePreset(
        id="focus",
        name="Deep Focus",
        icon="󱎫",
        tagline="Knowledge notes, Focus Studio Pomodoro & DND on",
        target_workspace=5,
        dnd=True,
        power_profile="balanced",
        apps=[
            AppCandidate("Notes Vault", [("obsidian", ["obsidian"]), ("logseq", ["logseq"])], "Knowledge vault"),
            AppCandidate("seiza. Focus Studio", [("seiza", ["seiza", "studio"])], "Pomodoro timer, scratchpad & snippets"),
        ],
    ),
    "everyday": WorkspacePreset(
        id="everyday",
        name="Everyday",
        icon="󰖟",
        tagline="Browser, file manager & clean terminal",
        target_workspace=1,
        dnd=False,
        power_profile="balanced",
        apps=[
            AppCandidate("Web Browser", [("zen-browser", ["zen-browser"]), ("firefox", ["firefox"]), ("chromium", ["chromium"])], "Daily browser"),
            AppCandidate("File Manager", [("nautilus", ["nautilus"]), ("dolphin", ["dolphin"]), ("thunar", ["thunar"])], "Clean file manager"),
            AppCandidate("Alacritty Terminal", [("alacritty", ["alacritty"])], "Clean shell"),
        ],
    ),
}


def check_preset_availability(preset: WorkspacePreset) -> List[Dict[str, str]]:
    rows = []
    for app in preset.apps:
        picked = _pick(app)
        rows.append({
            "label": app.label,
            "binary": picked[0] if picked else app.candidates[0][0],
            "available": "yes" if picked else "no",
            "desc": app.desc,
        })
    return rows


def launch_preset(preset_id: str, dry_run: bool = False) -> Dict[str, object]:
    key = preset_id.lower().strip()
    if key not in PRESETS:
        raise ValueError(f"Unknown workspace preset '{preset_id}'. Available: {', '.join(PRESETS)}")

    preset = PRESETS[key]
    launched: List[str] = []
    skipped: List[str] = []

    if not dry_run and preset.target_workspace and shutil.which("niri"):
        subprocess.run(["niri", "msg", "action", "focus-workspace", str(preset.target_workspace)], capture_output=True)

    if not dry_run and preset.dnd is not None and shutil.which("noctalia"):
        subprocess.run(
            ["noctalia", "msg", "notification-dnd-set", "true" if preset.dnd else "false"],
            capture_output=True,
        )

    if not dry_run and preset.power_profile and shutil.which("noctalia"):
        subprocess.run(["noctalia", "msg", "power-set", preset.power_profile], capture_output=True)

    for app in preset.apps:
        picked = _pick(app)
        if picked:
            binary, cmd = picked
            if not dry_run:
                subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    env=os.environ.copy(),
                )
            launched.append(f"{app.label} ({binary})")
        else:
            skipped.append(f"{app.label} ({'/'.join(b for b, _ in app.candidates)} not found)")

    if not dry_run and shutil.which("noctalia"):
        summary = f"Workspace: {preset.name}"
        body = f"Started: {', '.join(launched)}" if launched else "No verified apps available"
        subprocess.run(["noctalia", "msg", "notification-show", summary, body], capture_output=True)

    return {"preset": preset.name, "launched": launched, "skipped": skipped, "dry_run": dry_run}
