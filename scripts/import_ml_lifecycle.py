"""Preview one local ExperimentStore run; optionally register to an explicit database."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.ml_lifecycle.importer import preview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--destination-db", type=Path)
    parser.add_argument("--dataset-version-id", type=int)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    snapshot = preview(args.source_root, args.run)
    if not args.write:
        print(json.dumps({"mode": "preview", "source_hash": snapshot["source_hash"],
                          "files": snapshot["files"], "unavailable": snapshot["unavailable"]}, indent=2))
        return 0
    if args.destination_db is None or not args.dataset_version_id:
        parser.error("--write requires --destination-db and --dataset-version-id")
    from app import db
    from app.ml_lifecycle import service

    # Existing destination/version is required. Preview never imports SQLite code.
    destination = args.destination_db.absolute()
    if not destination.is_file() or destination.is_symlink():
        parser.error("destination must be an existing local registry database")
    db._db_path_override = str(destination)
    db.init_db()
    result = service.register({"name": "Imported " + args.run[:12], "dataset_version_id": args.dataset_version_id,
                               "dataset_content_hash": snapshot["source_hash"], "snapshot": snapshot})
    print(json.dumps({"id": result["id"], "completeness": result["completeness"], "integrity": result["integrity"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print("Import refused: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
