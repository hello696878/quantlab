"""Owned timezone lookup fixtures, retaining real installed TZif conversion data."""
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
import zoneinfo

import pytest

from app.futures_pit.calendar import local_to_utc, timezone_provenance

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


@pytest.fixture
def split_timezone_paths(tmp_path):
    original = tuple(zoneinfo.TZPATH)
    # Copy the installed database's real Chicago file, never a fake TZif blob.
    material = None
    for root in original:
        candidate = Path(root) / "America" / "Chicago"
        if candidate.is_file():
            material = candidate.read_bytes()
            break
    if material is None:
        material = files("tzdata.zoneinfo").joinpath("America", "Chicago").read_bytes()
    unrelated = tmp_path / "unrelated"
    supplying = tmp_path / "supplying"
    unrelated.mkdir()
    (supplying / "America").mkdir(parents=True)
    (unrelated / "tzdata.zi").write_text("# version synthetic-unrelated\n", encoding="utf-8")
    (supplying / "tzdata.zi").write_text("# version synthetic-supplying\n", encoding="utf-8")
    (supplying / "America" / "Chicago").write_bytes(material)
    try:
        zoneinfo.reset_tzpath((str(unrelated), str(supplying)))
        zoneinfo.ZoneInfo.clear_cache()
        yield supplying
    finally:
        zoneinfo.reset_tzpath(original)
        zoneinfo.ZoneInfo.clear_cache()


def test_timezone_provenance_uses_current_path_and_the_zone_supplying_root(split_timezone_paths):
    result = timezone_provenance("America/Chicago")
    assert result["source"] == "system_TZPATH"
    assert result["source_version"] == "synthetic-supplying"
    assert result["resolution_basis"] == "current_timezone_search_path"
    assert "cache origin is not tracked" in result["cache_limitation"]
    assert result["pinned"] is False
    # Independent fold expectations also confirm that copied TZif remains real.
    assert local_to_utc(datetime(2025, 11, 2, 1, 30), "America/Chicago", fold=0) == datetime(2025, 11, 2, 6, 30, tzinfo=timezone.utc)
    assert local_to_utc(datetime(2025, 11, 2, 1, 30), "America/Chicago", fold=1) == datetime(2025, 11, 2, 7, 30, tzinfo=timezone.utc)


def test_missing_supplying_version_does_not_borrow_another_roots_label(split_timezone_paths):
    (split_timezone_paths / "tzdata.zi").unlink()
    result = timezone_provenance("America/Chicago")
    assert result["source"] == "system_TZPATH"
    assert result["source_version"] is None
