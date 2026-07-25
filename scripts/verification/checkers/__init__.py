"""Checkers subpackage registry."""

from .chains import verify_primary_chain, verify_stage6_chain
from .gates import verify_expected_closures
from .lightcurve import verify_reference_lightcurve
from .pipeline import verify_phase5_and_5b, verify_phase6, verify_stage4_selector
from .pixel import verify_stage5_pixels
from .stellar import verify_gaia, verify_stellar_sed
from .transit import verify_sector_depths, verify_transit_geometry

ALL_GROUPS = [
    ("reference_lightcurve", verify_reference_lightcurve),
    ("primary_chain", verify_primary_chain),
    ("transit_geometry", verify_transit_geometry),
    ("sector_depths", verify_sector_depths),
    ("stellar_sed", verify_stellar_sed),
    ("gaia", verify_gaia),
    ("stage5_pixels", verify_stage5_pixels),
    ("stage4_selector", verify_stage4_selector),
    ("phase5", verify_phase5_and_5b),
    ("phase6", verify_phase6),
    ("stage6_free_ld", verify_stage6_chain),
    ("release_gates", verify_expected_closures),
]

__all__ = ["ALL_GROUPS"]
