from pathlib import Path

import pytest

from app.futures_pit.adapter import AdapterRequest, preview
from app.futures_pit.models import Snapshot
from app.futures_pit.revisions import as_of, compare, envelope_hash, table_hash

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
CORPUS = Path(__file__).parent / "fixtures/futures_pit"


@pytest.fixture
def inputs():
    return tuple(preview(AdapterRequest(provider="local_file", csv_path=str(CORPUS / csv),
                                       metadata_path=str(CORPUS / meta), calendar_path=str(CORPUS / "calendar.json")))
                 for csv, meta in (("bars.csv", "metadata.json"), ("correction.csv", "correction-metadata.json")))


def revised(snapshot, **changes):
    data = snapshot.model_dump(mode="json")
    data["bars"][0].update(changes)
    return Snapshot.model_validate(data)


def close(selection):
    return next(b.close for b in selection.bars if b.contract_symbol == "ESM25" and str(b.session) == "2025-06-12")


def test_revision_statuses_and_preserved_original(inputs):
    old, new = (r.snapshot for r in inputs)
    assert set(f["status"] for f in compare(old, old)) == {"exact_duplicate"}
    assert compare(old, new)[0]["status"] == "explicit_revision"
    assert next(b.close for b in old.bars if str(b.session) == "2025-06-12") == 100
    contradictory = revised(new, revision_id="v1", supersedes=None)
    assert compare(old, contradictory)[0]["status"] == "same_version_contradiction"
    assert compare(old, revised(new, supersedes=None))[0]["status"] == "ambiguous_provenance"
    assert compare(old, revised(new, session="2025-06-11", supersedes=None))[0]["status"] == "new_observation"


@pytest.mark.parametrize("mode", ["declared_source", "local_observed"])
def test_future_revision_cannot_change_earlier_selection(inputs, mode):
    old, correction = (r.snapshot for r in inputs)
    cutoff = "2025-06-18T12:00:00Z"
    prefix = as_of((old,), cutoff, mode)
    extended = as_of((old, correction), cutoff, mode)
    assert prefix.bars == extended.bars
    assert close(extended) == 100
    assert close(as_of((correction, old), "2025-06-21T12:00:00Z", mode)) == 102
    assert as_of((old, old), cutoff, mode).bars == prefix.bars
    assert table_hash(prefix.bars) == table_hash(tuple(reversed(prefix.bars)))
    assert envelope_hash(old, inputs[0].calendar) == envelope_hash(
        Snapshot.model_validate({**old.model_dump(mode="json"), "bars": [b.model_dump(mode="json") for b in reversed(old.bars)]}),
        inputs[0].calendar)


def test_declared_vs_observed_cutoff_no_import_time_substitution(inputs):
    snapshots = tuple(r.snapshot for r in inputs)
    assert close(as_of(snapshots, "2025-06-19T02:30:00Z", "declared_source")) == 102
    assert close(as_of(snapshots, "2025-06-19T02:30:00Z", "local_observed")) == 100
    unknown = revised(inputs[1].snapshot, availability={"price": None, "volume": None,
                                                      "open_interest": None, "local_received_at": None})
    result = as_of((inputs[0].snapshot, unknown), "2026-01-01T00:00:00Z", "local_observed")
    assert close(result) == 100 and result.excluded_unknown == 1
    assert unknown.bars[0].availability.local_received_at is None


@pytest.mark.parametrize("defect", ["same_version", "missing_parent", "two_roots", "tie", "reverse_time", "branch"])
def test_ambiguous_or_contradictory_vintages_refused(inputs, defect):
    old, correction = (r.snapshot for r in inputs)
    if defect == "same_version":
        altered = revised(correction, revision_id="v1", supersedes=None)
    elif defect == "missing_parent":
        altered = revised(correction, supersedes="missing")
    elif defect == "two_roots":
        altered = revised(correction, supersedes=None)
    elif defect in ("tie", "reverse_time"):
        times = next(b.availability.model_dump(mode="json") for b in old.bars if str(b.session) == "2025-06-12")
        if defect == "reverse_time":
            times = {k: "2025-06-11T00:00:00Z" for k in times}
        altered = revised(correction, availability=times)
    else:
        altered = revised(correction, revision_id="v3")
    corpus = (old, altered) if defect != "branch" else (old, correction, altered)
    with pytest.raises(ValueError):
        as_of(corpus, "2025-06-21T12:00:00Z", "declared_source")


def test_selection_refuses_mixed_context_and_bounds(inputs):
    old = inputs[0].snapshot
    changed = Snapshot.model_validate({**old.model_dump(mode="json"), "price_basis": "settlement"})
    with pytest.raises(ValueError, match="mixed"):
        as_of((old, changed), "2025-06-21T12:00:00Z", "declared_source")
    with pytest.raises(ValueError, match="contexts"):
        compare(old, changed)
    for snapshots, mode in (((), "declared_source"), ((old,) * 17, "declared_source"), ((old,), "guess")):
        with pytest.raises(ValueError):
            as_of(snapshots, "2025-06-21T12:00:00Z", mode)


def test_exact_cutoff_is_inclusive_and_record_boundary_conservative(inputs):
    snapshots = tuple(r.snapshot for r in inputs)
    assert close(as_of(snapshots, "2025-06-19T01:59:59Z", "declared_source")) == 100
    assert close(as_of(snapshots, "2025-06-19T02:00:00Z", "declared_source")) == 102
    assert close(as_of(snapshots, "2025-06-19T03:00:00Z", "local_observed")) == 102
