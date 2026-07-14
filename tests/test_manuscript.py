import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "toi3492_characterization.tex").read_text()


def test_unsupported_claims_are_absent():
    forbidden = [
        r"FPP\s*\\approx",
        r"0\.011\\%",
        r"increasing radius amplifies",
        r"transit duration of \\approx2\.9",
        r"free-geometry fit",
        r"on-target planetary signal",
        r"4\.3\\,\\sigma",
        r"independently recovers the official",
        r"eccentricity\s+illustrating",
        r"all have no match",
        r"giant-planet-size(?!d)",
        r"independent native-cadence geometry",
        r"13-hour window centered on transit",
        r"9\.222136",
        r"9\.22146",
        r"Mid-transit model depth\s+&.*\(posterior median\)",
        r"angle between the emergent intensity and the line of sight",
        r"an\s+\\operatorname\{Beta\}",
    ]
    for pattern in forbidden:
        assert re.search(pattern, TEXT, flags=re.IGNORECASE) is None


def test_adopted_numbers_are_present():
    required = [
        r"0\.05472\\pm0\.00049",
        r"10\.60\\pm0\.45",
        r"15\.47\\pm0\.66",
        r"3094",
        r"1616\^\{\+65\}_\{-61\}",
        r"2632\\pm22",
        r"2702\\pm38",
        r"a/R_\\star=10\.248",
        r"R_\\star=2\.671",
        r"0\.046",
        r"10\.44\^\{\+0\.32\}_\{-0\.29\}",
        r"10\.32\^\{\+0\.28\}_\{-0\.30\}",
        r"-144\\pm17",
        r"model-conditional",
        r"no scan over\s+secondary-eclipse phases allowed by eccentric orbits",
        r"preliminary implementation of a preregistered search",
        r"NASAExoplanetArchiveTOI",
        r"Husser2013",
        r"\|t-T_c\|<13",
        r"0\.05567\^\{\+0\.00039\}_\{-0\.00040\}",
        r"1\.95 adopted posterior",
        r"\\frac\{3\\pi\}\{G P\^2\}",
        r"TIC~v8 has no metallicity value",
        r"at the marginal posterior medians",
        r"No candidate passed all preregistered detection gates",
        r"9\.4--10\.9",
        r"\\mathrm\{BTJD\}=\\mathrm\{BJD\}_\{\\rm TDB\}-2457000",
        r"G M_\\star\(1\+q\)P\^2",
        r"\\Delta\\nu_\\odot=135\.1",
        r"false-alarm controls remain incomplete",
        r"false-positive probability \(FPP\)",
        r"I\(\\mu\)\$ is the emergent\s+specific intensity",
        r"local\s+surface normal and the line of sight",
        r"\\rho_\{\\star,\\rm circ\}\^\{\(q=0\)\}\\equiv\\rho_\{\\star,\\rm phot\}",
        r"\\hat d\$ is the fitted eclipse depth",
        r"TESS magnitude \$T_\{\\rm mag\}=8\.45\$",
    ]
    for pattern in required:
        assert re.search(pattern, TEXT) is not None


def test_unresolved_zenodo_doi_is_not_claimed():
    public_text = "\n".join(
        [
            TEXT,
            (ROOT / "README.md").read_text(),
            (ROOT / "CITATION.cff").read_text(),
        ]
    )
    assert "10.5281/zenodo.21327242" not in public_text
    assert "version 1.0.1" in TEXT
