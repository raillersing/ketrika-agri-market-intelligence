"""CSV export response generator for Ketrika API (SPECS §19)."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi.responses import Response


def export_csv_response(
    data: list[dict[str, Any]],
    filename: str = "export.csv",
) -> Response:
    """Generate CSV response from list of flat dictionaries."""
    if not data:
        return Response(
            content="",
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    fieldnames = list(data[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for row in data:
        # Convert any list/dict fields to string if present
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                clean_row[k] = str(v)
            else:
                clean_row[k] = v
        writer.writerow(clean_row)

    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
