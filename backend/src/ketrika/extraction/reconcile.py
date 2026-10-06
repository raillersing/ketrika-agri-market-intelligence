"""Reconciliation module between deterministic and LLM extractions (SPECS §11.1)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from ketrika.connectors.base import RecordBase
from ketrika.extraction.evidence import verify_evidence


@dataclass
class ReviewProposal:
    """Proposal for ops.review_item when extraction cannot be automatically accepted."""

    kind: str  # extraction_conflict | unverifiable_evidence
    payload: dict[str, Any]
    source_record_id: str | None = None


@dataclass
class ReconciledResult:
    """Outcome of reconciling deterministic and LLM records."""

    accepted_records: list[RecordBase] = field(default_factory=list)
    review_items: list[ReviewProposal] = field(default_factory=list)


def _get_record_numeric_value(rec: RecordBase) -> float | None:
    """Extract primary numeric value for numerical comparison."""
    if hasattr(rec, "price_value") and rec.price_value is not None:
        return float(rec.price_value)
    if hasattr(rec, "price_raw"):
        try:
            clean = str(rec.price_raw).replace(" ", "").replace(",", ".")
            return float(clean)
        except ValueError:
            pass
    if hasattr(rec, "value") and rec.value is not None:
        return float(rec.value)
    return None


def reconcile_records(
    source_id: str,
    deterministic_records: list[RecordBase],
    llm_records: list[RecordBase],
    page_texts: dict[int, str] | None = None,
    source_record_id: str | None = None,
) -> ReconciledResult:
    """Reconcile deterministic and LLM extractions according to SPECS §11.1 table.

    1. deterministic A == llm A: dual_agree (confidence 0.99)
    2. deterministic A, llm absent: deterministic (confidence 0.95)
    3. deterministic absent, llm B with verified evidence: llm_verified (confidence 0.80)
    4. deterministic absent, llm B with unverifiable evidence: review_item(unverifiable_evidence)
    5. deterministic A != llm B: review_item(extraction_conflict)
    """
    page_map = page_texts or {}
    det_map: dict[str, RecordBase] = {
        r.compute_natural_key(source_id): r for r in deterministic_records
    }
    llm_map: dict[str, RecordBase] = {r.compute_natural_key(source_id): r for r in llm_records}

    all_keys = set(det_map.keys()).union(set(llm_map.keys()))

    accepted: list[RecordBase] = []
    reviews: list[ReviewProposal] = []

    for nk in all_keys:
        det_rec = det_map.get(nk)
        llm_rec = llm_map.get(nk)

        # Case 1 & Case 5: Both deterministic and LLM present
        if det_rec is not None and llm_rec is not None:
            val_det = _get_record_numeric_value(det_rec)
            val_llm = _get_record_numeric_value(llm_rec)

            if val_det is not None and val_llm is not None and abs(val_det - val_llm) < 1e-4:
                # Case 1: Exact numerical agreement -> dual_agree, confidence 0.99
                res_rec = copy.deepcopy(det_rec)
                res_rec.extraction_method = "dual_agree"
                res_rec.confidence = 0.99
                accepted.append(res_rec)
            else:
                # Case 5: Disagreement -> review_item(extraction_conflict)
                reviews.append(
                    ReviewProposal(
                        kind="extraction_conflict",
                        source_record_id=source_record_id,
                        payload={
                            "natural_key": nk,
                            "deterministic": det_rec.model_dump(),
                            "llm": llm_rec.model_dump(),
                            "det_value": val_det,
                            "llm_value": val_llm,
                        },
                    )
                )

        # Case 2: Deterministic only -> deterministic, confidence 0.95
        elif det_rec is not None and llm_rec is None:
            res_rec = copy.deepcopy(det_rec)
            res_rec.extraction_method = "deterministic"
            res_rec.confidence = 0.95
            accepted.append(res_rec)

        # Case 3 & Case 4: LLM only
        elif det_rec is None and llm_rec is not None:
            page_num = llm_rec.evidence.get("page", 1) if llm_rec.evidence else 1
            page_txt = page_map.get(page_num, "")
            num_val = _get_record_numeric_value(llm_rec)

            is_verified = verify_evidence(num_val, llm_rec.evidence, page_txt)

            if is_verified:
                # Case 3: LLM verified -> llm_verified, confidence 0.80
                res_rec = copy.deepcopy(llm_rec)
                res_rec.extraction_method = "llm_verified"
                res_rec.confidence = 0.80
                accepted.append(res_rec)
            else:
                # Case 4: LLM unverifiable -> review_item(unverifiable_evidence)
                reviews.append(
                    ReviewProposal(
                        kind="unverifiable_evidence",
                        source_record_id=source_record_id,
                        payload={
                            "natural_key": nk,
                            "llm": llm_rec.model_dump(),
                            "evidence": llm_rec.evidence,
                            "page": page_num,
                        },
                    )
                )

    return ReconciledResult(accepted_records=accepted, review_items=reviews)
