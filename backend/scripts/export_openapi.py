"""Export OpenAPI specification to web/src/lib/api/openapi.json (SPECS §19)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from ketrika.api.main import app


def export_openapi() -> Path:
    """Export OpenAPI JSON specification to web directory."""
    # Check if inside docker with KETRIKA_REPO_ROOT or local repo root
    repo_root = Path(os.environ.get("KETRIKA_REPO_ROOT", "."))
    if not (repo_root / "web").exists():
        repo_root = Path(__file__).resolve().parent.parent.parent

    out_file = repo_root / "web" / "src" / "lib" / "api" / "openapi.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    out_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return out_file


if __name__ == "__main__":
    path = export_openapi()
    print(f"Exported OpenAPI specification to {path}")
