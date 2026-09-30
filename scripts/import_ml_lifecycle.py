"""Preview one local ExperimentStore run; optionally register to an explicit database."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.ml_lifecycle.importer import _safe_path, _signature, local_path, pinned_directory, preview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--destination-db", type=Path)
    parser.add_argument("--dataset-version-id", type=int)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.write and (args.destination_db is None or args.dataset_version_id is None or args.dataset_version_id <= 0):
        parser.error("--write requires --destination-db and a positive --dataset-version-id")
    snapshot = preview(args.source_root, args.run)
    if not args.write:
        print(json.dumps({"mode": "preview", "source_hash": snapshot["source_hash"],
                          "files": snapshot["files"], "unavailable": snapshot["unavailable"]}, indent=2))
        return 0
    from app import db
    from app.ml_lifecycle import service

    # Existing destination/version is required. Preview never imports SQLite code.
    destination = local_path(args.destination_db)
    previous = db._db_path_override
    with pinned_directory(destination.parent):
        before = _safe_path(destination, bounded=False)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(destination, flags), "rb") as handle:
            if _signature(os.fstat(handle.fileno())) != _signature(before):
                raise ValueError("destination changed while opening")
            try:
                db._db_path_override = destination
                db.init_db()
                result = service.register({"name": "Imported " + args.run[:12], "dataset_version_id": args.dataset_version_id,
                                           "dataset_content_hash": snapshot["source_hash"], "snapshot": snapshot})
            finally:
                db._db_path_override = previous
            after = _safe_path(destination, bounded=False)
            if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError("destination changed during registration")
    print(json.dumps({"id": result["id"], "completeness": result["completeness"], "integrity": result["integrity"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print("Import refused: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
