import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from asteroseismic_search import parse_product, symmetric_clip, transit_mask


ROOT = Path(__file__).resolve().parents[1]


def load_inventory():
    return json.loads(
        (ROOT / "outputs" / "asteroseismic_input_inventory.json").read_text()
    )


def test_spoc_seismic_inventory_metadata_is_complete():
    inventory = load_inventory()
    products = inventory["products"]
    assert inventory["includes_tpf"] is True
    assert len(products) == 18
    assert {row["product_type"] for row in products} == {"lc", "tpf"}
    assert {row["sector"] for row in products} == {37, 63, 64, 90, 99, 100}
    assert all(len(row["sha256"]) == 64 for row in products)
    assert all(row["size_bytes"] > 0 for row in products)


@pytest.mark.integration
def test_downloaded_spoc_seismic_files_match_inventory():
    inventory = load_inventory()
    products = inventory["products"]
    for row in products:
        path = ROOT / row["relative_path"]
        assert path.is_file()
        assert path.stat().st_size == row["size_bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_product_parser_handles_both_spoc_cadences():
    assert parse_product(
        Path("tess-x-s0090-0000000081077799-0287-a_fast-lc.fits")
    ) == (90, 20)
    assert parse_product(
        Path("tess-x-s0037-0000000081077799-0208-s_lc.fits")
    ) == (37, 120)


def test_seismic_preprocessing_masks_transit_and_clips_symmetrically():
    around_transit = np.array([2314.5211550, 2314.5211550 + 0.5])
    mask = transit_mask(around_transit)
    assert mask.tolist() == [False, True]

    flux = np.array([-10.0, -0.1, 0.0, 0.1, 10.0])
    clip = symmetric_clip(flux, sigma=3.0)
    assert clip[0] == clip[4] == False


def test_feasibility_values_and_non_detection_status_are_frozen():
    feasibility = json.loads(
        (ROOT / "outputs" / "asteroseismic_feasibility.json").read_text()
    )
    assert np.isclose(
        feasibility["scenarios"]["gaia_flame_mass_radius"]["dnu_density_scaling_uhz"],
        38.07907175119582,
    )
    assert np.isclose(
        feasibility["scenarios"]["circular_transit_density"]["dnu_density_scaling_uhz"],
        58.55708259349396,
    )
    assert feasibility["revised_atl"][0]["probability"] < 0.12

    preliminary = json.loads(
        (ROOT / "outputs" / "asteroseismic_preliminary_search.json").read_text()
    )
    pysyd = json.loads(
        (ROOT / "outputs" / "asteroseismic_pysyd_crosscheck.json").read_text()
    )
    assert "not_a_detection" in preliminary["status"]
    assert "not_a_detection" in pysyd["status"]
