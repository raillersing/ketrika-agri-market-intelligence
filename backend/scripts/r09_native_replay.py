"""Produce fresh native WB replay evidence in dedicated offline containers only."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.connectors import rtfp_archive
from ketrika.core.external_corpus import _readonly, inspect_packet
from ketrika.core.external_replay import PRICE, PRODUCER
from ketrika.core.qualification_reports import source_fingerprint
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild_qualification import (
    require_destination,
    require_network_none,
    run_offline_replay,
    versioned_recompute_receipt,
)
from wb_archive_qualification import COPY, PACKET, store

ROOT = Path("/workspace")
OUT = Path("/out")


def binding() -> dict[str, Any]:
    commit = os.environ["KETRIKA_SOURCE_COMMIT"]
    image = os.environ["KETRIKA_PROOF_BACKEND_IMAGE_ID"]
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None or re.fullmatch(
        r"sha256:[0-9a-f]{64}", image
    ) is None:
        raise ValueError("r09_producer_binding_invalid")
    fingerprint = source_fingerprint(ROOT)
    if fingerprint != os.environ["KETRIKA_SOURCE_FINGERPRINT"]:
        raise ValueError("r09_source_changed")
    packet = inspect_packet(ROOT, PACKET.parent, PACKET)
    return {
        "commit": commit,
        "source_fingerprint": fingerprint,
        "packet_sha256": packet["packet_sha256"],
        "producer_environment": {"producer": PRODUCER, "backend_image_id": image},
    }


def run(role: str) -> None:
    if os.getuid() != 1000:
        raise ValueError("r09_nonroot_worker_required")
    require_network_none()
    for path in (ROOT, COPY, PACKET):
        _readonly(path)
    target = OUT / (role + ".json")
    if target.exists():
        raise ValueError("r09_refuse_receipt_overwrite")
    before_binding = binding()
    original = rtfp_archive.parse_persisted
    changed = 0

    def false_parser(*args: Any, **kwargs: Any) -> Any:
        nonlocal changed
        parsed = original(*args, **kwargs)
        if not changed and parsed.records:
            records = list(parsed.records)
            first = records[0]
            wrong = Decimal(first.price_raw) + 1
            records[0] = first.model_copy(
                update={"price_raw": str(wrong), "price_value": float(wrong)}
            )
            changed += 1
            return parsed.model_copy(update={"records": records})
        return parsed

    engine = create_engine(get_settings().database_url)
    try:
        if role == "negative":
            rtfp_archive.parse_persisted = false_parser
        with Session(engine) as session:
            require_destination(session)
            result = run_offline_replay(session, store())
            if role == "positive":
                if result["replay_passed"] is True:
                    result["versioned_recompute"] = versioned_recompute_receipt(session)
            else:
                result["deliberately_changed_values"] = changed
                result["counterproof_passed"] = (
                    changed == 1
                    and result["replay_passed"] is False
                    and set(result["diff"]["changed_tables"]) == {PRICE}
                    and result["before"]["tables"][PRICE]["count"]
                    == result["after"]["tables"][PRICE]["count"] == 163
                    and result["protected_before"] == result["protected_after"]
                    and result["bronze_inventory_verified"] is True
                )
        if binding() != before_binding:
            raise ValueError("r09_producer_input_changed")
        result.update(
            **before_binding,
            role=role,
            uid=os.getuid(),
            captured_at=datetime.now(UTC).isoformat(),
            human_reviewed=False,
            model_qualified=False,
        )
        with target.open("x", encoding="utf-8") as output:
            json.dump(result, output, separators=(",", ":"), default=str)
        passed = result.get(
            "counterproof_passed" if role == "negative" else "replay_passed"
        ) is True
        print(json.dumps({"role": role, "passed": passed, "receipt": str(target)}))
        if not passed:
            raise SystemExit(1)
    finally:
        rtfp_archive.parse_persisted = original
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("positive", "negative"))
    run(parser.parse_args().role)
