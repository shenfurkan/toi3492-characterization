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
        r"4\.3\\,\\sigma",
        r"2632\\pm22",
        r"2702\\pm38",
        r"a/R_\\star=10\.248",
        r"R_\\star=2\.671",
        r"p=0\.046",
        r"10\.44\^\{\+0\.32\}_\{-0\.29\}",
        r"10\.32\^\{\+0\.28\}_\{-0\.30\}",
        r"-144\\pm17",
    ]
    for pattern in required:
        assert re.search(pattern, TEXT) is not None
