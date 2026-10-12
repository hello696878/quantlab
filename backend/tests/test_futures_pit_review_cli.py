"""Real public CLI failures and acceptance from a disposable external cwd."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.futures_pit.adapter import AdapterFailure, AdapterRequest, preview


pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
ROOT = Path(__file__).parents[2]
CORPUS = Path(__file__).parent / "fixtures/futures_pit"
SCRIPT = ROOT / "scripts/validate_futures_point_in_time.py"
SECRET = "SYNTHETIC_SECRET_MARKER"
NAMES = ("bars.csv", "metadata.json", "calendar.json")


@pytest.fixture
def local_inputs(tmp_path):
    sources = tmp_path / "inputs"
    sources.mkdir()
    cwd = tmp_path / "external-cwd"
    cwd.mkdir()
    for name in NAMES:
        (sources / name).write_bytes((CORPUS / name).read_bytes())
    return sources, cwd


def source_state(sources):
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sources.iterdir() if p.is_file()}


def run_cli(local_inputs, args, *, json_output=True):
    sources, cwd = local_inputs
    before = source_state(sources)
    names = sorted(p.name for p in sources.iterdir())
    corpus_before = source_state(CORPUS)
    done = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=cwd,
                          capture_output=True, text=True, check=False, timeout=45)
    assert source_state(sources) == before
    assert sorted(p.name for p in sources.iterdir()) == names
    assert source_state(CORPUS) == corpus_before
    assert list(cwd.iterdir()) == []
    assert "Traceback" not in done.stderr
    return done, json.loads(done.stdout) if json_output else None


def input_args(sources, cutoff="2025-06-21T12:00:00Z"):
    return ["--csv", str(sources / "bars.csv"), "--metadata", str(sources / "metadata.json"),
            "--calendar", str(sources / "calendar.json"), "--as-of", cutoff]


@pytest.mark.parametrize("mode,code,status", [
    ("valid", 0, "pass"), ("demo", 1, "warning"),
    ("no_inputs", 2, "invalid"), ("disabled", 2, "invalid"),
])
def test_public_cli_from_external_cwd(local_inputs, mode, code, status):
    sources, _ = local_inputs
    args = {"valid": input_args(sources), "demo": ["--demo"], "no_inputs": [],
            "disabled": ["--provider", "external", "--csv", "provider://inert"]}[mode]
    done, summary = run_cli(local_inputs, args)
    assert done.returncode == code
    assert summary["status"] == status
    if mode == "valid":
        assert summary["as_of"]["selected"] == 17
    elif mode == "demo":
        assert summary["restatement_demo"] == {"earlier_close": 100, "later_close": 102}
        assert summary["rolls"][0]["effective"] == "2025-06-13"
    elif mode == "disabled":
        assert summary["failure"] == "provider_disabled"


@pytest.mark.parametrize("cutoff", [
    "0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00",
])
def test_cutoff_utc_overflow_is_controlled_invalid(local_inputs, cutoff):
    done, summary = run_cli(local_inputs, input_args(local_inputs[0], cutoff))
    assert done.returncode == 2
    assert summary["status"] == "invalid" and summary["failure"] == "invalid_input"
    assert len(summary["message"]) <= 240


@pytest.mark.parametrize("args", [
    ["--" + SECRET], ["--provider", SECRET], ["--" + SECRET + "x" * 16000],
], ids=["unknown_option", "invalid_choice", "long_unknown_option"])
def test_argument_errors_do_not_echo_values(local_inputs, args):
    done, summary = run_cli(local_inputs, args)
    assert done.returncode == 2 and summary["status"] == "invalid"
    assert "--help" in summary["message"]
    assert len(done.stdout) < 1000 and len(done.stderr) < 200
    assert SECRET not in done.stdout + done.stderr


def test_cli_help_still_exits_successfully(local_inputs):
    done, _ = run_cli(local_inputs, ["--help"], json_output=False)
    assert done.returncode == 0 and done.stderr == ""
    assert "usage:" in done.stdout and "--correction-csv" in done.stdout


def alter_csv(sources, field, value):
    path = sources / "bars.csv"
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
    rows[1][rows[0].index(field)] = value
    output = io.StringIO(newline="")
    csv.writer(output).writerows(rows)
    path.write_text(output.getvalue(), encoding="utf-8", newline="")


@pytest.mark.parametrize("defect", [
    "unknown_root", "malformed_contract", "extra_metadata", "many_extra_fields",
    "invalid_number", "invalid_date", "missing_path",
])
def test_public_failures_are_bounded_without_submitted_values(local_inputs, defect):
    sources, _ = local_inputs
    args = input_args(sources)
    if defect in {"extra_metadata", "many_extra_fields"}:
        path = sources / "metadata.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        count = 1 if defect == "extra_metadata" else 200
        metadata.update({f"private_{i}": SECRET for i in range(count)})
        path.write_text(json.dumps(metadata), encoding="utf-8")
    elif defect == "missing_path":
        args[1] = str(sources / f"{SECRET}.csv")
    else:
        field = {"unknown_root": "root_symbol", "malformed_contract": "contract_symbol",
                 "invalid_number": "open", "invalid_date": "session"}[defect]
        alter_csv(sources, field, SECRET)
    done, summary = run_cli(local_inputs, args)
    assert done.returncode == 2
    assert summary["status"] == "invalid" and summary["failure"] == "invalid_input"
    assert len(summary["message"]) <= 240
    assert len(done.stdout) < 1000
    assert SECRET not in done.stdout + done.stderr
    assert str(sources) not in done.stdout + done.stderr


def test_adapter_also_sanitizes_validation_and_os_errors(local_inputs):
    sources, _ = local_inputs
    path = sources / "metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["private_note"] = SECRET
    path.write_text(json.dumps(metadata), encoding="utf-8")
    request = AdapterRequest(provider="local_file", csv_path=str(sources / "bars.csv"),
                             metadata_path=str(path), calendar_path=str(sources / "calendar.json"))
    before = source_state(sources)
    for current in (request, request.model_copy(update={"csv_path": str(sources / f"{SECRET}.csv")})):
        with pytest.raises(AdapterFailure) as caught:
            preview(current)
        assert caught.value.code == "invalid_input"
        assert len(str(caught.value)) <= 240
        assert SECRET not in str(caught.value) and str(sources) not in str(caught.value)
    assert source_state(sources) == before
