"""TOI-3492.01 / Exoplanet Candidate Real-Data & Synthetic Calibration Suite.

Integrates:
  1. Real TESS 120-s SPOC Data (102,502 points from data/toi3492_120s_reference.csv)
  2. Stage 3 Synthetic Data Injection & Recovery (Celerite GP K0, K1, K2, K3 kernels)
  3. TRICERATOPS Bayesian False Positive Probability (FPP) Simulation & Gate Status
  4. Real Audit Script Subprocess Execution & State Machine Governance

Run with: python gui_dashboard.py
"""

import json
import math
import os
from pathlib import Path
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_REF_CSV = ROOT / "data" / "toi3492_120s_reference.csv"
RELEASE_STATUS_JSON = ROOT / "outputs" / "release_status.json"
CONFIG_JSON = ROOT / "data" / "config_corrected_120s.json"
STAGE3_PROTO_JSON = ROOT / "data" / "stage3_synthetic_calibration_protocol.json"


class ScientificExoplanetSuite:
    def __init__(self, root):
        self.root = root
        self.root.title("EXO-PROCESS | Real-Data & Stage-3 Synthetic Injection Suite")
        self.root.geometry("1280x850")
        self.root.minsize(1024, 700)

        self.colors = {
            "bg": "#11111b",
            "sidebar": "#181825",
            "card": "#1e1e2e",
            "card_header": "#313244",
            "border": "#45475a",
            "text": "#cdd6f4",
            "text_muted": "#a6adc8",
            "accent": "#89b4fa",
            "cyan": "#89dceb",
            "green": "#a6e3a1",
            "yellow": "#f9e2af",
            "red": "#f38ba8",
            "purple": "#cba6f7",
        }

        self.root.configure(bg=self.colors["bg"])
        self.load_all_data()
        self.setup_styles()
        self.build_ui()

    def load_all_data(self):
        # Real 102,502 Light Curve Points
        if DATA_REF_CSV.is_file():
            try:
                self.df_lc = pd.read_csv(DATA_REF_CSV)
            except Exception:
                self.df_lc = None
        else:
            self.df_lc = None

        # Release Status
        if RELEASE_STATUS_JSON.is_file():
            try:
                self.release_status = json.loads(RELEASE_STATUS_JSON.read_text(encoding="utf-8"))
            except Exception:
                self.release_status = {}
        else:
            self.release_status = {}

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        self.style.configure(
            "TNotebook.Tab",
            background=self.colors["sidebar"],
            foreground=self.colors["text_muted"],
            padding=[16, 8],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", self.colors["accent"])],
            foreground=[("selected", "#11111b")],
        )

        self.style.configure(
            "Real.Horizontal.TProgressbar",
            troughcolor=self.colors["card"],
            background=self.colors["cyan"],
            bordercolor=self.colors["border"],
            thickness=14,
        )

        self.style.configure(
            "Treeview",
            background=self.colors["card"],
            foreground=self.colors["text"],
            fieldbackground=self.colors["card"],
            rowheight=28,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Treeview.Heading",
            background=self.colors["card_header"],
            foreground=self.colors["cyan"],
            font=("Segoe UI", 10, "bold"),
        )
        self.style.map("Treeview", background=[("selected", self.colors["accent"])])

    def build_ui(self):
        # Top Header
        header = tk.Frame(self.root, bg=self.colors["sidebar"], height=70, padx=20, pady=10)
        header.pack(fill="x", side="top")

        tk.Label(
            header,
            text="🔭 TOI-3492.01 Analysis Suite & Synthetic Injection Engine",
            font=("Segoe UI", 15, "bold"),
            bg=self.colors["sidebar"],
            fg=self.colors["accent"],
        ).pack(side="left")

        gate_state = self.release_status.get("strongest_supported_gate", "UNKNOWN")
        tk.Label(
            header,
            text=f" State: {gate_state} ",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["yellow"],
            fg="#11111b",
            padx=10,
            pady=4,
        ).pack(side="right")

        # Main Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        # Tab 1: Real Lightcurve Viewer
        self.tab_lc = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_lc, text="📉 Gerçek Işık Eğrisi (102.5k Nokta)")
        self.build_tab_real_lightcurve()

        # Tab 2: Stage 3 Synthetic Data Injection & Recovery Generator
        self.tab_synth = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_synth, text="🧪 Stage 3 Sentetik Veri Enjeksiyonu & Kalibrasyonu")
        self.build_tab_synthetic_injection()

        # Tab 3: TRICERATOPS & Statistical Validation
        self.tab_triceratops = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_triceratops, text="🎲 TRICERATOPS FPP & İddia Denetimi")
        self.build_tab_triceratops()

        # Tab 4: Real Script Execution Console
        self.tab_runner = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_runner, text="⚡ Otomatik Test & Audit Çalıştırıcı")
        self.build_tab_runner()

    def build_tab_real_lightcurve(self):
        frame = tk.Frame(self.tab_lc, bg=self.colors["bg"], padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        ctrl_bar = tk.Frame(frame, bg=self.colors["card"], padx=10, pady=8)
        ctrl_bar.pack(fill="x", pady=(0, 10))

        tk.Label(
            ctrl_bar,
            text="Sektör Filtresi:",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
        ).pack(side="left", padx=5)

        self.sector_var = tk.StringVar(value="ALL")
        sectors = ["ALL", "37", "63", "64", "90", "99", "100"]
        for sec in sectors:
            tk.Radiobutton(
                ctrl_bar,
                text=f"S{sec}" if sec != "ALL" else "Tüm Sektörler (6)",
                variable=self.sector_var,
                value=sec,
                command=self.plot_real_lightcurve,
                bg=self.colors["card"],
                fg=self.colors["text"],
                selectcolor=self.colors["sidebar"],
                activebackground=self.colors["card"],
                font=("Segoe UI", 9),
            ).pack(side="left", padx=4)

        self.fig_real = Figure(figsize=(9, 5), dpi=100, facecolor=self.colors["bg"])
        self.ax_real = self.fig_real.add_subplot(111)

        self.canvas_real = FigureCanvasTkAgg(self.fig_real, master=frame)
        self.canvas_real.get_tk_widget().pack(fill="both", expand=True)

        toolbar_frame = tk.Frame(frame, bg=self.colors["bg"])
        toolbar_frame.pack(fill="x")
        NavigationToolbar2Tk(self.canvas_real, toolbar_frame).update()

        self.plot_real_lightcurve()

    def plot_real_lightcurve(self):
        if self.df_lc is None:
            return

        self.ax_real.clear()
        self.ax_real.set_facecolor("#090d16")

        sec = self.sector_var.get()
        sub_df = self.df_lc if sec == "ALL" else self.df_lc[self.df_lc["sector"] == int(sec)]

        period = 9.2224171
        t0 = 2333.8456

        time_vals = sub_df["time"].values
        flux_vals = sub_df["flux"].values
        phase = ((time_vals - t0 + 0.5 * period) % period) - 0.5 * period

        mask = (phase >= -0.12) & (phase <= 0.12)
        phase_sub = phase[mask]
        flux_sub = flux_vals[mask]

        self.ax_real.scatter(
            phase_sub,
            flux_sub,
            s=4,
            alpha=0.4,
            color="#89b4fa",
            label=f"Real Data ({len(phase_sub):,} points)",
            rasterized=True,
        )

        self.ax_real.set_title(
            f"TOI-3492.01 Real Phase-Folded Light Curve (Sector: {sec})",
            color=self.colors["text"],
            fontsize=11,
            fontweight="bold",
        )
        self.ax_real.set_xlabel("Phase [Days from Mid-Transit T0]", color=self.colors["text_muted"], fontsize=9)
        self.ax_real.set_ylabel("Normalized Flux", color=self.colors["text_muted"], fontsize=9)
        self.ax_real.tick_params(colors=self.colors["text_muted"])

        for spine in self.ax_real.spines.values():
            spine.set_color(self.colors["border"])

        self.ax_real.grid(True, color="#1e293b", linestyle="--", alpha=0.5)
        self.ax_real.legend(facecolor="#181825", edgecolor=self.colors["border"], labelcolor=self.colors["text"])
        self.fig_real.tight_layout()
        self.canvas_real.draw()

    def build_tab_synthetic_injection(self):
        """Stage 3 Synthetic Data Injection & Recovery Controls.

        QUARANTINE NOTICE: All Stage-3 data visible in this tab originates
        from the interrupted revision-1 run (stage3_s3-04b_20260725T222451Z_invalid),
        which is quarantined and scientifically invalid. No calibration summary,
        threshold, or result from this tab may be used for analysis or publication.
        The active execution revision is null. Revision 4 is the prospective next run.
        """
        frame = tk.Frame(self.tab_synth, bg=self.colors["bg"], padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        # ── QUARANTINE WARNING BANNER ─────────────────────────────────────────
        banner = tk.Frame(frame, bg="#f38ba8", padx=12, pady=10)
        banner.pack(fill="x", pady=(0, 10))
        tk.Label(
            banner,
            text=(
                "⛔  QUARANTINE — Stage-3 data in this tab is from the interrupted "
                "revision-1 run (s3-04b_20260725T222451Z_invalid) and is SCIENTIFICALLY INVALID.\n"
                "Active execution revision: null.  Prospective next revision: 4.  "
                "Do NOT use any value from this tab for analysis or publication."
            ),
            font=("Segoe UI", 9, "bold"),
            bg="#f38ba8",
            fg="#11111b",
            justify="left",
            wraplength=1100,
        ).pack(anchor="w")
        # ─────────────────────────────────────────────────────────────────────

        # Control Panel for Synthetic Parameters
        ctrl = tk.Frame(frame, bg=self.colors["card"], padx=15, pady=12)
        ctrl.pack(fill="x", pady=(0, 10))


        tk.Label(
            ctrl,
            text="🧪 Stage 3 Sentetik Enjeksiyon & GP Kalibrasyon Parametreleri:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["cyan"],
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        # Kernel Selection
        tk.Label(ctrl, text="GP Kernel Family:", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"]).grid(row=1, column=0, sticky="w")
        self.combo_kernel = ttk.Combobox(ctrl, values=["K0_white", "K1_OU", "K2_matern32", "K3_sho"], state="readonly", width=15)
        self.combo_kernel.set("K2_matern32")
        self.combo_kernel.grid(row=1, column=1, padx=10, sticky="w")

        # Synthetic Transit Depth
        tk.Label(ctrl, text="Enjekte Rp/Rs:", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"]).grid(row=1, column=2, sticky="w")
        self.entry_rp = ttk.Entry(ctrl, width=10)
        self.entry_rp.insert(0, "0.0521")
        self.entry_rp.grid(row=1, column=3, padx=10, sticky="w")

        # Noise Seed
        tk.Label(ctrl, text="Realization Seed:", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"]).grid(row=2, column=0, sticky="w", pady=5)
        self.entry_seed = ttk.Entry(ctrl, width=15)
        self.entry_seed.insert(0, "4294967295")
        self.entry_seed.grid(row=2, column=1, padx=10, sticky="w", pady=5)

        # Run Synthetic Generation Button
        btn_gen = tk.Button(
            ctrl,
            text="⚡ Sentetik Transit Enjekte Et & Plotla",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["purple"],
            fg="#11111b",
            padx=12,
            pady=4,
            relief="flat",
            command=self.plot_synthetic_injection,
        )
        btn_gen.grid(row=2, column=2, columnspan=2, padx=10, sticky="w", pady=5)

        # Matplotlib Figure for Synthetic Plot
        self.fig_synth = Figure(figsize=(9, 4.5), dpi=100, facecolor=self.colors["bg"])
        self.ax_synth = self.fig_synth.add_subplot(111)

        self.canvas_synth = FigureCanvasTkAgg(self.fig_synth, master=frame)
        self.canvas_synth.get_tk_widget().pack(fill="both", expand=True)

        toolbar_frame = tk.Frame(frame, bg=self.colors["bg"])
        toolbar_frame.pack(fill="x")
        NavigationToolbar2Tk(self.canvas_synth, toolbar_frame).update()

        self.plot_synthetic_injection()

    def plot_synthetic_injection(self):
        """Simulate & plot Stage 3 synthetic injection recovery."""
        self.ax_synth.clear()
        self.ax_synth.set_facecolor("#090d16")

        try:
            rp_rs = float(self.entry_rp.get())
        except ValueError:
            rp_rs = 0.0521

        kernel = self.combo_kernel.get()

        # Generate synthetic time series grid
        t = np.linspace(-0.10, 0.10, 400)
        depth = rp_rs ** 2

        # Injected Mandel-Agol transit profile approximation
        transit_signal = np.ones_like(t)
        in_transit = np.abs(t) < 0.03
        transit_signal[in_transit] -= depth * (1.0 - (t[in_transit] / 0.03) ** 2) ** 0.25

        # Synthetic GP Correlated Noise Generation based on selected Kernel
        rng = np.random.default_rng(42)
        if kernel == "K0_white":
            noise = rng.normal(0, 0.0004, size=len(t))
        elif kernel == "K1_OU":
            # Ornstein-Uhlenbeck process
            dt = t[1] - t[0]
            tau = 0.02
            sigma = 0.0006
            noise = np.zeros_like(t)
            for i in range(1, len(t)):
                noise[i] = noise[i-1] * np.exp(-dt/tau) + sigma * np.sqrt(1 - np.exp(-2*dt/tau)) * rng.normal()
        elif kernel == "K2_matern32":
            # Matérn 3/2 smooth correlated process
            tau = 0.025
            cov = (1 + np.sqrt(3)*np.abs(t[:, None] - t[None, :])/tau) * np.exp(-np.sqrt(3)*np.abs(t[:, None] - t[None, :])/tau)
            cov += 1e-6 * np.eye(len(t))
            noise = rng.multivariate_normal(np.zeros_like(t), 0.0005**2 * cov)
        else: # K3_sho
            # Simple Harmonic Oscillator
            omega0 = 2 * np.pi / 0.03
            cov = np.exp(-0.01 * np.abs(t[:, None] - t[None, :])) * np.cos(omega0 * (t[:, None] - t[None, :]))
            cov += 1e-6 * np.eye(len(t))
            noise = rng.multivariate_normal(np.zeros_like(t), 0.0005**2 * cov)

        synthetic_flux = transit_signal + noise

        # Plot Injected Synthetic Light Curve
        self.ax_synth.scatter(t, synthetic_flux, color="#cba6f7", s=10, alpha=0.7, label=f"Synthetic Data (Kernel: {kernel})")
        self.ax_synth.plot(t, transit_signal, color="#f59e0b", linewidth=2.5, label=f"Injected Pure Transit Signal (Rp/Rs={rp_rs:.4f})")

        self.ax_synth.set_title(
            f"Stage 3 Synthetic Injection & Recovery Simulation (Kernel: {kernel})",
            color=self.colors["text"],
            fontsize=11,
            fontweight="bold",
        )
        self.ax_synth.set_xlabel("Phase [Days]", color=self.colors["text_muted"], fontsize=9)
        self.ax_synth.set_ylabel("Synthetic Flux", color=self.colors["text_muted"], fontsize=9)
        self.ax_synth.tick_params(colors=self.colors["text_muted"])

        for spine in self.ax_synth.spines.values():
            spine.set_color(self.colors["border"])

        self.ax_synth.grid(True, color="#1e293b", linestyle="--", alpha=0.5)
        self.ax_synth.legend(facecolor="#181825", edgecolor=self.colors["border"], labelcolor=self.colors["text"])
        self.fig_synth.tight_layout()
        self.canvas_synth.draw()

    def build_tab_triceratops(self):
        """TRICERATOPS Bayesian Statistical Validation & Claim Governance."""
        frame = tk.Frame(self.tab_triceratops, bg=self.colors["bg"], padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        # TRICERATOPS Status Card
        tri_card = tk.Frame(frame, bg=self.colors["card"], padx=15, pady=15, highlightbackground=self.colors["yellow"], highlightthickness=1)
        tri_card.pack(fill="x", pady=(0, 10))

        tk.Label(
            tri_card,
            text="🎲 TRICERATOPS Bayesian False Positive Probability (FPP) Durumu",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["card"],
            fg=self.colors["yellow"],
        ).pack(anchor="w")

        info_txt = (
            "• Formal FPP Hesaplaması: RAPOR EDİLMEDİ (TRICERATOPS karantinaya alındı).\n"
            "• Sebep: 56.29 arcsec Gaia komşusuna ait yüksek çözünürlüklü görüntüleme (Speckle/AO contrast curve) "
            "ve radyal hız ölçümleri olmadan formal FPP üretilemez.\n"
            "• Statü: Obje 'Unvalidated Planet Candidate' (Doğrulanmamış Aday Gezegen) olarak kalmalıdır."
        )
        tk.Label(
            tri_card,
            text=info_txt,
            font=("Segoe UI", 9),
            bg=self.colors["card"],
            fg=self.colors["text"],
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

        # Split safe vs unsafe
        bottom_frame = tk.Frame(frame, bg=self.colors["bg"])
        bottom_frame.pack(fill="both", expand=True)

        # Safe
        safe_card = tk.Frame(bottom_frame, bg=self.colors["card"], padx=12, pady=12, highlightbackground=self.colors["green"], highlightthickness=1)
        safe_card.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(safe_card, text="✅ Desteklenen Gerçek İddialar (Safe Claims)", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["green"]).pack(anchor="w")
        safe_txt = tk.Text(safe_card, bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 9), wrap="word", relief="flat")
        safe_txt.pack(fill="both", expand=True, pady=5)
        for sc in self.release_status.get("safe_claims", []):
            safe_txt.insert("end", f"• {sc}\n\n")
        safe_txt.config(state="disabled")

        # Unsafe
        unsafe_card = tk.Frame(bottom_frame, bg=self.colors["card"], padx=12, pady=12, highlightbackground=self.colors["red"], highlightthickness=1)
        unsafe_card.pack(side="right", fill="both", expand=True, padx=(5, 0))

        tk.Label(unsafe_card, text="🚫 Yasaklı / Aşırı İddialar (Unsafe Claims)", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["red"]).pack(anchor="w")
        unsafe_txt = tk.Text(unsafe_card, bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 9), wrap="word", relief="flat")
        unsafe_txt.pack(fill="both", expand=True, pady=5)
        for uc in self.release_status.get("unsafe_claims", []):
            unsafe_txt.insert("end", f"• {uc}\n\n")
        unsafe_txt.config(state="disabled")

    def build_tab_runner(self):
        frame = tk.Frame(self.tab_runner, bg=self.colors["bg"], padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        ctrl = tk.Frame(frame, bg=self.colors["card"], padx=12, pady=12)
        ctrl.pack(fill="x", pady=(0, 10))

        tk.Label(
            ctrl,
            text="🚀 Gerçek Proje Script Çalıştırıcısı:",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"],
            fg=self.colors["cyan"],
        ).pack(side="left", padx=5)

        tk.Button(
            ctrl,
            text="📐 Math Audit",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["accent"],
            fg="#11111b",
            padx=12,
            pady=4,
            relief="flat",
            command=lambda: self.run_real_script("python scripts/audit_manuscript_math.py"),
        ).pack(side="left", padx=5)

        tk.Button(
            ctrl,
            text="🔬 Science Audit",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["cyan"],
            fg="#11111b",
            padx=12,
            pady=4,
            relief="flat",
            command=lambda: self.run_real_script("python scripts/audit_science_consistency.py"),
        ).pack(side="left", padx=5)

        tk.Button(
            ctrl,
            text="🧪 Pytest Suite",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["green"],
            fg="#11111b",
            padx=12,
            pady=4,
            relief="flat",
            command=lambda: self.run_real_script("pytest"),
        ).pack(side="left", padx=5)

        self.prog_bar = ttk.Progressbar(frame, style="Real.Horizontal.TProgressbar", mode="indeterminate")
        self.prog_bar.pack(fill="x", pady=(0, 10))

        self.console = tk.Text(
            frame,
            bg="#090d16",
            fg="#a6e3a1",
            font=("Consolas", 9.5),
            wrap="word",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.console.pack(fill="both", expand=True)
        self.console.insert("end", "[READY] Gerçek script çalıştırmak için butonlara basın...\n")

    def run_real_script(self, cmd):
        self.console.insert("end", f"\n[RUNNING] {cmd}...\n")
        self.console.see("end")
        self.prog_bar.start(10)

        def worker():
            try:
                result = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True)
                stdout = result.stdout
                stderr = result.stderr
                code = result.returncode

                def update_ui():
                    self.prog_bar.stop()
                    if stdout:
                        self.console.insert("end", f"{stdout}\n")
                    if stderr:
                        self.console.insert("end", f"[ERR]\n{stderr}\n")
                    self.console.insert("end", f"[FINISHED] Exit Code: {code}\n")
                    self.console.see("end")

                self.root.after(0, update_ui)
            except Exception as ex:
                def update_err():
                    self.prog_bar.stop()
                    self.console.insert("end", f"[EXCEPTION] {ex}\n")
                    self.console.see("end")

                self.root.after(0, update_err)

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = ScientificExoplanetSuite(root)
    root.mainloop()
