"""Difference-image centroid offset significance.

``Z_centroid`` evaluates whether the transit signal originates on the target
star or an offset background source:

    Z = sqrt((d_ra*cos(dec))^2 + (d_dec)^2) / sigma_centroid

Pass (on-target transit): Z < 3.0 sigma.
Fail (background eclipsing binary): Z >= 3.0 sigma.
"""

from __future__ import annotations

import math
from typing import Tuple

CENTROID_THRESHOLD = 3.0


def centroid_offset_z(
    ra_offset_arcsec: float,
    dec_offset_arcsec: float,
    dec_deg: float,
    sigma_arcsec: float,
) -> float:
    """Return the centroid offset significance Z in sigma units."""
    if sigma_arcsec <= 0:
        raise ValueError("sigma_arcsec must be positive")
    separation = math.hypot(
        ra_offset_arcsec * math.cos(math.radians(dec_deg)), dec_offset_arcsec
    )
    return separation / sigma_arcsec


def centroid_gate(
    ra_offset_arcsec: float,
    dec_offset_arcsec: float,
    dec_deg: float,
    sigma_arcsec: float,
    threshold: float = CENTROID_THRESHOLD,
) -> Tuple[bool, float]:
    """Return (pass, Z). Pass means the signal is consistent with on-target."""
    z = centroid_offset_z(ra_offset_arcsec, dec_offset_arcsec, dec_deg, sigma_arcsec)
    return z < threshold, z
