"""Unified `seiza` CLI toolkit command router."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from rich import box
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from . import displays, productivity, receipts, screen_tools, telemetry, workspaces
from .theme import PAL, TAGLINE, console, print_header


def cmd_help(_args: argparse.Namespace) -> int:
    print_header("Command Reference", TAGLINE)
    groups = [
        (
            "Core & Identity",
            [
                ("seiza help", "Show this command reference"),
                ("seiza welcome", "Manual SEIZA welcome dashboard (adaptive wide/compact)"),
                ("seiza status [--json]", "Overall workstation, GPU, memory, display & systemd health"),
                ("seiza doctor", "Diagnose failed services, compositor/shell config & NVIDIA stability"),
            ],
        ),
        (
            "AI, Hardware & Updates",
            [
                ("seiza gpu [--watch|--gui|--json]", "GPU VRAM, power, CUDA, processes & model estimator"),
                ("seiza gpu --estimate <paramsB>", "Estimate LLM VRAM fit (e.g. --quant q4_k_m --ctx 8192)"),
                ("seiza dashboard", "Launch the AI, ML, Health & Receipts GUI dashboard"),
                ("seiza update [--check|--receipts|--last]", "Safe upgrade interface with Pacman upgrade receipts"),
                ("seiza clean [--dry-run]", "Preview & selectively clean safe caches, orphans & logs"),
                ("seiza network [--ping|--ports]", "Network interfaces, Wi-Fi link, DNS, latency & open ports"),
            ],
        ),
        (
            "Desktop, Displays & Productivity",
            [
                ("seiza display [subcmd]", "Wayland/Niri display manager GUI (or list/internal/extend/mirror/present)"),
                ("seiza theme [subcmd]", "Wallpaper & palette manager (status/seiza/dynamic/next/random/list/set)"),
                ("seiza workspace [preset|list]", "Launch curated workspaces (development, ai-research, electronics, focus, everyday)"),
                ("seiza keys [query|--gui]", "Searchable Niri keyboard shortcut cheatsheet"),
                ("seiza palette", "Universal Command Centre (apps, files, calc, clips, bookmarks, actions)"),
                ("seiza studio / notes / pomodoro", "Open Focus Studio (quick scratchpad, Pomodoro, pinned snippets)"),
                ("seiza snippets [list|add|copy|clear]", "Manage pinned clipboard snippets with sensitive-data shield"),
                ("seiza color / ocr / record", "Screen color picker, region OCR capture, screen recorder toggle"),
                ("seiza backup [name] / restore [name]", "Manage desktop config snapshots & rollback"),
            ],
        ),
    ]
    for title, rows in groups:
        tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        tbl.add_column("Cmd", style=f"bold {PAL['secondary']}", width=36)
        tbl.add_column("Desc", style=PAL["text"])
        for c, d in rows:
            tbl.add_row(c, d)
        console.print(f"[brand]{title}[/]")
        console.print(tbl)
    return 0


def cmd_welcome(_args: argparse.Namespace) -> int:
    cols = shutil.get_terminal_size((100, 30)).columns
    if shutil.which("fastfetch"):
        ff_cmd = "fastfetch -c ~/.config/fastfetch/compact.jsonc" if cols < 88 else "fastfetch"
        shell_runner = "fish" if shutil.which("fish") else "sh"
        subprocess.run([shell_runner, "-c", ff_cmd])
    cpu = telemetry.get_cpu_stats()
    mem = telemetry.get_memory_stats()
    gpu = telemetry.get_gpu_stats()["nvidia"]
    pwr = telemetry.get_battery_power()
    outs = displays.get_outputs()
    disp_str = ", ".join(f"{o['name']} ({o['current_mode']})" for o in outs if o.get("enabled")) or "eDP-1"
    vram_str = (
        f"{gpu['vram_used_mib']:.0f}/{gpu['vram_total_mib']:.0f} MiB · {gpu['temp_c']:.0f}°C"
        if gpu.get("available")
        else "idle"
    )
    console.print(
        Panel(
            f"[brand]CPU[/] {cpu['percent']}% ({cpu.get('temp_c') or '?'}°C)  ·  "
            f"[accent]RAM[/] {mem['used_gib']}/{mem['total_gib']} GiB  ·  "
            f"[pink]GPU[/] {vram_str}\n"
            f"[ok]Profile[/] {pwr['profile']}  ·  "
            f"[muted]Display:[/] {disp_str}\n"
            f"[dim]Tools:[/] [accent]seiza palette[/] · [accent]dashboard[/] · "
            f"[accent]display[/] · [accent]workspace[/] · [accent]studio[/] · [accent]keys[/]",
            border_style=PAL["border"],
            title="[brand]seiza. // A system of my own.[/]",
            title_align="left",
        )
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cpu = telemetry.get_cpu_stats()
    mem = telemetry.get_memory_stats()
    gpu = telemetry.get_gpu_stats()
    disks = telemetry.get_storage_stats()
    pwr = telemetry.get_battery_power()
    sys_h = telemetry.get_systemd_health()
    outs = displays.get_outputs()

    if args.json:
        print(
            json.dumps(
                {
                    "cpu": cpu,
                    "memory": mem,
                    "gpu": gpu,
                    "storage": disks,
                    "power": pwr,
                    "health": sys_h,
                    "outputs": outs,
                },
                indent=2,
            )
        )
        return 0

    print_header("System Health & Status", f"Uptime {telemetry.format_uptime(sys_h['uptime_sec'])}")
    tbl = Table(box=box.ROUNDED, border_style=PAL["border"], show_header=True, header_style=f"bold {PAL['primary']}")
    tbl.add_column("Subsystem", width=18)
    tbl.add_column("Status", width=10)
    tbl.add_column("Details")

    days = sys_h["uptime_sec"] // 86400
    up_st = "[ok]OK[/]" if days < 4 else "[warn]REBOOT[/]"
    tbl.add_row("System", up_st, f"Uptime {telemetry.format_uptime(sys_h['uptime_sec'])} | Load {cpu['load']} | Profile: {pwr['profile']}")
    tbl.add_row("CPU", "[ok]OK[/]", f"{cpu['model']} · {cpu['percent']}% · Temp {cpu.get('temp_c') or 'N/A'}°C")
    mem_st = "[ok]OK[/]" if mem["percent"] < 85 else "[warn]HIGH[/]"
    tbl.add_row("Memory", mem_st, f"{mem['used_gib']}/{mem['total_gib']} GiB ({mem['percent']}%) · Swap {mem['swap_used_gib']}/{mem['swap_total_gib']} GiB")

    nv = gpu["nvidia"]
    if nv.get("available"):
        g_st = "[ok]OK[/]" if (nv.get("temp_c") or 0) < 82 else "[warn]WARM[/]"
        tbl.add_row(
            nv.get("name", "NVIDIA GPU").replace("NVIDIA GeForce ", "").replace(" Laptop GPU", "")[:18],
            g_st,
            f"VRAM {nv['vram_used_mib']:.0f}/{nv['vram_total_mib']:.0f} MiB ({nv['vram_percent']}%) · "
            f"Util {nv['util_gpu']:.0f}% · {nv['temp_c']:.0f}°C · {nv['power_w']:.1f}W",
        )
    for d in disks:
        d_st = "[ok]OK[/]" if d["percent"] < 88 else "[warn]FULL[/]"
        tbl.add_row(f"Disk {d['mount']}", d_st, f"{d['used_gib']}/{d['total_gib']} GiB ({d['percent']}%) free {d['free_gib']} GiB [{d['fstype']}]")

    disp_desc = ", ".join(f"{o['name']} {o['current_mode']} @{o['scale']}x" for o in outs if o.get("enabled"))
    tbl.add_row("Displays", "[ok]OK[/]", disp_desc or "No enabled outputs")

    svc_fail = len(sys_h["system_failed"]) + len(sys_h["user_failed"])
    svc_st = "[ok]OK[/]" if svc_fail == 0 else "[warn]WARN[/]"
    fail_names = [u["unit"] for u in sys_h["system_failed"] + sys_h["user_failed"]]
    tbl.add_row(
        "Desktop/Units",
        svc_st,
        f"Niri={'on' if sys_h['niri_running'] else 'off'}, Noctalia={'on' if sys_h['noctalia_running'] else 'off'} | "
        f"Failed units: {svc_fail}" + (f" ({', '.join(fail_names)})" if fail_names else ""),
    )
    console.print(tbl)
    return 0


def cmd_gpu(args: argparse.Namespace) -> int:
    if args.gui:
        return cmd_dashboard(args)

    if args.estimate is not None:
        nv = telemetry.get_gpu_stats()["nvidia"]
        tot = (nv.get("vram_total_mib", 8151.0)) / 1024.0
        free = (nv.get("vram_free_mib", 6800.0)) / 1024.0
        est = telemetry.estimate_model_vram(
            args.estimate,
            quant_label=args.quant,
            ctx_len=args.ctx,
            batch_size=args.batch,
            kv_precision=args.kv,
            total_vram_gib=tot,
            free_vram_gib=free,
        )
        print_header("Model VRAM Fit Estimator", f"{args.estimate}B · {args.quant} · ctx={args.ctx}")
        tbl = Table(box=box.ROUNDED, border_style=PAL["border"], show_header=False)
        tbl.add_column("Metric", style=f"bold {PAL['primary']}")
        tbl.add_column("Value")
        tbl.add_row("Model Weights", f"{est['weights_gib']} GiB")
        tbl.add_row("KV Cache", f"{est['kv_cache_gib']} GiB (batch={args.batch}, {args.kv.upper()})")
        tbl.add_row("CUDA / Activations", f"{est['overhead_gib']} GiB")
        tbl.add_row("Estimated Total", f"[bold]{est['total_gib']} GiB[/] (free right now: {est['headroom_gib']} GiB / {tot:.2f} GiB total)")
        st_tag = {"ok": "ok", "warn": "warn", "err": "err"}[est["status"]]
        tbl.add_row("Verdict", f"[{st_tag}]{est['verdict']}[/]")
        tbl.add_row("Assumptions", f"[dim]{est['assumptions']}[/]")
        console.print(tbl)
        return 0

    def render_once() -> None:
        gpu = telemetry.get_gpu_stats()
        ml = telemetry.get_cuda_and_ml_env()
        nv = gpu["nvidia"]
        amd = gpu["amd_igpu"]
        if args.json:
            print(json.dumps({"gpu": gpu, "cuda_ml": ml}, indent=2))
            return
        print_header("AI & GPU Telemetry", "On-demand probe (zero background polling)")
        if amd.get("present"):
            console.print(
                f"[accent]iGPU · AMD amdgpu[/]  temp={amd.get('temp_c') or '?'}°C  clock={amd.get('clock_mhz') or '?'} MHz"
            )
        if not nv.get("available"):
            console.print("[warn]NVIDIA GPU unavailable or asleep.[/]")
            return
        console.print(
            f"[brand]dGPU · {nv['name']}[/]  driver={nv['driver']}  CUDA={ml.get('cuda_driver_version') or '?'} "
            f"(nvcc {ml.get('cuda_toolkit_version') or '?'})  pstate={nv['pstate']}  persistence={nv['persistence']}"
        )
        console.print(
            f"  [pink]VRAM[/] {nv['vram_used_mib']:.0f} / {nv['vram_total_mib']:.0f} MiB ({nv['vram_percent']}%, "
            f"{nv['vram_free_mib']:.0f} MiB free)  │  [accent]Compute[/] {nv['util_gpu']:.0f}%  │  "
            f"[ok]Temp[/] {nv['temp_c']:.0f}°C  │  [warn]Power[/] {nv['power_w']:.1f}W / {nv.get('power_limit_w') or '?'}W"
        )
        console.print(
            f"  [dim]Clocks:[/] Core {nv['clock_gfx_mhz']:.0f}/{nv['clock_gfx_max_mhz']:.0f} MHz  │  "
            f"Mem {nv['clock_mem_mhz']:.0f}/{nv['clock_mem_max_mhz']:.0f} MHz  │  "
            f"PYTORCH_CUDA_ALLOC_CONF={ml['pytorch_cuda_alloc_conf']}"
        )
        if nv["processes"]:
            pt = Table(box=box.SIMPLE, title="Active GPU Processes", title_justify="left")
            pt.add_column("PID", style="accent")
            pt.add_column("Type")
            pt.add_column("Process")
            pt.add_column("VRAM", justify="right", style="pink")
            for p in nv["processes"]:
                pt.add_row(str(p.get("pid", "")), str(p.get("type", "")), str(p.get("name", "")), f"{p.get('vram_mib', 0)} MiB")
            console.print(pt)

    if args.watch and not args.json:
        try:
            while True:
                console.clear()
                render_once()
                console.print("[dim]Refreshing every 1.5s · Ctrl+C to exit[/]")
                time.sleep(1.5)
        except KeyboardInterrupt:
            return 0
    render_once()
    return 0


def _dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _dirs, files in os.walk(path):
        for fn in files:
            try:
                total += (Path(root) / fn).lstat().st_size
            except OSError:
                pass
    return total


def cmd_clean(args: argparse.Namespace) -> int:
    print_header("Safe System Cleaner", "Preview first · zero destructive blind deletes")
    home = Path.home()
    candidates: List[Dict[str, Any]] = []
    for label, p in [
        ("Thumbnail cache (~/.cache/thumbnails)", home / ".cache/thumbnails"),
        ("Noctalia cache (~/.cache/noctalia)", home / ".cache/noctalia"),
        ("Fontconfig cache (~/.cache/fontconfig)", home / ".cache/fontconfig"),
    ]:
        if p.is_dir():
            sz = _dir_size_bytes(p)
            if sz > 0:
                candidates.append({"kind": "dir", "label": label, "path": p, "mb": round(sz / (1024**2), 2)})

    orphans = []
    if shutil.which("pacman"):
        r = subprocess.run(["pacman", "-Qdtq"], capture_output=True, text=True)
        orphans = [x for x in r.stdout.splitlines() if x.strip()]

    paccache_preview = ""
    if shutil.which("paccache"):
        paccache_preview = subprocess.run(["paccache", "-dk2"], capture_output=True, text=True).stdout.strip()

    j_size = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True).stdout.strip()

    tbl = Table(box=box.ROUNDED, border_style=PAL["border"])
    tbl.add_column("Target")
    tbl.add_column("Details", style="accent")
    for c in candidates:
        tbl.add_row(c["label"], f"{c['mb']:.2f} MiB")
    tbl.add_row("Pacman orphan packages", f"{len(orphans)} package(s): {', '.join(orphans[:8])}" if orphans else "0 orphans")
    tbl.add_row("Pacman cache (keep latest 2)", paccache_preview or "Nothing to prune")
    tbl.add_row("Systemd journal usage", j_size or "N/A")
    console.print(tbl)

    if args.dry_run:
        console.print("[ok]Dry run complete — no changes made.[/]")
        return 0

    if not sys.stdin.isatty():
        console.print("[warn]Non-interactive terminal; pass --dry-run or run interactively to confirm cleanup.[/]")
        return 0

    if candidates and Confirm.ask("Clean user thumbnail/fontconfig caches listed above?", default=False):
        for c in candidates:
            p: Path = c["path"]
            for child in p.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
        console.print("[ok]User caches cleaned.[/]")

    if shutil.which("paccache") and paccache_preview and "no candidate" not in paccache_preview.lower():
        if Confirm.ask("Run 'sudo paccache -rk2' (keep latest 2 package versions)?", default=False):
            subprocess.run(["sudo", "paccache", "-rk2"])
    if orphans and Confirm.ask(f"Remove {len(orphans)} orphan package(s) via sudo pacman -Rns?", default=False):
        subprocess.run(["sudo", "pacman", "-Rns", *orphans])
    return 0


def _print_receipt(r: Dict[str, Any]) -> None:
    snaps = r.get("snapshots") or {}
    snap_txt = f"pre={snaps.get('pre') or '-'} post={snaps.get('post') or '-'}"
    delta = r.get("disk_delta_mb")
    delta_txt = f"{delta:+.1f} MiB" if isinstance(delta, (int, float)) else "N/A"
    body = (
        f"[key]Started:[/] {r.get('started_at')}   [key]Duration:[/] {r.get('duration_sec')}s   "
        f"[key]Disk Delta:[/] {delta_txt}\n"
        f"[key]Command:[/] {r.get('command')}   [key]Snapshots:[/] {snap_txt}\n"
        f"[ok]Upgraded:[/] {len(r.get('upgraded', []))}   "
        f"[accent]Installed:[/] {len(r.get('installed', []))}   "
        f"[warn]Removed:[/] {len(r.get('removed', []))}   "
        f"[err]Alerts:[/] {len(r.get('alerts', []))}"
    )
    console.print(Panel(body, border_style=PAL["border"], title=f"[brand]Receipt · {r.get('started_at')}[/]"))
    for u in r.get("upgraded", [])[:20]:
        console.print(f"  [ok]↑[/] {u['pkg']} [dim]({u['ver']})[/]")
    for u in r.get("installed", [])[:10]:
        console.print(f"  [accent]+[/] {u['pkg']} [dim]({u['ver']})[/]")
    for u in r.get("removed", [])[:10]:
        console.print(f"  [warn]-[/] {u['pkg']} [dim]({u['ver']})[/]")
    for a in r.get("alerts", []):
        console.print(f"  [err]![/] {a}")


def cmd_update(args: argparse.Namespace) -> int:
    if args.receipts or args.last:
        print_header("Pacman Upgrade Receipts", "Transaction history, versions & rollback info")
        recs = receipts.load_saved_receipts(limit=1 if args.last else 12)
        if not recs:
            console.print("[muted]No upgrade transactions found.[/]")
            return 0
        for r in recs[: (1 if args.last else 6)]:
            _print_receipt(r)
        return 0

    print_header("System Update", "Safe full upgrade (never partial-upgrades)")
    if Path("/var/lib/pacman/db.lck").exists():
        console.print("[err]✗ /var/lib/pacman/db.lck exists. Resolve active/stale pacman lock first.[/]")
        return 1

    repo_updates = []
    if shutil.which("checkupdates"):
        out = subprocess.run(["checkupdates"], capture_output=True, text=True).stdout.strip()
        repo_updates = [ln for ln in out.splitlines() if ln.strip()]
    console.print(f"[accent]Available repository updates:[/] {len(repo_updates)}")
    for line in repo_updates[:15]:
        console.print(f"  · {line}")
    if len(repo_updates) > 15:
        console.print(f"  [dim]... and {len(repo_updates) - 15} more[/]")

    if args.check:
        return 0

    if not sys.stdin.isatty():
        console.print("[warn]Interactive confirmation required to run system update. Use --check or --receipts non-interactively.[/]")
        return 0

    if Confirm.ask("Proceed with full system upgrade and generate upgrade receipt?", default=False):
        rec = receipts.run_safe_update(repo_only=args.repo_only)
        console.print()
        _print_receipt(rec)
        console.print(f"[dim]Saved receipt: {rec.get('receipt_path')}[/]")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    print_header("System Doctor", "Config validation, services & hardware guardrails")
    issues = 0

    def check(ok_cond: bool, label: str, detail: str, warn_only: bool = False) -> None:
        nonlocal issues
        if ok_cond:
            console.print(f"  [ok]✓[/] [bold]{label}:[/] {detail}")
        elif warn_only:
            console.print(f"  [warn]![/] [bold]{label}:[/] {detail}")
        else:
            issues += 1
            console.print(f"  [err]✗[/] [bold]{label}:[/] {detail}")

    niri_v = subprocess.run(["niri", "validate"], capture_output=True, text=True)
    check(niri_v.returncode == 0, "Niri config", "valid" if niri_v.returncode == 0 else niri_v.stderr.strip())

    noc_v = subprocess.run(["noctalia", "config", "validate"], capture_output=True, text=True)
    check(noc_v.returncode == 0, "Noctalia config", "valid" if noc_v.returncode == 0 else noc_v.stdout.strip())

    fish_v = subprocess.run(["fish", "-n", str(Path.home() / ".config/fish/config.fish")], capture_output=True, text=True)
    check(fish_v.returncode == 0, "Fish config syntax", "valid" if fish_v.returncode == 0 else fish_v.stderr.strip())

    h = telemetry.get_systemd_health()
    check(not h["db_lock_exists"], "Pacman lock", "clean (no /var/lib/pacman/db.lck)")
    check(h["localsearch_masked"], "GNOME Tracker leak guard", "localsearch-3.service masked" if h["localsearch_masked"] else "not masked", warn_only=True)

    sys_fail = h["system_failed"]
    usr_fail = h["user_failed"]
    check(len(sys_fail) == 0, "System failed units", "0 failed" if not sys_fail else ", ".join(u["unit"] for u in sys_fail), warn_only=True)
    check(len(usr_fail) == 0, "User failed units", "0 failed" if not usr_fail else ", ".join(u["unit"] for u in usr_fail), warn_only=True)

    nv = telemetry.get_gpu_stats()["nvidia"]
    if nv.get("available"):
        check(nv.get("persistence") == "Enabled", "NVIDIA persistence", nv.get("persistence", "unknown"), warn_only=True)
    check(os.environ.get("QT_QPA_PLATFORMTHEME") == "gtk3", "Qt platform theme", os.environ.get("QT_QPA_PLATFORMTHEME", "unset"), warn_only=True)
    check(os.environ.get("GSK_RENDERER") == "gl", "GSK renderer", os.environ.get("GSK_RENDERER", "unset"), warn_only=True)
    check(shutil.which("tesseract") is not None, "OCR engine (tesseract)", "installed" if shutil.which("tesseract") else "missing — install via: sudo pacman -S tesseract tesseract-data-eng", warn_only=True)

    console.print(f"\n[brand]Doctor complete[/] · {issues} critical error(s).")
    return 1 if issues else 0


def cmd_backup(args: argparse.Namespace) -> int:
    name = args.name or f"seiza_{time.strftime('%Y%m%d_%H%M%S')}"
    subprocess.run([str(Path.home() / ".local/bin/snap"), "save", name], check=True)
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    if args.list or not args.name:
        subprocess.run([str(Path.home() / ".local/bin/snap"), "list"], check=True)
        if not args.list and sys.stdin.isatty():
            subprocess.run([str(Path.home() / ".local/bin/rice-restore")])
        return 0
    subprocess.run([str(Path.home() / ".local/bin/rice-restore"), args.name], check=True)
    return 0


def cmd_display(args: argparse.Namespace) -> int:
    sub = args.action
    if not sub:
        from .gui_display import launch_display_gui
        return launch_display_gui()
    if sub in ("list", "status"):
        print_header("Wayland / Niri Displays")
        for o in displays.get_outputs():
            st = "[ok]enabled[/]" if o["enabled"] else "[dim]disabled[/]"
            console.print(
                f"  [brand]{o['name']}[/] ({o['make']} {o['model']}) · {st} · "
                f"mode={o['current_mode'] or '-'} · scale={o['scale']} · pos=({o['x']},{o['y']})"
            )
        return 0
    if sub == "internal":
        console.print(f"[ok]✓[/] {displays.set_internal_only()}")
        return 0
    if sub == "present":
        console.print(f"[ok]✓[/] {displays.set_presentation(args.target)}")
        return 0
    if sub == "extend":
        sec = args.target
        if not sec:
            prim = displays.primary_output_name()
            outs = [o["name"] for o in displays.get_outputs() if o["name"] != prim]
            if not outs:
                console.print("[warn]No external display currently connected to extend.[/]")
                return 1
            sec = outs[0]
        console.print(f"[ok]✓[/] {displays.set_extend(prim, sec, args.side)}")
        return 0
    if sub == "mirror":
        sec = args.target
        if not sec:
            prim = displays.primary_output_name()
            outs = [o["name"] for o in displays.get_outputs() if o["name"] != prim]
            if not outs:
                console.print("[warn]No external display currently connected to mirror.[/]")
                return 1
            sec = outs[0]
        console.print(f"[ok]✓[/] {displays.start_mirror(prim, sec)}")
        return 0
    if sub == "profiles":
        profs = displays.load_profiles()
        console.print("Saved display profiles:", list(profs.keys()) or "none")
        return 0
    console.print(f"[err]Unknown display action '{sub}'[/]")
    return 1


def cmd_theme(args: argparse.Namespace) -> int:
    sub = args.action or "status"
    sync = str(Path.home() / ".local/bin/theme-sync")
    wdir = Path.home() / "Pictures/Wallpapers/Celestia"
    if sub == "status":
        subprocess.run([sync, "--status"])
        w = subprocess.run(["noctalia", "msg", "wallpaper-get"], capture_output=True, text=True).stdout.strip()
        console.print(f"[brand]Wallpaper:[/] {w}")
        return 0
    if sub in ("seiza", "celestia", "pinned", "sync"):
        subprocess.run([sync])
        return 0
    if sub == "dynamic":
        cmd = [sync, "--dynamic"] + ([args.value] if args.value else [])
        subprocess.run(cmd)
        return 0
    if sub in ("next", "prev", "random"):
        ncmd = {"next": "wallpaper-next", "prev": "wallpaper-previous", "random": "wallpaper-random"}[sub]
        subprocess.run(["noctalia", "msg", ncmd], check=True)
        time.sleep(0.35)
        subprocess.run([sync])
        return 0
    if sub in ("list", "wallpapers"):
        print_header("seiza. Celestial Wallpapers")
        for p in sorted(wdir.glob("*")):
            console.print(f"  · [accent]{p.name}[/] [dim]({p})[/]")
        return 0
    if sub == "set" and args.value:
        p = Path(args.value)
        if not p.exists() and (wdir / args.value).exists():
            p = wdir / args.value
        subprocess.run(["noctalia", "msg", "wallpaper-set", str(p.resolve())], check=True)
        time.sleep(0.3)
        subprocess.run([sync])
        return 0
    console.print("[warn]Usage: seiza theme [status|seiza|dynamic|next|prev|random|list|set <path>][/]")
    return 1


def cmd_network(args: argparse.Namespace) -> int:
    print_header("Network Diagnostics")
    n = telemetry.get_network_stats(run_ping=args.ping or True)
    tbl = Table(box=box.ROUNDED, border_style=PAL["border"])
    tbl.add_column("Interface", style=f"bold {PAL['primary']}")
    tbl.add_column("State")
    tbl.add_column("IPv4 / IPv6")
    for i in n["interfaces"]:
        if i["name"].startswith("veth"):
            continue
        st = "[ok]UP[/]" if i["up"] else "[dim]DOWN[/]"
        ips = ", ".join(i["ipv4"] + i["ipv6"]) or "—"
        tbl.add_row(i["name"], st, ips)
    console.print(tbl)
    if n["wifi"]:
        w = n["wifi"]
        console.print(f"[accent]Wi-Fi:[/] SSID={w['ssid']} · Signal={w['signal']}% · Rate={w['rate']} · Ch={w['channel']}")
    gw_lat = f"{n['gateway_ms']} ms" if n.get("gateway_ms") is not None else "no ping"
    console.print(
        f"[muted]Gateway:[/] {n['gateway'] or 'none'} ({gw_lat})  │  "
        f"[muted]DNS:[/] {', '.join(n['dns']) or 'none'}"
    )
    if args.ports:
        console.print("\n[brand]Listening TCP/UDP Sockets:[/]")
        subprocess.run(["ss", "-tuln"])
    return 0


def cmd_workspace(args: argparse.Namespace) -> int:
    if args.gui or (not args.preset and not args.list):
        if shutil.which("fuzzel") and not args.list:
            choices = "\n".join(f"{p.id}\t{p.name} — {p.tagline}" for p in workspaces.PRESETS.values())
            sel = subprocess.run(
                ["fuzzel", "--dmenu", "--prompt", "seiza. workspace: ", "--lines", "8", "--width", "60"],
                input=choices,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if not sel:
                return 0
            pid = sel.split("\t", 1)[0].strip()
            res = workspaces.launch_preset(pid, dry_run=args.dry_run)
            console.print(f"[ok]✓ Launched {res['preset']}:[/] {', '.join(res['launched'])}")
            return 0
        args.list = True

    if args.list:
        print_header("Developer Workspaces")
        for p in workspaces.PRESETS.values():
            rows = workspaces.check_preset_availability(p)
            apps_txt = ", ".join(
                f"[ok]{r['label']}[/]" if r["available"] == "yes" else f"[dim]{r['label']} (missing)[/]"
                for r in rows
            )
            console.print(f"  [brand]{p.id:12}[/] [bold]{p.name}[/] — {p.tagline}\n    [dim]Apps:[/] {apps_txt}")
        return 0

    try:
        res = workspaces.launch_preset(args.preset, dry_run=args.dry_run)
        console.print(f"[ok]✓ Workspace {res['preset']}:[/] launched {', '.join(res['launched']) or 'none'}")
        if res["skipped"]:
            console.print(f"[warn]Skipped:[/] {', '.join(res['skipped'])}")
        return 0
    except ValueError as e:
        console.print(f"[err]✗ {e}[/]")
        return 1


def cmd_keys(args: argparse.Namespace) -> int:
    if args.gui:
        from .gui_studio import launch_studio_gui
        return launch_studio_gui(initial_tab="keys")
    rows = productivity.parse_keybinds()
    q = (args.query or "").lower().strip()
    if q:
        rows = [r for r in rows if q in r["chord"].lower() or q in r["description"].lower() or q in r["section"].lower()]
    if args.fuzzel and shutil.which("fuzzel"):
        lines = "\n".join(f"{r['chord']:22} · {r['description']} [{r['section']}]" for r in rows)
        subprocess.run(["fuzzel", "--dmenu", "--prompt", "seiza. keys: ", "--lines", "16", "--width", "70"], input=lines, text=True)
        return 0
    print_header("Keyboard Shortcut Reference", f"{len(rows)} bindings")
    tbl = Table(box=box.ROUNDED, border_style=PAL["border"])
    tbl.add_column("Section", style="dim", width=24)
    tbl.add_column("Shortcut", style=f"bold {PAL['primary']}", width=22)
    tbl.add_column("Action")
    for r in rows:
        tbl.add_row(r["section"], r["chord"], r["description"])
    console.print(tbl)
    return 0


def cmd_dashboard(_args: argparse.Namespace) -> int:
    from .gui_dashboard import launch_dashboard_gui
    return launch_dashboard_gui()


def cmd_palette(_args: argparse.Namespace) -> int:
    from .gui_palette import launch_palette_gui
    return launch_palette_gui()


def cmd_studio(args: argparse.Namespace) -> int:
    from .gui_studio import launch_studio_gui
    return launch_studio_gui(initial_tab=getattr(args, "tab", "notes"))


def cmd_snippets(args: argparse.Namespace) -> int:
    sub = args.action or "list"
    if sub == "list":
        print_header("Clipboard Pinned Snippets", "Sensitive tokens automatically masked")
        for idx, s in enumerate(productivity.load_snippets()):
            console.print(f"  [{idx}] [brand]{s['title']}[/] · {productivity.mask_preview(s['text'], s.get('sensitive', False))}")
        return 0
    if sub == "add":
        try:
            rec = productivity.add_snippet(args.title or "", args.text or "", allow_sensitive=args.allow_sensitive)
            console.print(f"[ok]✓ Pinned snippet:[/] {rec['title']}")
            return 0
        except ValueError as e:
            console.print(f"[err]✗ {e}[/]")
            return 1
    if sub == "copy":
        items = productivity.load_snippets()
        idx = int(args.title or 0)
        if 0 <= idx < len(items):
            productivity.copy_text(items[idx]["text"])
            console.print(f"[ok]✓ Copied '{items[idx]['title']}' to clipboard.[/]")
            return 0
        console.print("[err]Invalid snippet index[/]")
        return 1
    if sub == "clear-history":
        productivity.clear_clipboard_history()
        console.print("[ok]✓ Cleared cliphist & Noctalia clipboard history.[/]")
        return 0
    return 0


def cmd_color(_args: argparse.Namespace) -> int:
    hx = screen_tools.pick_screen_color()
    if hx:
        console.print(f"[ok]✓ Picked & copied:[/] {hx}")
    return 0


def cmd_ocr(args: argparse.Namespace) -> int:
    img = Path(args.image) if getattr(args, "image", None) else None
    ok, msg = screen_tools.run_ocr(img)
    if ok:
        console.print(f"[ok]✓ OCR copied to clipboard:[/]\n{msg}")
    else:
        console.print(f"[warn]{msg}[/]")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    res = screen_tools.toggle_recording(args.action or "toggle")
    console.print(f"[accent]{res}[/]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="seiza", description="seiza. // A system of my own. — Workstation CLI")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("help", help="List available commands").set_defaults(func=cmd_help)
    sub.add_parser("welcome", help="Open manual terminal welcome dashboard").set_defaults(func=cmd_welcome)

    sp_st = sub.add_parser("status", help="System health summary")
    sp_st.add_argument("--json", action="store_true")
    sp_st.set_defaults(func=cmd_status)

    sp_gpu = sub.add_parser("gpu", help="GPU telemetry & VRAM estimator")
    sp_gpu.add_argument("--watch", "-w", action="store_true")
    sp_gpu.add_argument("--gui", action="store_true")
    sp_gpu.add_argument("--json", action="store_true")
    sp_gpu.add_argument("--estimate", type=float, metavar="PARAMS_B", help="Estimate model VRAM fit (in billions of params)")
    sp_gpu.add_argument("--quant", default="q4_k_m / awq / gptq-4bit")
    sp_gpu.add_argument("--ctx", type=int, default=8192)
    sp_gpu.add_argument("--batch", type=int, default=1)
    sp_gpu.add_argument("--kv", default="fp16", choices=["fp16", "q8"])
    sp_gpu.set_defaults(func=cmd_gpu)

    sp_cl = sub.add_parser("clean", help="Preview and safely clean caches")
    sp_cl.add_argument("--dry-run", action="store_true")
    sp_cl.set_defaults(func=cmd_clean)

    sp_up = sub.add_parser("update", help="System upgrade interface & receipts")
    sp_up.add_argument("--check", action="store_true")
    sp_up.add_argument("--receipts", action="store_true")
    sp_up.add_argument("--last", action="store_true")
    sp_up.add_argument("--repo-only", action="store_true")
    sp_up.set_defaults(func=cmd_update)

    sub.add_parser("doctor", help="Diagnose failed services and configs").set_defaults(func=cmd_doctor)

    sp_bk = sub.add_parser("backup", help="Create configuration snapshot")
    sp_bk.add_argument("name", nargs="?")
    sp_bk.set_defaults(func=cmd_backup)

    sp_rs = sub.add_parser("restore", help="Restore a configuration snapshot")
    sp_rs.add_argument("name", nargs="?")
    sp_rs.add_argument("--list", action="store_true")
    sp_rs.set_defaults(func=cmd_restore)

    sp_dp = sub.add_parser("display", help="External display manager")
    sp_dp.add_argument("action", nargs="?", choices=["list", "status", "internal", "extend", "mirror", "present", "profiles"])
    sp_dp.add_argument("target", nargs="?")
    sp_dp.add_argument("--side", default="right", choices=["right", "left", "above", "below"])
    sp_dp.set_defaults(func=cmd_display)

    sp_th = sub.add_parser("theme", help="Wallpaper and theme controls")
    sp_th.add_argument("action", nargs="?")
    sp_th.add_argument("value", nargs="?")
    sp_th.set_defaults(func=cmd_theme)

    sp_nw = sub.add_parser("network", help="Network diagnostics")
    sp_nw.add_argument("--ping", action="store_true")
    sp_nw.add_argument("--ports", action="store_true")
    sp_nw.set_defaults(func=cmd_network)

    sp_ws = sub.add_parser("workspace", help="Launch curated developer workspaces")
    sp_ws.add_argument("preset", nargs="?")
    sp_ws.add_argument("--list", action="store_true")
    sp_ws.add_argument("--gui", action="store_true")
    sp_ws.add_argument("--dry-run", action="store_true")
    sp_ws.set_defaults(func=cmd_workspace)

    sp_ky = sub.add_parser("keys", help="Searchable keyboard shortcut reference")
    sp_ky.add_argument("query", nargs="?")
    sp_ky.add_argument("--gui", action="store_true")
    sp_ky.add_argument("--fuzzel", action="store_true")
    sp_ky.set_defaults(func=cmd_keys)

    sub.add_parser("dashboard", help="Open AI, ML & Health GUI Dashboard").set_defaults(func=cmd_dashboard)
    sub.add_parser("palette", help="Open Universal Command Centre").set_defaults(func=cmd_palette)
    sub.add_parser("color", help="Screen pixel color picker").set_defaults(func=cmd_color)

    sp_ocr = sub.add_parser("ocr", help="Screen region OCR capture")
    sp_ocr.add_argument("image", nargs="?")
    sp_ocr.set_defaults(func=cmd_ocr)

    sp_rec = sub.add_parser("record", help="Screen recording toggle")
    sp_rec.add_argument("action", nargs="?", default="toggle")
    sp_rec.set_defaults(func=cmd_record)

    sub.add_parser("studio", help="Open Focus Studio (Notes, Pomodoro, Snippets)").set_defaults(func=cmd_studio, tab="notes")
    sub.add_parser("notes", help="Open Quick Scratchpad").set_defaults(func=cmd_studio, tab="notes")
    sub.add_parser("pomodoro", help="Open Pomodoro Focus Timer").set_defaults(func=cmd_studio, tab="pomodoro")

    sp_sn = sub.add_parser("snippets", help="Manage clipboard snippets & privacy")
    sp_sn.add_argument("action", nargs="?", default="list", choices=["list", "add", "copy", "clear-history"])
    sp_sn.add_argument("title", nargs="?")
    sp_sn.add_argument("text", nargs="?")
    sp_sn.add_argument("--allow-sensitive", action="store_true")
    sp_sn.set_defaults(func=cmd_snippets)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        return cmd_help(args)
    return int(args.func(args))
