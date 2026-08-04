"""Core verification harness, mathematical utilities, and assertion helpers."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.constants import c, h, k
from scipy.special import ndtri
from scipy.stats import beta as beta_distribution
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parent.parent.parent
SECTORS = (37, 63, 64, 90, 99, 100)


def _load(relative_path: str | Path) -> Any:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def _as_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes"}


def _close(left: float, right: float, rel: float = 1e-8, abs_tol: float = 1e-10) -> bool:
    return bool(math.isclose(float(left), float(right), rel_tol=rel, abs_tol=abs_tol))


def _rank_split_rhat(draws: np.ndarray) -> np.ndarray:
    """Rank-normalized split R-hat for an (draw, walker, parameter) chain."""
    draws = np.asarray(draws, dtype=np.float64)
    n_draws, n_walkers, n_parameters = draws.shape
    half = n_draws // 2
    split = np.concatenate((draws[:half], draws[-half:]), axis=1)
    chains = np.transpose(split, (1, 0, 2))
    m, n, _ = chains.shape
    output = []
    for parameter in range(n_parameters):
        values = chains[:, :, parameter].reshape(-1)
        ranked = rankdata(values, method="average")
        normalized = ndtri((ranked - 0.375) / (len(ranked) + 0.25)).reshape(m, n)
        folded = np.abs(normalized - np.median(normalized))
        r_hats = []
        for transformed in (normalized, folded):
            within = np.mean(np.var(transformed, axis=1, ddof=1))
            between = n * np.var(np.mean(transformed, axis=1), ddof=1)
            r_hats.append(math.sqrt(((n - 1.0) / n * within + between / n) / within))
        output.append(max(r_hats))
    return np.asarray(output)


def _integrated_autocorrelation_time(draws: np.ndarray) -> np.ndarray:
    """Initial-positive-sequence IAT averaged across walkers."""
    draws = np.asarray(draws, dtype=np.float64)
    n_draws, _, n_parameters = draws.shape
    result = []
    for parameter in range(n_parameters):
        values = draws[:, :, parameter]
        values = values - np.mean(values, axis=0, keepdims=True)
        spectrum = np.fft.rfft(values, n=2 * n_draws, axis=0)
        acf = np.fft.irfft(spectrum * np.conjugate(spectrum), axis=0)[:n_draws]
        acf /= acf[0]
        mean_acf = np.mean(acf, axis=1)
        maximum = 1
        for lag in range(1, n_draws - 1, 2):
            if mean_acf[lag] + mean_acf[lag + 1] <= 0:
                break
            maximum = lag + 1
        tau = 1.0 + 2.0 * float(np.sum(mean_acf[1 : maximum + 1]))
        result.append(max(1.0, tau))
    return np.asarray(result)


def _duration_hours(rp_rs: float | np.ndarray, a_rs: float | np.ndarray, impact_parameter: float | np.ndarray, period_days: float) -> np.ndarray | float:
    sin_i = np.sqrt(1.0 - (impact_parameter / a_rs) ** 2)
    argument = np.sqrt((1.0 + rp_rs) ** 2 - impact_parameter ** 2) / (a_rs * sin_i)
    return period_days * 24.0 / math.pi * np.arcsin(np.clip(argument, -1.0, 1.0))


def _sign_flip_pvalue(values: np.ndarray) -> float:
    import itertools
    values = np.asarray(values, dtype=np.float64)
    observed = float(np.sum(values))
    totals = [float(np.dot(signs, values)) for signs in itertools.product((-1.0, 1.0), repeat=len(values))]
    return float(np.mean(np.asarray(totals) >= observed - 1e-12))


def _clopper_pearson(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    if successes == 0:
        lower = 0.0
    else:
        lower = float(beta_distribution.ppf(alpha, successes, trials - successes + 1))
    if successes == trials:
        upper = 1.0
    else:
        upper = float(beta_distribution.ppf(1.0 - alpha, successes + 1, trials - successes))
    return lower, upper


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, probabilities: list[float] | np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    cumulative = np.cumsum(np.asarray(weights)[order])
    cumulative /= cumulative[-1]
    return np.interp(probabilities, cumulative, np.asarray(values)[order])


def _blackbody_magnitudes(teff: float, log_radius_over_distance: float, av: float, band_data: list) -> np.ndarray:
    radius_distance = math.exp(log_radius_over_distance)
    model = []
    for _, wavelength_micron, zero_jy, extinction_ratio in band_data:
        wavelength = wavelength_micron * 1e-6
        frequency = c / wavelength
        intensity = 2.0 * h * frequency**3 / c**2 / math.expm1(
            h * frequency / (k * teff)
        )
        flux_jy = math.pi * intensity * radius_distance**2 / 1e-26
        model.append(-2.5 * math.log10(flux_jy / zero_jy) + av * extinction_ratio)
    return np.asarray(model)


class Verification:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.commands: list[dict[str, Any]] = []

    def check(self, group: str, item: str, ok: bool, detail: str = "") -> bool:
        self.checks.append({
            "group": group,
            "item": item,
            "ok": bool(ok),
            "detail": str(detail)[:500],
        })
        return bool(ok)

    def warning(self, group: str, item: str, detail: str) -> None:
        self.warnings.append({"group": group, "item": item, "detail": detail})

    def run_group(self, name: str, function: Callable[[Verification], None]) -> None:
        print(f"[calculation] {name}", flush=True)
        started = time.monotonic()
        try:
            function(self)
        except Exception as exc:
            self.check(name, "unhandled_exception", False, f"{type(exc).__name__}: {exc}")
        elapsed = time.monotonic() - started
        group_checks = [c for c in self.checks if c["group"] == name]
        failed = sum(not c["ok"] for c in group_checks)
        print(f"  {len(group_checks)} checks, {failed} failed, {elapsed:.1f}s", flush=True)

    def run_command(self, label: str, command: list[str]) -> None:
        print(f"[suite] {label}", flush=True)
        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        elapsed = time.monotonic() - started
        self.commands.append({
            "label": label,
            "command": command,
            "returncode": result.returncode,
            "elapsed_seconds": round(elapsed, 1),
            "stdout": result.stdout,
            "stderr": result.stderr,
        })
        self.check("suite", label, result.returncode == 0,
                   f"returncode={result.returncode} elapsed={elapsed:.1f}s")
        print(f"  {'passed' if result.returncode == 0 else 'FAILED'} ({elapsed:.1f}s)", flush=True)
