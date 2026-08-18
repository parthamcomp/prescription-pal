"""Regenerate the OpenAPI contract snapshot after a deliberate API change.

Usage (from backend/): python -m tests.contract.generate_snapshot
"""
import json
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    path = Path(__file__).parent / "openapi_snapshot.json"
    path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True))
    print(f"Wrote {path}")
