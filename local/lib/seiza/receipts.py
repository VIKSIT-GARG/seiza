"""Pacman upgrade receipt parser, recorder, and safe upgrade runner."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

RECEIPTS_DIR = Path.home() / ".local/state/seiza/receipts"
PACMAN_LOG = Path("/var/log/pacman.log")

TX_RE = re.compile(r"^\[([^\]]+)\]\s+\[(PACMAN|ALPM|ALPM-SCRIPTLET)\]\s+(.*)$")
UPG_RE = re.compile(r"^upgraded\s+(\S+)\s+\(([^)]+)\)$")
INS_RE = re.compile(r"^installed\s+(\S+)\s+\(([^)]+)\)$")
REM_RE = re.compile(r"^removed\s+(\S+)\s+\(([^)]+)\)$")
REI_RE = re.compile(r"^reinstalled\s+(\S+)\s+\(([^)]+)\)$")
SNAP_RE = re.compile(r"==>\s*(?:root|home):\s*(\d+)")


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def parse_pacman_transactions(min_offset: int = 0, limit: int = 25) -> List[Dict[str, Any]]:
    if not PACMAN_LOG.is_file():
        return []
    with PACMAN_LOG.open("r", errors="replace") as fh:
        if min_offset > 0:
            fh.seek(min_offset)
        lines = fh.readlines()

    transactions: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    last_cmd = ""
    last_pre_snap = None

    for line in lines:
        m = TX_RE.match(line.rstrip("\n"))
        if not m:
            continue
        ts_str, tag, msg = m.groups()
        if tag == "PACMAN" and msg.startswith("Running '"):
            last_cmd = msg[len("Running '") : -1]
        elif tag == "ALPM" and msg == "transaction started":
            cur = {
                "started_at": ts_str,
                "ended_at": ts_str,
                "duration_sec": 0.0,
                "command": last_cmd or "pacman",
                "upgraded": [],
                "installed": [],
                "removed": [],
                "reinstalled": [],
                "snapshots": {"pre": last_pre_snap, "post": None},
                "alerts": [],
            }
        elif tag == "ALPM-SCRIPTLET":
            sm = SNAP_RE.search(msg)
            if sm:
                sid = sm.group(1)
                if cur is None:
                    last_pre_snap = sid
                else:
                    cur["snapshots"]["post"] = sid
            if "pacnew" in msg.lower() or "error" in msg.lower() or "warning" in msg.lower():
                if cur is not None:
                    cur["alerts"].append(msg)
        elif tag == "ALPM" and cur is not None:
            if msg == "transaction completed":
                cur["ended_at"] = ts_str
                t0, t1 = _parse_iso(cur["started_at"]), _parse_iso(ts_str)
                if t0 and t1:
                    cur["duration_sec"] = round((t1 - t0).total_seconds(), 1)
                transactions.append(cur)
                cur = None
                last_pre_snap = None
            elif msg == "transaction failed" or "error" in msg.lower() or "warning" in msg.lower():
                cur["alerts"].append(msg)
            else:
                if um := UMG_MATCH(UPG_RE, msg):
                    cur["upgraded"].append({"pkg": um[0], "ver": um[1]})
                elif im := UMG_MATCH(INS_RE, msg):
                    cur["installed"].append({"pkg": im[0], "ver": im[1]})
                elif rm := UMG_MATCH(REM_RE, msg):
                    cur["removed"].append({"pkg": rm[0], "ver": rm[1]})
                elif rim := UMG_MATCH(REI_RE, msg):
                    cur["reinstalled"].append({"pkg": rim[0], "ver": rim[1]})

    return transactions[-limit:]


def UMG_MATCH(pat: re.Pattern[str], text: str):
    m = pat.match(text)
    return m.groups() if m else None


def load_saved_receipts(limit: int = 20) -> List[Dict[str, Any]]:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for p in sorted(RECEIPTS_DIR.glob("receipt_*.json"), reverse=True)[:limit]:
        try:
            saved.append(json.loads(p.read_text()))
        except Exception:
            pass
    if saved:
        return saved
    # Bootstrap view cleanly from system pacman.log history (read-only)
    hist = parse_pacman_transactions(limit=limit)
    hist.reverse()
    for tx in hist:
        tx["source"] = "pacman.log"
        tx["disk_delta_mb"] = None
    return hist


def save_receipt(receipt: Dict[str, Any]) -> Path:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = RECEIPTS_DIR / f"receipt_{stamp}.json"
    md_path = RECEIPTS_DIR / f"receipt_{stamp}.md"
    json_path.write_text(json.dumps(receipt, indent=2))

    lines = [
        f"# seiza. System Upgrade Receipt — {receipt.get('started_at', stamp)}",
        "",
        f"- **Command:** `{receipt.get('command', '')}`",
        f"- **Exit Code:** `{receipt.get('exit_code', 0)}`",
        f"- **Duration:** `{receipt.get('duration_sec', 0)}s`",
        f"- **Disk Delta (`/`):** `{receipt.get('disk_delta_mb', 0):+.1f} MiB`",
        f"- **Rollback Snapshots:** `{receipt.get('snapshots', {})}`",
        "",
        f"## Package Changes ({len(receipt.get('upgraded', []))} upgraded, "
        f"{len(receipt.get('installed', []))} installed, {len(receipt.get('removed', []))} removed)",
    ]
    for item in receipt.get("upgraded", []):
        lines.append(f"- ↑ `{item['pkg']}` ({item['ver']})")
    for item in receipt.get("installed", []):
        lines.append(f"- + `{item['pkg']}` ({item['ver']})")
    for item in receipt.get("removed", []):
        lines.append(f"- - `{item['pkg']}` ({item['ver']})")
    if receipt.get("alerts"):
        lines += ["", "## Alerts / Notices"] + [f"- {a}" for a in receipt["alerts"]]
    lines += [
        "",
        "## Safe Rollback Guidance",
        "- Prefer Btrfs snapshot rollback (`sudo snapper list` / `limine-snapper`) if an upgrade regresses.",
        "- Never partial-upgrade (`pacman -Sy <pkg>`). Use `pacman -U /var/cache/pacman/pkg/<old>.pkg.tar.zst` only when necessary.",
    ]
    md_path.write_text("\n".join(lines) + "\n")
    return json_path


def run_safe_update(repo_only: bool = False) -> Dict[str, Any]:
    if Path("/var/lib/pacman/db.lck").exists():
        raise RuntimeError("/var/lib/pacman/db.lck exists — another package manager is active or stale lock needs inspection.")

    helper = "pacman" if repo_only or not shutil.which("paru") else "paru"
    cmd = ["sudo", "pacman", "-Syu"] if helper == "pacman" else ["paru", "-Syu"]

    pre_offset = PACMAN_LOG.stat().st_size if PACMAN_LOG.is_file() else 0
    pre_used = shutil.disk_usage("/").used
    t0 = time.time()
    proc = subprocess.run(cmd)
    duration = round(time.time() - t0, 1)
    post_used = shutil.disk_usage("/").used
    delta_mb = round((post_used - pre_used) / (1024**2), 1)

    txs = parse_pacman_transactions(min_offset=pre_offset, limit=10)
    merged: Dict[str, Any] = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "ended_at": datetime.now().isoformat(timespec="seconds"),
        "duration_sec": duration,
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "disk_delta_mb": delta_mb,
        "upgraded": [],
        "installed": [],
        "removed": [],
        "reinstalled": [],
        "snapshots": {"pre": None, "post": None},
        "alerts": [],
        "source": "seiza update",
    }
    for tx in txs:
        merged["upgraded"].extend(tx["upgraded"])
        merged["installed"].extend(tx["installed"])
        merged["removed"].extend(tx["removed"])
        merged["reinstalled"].extend(tx["reinstalled"])
        if tx["snapshots"].get("pre") and not merged["snapshots"]["pre"]:
            merged["snapshots"]["pre"] = tx["snapshots"]["pre"]
        if tx["snapshots"].get("post"):
            merged["snapshots"]["post"] = tx["snapshots"]["post"]
        merged["alerts"].extend(tx["alerts"])

    if proc.returncode != 0:
        merged["alerts"].append(f"Update command exited with non-zero code {proc.returncode}")

    receipt_path = save_receipt(merged)
    merged["receipt_path"] = str(receipt_path)
    return merged
