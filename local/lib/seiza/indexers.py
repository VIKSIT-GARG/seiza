"""Search indexers for apps, files/folders, browser bookmarks & safe calculator."""

from __future__ import annotations

import ast
import configparser
import json
import math
import operator
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
FUNCS = {"sqrt": math.sqrt, "log": math.log10, "ln": math.log, "sin": math.sin, "cos": math.cos, "abs": abs, "round": round}
CONSTS = {"pi": math.pi, "e": math.e}


def eval_math(expr: str) -> Optional[str]:
    clean = expr.strip()
    if clean.startswith("="):
        clean = clean[1:].strip()
    if not clean or not any(ch.isdigit() for ch in clean):
        return None
    if not any(op in clean for op in "+-*/%^()"):
        return None
    clean = clean.replace("^", "**")
    try:
        node = ast.parse(clean, mode="eval").body

        def _eval(n: ast.AST) -> float:
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return float(n.value)
            if isinstance(n, ast.Name) and n.id in CONSTS:
                return CONSTS[n.id]
            if isinstance(n, ast.BinOp) and type(n.op) in OPS:
                return float(OPS[type(n.op)](_eval(n.left), _eval(n.right)))
            if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
                return float(OPS[type(n.op)](_eval(n.operand)))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS:
                return float(FUNCS[n.func.id](*[_eval(a) for a in n.args]))
            raise ValueError("Unsupported expression")

        val = _eval(node)
        if abs(val - round(val)) < 1e-10:
            return str(int(round(val)))
        return f"{val:.6g}"
    except Exception:
        return None


def load_desktop_apps() -> List[Dict[str, str]]:
    dirs = [
        Path.home() / ".local/share/applications",
        Path.home() / ".local/share/flatpak/exports/share/applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        Path("/usr/share/applications"),
    ]
    apps: List[Dict[str, str]] = []
    seen = set()
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                cp.read(f, encoding="utf-8")
            except Exception:
                continue
            if "Desktop Entry" not in cp:
                continue
            sec = cp["Desktop Entry"]
            if sec.get("NoDisplay", "").lower() == "true" or sec.get("Hidden", "").lower() == "true":
                continue
            name = sec.get("Name", "").strip()
            exec_cmd = sec.get("Exec", "").strip()
            if not name or not exec_cmd:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            # Strip desktop field codes %u %U %f %F %i %c %k
            cleaned = " ".join(tok for tok in exec_cmd.split() if not (tok.startswith("%") and len(tok) == 2))
            apps.append(
                {
                    "kind": "App",
                    "title": name,
                    "subtitle": sec.get("Comment", sec.get("GenericName", "")).strip() or f.stem,
                    "exec": cleaned,
                    "desktop_id": f.stem,
                }
            )
    return apps


def load_bookmarks() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    seen_urls = set()

    def walk_chromium(node: Any, browser: str, folder: str = "") -> None:
        if isinstance(node, dict):
            if node.get("type") == "url" and node.get("url"):
                u = node["url"]
                if u not in seen_urls:
                    seen_urls.add(u)
                    items.append(
                        {
                            "kind": "Bookmark",
                            "title": node.get("name") or u,
                            "subtitle": f"{browser}{(' · ' + folder) if folder else ''} · {u[:65]}",
                            "url": u,
                        }
                    )
            elif "children" in node:
                sub = node.get("name", folder)
                for ch in node.get("children", []):
                    walk_chromium(ch, browser, sub)

    for browser, path in (
        ("Brave", Path.home() / ".config/BraveSoftware/Brave-Browser/Default/Bookmarks"),
        ("Chromium", Path.home() / ".config/chromium/Default/Bookmarks"),
    ):
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                for root_node in data.get("roots", {}).values():
                    walk_chromium(root_node, browser)
            except Exception:
                pass

    # Firefox / Zen immutable read-only query if profile exists
    for browser, base in (("Zen", Path.home() / ".zen"), ("Firefox", Path.home() / ".mozilla/firefox")):
        if not base.is_dir():
            continue
        for db in base.glob("*/places.sqlite"):
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True, timeout=0.5)
                rows = conn.execute(
                    "SELECT b.title, p.url FROM moz_bookmarks b JOIN moz_places p ON b.fk = p.id "
                    "WHERE b.type = 1 AND p.url LIKE 'http%' LIMIT 250"
                ).fetchall()
                conn.close()
                for title, url in rows:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        items.append(
                            {
                                "kind": "Bookmark",
                                "title": title or url,
                                "subtitle": f"{browser} · {url[:65]}",
                                "url": url,
                            }
                        )
            except Exception:
                pass

    return items


def scan_home_files(max_items: int = 350) -> List[Dict[str, str]]:
    home = Path.home()
    roots = [home, home / "Documents", home / "Downloads", home / "Pictures", home / ".config/niri", home / ".config/noctalia", home / ".local/bin"]
    results: List[Dict[str, str]] = []
    seen = set()
    skip_dirs = {".git", "node_modules", ".venv", "__pycache__", ".cache", "rice_backups", ".cargo", ".local/share"}

    for root in roots:
        if not root.exists():
            continue
        depth_limit = 1 if root == home else 2
        for cur_root, dirs, files in os.walk(root):
            rel_parts = Path(cur_root).relative_to(root).parts
            dirs[:] = [d for d in sorted(dirs) if not d.startswith(".") or root != home]
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            if len(rel_parts) >= depth_limit:
                dirs[:] = []
            for d in dirs:
                p = Path(cur_root) / d
                if str(p) not in seen:
                    seen.add(str(p))
                    results.append({"kind": "Folder", "title": d, "subtitle": str(p).replace(str(home), "~"), "path": str(p)})
            for fn in sorted(files):
                if root == home and fn.startswith("."):
                    continue
                p = Path(cur_root) / fn
                if str(p) not in seen:
                    seen.add(str(p))
                    results.append({"kind": "File", "title": fn, "subtitle": str(p).replace(str(home), "~"), "path": str(p)})
            if len(results) >= max_items:
                return results[:max_items]
    return results
