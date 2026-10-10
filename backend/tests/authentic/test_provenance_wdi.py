"""Verify authentic archived WDI cells, not a fictitious GDP price/Silver chain."""

import copy
import json
from typing import Any

import pytest

from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.registry import find_repo_root


def test_original_wdi_numeric_cells_and_record_identity() -> None:
    base = find_repo_root() / "backend"
    golden = json.loads(
        (
            base / "tests/golden/authentic/world_bank_wdi/wdi_mdg_gdp_2022_2023.expected.json"
        ).read_text()
    )
    content = (base / golden["metadata"]["document_path"]).read_bytes()
    for index in (0, 1):
        cells = [cell for cell in golden["cells"] if cell["path"][1] == index]
        proof: dict[str, Any] = {
            "version": 1,
            "format": "json",
            "scope_path": [1, index],
            "cells": [
                {
                    "field": f"selected_cell_{position}",
                    "role": "value" if cell["value_type"] == "number" else "identity",
                    "kind": cell["value_type"],
                    "path": cell["path"],
                    "expected": cell["expected"],
                }
                for position, cell in enumerate(cells)
            ],
        }
        assert verify_cells(content, "application/json", proof) == 5
        changed = copy.deepcopy(proof)
        changed["cells"][0]["expected"] = "wrong independent cell"
        with pytest.raises(ProofError):
            verify_cells(content, "application/json", changed)
