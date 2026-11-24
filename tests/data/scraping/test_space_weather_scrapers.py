from pathlib import Path

from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.scraping.base import SCRAPERS
from spacegeo.data.scraping.gfz_kp import GfzKpScraper
from spacegeo.data.scraping.omni import OmniScraper


class _NoNetwork:
    def download(self, url: str, dest: Path) -> None:
        raise AssertionError("plan() must not download")


def test_omni_plans_one_file_per_year_end_exclusive(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2024-06-01T00:00Z"), to_utc("2026-01-01T00:00Z"))
    plan = OmniScraper(tmp_path, client=_NoNetwork()).plan(window)
    assert [r.filename for r in plan] == ["omni2_2024.dat", "omni2_2025.dat"]
    assert plan[0].url == "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_2024.dat"


def test_gfz_plans_the_single_file(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2001-01-01T00:00Z"), to_utc("2026-11-23T00:00Z"))
    plan = GfzKpScraper(tmp_path, client=_NoNetwork()).plan(window)
    assert len(plan) == 1
    assert plan[0].url.endswith("Kp_ap_Ap_SN_F107_since_1932.txt")


def test_registered_by_name() -> None:
    assert SCRAPERS.get("omni2") is OmniScraper
    assert SCRAPERS.get("gfz_kp") is GfzKpScraper
