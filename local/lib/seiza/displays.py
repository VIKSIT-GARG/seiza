"""Wayland / Niri external display discovery, layout control, wl-mirror, profiles & rollback."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

DISPLAY_KDL = Path.home() / ".config/niri/cfg/display.kdl"
PROFILES_PATH = Path.home() / ".local/state/seiza/display_profiles.json"


def get_outputs() -> List[Dict[str, Any]]:
    try:
        raw = subprocess.check_output(["niri", "msg", "-j", "outputs"], text=True, timeout=3.0)
        data = json.loads(raw)
        results = []
        items = data.values() if isinstance(data, dict) else data
        for out in items:
            modes = []
            for m in out.get("modes", []):
                w, h = m.get("width"), m.get("height")
                rr = m.get("refresh_rate")
                hz = f"{rr / 1000:.3f}" if isinstance(rr, (int, float)) else ""
                if w and h:
                    modes.append(f"{w}x{h}@{hz}" if hz else f"{w}x{h}")
            cur_idx = out.get("current_mode")
            cur_mode = modes[cur_idx] if isinstance(cur_idx, int) and 0 <= cur_idx < len(modes) else ""
            logical = out.get("logical") or {}
            results.append(
                {
                    "name": out.get("name", "unknown"),
                    "make": out.get("make", ""),
                    "model": out.get("model", ""),
                    "enabled": logical != {} and out.get("logical") is not None,
                    "current_mode": cur_mode,
                    "modes": modes,
                    "scale": logical.get("scale", 1.0),
                    "x": logical.get("x", 0),
                    "y": logical.get("y", 0),
                    "width": logical.get("width", 0),
                    "height": logical.get("height", 0),
                    "transform": logical.get("transform", "Normal"),
                    "vrr_supported": bool(out.get("vrr_supported", False)),
                    "vrr_enabled": bool(out.get("vrr_enabled", False)),
                }
            )
        return results
    except Exception:
        return []


def stop_mirror() -> None:
    subprocess.run(["pkill", "-x", "wl-mirror"], capture_output=True)


def run_niri_output(args: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["niri", "msg", "output", *args], capture_output=True, text=True, timeout=5.0)


def snapshot_state() -> Dict[str, Any]:
    return {
        "outputs": get_outputs(),
        "display_kdl": DISPLAY_KDL.read_text() if DISPLAY_KDL.is_file() else "",
    }


def restore_snapshot(snap: Dict[str, Any]) -> None:
    stop_mirror()
    if snap.get("display_kdl"):
        DISPLAY_KDL.write_text(snap["display_kdl"])
    for out in snap.get("outputs", []):
        name = out["name"]
        if out.get("enabled"):
            run_niri_output([name, "on"])
            if out.get("current_mode"):
                run_niri_output([name, "mode", out["current_mode"]])
            if out.get("scale") is not None:
                run_niri_output([name, "scale", str(out["scale"])])
            run_niri_output([name, "position", "set", str(out.get("x", 0)), str(out.get("y", 0))])
        else:
            run_niri_output([name, "off"])



def primary_output_name() -> str:
    outs = get_outputs()
    for o in outs:
        if o["name"].startswith("eDP"):
            return o["name"]
    for o in outs:
        if o.get("enabled"):
            return o["name"]
    return outs[0]["name"] if outs else "eDP-1"

def set_internal_only(internal: Optional[str] = None) -> str:
    internal = internal or primary_output_name()
    stop_mirror()
    outs = get_outputs()
    run_niri_output([internal, "on"])
    run_niri_output([internal, "position", "set", "0", "0"])
    disabled = []
    for o in outs:
        if o["name"] != internal and o["enabled"]:
            run_niri_output([o["name"], "off"])
            disabled.append(o["name"])
    return f"Internal only ({internal}); disabled: {', '.join(disabled) or 'none'}"


def set_extend(primary: str, secondary: str, side: str = "right", mode: Optional[str] = None, scale: Optional[float] = None) -> str:
    stop_mirror()
    outs = {o["name"]: o for o in get_outputs()}
    if primary not in outs or secondary not in outs:
        raise ValueError(f"Output(s) not connected. Available: {', '.join(outs) or 'none'}")

    run_niri_output([primary, "on"])
    run_niri_output([secondary, "on"])
    if mode:
        run_niri_output([secondary, "mode", mode])
    if scale:
        run_niri_output([secondary, "scale", str(scale)])

    # Re-fetch logical dimensions after enable/mode change
    outs = {o["name"]: o for o in get_outputs()}
    p = outs[primary]
    s = outs[secondary]
    pw, ph = int(p.get("width") or 2560), int(p.get("height") or 1440)
    sw, sh = int(s.get("width") or 1920), int(s.get("height") or 1080)

    run_niri_output([primary, "position", "set", "0", "0"])
    if side == "left":
        run_niri_output([secondary, "position", "set", str(-sw), "0"])
    elif side == "above":
        run_niri_output([secondary, "position", "set", "0", str(-sh)])
    elif side == "below":
        run_niri_output([secondary, "position", "set", "0", str(ph)])
    else:
        run_niri_output([secondary, "position", "set", str(pw), "0"])
    return f"Extended {secondary} {side} of {primary}"


def start_mirror(source: str, target: str) -> str:
    if not shutil.which("wl-mirror"):
        raise RuntimeError("wl-mirror binary is not installed")
    outs = {o["name"]: o for o in get_outputs()}
    if source not in outs or target not in outs:
        raise ValueError(f"Connected outputs needed for mirroring. Connected: {', '.join(outs) or 'none'}")

    set_extend(source, target, "right")
    stop_mirror()
    subprocess.run(["niri", "msg", "action", "focus-monitor", target], capture_output=True)
    subprocess.Popen(
        ["wl-mirror", "--fullscreen", source],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return f"Mirroring {source} -> {target} via wl-mirror"


def set_presentation(external: Optional[str] = None) -> str:
    outs = get_outputs()
    prim = primary_output_name()
    ext = external or next((o["name"] for o in outs if o["name"] != prim), None)
    if shutil.which("noctalia"):
        subprocess.run(["noctalia", "msg", "caffeine-enable"], capture_output=True)
    if ext:
        return start_mirror(prim, ext)
    return "No external display connected; enabled presentation caffeine mode on eDP-1."


def write_persistent_display_kdl() -> Path:
    outs = get_outputs()
    lines = ["// ────────────── seiza. — Persistent Niri Display Configuration ──────────────"]
    for o in outs:
        if not o["enabled"]:
            lines.append(f'output "{o["name"]}" {{\n    off\n}}')
            continue
        lines.append(f'output "{o["name"]}" {{')
        if o["current_mode"]:
            lines.append(f'    mode "{o["current_mode"]}"')
        lines.append(f'    scale {o["scale"]}')
        lines.append(f'    position x={int(o["x"])} y={int(o["y"])}')
        if o.get("vrr_supported"):
            lines.append("    variable-refresh-rate")
        lines.append("}")
    DISPLAY_KDL.write_text("\n".join(lines) + "\n")
    return DISPLAY_KDL


def load_profiles() -> Dict[str, Any]:
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PROFILES_PATH.is_file():
        try:
            return json.loads(PROFILES_PATH.read_text())
        except Exception:
            pass
    return {}


def save_profile(name: str) -> Path:
    profiles = load_profiles()
    profiles[name] = get_outputs()
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(json.dumps(profiles, indent=2))
    return PROFILES_PATH


def apply_profile(name: str) -> str:
    profiles = load_profiles()
    if name not in profiles:
        raise ValueError(f"Profile '{name}' not found")
    stop_mirror()
    connected = {o["name"] for o in get_outputs()}
    applied = []
    for o in profiles[name]:
        if o["name"] not in connected:
            continue
        if o.get("enabled"):
            run_niri_output([o["name"], "on"])
            if o.get("current_mode"):
                run_niri_output([o["name"], "mode", o["current_mode"]])
            run_niri_output([o["name"], "scale", str(o.get("scale", 1.0))])
            run_niri_output([o["name"], "position", "set", str(o.get("x", 0)), str(o.get("y", 0))])
            applied.append(o["name"])
        else:
            run_niri_output([o["name"], "off"])
    return f"Applied profile '{name}' to {', '.join(applied) or 'no connected displays'}"
