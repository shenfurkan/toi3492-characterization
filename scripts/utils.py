"""Shared utilities used by the TOI-3492.01 pipeline scripts.

Provides:

    * load_config / save_config  –  read/write JSON configuration files
    * load_lightcurve            –  read the reference CSV into numpy arrays
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    """Load a JSON configuration file.

    Parameters
    ----------
    path : Path or str, optional
        Path to the JSON file.  Defaults to ``data/config.json``.

    Returns
    -------
    dict
    """
    if path is None:
        path = ROOT / "data" / "config.json"
    with open(path, "r") as f:
        return json.load(f)


def save_config(config, path=None):
    """Write a dictionary to a JSON configuration file.

    Parameters
    ----------
    config : dict
    path : Path or str, optional
        Defaults to ``data/config.json``.
    """
    if path is None:
        path = ROOT / "data" / "config.json"
    with open(path, "w") as f:
        json.dump(config, f, indent=4)
    print(f"Config saved to {path}")


def load_lightcurve(path=None):
    """Read the corrected 120-s reference light curve CSV.

    Parameters
    ----------
    path : Path or str, optional
        Defaults to ``data/toi3492_120s_reference.csv``.

    Returns
    -------
    t : ndarray
        BJD - 2457000 time array.
    flux : ndarray
        Normalised flux.
    flux_err : ndarray
        Flux uncertainty.
    """
    if path is None:
        path = ROOT / "data" / "toi3492_120s_reference.csv"
    df = pd.read_csv(path)
    t = df["time"].values
    flux = df["flux"].values
    flux_err = df["flux_err"].values
    return t, flux, flux_err
