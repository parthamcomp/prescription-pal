"""Tier 4 contract test - the TIER 4 REFERENCE IMPLEMENTATION.

Pattern: generate the schema from the real app instead of hand-writing one
(so it can never itself drift from the actual routes), diff against a
committed snapshot, and fail loudly on any change. A breaking change to a
public contract (renamed field, changed type, removed endpoint) must be a
deliberate, reviewed diff to the snapshot file - never a silent side effect
of an unrelated change.

To intentionally accept a contract change: regenerate the snapshot with
    python -m tests.contract.generate_snapshot
and review the resulting git diff like any other reviewed change.
"""
import json
from pathlib import Path

from deepdiff import DeepDiff

from app.main import app

SNAPSHOT_PATH = Path(__file__).parent / "openapi_snapshot.json"


def test_openapi_schema_matches_committed_snapshot():
    current = app.openapi()

    if not SNAPSHOT_PATH.exists():
        raise AssertionError(
            f"No snapshot at {SNAPSHOT_PATH} - generate one with "
            "`python -m tests.contract.generate_snapshot` and commit it."
        )

    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    diff = DeepDiff(snapshot, current, ignore_order=True)

    assert not diff, (
        "The API's public contract changed. If this is intentional, "
        "regenerate the snapshot with `python -m tests.contract."
        f"generate_snapshot` and commit it. Diff:\n{diff.pretty()}"
    )
