import json

import numpy as np
import pytest

from exonym.catalog import (
    IdentifierError,
    make_provenance,
    mission_for_identifier,
    parse_identifier,
    write_provenance_sidecar,
)
from exonym.ingest import ingest_products
from exonym.workspace import create_candidate, discover_candidates


@pytest.mark.parametrize(
    "raw, kind, mission, value",
    [
        ("TOI 1234.01", "toi", "tess", "1234.01"),
        ("toi-8888.01", "toi", "tess", "8888.01"),
        ("TIC 123456789", "tic", "tess", "123456789"),
        ("TIC:987654321", "tic", "tess", "987654321"),
        ("K00007.01", "koi", "kepler", "00007.01"),
        ("K7.01", "koi", "kepler", "7.01"),
        ("EPIC 201367065", "epic", "k2", "201367065"),
        ("PIC-12345", "pic", "plato", "12345"),
        ("CHEOPS-ABCD123", "cheops", "cheops", "ABCD123"),
    ],
)
def test_parse_identifier(raw, kind, mission, value):
    parsed = parse_identifier(raw)
    assert parsed["kind"] == kind
    assert parsed["mission"] == mission
    assert parsed["value"] == value
    assert mission_for_identifier(raw) == mission


@pytest.mark.parametrize("raw", ["", "garbage", "TOI", "1234.01", "K1234"])
def test_parse_identifier_rejects_unknown(raw):
    with pytest.raises(IdentifierError):
        parse_identifier(raw)


def test_make_provenance_records_sha256(tmp_path):
    product = tmp_path / "lc.fits"
    product.write_bytes(b"fits-data")
    record = make_provenance(
        product,
        "https://archive.stsci.edu/example",
        fetched_by="test",
        download_timestamp_utc="2026-08-04T00:00:00Z",
    )
    assert record["sha256"] == "a" * 64 or len(record["sha256"]) == 64
    assert record["download_timestamp_utc"] == "2026-08-04T00:00:00Z"
    assert record["fetched_by"] == "test"


def test_write_provenance_sidecar_matches_gatekeeper_convention(tmp_path):
    product = tmp_path / "s0001_lc.fits.gz"
    product.write_bytes(b"fits")
    sidecar = write_provenance_sidecar(product, "https://example.invalid/p", fetched_by="test")
    assert sidecar.name == "s0001_lc.fits.provenance.json"
    assert sidecar.is_file()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["source_uri"] == "https://example.invalid/p"


def test_ingest_products_copies_and_sidecars(tmp_path):
    create_candidate(tmp_path, "candidate-alpha")
    candidate = [c for c in discover_candidates(tmp_path)][0]

    staging = tmp_path / "staging"
    staging.mkdir()
    product = staging / "s0037_lc.fits"
    product.write_bytes(b"fits")

    written = ingest_products(
        candidate, [(product, "https://archive.stsci.edu/example")], fetched_by="test"
    )
    raw = candidate.path / "data" / "raw"
    assert (raw / "s0037_lc.fits").is_file()
    assert (raw / "s0037_lc.provenance.json").is_file()
    assert written == [(raw / "s0037_lc.fits")]

    with pytest.raises(FileExistsError):
        ingest_products(candidate, [(product, "https://archive.stsci.edu/example")])


def test_ingest_products_requires_tic_for_network_fetch(tmp_path):
    create_candidate(tmp_path, "candidate-beta")
    candidate = [c for c in discover_candidates(tmp_path) if c.candidate_id == "candidate-beta"][0]

    from exonym.ingest import fetch_tess_products

    with pytest.raises(ValueError, match="TIC"):
        fetch_tess_products(candidate, sectors=[37])


class _FakeDownload:
    def __init__(self, light_curve):
        self._light_curve = light_curve

    def download(self):
        return self._light_curve


class _FakeSearch:
    def __init__(self, table, light_curves):
        self.table = table
        self._light_curves = light_curves

    def __len__(self):
        return len(self._light_curves)

    def __getitem__(self, index):
        return _FakeDownload(self._light_curves[index])


def test_fetch_tess_products_writes_fits_and_ingests(tmp_path, monkeypatch):
    import lightkurve as lk
    from astropy.table import Table

    from exonym.ingest import fetch_tess_products, ingest_products

    create_candidate(tmp_path, "candidate-ingest", tic="123456789")
    candidate = [
        c for c in discover_candidates(tmp_path) if c.candidate_id == "candidate-ingest"
    ][0]

    table = Table(
        rows=[("s0037", "tess2021000000000-s0037-0000000123456789-0218-s.fits")],
        names=("sequence_number", "obs_id"),
    )
    time = np.linspace(2459000.0, 2459030.0, 600)
    light_curve = lk.LightCurve(time=time, flux=np.ones_like(time))
    fake_search = _FakeSearch(table, [light_curve])

    monkeypatch.setattr(lk, "search_lightcurve", lambda *args, **kwargs: fake_search)

    products = fetch_tess_products(candidate, exptime=120)
    assert len(products) == 1
    staged, source_uri = products[0]
    assert staged.is_file()
    assert staged.stat().st_size > 0
    assert source_uri.startswith("https://mast.stsci.edu")

    written = ingest_products(candidate, products)
    raw = candidate.path / "data" / "raw"
    assert written[0].is_file()
    assert written[0].parent == raw
    sidecar = written[0].with_name(written[0].stem + ".provenance.json")
    assert sidecar.is_file()
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    assert record["source_uri"] == source_uri
    assert len(record["sha256"]) == 64
