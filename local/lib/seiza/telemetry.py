"""On-demand hardware, NVIDIA/CUDA, system health, and VRAM estimator telemetry."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil


def _run(cmd: List[str], timeout: float = 3.0) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.stdout.strip()
    except Exception:
        return ""


def _read_first(path: Path) -> str:
    try:
        return path.read_text().strip()
    except Exception:
        return ""


def discover_hwmon() -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    root = Path("/sys/class/hwmon")
    if not root.is_dir():
        return out
    for entry in sorted(root.iterdir()):
        name = _read_first(entry / "name")
        if name and name not in out:
            out[name] = entry
    return out


def get_cpu_stats() -> Dict[str, Any]:
    model = "Unknown CPU"
    for line in _read_first(Path("/proc/cpuinfo")).splitlines():
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
            break
    freq = psutil.cpu_freq()
    pct_total = psutil.cpu_percent(interval=0.05)
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    load1, load5, load15 = os.getloadavg()

    hw = discover_hwmon()
    temp_c: Optional[float] = None
    for key in ("k10temp", "coretemp", "zenpower", "acpitz"):
        if key in hw:
            raw = _read_first(hw[key] / "temp1_input")
            if raw.isdigit():
                temp_c = round(int(raw) / 1000.0, 1)
                break

    return {
        "model": model,
        "cores_physical": psutil.cpu_count(logical=False) or 0,
        "cores_logical": psutil.cpu_count(logical=True) or 0,
        "percent": pct_total,
        "per_core": per_core,
        "freq_mhz": round(freq.current, 0) if freq else None,
        "freq_max_mhz": round(freq.max, 0) if freq and freq.max else None,
        "load": [round(load1, 2), round(load5, 2), round(load15, 2)],
        "temp_c": temp_c,
    }


def get_memory_stats() -> Dict[str, Any]:
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    zram_raw = _run(["zramctl", "--noheadings", "--bytes", "--output", "NAME,DISKSIZE,DATA,COMPR,ALGORITHM"])
    zram = []
    for line in zram_raw.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            try:
                disk_b, data_b, compr_b = int(parts[1]), int(parts[2]), int(parts[3])
            except ValueError:
                continue
            zram.append(
                {
                    "name": parts[0],
                    "size_gib": round(disk_b / (1024**3), 2),
                    "data_mib": round(data_b / (1024**2), 1),
                    "compr_mib": round(compr_b / (1024**2), 1),
                    "algo": parts[4],
                }
            )
    return {
        "total_gib": round(vm.total / (1024**3), 2),
        "used_gib": round(vm.used / (1024**3), 2),
        "avail_gib": round(vm.available / (1024**3), 2),
        "percent": vm.percent,
        "swap_total_gib": round(sm.total / (1024**3), 2),
        "swap_used_gib": round(sm.used / (1024**3), 2),
        "swap_percent": sm.percent,
        "zram": zram,
    }


def get_cuda_and_ml_env() -> Dict[str, Any]:
    nvcc_out = _run(["nvcc", "--version"])
    cuda_toolkit = None
    m = re.search(r"release\s+([\d.]+)", nvcc_out)
    if m:
        cuda_toolkit = m.group(1)

    # Query CUDA UMD version from nvidia-smi header (very fast)
    smi_head = _run(["nvidia-smi", "-q", "-d", "MEMORY"], timeout=2.0)
    cuda_driver = None
    for line in smi_head.splitlines():
        if "CUDA Version" in line:
            cuda_driver = line.split(":", 1)[1].split("[", 1)[0].strip()
            break

    # Probe user Python environments via dist-info metadata without importing torch
    envs: List[Dict[str, str]] = []
    candidates = [
        ("System Python", Path("/usr/lib")),
        ("~/.venv", Path.home() / ".venv"),
        ("~/.platformio-venv", Path.home() / ".platformio-venv"),
    ]
    for label, base in candidates:
        if not base.exists():
            continue
        pkgs: Dict[str, str] = {}
        site_dirs = list(base.glob("lib/python*/site-packages")) + list(base.glob("python*/site-packages"))
        for sp in site_dirs:
            for meta in sp.glob("*.dist-info"):
                n = meta.name.lower()
                for target in ("torch-", "transformers-", "onnxruntime", "vllm-", "llama_cpp", "jax-", "pyqt6-"):
                    if n.startswith(target):
                        pkg_name = meta.name[:-len(".dist-info")]
                        pkgs[pkg_name.split("-", 1)[0]] = pkg_name.split("-", 1)[1] if "-" in pkg_name else "installed"
        if pkgs:
            envs.append({"env": label, "packages": ", ".join(f"{k} {v}" for k, v in sorted(pkgs.items()))})

    return {
        "cuda_driver_version": cuda_driver,
        "cuda_toolkit_version": cuda_toolkit,
        "pytorch_cuda_alloc_conf": os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "unset"),
        "ml_envs": envs,
    }


def get_gpu_stats() -> Dict[str, Any]:
    hw = discover_hwmon()
    amd: Dict[str, Any] = {"present": "amdgpu" in hw}
    if "amdgpu" in hw:
        t = _read_first(hw["amdgpu"] / "temp1_input")
        f = _read_first(hw["amdgpu"] / "freq1_input")
        amd["temp_c"] = round(int(t) / 1000.0, 1) if t.isdigit() else None
        amd["clock_mhz"] = round(int(f) / 1e6, 0) if f.isdigit() else None

    nvidia: Dict[str, Any] = {"available": False, "processes": []}
    if shutil.which("nvidia-smi"):
        q = (
            "name,driver_version,pstate,temperature.gpu,utilization.gpu,"
            "utilization.memory,memory.used,memory.free,memory.total,"
            "power.draw,power.limit,clocks.current.graphics,clocks.max.graphics,"
            "clocks.current.memory,clocks.max.memory,persistence_mode"
        )
        raw = _run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"])
        if raw:
            parts = [x.strip() for x in raw.splitlines()[0].split(",")]
            if len(parts) >= 16:
                def fnum(v: str) -> Optional[float]:
                    try:
                        return float(v)
                    except ValueError:
                        return None

                mem_used = fnum(parts[6]) or 0.0
                mem_total = fnum(parts[8]) or 8151.0
                nvidia.update(
                    {
                        "available": True,
                        "name": parts[0],
                        "driver": parts[1],
                        "pstate": parts[2],
                        "temp_c": fnum(parts[3]),
                        "util_gpu": fnum(parts[4]),
                        "util_mem": fnum(parts[5]),
                        "vram_used_mib": mem_used,
                        "vram_free_mib": fnum(parts[7]) or max(0.0, mem_total - mem_used),
                        "vram_total_mib": mem_total,
                        "vram_percent": round((mem_used / mem_total) * 100.0, 1) if mem_total else 0.0,
                        "power_w": fnum(parts[9]),
                        "power_limit_w": fnum(parts[10]),
                        "clock_gfx_mhz": fnum(parts[11]),
                        "clock_gfx_max_mhz": fnum(parts[12]),
                        "clock_mem_mhz": fnum(parts[13]),
                        "clock_mem_max_mhz": fnum(parts[14]),
                        "persistence": parts[15],
                    }
                )
        # Collect compute + graphics apps via nvidia-smi -q -d PIDS for full process coverage
        pid_out = _run(["nvidia-smi", "-q", "-d", "PIDS"])
        cur: Dict[str, Any] = {}
        procs: List[Dict[str, Any]] = []
        for line in pid_out.splitlines():
            s = line.strip()
            if s.startswith("Process ID"):
                if cur.get("pid"):
                    procs.append(cur)
                cur = {"pid": s.split(":", 1)[1].strip()}
            elif s.startswith("Type") and cur:
                cur["type"] = s.split(":", 1)[1].strip()
            elif s.startswith("Name") and cur:
                raw_name = s.split(":", 1)[1].strip().split(" --", 1)[0]
                cur["name"] = Path(raw_name).name if "/" in raw_name else raw_name
            elif s.startswith("Used GPU Memory") and cur:
                m = re.search(r"(\d+)", s.split(":", 1)[1])
                cur["vram_mib"] = int(m.group(1)) if m else 0
        if cur.get("pid"):
            procs.append(cur)
        procs.sort(key=lambda x: x.get("vram_mib", 0), reverse=True)
        nvidia["processes"] = procs

    return {"amd_igpu": amd, "nvidia": nvidia}


QUANT_BYTES = {
    "fp32": 4.0,
    "bf16 / fp16": 2.0,
    "fp8 / int8 / q8_0": 1.05,
    "q6_k": 0.82,
    "q5_k_m": 0.69,
    "q4_k_m / awq / gptq-4bit": 0.5625,
    "iq3_xs": 0.42,
}


def estimate_model_vram(
    params_b: float,
    quant_label: str = "q4_k_m / awq / gptq-4bit",
    ctx_len: int = 8192,
    batch_size: int = 1,
    kv_precision: str = "fp16",
    total_vram_gib: float = 7.96,
    free_vram_gib: Optional[float] = None,
) -> Dict[str, Any]:
    """Estimate LLM / ML VRAM footprint on local GPU with explicit assumptions."""
    bpw = QUANT_BYTES.get(quant_label, 0.5625)
    weights_gib = (params_b * 1e9 * bpw) / (1024**3)

    # Heuristic modern GQA transformer dims scaled by param count (explicitly displayed)
    if params_b <= 2.0:
        layers, kv_heads, head_dim = 28, 4, 128
    elif params_b <= 5.0:
        layers, kv_heads, head_dim = 32, 4, 128
    elif params_b <= 9.5:
        layers, kv_heads, head_dim = 36, 8, 128
    elif params_b <= 16.0:
        layers, kv_heads, head_dim = 40, 8, 128
    else:
        layers, kv_heads, head_dim = 64, 8, 128

    kv_bytes = 2 if kv_precision == "fp16" else 1
    kv_gib = (2 * layers * kv_heads * head_dim * ctx_len * batch_size * kv_bytes) / (1024**3)
    runtime_overhead_gib = 0.55 + (weights_gib * 0.06)
    total_est_gib = weights_gib + kv_gib + runtime_overhead_gib

    headroom_gib = free_vram_gib if free_vram_gib is not None else total_vram_gib
    if total_est_gib <= headroom_gib * 0.90:
        verdict = "Comfortable fit in free VRAM"
        status = "ok"
    elif total_est_gib <= total_vram_gib * 0.96:
        verdict = "Fits total 8 GiB VRAM (close background GPU apps or partial CPU offload)"
        status = "warn"
    else:
        verdict = "Exceeds 8 GiB VRAM — requires CPU layer offload or tighter quantization"
        status = "err"

    return {
        "weights_gib": round(weights_gib, 2),
        "kv_cache_gib": round(kv_gib, 2),
        "overhead_gib": round(runtime_overhead_gib, 2),
        "total_gib": round(total_est_gib, 2),
        "headroom_gib": round(headroom_gib, 2),
        "status": status,
        "verdict": verdict,
        "assumptions": (
            f"GQA heuristic ({layers}L, {kv_heads} KV heads, d={head_dim}), "
            f"{bpw:.3f} B/param weights, {kv_precision.upper()} KV cache, "
            f"~0.55 GiB CUDA context + 6% activation buffer"
        ),
    }


def get_storage_stats() -> List[Dict[str, Any]]:
    disks = []
    seen = set()
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint in ("/", "/home") and part.mountpoint not in seen:
            seen.add(part.mountpoint)
            u = psutil.disk_usage(part.mountpoint)
            disks.append(
                {
                    "mount": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gib": round(u.total / (1024**3), 1),
                    "used_gib": round(u.used / (1024**3), 1),
                    "free_gib": round(u.free / (1024**3), 1),
                    "percent": u.percent,
                }
            )
    return disks


def get_battery_power() -> Dict[str, Any]:
    bat_dir = None
    for p in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        bat_dir = p
        break
    cap = _read_first(bat_dir / "capacity") if bat_dir else ""
    stat = _read_first(bat_dir / "status") if bat_dir else "AC"
    pwr_uw = _read_first(bat_dir / "power_now") if bat_dir else ""
    active_prof = _run(["powerprofilesctl", "get"]) or "unknown"
    return {
        "capacity": int(cap) if cap.isdigit() else None,
        "status": stat or "Unknown",
        "power_w": round(int(pwr_uw) / 1e6, 1) if pwr_uw.isdigit() else None,
        "profile": active_prof,
    }


def get_systemd_health() -> Dict[str, Any]:
    def parse_failed(user: bool) -> List[Dict[str, str]]:
        cmd = ["systemctl"] + (["--user"] if user else []) + ["--failed", "--output=json", "--no-pager"]
        raw = _run(cmd, timeout=2.5)
        try:
            items = json.loads(raw) if raw else []
            return [{"unit": x.get("unit", ""), "sub": x.get("sub", ""), "desc": x.get("description", "")} for x in items]
        except Exception:
            return []

    return {
        "system_failed": parse_failed(False),
        "user_failed": parse_failed(True),
        "uptime_sec": int(time.time() - psutil.boot_time()),
        "niri_running": any(p.name() == "niri" for p in psutil.process_iter(["name"])),
        "noctalia_running": any(p.name() == "noctalia" for p in psutil.process_iter(["name"])),
        "localsearch_masked": _run(["systemctl", "--user", "is-enabled", "localsearch-3.service"]) == "masked",
        "db_lock_exists": Path("/var/lib/pacman/db.lck").exists(),
    }


def get_network_stats(run_ping: bool = False) -> Dict[str, Any]:
    ifaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    for name, st in sorted(stats.items()):
        if name == "lo":
            continue
        v4 = [a.address for a in addrs.get(name, []) if a.family == socket.AF_INET]
        v6 = [a.address for a in addrs.get(name, []) if a.family == socket.AF_INET6 and not a.address.startswith("fe80")]
        ifaces.append({"name": name, "up": st.isup, "speed": st.speed, "ipv4": v4, "ipv6": v6})

    wifi_raw = _run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,RATE,CHAN", "dev", "wifi"])
    wifi = None
    for line in wifi_raw.splitlines():
        if line.startswith("yes:"):
            parts = line.split(":")
            if len(parts) >= 5:
                wifi = {"ssid": parts[1], "signal": parts[2], "rate": parts[3], "channel": parts[4]}
            break

    gw = ""
    route = _run(["ip", "route", "show", "default"])
    if route:
        m = re.search(r"via\s+(\S+)", route)
        if m:
            gw = m.group(1)

    dns = []
    for line in _read_first(Path("/etc/resolv.conf")).splitlines():
        if line.strip().startswith("nameserver"):
            dns.append(line.split()[1])

    latency_ms = None
    if run_ping and gw:
        ping_out = _run(["ping", "-c", "1", "-W", "1", gw], timeout=2.0)
        pm = re.search(r"time[=<]([\d.]+)\s*ms", ping_out)
        if pm:
            latency_ms = float(pm.group(1))

    return {"interfaces": ifaces, "wifi": wifi, "gateway": gw, "dns": dns, "gateway_ms": latency_ms}


def format_uptime(sec: int) -> str:
    d = sec // 86400
    h = (sec % 86400) // 3600
    m = (sec % 3600) // 60
    return f"{d}d {h}h {m}m"
