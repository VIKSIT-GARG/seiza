"""seiza. AI, ML & System Health Dashboard (PyQt6, zero background daemon)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import displays, receipts, telemetry
from .theme import PAL, build_qt_qss


def _card(object_name: str = "Card") -> QFrame:
    f = QFrame()
    f.setObjectName(object_name)
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("SectionTitle")
    return lbl


class DashboardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("seiza. // AI Workstation & Health")
        self.resize(1040, 720)
        self.polling_enabled = True
        self._vram_free_gib = 6.8
        self._vram_total_gib = 7.96
        self._receipts = []

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        # Top header bar
        hdr = QHBoxLayout()
        brand_col = QVBoxLayout()
        brand_col.setSpacing(2)
        title = QLabel("✦ seiza.  //  Workstation Intelligence")
        title.setObjectName("BrandTitle")
        subtitle = QLabel("A system of my own · On-demand telemetry (pauses cleanly when closed)")
        subtitle.setObjectName("BrandTagline")
        brand_col.addWidget(title)
        brand_col.addWidget(subtitle)
        hdr.addLayout(brand_col)
        hdr.addStretch()

        self.tab_buttons: Dict[int, QPushButton] = {}
        for idx, label in [(0, "AI && GPU"), (1, "System && Health"), (2, "Upgrade Receipts")]:
            btn = QPushButton(label)
            btn.setObjectName("NavTab")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.clicked.connect(lambda _c=False, i=idx: self._switch_tab(i))
            self.tab_buttons[idx] = btn
            hdr.addWidget(btn)

        hdr.addSpacing(10)
        self.btn_pause = QPushButton("Live (2s)")
        self.btn_pause.clicked.connect(self._toggle_polling)
        hdr.addWidget(self.btn_pause)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("PrimaryBtn")
        btn_refresh.clicked.connect(self.refresh_all)
        hdr.addWidget(btn_refresh)
        outer.addLayout(hdr)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_ai_tab())
        self.stack.addWidget(self._build_health_tab())
        self.stack.addWidget(self._build_receipts_tab())

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh_live)
        self.refresh_all()
        self.timer.start()

    def closeEvent(self, event) -> None:
        self.timer.stop()
        super().closeEvent(event)

    def _switch_tab(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        for i, btn in self.tab_buttons.items():
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if idx == 2 and not self._receipts:
            self._refresh_receipts()

    def _toggle_polling(self) -> None:
        self.polling_enabled = not self.polling_enabled
        if self.polling_enabled:
            self.btn_pause.setText("Live (2s)")
            self.timer.start()
            self.refresh_live()
        else:
            self.btn_pause.setText("Paused")
            self.timer.stop()

    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        top_grid = QGridLayout()
        top_grid.setSpacing(12)

        # GPU card
        gpu_card = _card()
        gl = QVBoxLayout(gpu_card)
        gl.setContentsMargins(16, 14, 16, 14)
        gl.setSpacing(8)
        gl.addWidget(_section_label("Discrete GPU · NVIDIA"))
        self.lbl_gpu_meta = QLabel("Loading...")
        self.lbl_gpu_meta.setStyleSheet(f"color: {PAL['muted']};")
        gl.addWidget(self.lbl_gpu_meta)

        vram_row = QHBoxLayout()
        self.lbl_vram = QLabel("VRAM: -- / -- MiB")
        self.lbl_vram.setObjectName("MetricValue")
        self.lbl_gpu_badges = QLabel("")
        self.lbl_gpu_badges.setObjectName("Mono")
        self.lbl_gpu_badges.setStyleSheet(f"color: {PAL['secondary']};")
        vram_row.addWidget(self.lbl_vram)
        vram_row.addStretch()
        vram_row.addWidget(self.lbl_gpu_badges)
        gl.addLayout(vram_row)

        self.bar_vram = QProgressBar()
        gl.addWidget(self.bar_vram)

        sub_row = QHBoxLayout()
        self.lbl_gpu_util = QLabel("Compute: --% · Temp: --°C · Power: --W")
        self.lbl_gpu_util.setObjectName("Mono")
        self.lbl_gpu_util.setStyleSheet(f"color: {PAL['text']}; font-size: 12px;")
        self.lbl_gpu_clocks = QLabel("Clocks: --")
        self.lbl_gpu_clocks.setObjectName("Mono")
        self.lbl_gpu_clocks.setStyleSheet(f"color: {PAL['muted']}; font-size: 12px;")
        sub_row.addWidget(self.lbl_gpu_util)
        sub_row.addStretch()
        sub_row.addWidget(self.lbl_gpu_clocks)
        gl.addLayout(sub_row)
        top_grid.addWidget(gpu_card, 0, 0, 1, 2)

        # CUDA / ML Runtime card
        ml_card = _card()
        ml = QVBoxLayout(ml_card)
        ml.setContentsMargins(16, 14, 16, 14)
        ml.setSpacing(6)
        ml.addWidget(_section_label("CUDA & Python ML Environment"))
        self.lbl_cuda = QLabel("CUDA: probing...")
        self.lbl_cuda.setObjectName("Mono")
        self.lbl_cuda.setWordWrap(True)
        self.lbl_ml_pkgs = QLabel("Envs: probing...")
        self.lbl_ml_pkgs.setStyleSheet(f"color: {PAL['muted']}; font-size: 12px;")
        self.lbl_ml_pkgs.setWordWrap(True)
        self.lbl_igpu = QLabel("iGPU: --")
        self.lbl_igpu.setStyleSheet(f"color: {PAL['secondary']}; font-size: 12px;")
        ml.addWidget(self.lbl_cuda)
        ml.addWidget(self.lbl_ml_pkgs)
        ml.addWidget(self.lbl_igpu)
        ml.addStretch()
        top_grid.addWidget(ml_card, 0, 2, 1, 1)

        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)
        top_grid.setColumnStretch(2, 1)
        lay.addLayout(top_grid)

        # Bottom split: VRAM estimator + GPU Processes
        bot = QHBoxLayout()
        bot.setSpacing(12)

        est_card = _card()
        el = QVBoxLayout(est_card)
        el.setContentsMargins(16, 14, 16, 14)
        el.setSpacing(8)
        el.addWidget(_section_label("Local Model VRAM Estimator (8 GiB Budget)"))

        preset_row = QHBoxLayout()
        for pb in (1.5, 3.0, 7.0, 8.0, 14.0):
            b = QPushButton(f"{pb:g}B")
            b.clicked.connect(lambda _c=False, v=pb: self.spin_params.setValue(v))
            preset_row.addWidget(b)
        el.addLayout(preset_row)

        form = QGridLayout()
        form.addWidget(QLabel("Parameters (B)"), 0, 0)
        self.spin_params = QDoubleSpinBox()
        self.spin_params.setRange(0.1, 70.0)
        self.spin_params.setSingleStep(0.5)
        self.spin_params.setValue(7.0)
        self.spin_params.valueChanged.connect(self._recalc_vram)
        form.addWidget(self.spin_params, 0, 1)

        form.addWidget(QLabel("Quantization"), 0, 2)
        self.cmb_quant = QComboBox()
        self.cmb_quant.addItems(list(telemetry.QUANT_BYTES.keys()))
        self.cmb_quant.setCurrentText("q4_k_m / awq / gptq-4bit")
        self.cmb_quant.currentTextChanged.connect(self._recalc_vram)
        form.addWidget(self.cmb_quant, 0, 3)

        form.addWidget(QLabel("Context Tokens"), 1, 0)
        self.cmb_ctx = QComboBox()
        for c in ("2048", "4096", "8192", "16384", "32768"):
            self.cmb_ctx.addItem(c)
        self.cmb_ctx.setCurrentText("8192")
        self.cmb_ctx.currentTextChanged.connect(self._recalc_vram)
        form.addWidget(self.cmb_ctx, 1, 1)

        form.addWidget(QLabel("Batch / KV"), 1, 2)
        bk_row = QHBoxLayout()
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1, 16)
        self.spin_batch.setValue(1)
        self.spin_batch.valueChanged.connect(self._recalc_vram)
        self.cmb_kv = QComboBox()
        self.cmb_kv.addItems(["fp16", "q8"])
        self.cmb_kv.currentTextChanged.connect(self._recalc_vram)
        bk_row.addWidget(self.spin_batch)
        bk_row.addWidget(self.cmb_kv)
        form.addLayout(bk_row, 1, 3)
        el.addLayout(form)

        sub_est = _card("SubCard")
        sel = QVBoxLayout(sub_est)
        sel.setContentsMargins(12, 10, 12, 10)
        self.lbl_est_breakdown = QLabel("")
        self.lbl_est_breakdown.setObjectName("Mono")
        self.lbl_est_verdict = QLabel("")
        self.lbl_est_verdict.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.lbl_est_assumptions = QLabel("")
        self.lbl_est_assumptions.setStyleSheet(f"color: {PAL['dim']}; font-size: 11px;")
        self.lbl_est_assumptions.setWordWrap(True)
        sel.addWidget(self.lbl_est_breakdown)
        sel.addWidget(self.lbl_est_verdict)
        sel.addWidget(self.lbl_est_assumptions)
        el.addWidget(sub_est)
        el.addStretch()
        bot.addWidget(est_card, 1)

        proc_card = _card()
        pl = QVBoxLayout(proc_card)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(8)
        pl.addWidget(_section_label("Active GPU Processes"))
        self.tbl_gpu_procs = QTableWidget(0, 4)
        self.tbl_gpu_procs.setHorizontalHeaderLabels(["PID", "Type", "Process", "VRAM"])
        self.tbl_gpu_procs.horizontalHeader().setStretchLastSection(True)
        self.tbl_gpu_procs.verticalHeader().setVisible(False)
        self.tbl_gpu_procs.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        pl.addWidget(self.tbl_gpu_procs, 1)
        bot.addWidget(proc_card, 1)

        lay.addLayout(bot, 1)
        return w

    def _build_health_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(12)

        cpu_c = _card()
        cl = QVBoxLayout(cpu_c)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.addWidget(_section_label("CPU & Thermals"))
        self.lbl_cpu = QLabel("...")
        self.lbl_cpu.setObjectName("MetricValue")
        self.bar_cpu = QProgressBar()
        self.lbl_cpu_sub = QLabel("...")
        self.lbl_cpu_sub.setStyleSheet(f"color: {PAL['muted']};")
        cl.addWidget(self.lbl_cpu)
        cl.addWidget(self.bar_cpu)
        cl.addWidget(self.lbl_cpu_sub)
        grid.addWidget(cpu_c, 0, 0)

        mem_c = _card()
        ml = QVBoxLayout(mem_c)
        ml.setContentsMargins(16, 14, 16, 14)
        ml.addWidget(_section_label("RAM & ZRAM Swap"))
        self.lbl_mem = QLabel("...")
        self.lbl_mem.setObjectName("MetricValue")
        self.bar_mem = QProgressBar()
        self.lbl_mem_sub = QLabel("...")
        self.lbl_mem_sub.setStyleSheet(f"color: {PAL['muted']};")
        ml.addWidget(self.lbl_mem)
        ml.addWidget(self.bar_mem)
        ml.addWidget(self.lbl_mem_sub)
        grid.addWidget(mem_c, 0, 1)

        pwr_c = _card()
        pwl = QVBoxLayout(pwr_c)
        pwl.setContentsMargins(16, 14, 16, 14)
        pwl.addWidget(_section_label("Power Profile & Battery"))
        self.lbl_pwr = QLabel("...")
        self.lbl_pwr.setObjectName("MetricValue")
        prow = QHBoxLayout()
        for prof in ("power-saver", "balanced", "performance"):
            b = QPushButton(prof)
            b.clicked.connect(lambda _c=False, p=prof: self._set_power_profile(p))
            prow.addWidget(b)
        self.lbl_disk = QLabel("...")
        self.lbl_disk.setStyleSheet(f"color: {PAL['muted']};")
        pwl.addWidget(self.lbl_pwr)
        pwl.addLayout(prow)
        pwl.addWidget(self.lbl_disk)
        grid.addWidget(pwr_c, 0, 2)

        lay.addLayout(grid)

        svc_card = _card()
        sl = QVBoxLayout(svc_card)
        sl.setContentsMargins(16, 14, 16, 14)
        hdr = QHBoxLayout()
        hdr.addWidget(_section_label("Systemd & Desktop Health Diagnostics"))
        hdr.addStretch()
        self.lbl_uptime_badge = QLabel("Uptime: --")
        self.lbl_uptime_badge.setObjectName("Mono")
        hdr.addWidget(self.lbl_uptime_badge)
        sl.addLayout(hdr)
        self.lbl_health_flags = QLabel("...")
        self.lbl_health_flags.setObjectName("Mono")
        self.lbl_health_flags.setWordWrap(True)
        sl.addWidget(self.lbl_health_flags)
        self.tbl_failed = QTableWidget(0, 3)
        self.tbl_failed.setHorizontalHeaderLabels(["Scope", "Unit", "Description"])
        self.tbl_failed.horizontalHeader().setStretchLastSection(True)
        self.tbl_failed.verticalHeader().setVisible(False)
        self.tbl_failed.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        sl.addWidget(self.tbl_failed, 1)
        lay.addWidget(svc_card, 1)
        return w

    def _build_receipts_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(_section_label("Pacman Upgrade Receipts & Rollback Audit"))
        top.addStretch()
        btn_check = QPushButton("Check Updates")
        btn_check.clicked.connect(self._run_check_updates)
        btn_term_upd = QPushButton("Launch Safe Upgrade in Alacritty")
        btn_term_upd.setObjectName("PrimaryBtn")
        btn_term_upd.clicked.connect(self._launch_upgrade_terminal)
        top.addWidget(btn_check)
        top.addWidget(btn_term_upd)
        lay.addLayout(top)

        self.lbl_updates_status = QLabel("Click 'Check Updates' to query pending repo upgrades cleanly.")
        self.lbl_updates_status.setStyleSheet(f"color: {PAL['muted']};")
        lay.addWidget(self.lbl_updates_status)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.list_receipts = QListWidget()
        self.list_receipts.currentRowChanged.connect(self._show_receipt_detail)
        self.txt_receipt_detail = QTextEdit()
        self.txt_receipt_detail.setReadOnly(True)
        self.txt_receipt_detail.setStyleSheet("font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 12px;")
        split.addWidget(self.list_receipts)
        split.addWidget(self.txt_receipt_detail)
        split.setSizes([340, 660])
        lay.addWidget(split, 1)
        return w

    def _recalc_vram(self) -> None:
        est = telemetry.estimate_model_vram(
            params_b=self.spin_params.value(),
            quant_label=self.cmb_quant.currentText(),
            ctx_len=int(self.cmb_ctx.currentText()),
            batch_size=self.spin_batch.value(),
            kv_precision=self.cmb_kv.currentText(),
            total_vram_gib=self._vram_total_gib,
            free_vram_gib=self._vram_free_gib,
        )
        self.lbl_est_breakdown.setText(
            f"Weights: {est['weights_gib']} GiB  |  KV: {est['kv_cache_gib']} GiB  |  "
            f"CUDA Overhead: {est['overhead_gib']} GiB\n"
            f"Total Required: {est['total_gib']} GiB  (Free GPU VRAM now: {est['headroom_gib']} GiB)"
        )
        col = {"ok": PAL["mint"], "warn": PAL["amber"], "err": PAL["error"]}[est["status"]]
        self.lbl_est_verdict.setStyleSheet(f"color: {col}; font-weight: 700; font-size: 13px;")
        self.lbl_est_verdict.setText(f"● {est['verdict']}")
        self.lbl_est_assumptions.setText(f"Assumptions: {est['assumptions']}")

    def _set_power_profile(self, prof: str) -> None:
        if shutil.which("noctalia"):
            subprocess.run(["noctalia", "msg", "power-set", prof], capture_output=True)
        else:
            subprocess.run(["powerprofilesctl", "set", prof], capture_output=True)
        self.refresh_live()

    def _run_check_updates(self) -> None:
        if not shutil.which("checkupdates"):
            self.lbl_updates_status.setText("checkupdates unavailable.")
            return
        out = subprocess.run(["checkupdates"], capture_output=True, text=True).stdout.splitlines()
        self.lbl_updates_status.setText(
            f"{len(out)} pending repository update(s)." + (f" First: {', '.join(out[:4])}" if out else " System up to date.")
        )

    def _launch_upgrade_terminal(self) -> None:
        subprocess.Popen(["alacritty", "-e", "fish", "-C", "seiza update"], start_new_session=True)

    def _refresh_receipts(self) -> None:
        self._receipts = receipts.load_saved_receipts(limit=25)
        self.list_receipts.clear()
        for r in self._receipts:
            ts = str(r.get("started_at", ""))[:19]
            up = len(r.get("upgraded", []))
            ins = len(r.get("installed", []))
            rem = len(r.get("removed", []))
            self.list_receipts.addItem(f"{ts}  ·  ↑{up} +{ins} -{rem}")
        if self._receipts:
            self.list_receipts.setCurrentRow(0)

    def _show_receipt_detail(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._receipts):
            return
        r = self._receipts[idx]
        lines = [
            f"Timestamp : {r.get('started_at')} -> {r.get('ended_at')}",
            f"Duration  : {r.get('duration_sec')}s",
            f"Command   : {r.get('command')}",
            f"Snapshots : {r.get('snapshots')}",
            f"Disk Delta: {r.get('disk_delta_mb') if r.get('disk_delta_mb') is not None else 'N/A (pacman.log)'}",
            "",
            f"--- Upgraded ({len(r.get('upgraded', []))}) ---",
        ]
        lines += [f"  ↑ {x['pkg']} ({x['ver']})" for x in r.get("upgraded", [])]
        lines += ["", f"--- Installed ({len(r.get('installed', []))}) ---"]
        lines += [f"  + {x['pkg']} ({x['ver']})" for x in r.get("installed", [])]
        lines += ["", f"--- Removed ({len(r.get('removed', []))}) ---"]
        lines += [f"  - {x['pkg']} ({x['ver']})" for x in r.get("removed", [])]
        if r.get("alerts"):
            lines += ["", "--- Alerts ---"] + [f"  ! {a}" for a in r["alerts"]]
        lines += [
            "",
            "--- Safe Rollback Note ---",
            "  Use Btrfs snapshots ('sudo snapper list' / Limine boot menu) or cached packages in /var/cache/pacman/pkg/.",
        ]
        self.txt_receipt_detail.setPlainText("\n".join(lines))

    def refresh_all(self) -> None:
        ml = telemetry.get_cuda_and_ml_env()
        self.lbl_cuda.setText(
            f"Driver CUDA: {ml.get('cuda_driver_version') or 'N/A'}  |  nvcc: {ml.get('cuda_toolkit_version') or 'N/A'}\n"
            f"PYTORCH_CUDA_ALLOC_CONF: {ml['pytorch_cuda_alloc_conf']}"
        )
        envs_txt = "\n".join(f"• {e['env']}: {e['packages']}" for e in ml["ml_envs"]) or "• No local torch/transformers dist-info found yet"
        self.lbl_ml_pkgs.setText(envs_txt)
        self._refresh_receipts()
        self.refresh_live()

    def refresh_live(self) -> None:
        gpu = telemetry.get_gpu_stats()
        nv = gpu["nvidia"]
        amd = gpu["amd_igpu"]
        if nv.get("available"):
            self._vram_total_gib = nv["vram_total_mib"] / 1024.0
            self._vram_free_gib = nv["vram_free_mib"] / 1024.0
            self.lbl_gpu_meta.setText(f"{nv['name']} · Driver {nv['driver']} · Persistence: {nv['persistence']}")
            self.lbl_vram.setText(f"{nv['vram_used_mib']:.0f} / {nv['vram_total_mib']:.0f} MiB ({nv['vram_percent']}%)")
            self.lbl_gpu_badges.setText(f"PState {nv['pstate']}  ·  Free {nv['vram_free_mib']:.0f} MiB")
            self.bar_vram.setValue(int(round(nv["vram_percent"])))
            self.lbl_gpu_util.setText(
                f"Compute: {nv['util_gpu']:.0f}%  |  MemCtrl: {nv['util_mem']:.0f}%  |  "
                f"Temp: {nv['temp_c']:.0f}°C  |  Power: {nv['power_w']:.1f}W / {nv.get('power_limit_w') or '?'}W"
            )
            self.lbl_gpu_clocks.setText(f"Core {nv['clock_gfx_mhz']:.0f} MHz · Mem {nv['clock_mem_mhz']:.0f} MHz")

            procs = nv["processes"]
            self.tbl_gpu_procs.setRowCount(len(procs))
            for row, p in enumerate(procs):
                for col, val in enumerate([str(p.get("pid", "")), str(p.get("type", "")), str(p.get("name", "")), f"{p.get('vram_mib', 0)} MiB"]):
                    self.tbl_gpu_procs.setItem(row, col, QTableWidgetItem(val))
        else:
            self.lbl_gpu_meta.setText("NVIDIA GPU asleep / unavailable")

        if amd.get("present"):
            self.lbl_igpu.setText(f"AMD Integrated GPU: {amd.get('temp_c') or '?'}°C · {amd.get('clock_mhz') or '?'} MHz")

        self._recalc_vram()

        cpu = telemetry.get_cpu_stats()
        mem = telemetry.get_memory_stats()
        pwr = telemetry.get_battery_power()
        disks = telemetry.get_storage_stats()
        sh = telemetry.get_systemd_health()

        self.lbl_cpu.setText(f"{cpu['percent']:.0f}%  ·  {cpu.get('temp_c') or '?'}°C")
        self.bar_cpu.setValue(int(round(cpu["percent"])))
        self.lbl_cpu_sub.setText(f"{cpu['model']} · Load {cpu['load']} · {cpu.get('freq_mhz') or '?'} MHz")

        self.lbl_mem.setText(f"{mem['used_gib']} / {mem['total_gib']} GiB")
        self.bar_mem.setValue(int(round(mem["percent"])))
        zram_str = f"zram {mem['zram'][0]['data_mib']}M->{mem['zram'][0]['compr_mib']}M" if mem["zram"] else "no zram"
        self.lbl_mem_sub.setText(f"Avail {mem['avail_gib']} GiB · Swap {mem['swap_used_gib']}/{mem['swap_total_gib']} GiB · {zram_str}")

        bat = f"{pwr['capacity']}% ({pwr['status']})" if pwr["capacity"] is not None else pwr["status"]
        self.lbl_pwr.setText(f"{pwr['profile']}  ·  {bat}")
        self.lbl_disk.setText("  |  ".join(f"{d['mount']}: {d['used_gib']}/{d['total_gib']}G ({d['percent']}%)" for d in disks))

        self.lbl_uptime_badge.setText(f"Uptime: {telemetry.format_uptime(sh['uptime_sec'])}")
        outs = displays.get_outputs()
        disp_str = ", ".join(f"{o['name']}@{o['current_mode']}" for o in outs if o["enabled"]) or "none"
        self.lbl_health_flags.setText(
            f"Niri={'active' if sh['niri_running'] else 'down'}  |  Noctalia={'active' if sh['noctalia_running'] else 'down'}  |  "
            f"Pacman Lock={'PRESENT!' if sh['db_lock_exists'] else 'clean'}  |  "
            f"localsearch-3={'masked' if sh['localsearch_masked'] else 'UNMASKED'}  |  Displays: {disp_str}"
        )

        failed = [("system", u) for u in sh["system_failed"]] + [("user", u) for u in sh["user_failed"]]
        self.tbl_failed.setRowCount(len(failed))
        for r, (scope, u) in enumerate(failed):
            self.tbl_failed.setItem(r, 0, QTableWidgetItem(scope))
            self.tbl_failed.setItem(r, 1, QTableWidgetItem(u["unit"]))
            self.tbl_failed.setItem(r, 2, QTableWidgetItem(u["desc"]))


def launch_dashboard_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setDesktopFileName("seiza-dashboard")
    app.setStyleSheet(build_qt_qss())
    win = DashboardWindow()
    win.show()
    return app.exec()
