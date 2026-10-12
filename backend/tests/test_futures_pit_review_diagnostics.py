"""Independent completeness checks for the public continuous validator."""
from pathlib import Path

import pandas as pd
import pytest

from app.datastore.futures_continuous import build_continuous_futures
from app.futures_pit.adapter import AdapterRequest, preview
from app.futures_pit.diagnostics import validate_continuous
from app.futures_pit.revisions import legacy_frame
from app.instruments import get_instrument

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
CORPUS = Path(__file__).parent / "fixtures/futures_pit"


@pytest.fixture
def inputs():
    result = preview(AdapterRequest(provider="local_file", csv_path=str(CORPUS / "bars.csv"),
                                   metadata_path=str(CORPUS / "metadata.json"),
                                   calendar_path=str(CORPUS / "calendar.json")))
    return legacy_frame(result.snapshot.bars), get_instrument("ES"), result.calendar


@pytest.mark.parametrize("edge,missing", [("first", "2025-06-09"), ("last", "2025-06-20")])
def test_validator_refuses_truncated_built_history(inputs, edge, missing):
    raw, spec, calendar = inputs
    curve = build_continuous_futures(raw, spec, declared_calendar=calendar)
    truncated = curve.iloc[1:] if edge == "first" else curve.iloc[:-1]
    before = truncated.copy(deep=True)
    findings = validate_continuous(truncated, raw, spec, calendar)
    assert {f["session"] for f in findings if f["code"] == "missing_built_session"} == {missing}
    assert any(f["code"] == "missing_built_session" and f["severity"] == "error" for f in findings)
    pd.testing.assert_frame_equal(truncated, before)


def test_single_quote_is_insufficient_even_when_material_matches(inputs):
    raw, spec, calendar = inputs
    # A genuine one-contract, one-session input has no seam or return to validate.
    raw = raw.iloc[[0]].copy()
    curve = build_continuous_futures(raw, spec, declared_calendar=calendar)
    findings = validate_continuous(curve, raw, spec, calendar)
    assert findings == ({"code": "insufficient_continuous_history", "severity": "warning", "session": None},)


def test_oversized_diagnostic_number_is_a_finding(inputs):
    raw, spec, calendar = inputs
    curve = build_continuous_futures(raw, spec, declared_calendar=calendar)
    curve["close_raw"] = curve.close_raw.astype(object)
    curve.at[0, "close_raw"] = 10**400
    findings = validate_continuous(curve, raw, spec, calendar)
    assert any(f["code"] == "nonfinite_or_invalid_numeric" and f["severity"] == "error" for f in findings)
