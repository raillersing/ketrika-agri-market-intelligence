"""One deliberately corrupted historical value on a separate owned clone.

Never run on the positive reception DB. Docker inspect/volume identities are
required alongside this receipt; both clusters use the guarded Unix-socket DSN.
"""

import hashlib
import json
import os
import runpy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from ketrika.connectors import rtfp_archive
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild_qualification import (
    require_destination,
    require_network_none,
    run_offline_replay,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

assert os.getuid() != 0
network = require_network_none()
engine = create_engine(get_settings().database_url)
original = rtfp_archive.parse_persisted
changed = 0


def false_parser(*args, **kwargs):
    global changed
    parsed = original(*args, **kwargs)
    if not changed and parsed.records:
        records = list(parsed.records)
        first = records[0]
        # Corrupt exactly one old-edition value, subsequently superseded. Gold
        # current rows alone cannot detect this historical content difference.
        wrong = Decimal(first.price_raw) + 1
        records[0] = first.model_copy(update={"price_raw": str(wrong), "price_value": float(wrong)})
        changed += 1
        return parsed.model_copy(update={"records": records})
    return parsed


rtfp_archive.parse_persisted = false_parser
store = runpy.run_path("/workspace/backend/scripts/wb_archive_qualification.py")["store"]()
try:
    with Session(engine) as session:
        require_destination(session)
        result = run_offline_replay(session, store)
        before = result["before"]["tables"]["obs.price_observation"]
        after = result["after"]["tables"]["obs.price_observation"]
        passed = (
            changed == 1
            and before["count"] == after["count"] == 163
            and before["sha256"] != after["sha256"]
            and not result["replay_passed"]
            and not result["diff"]["content_identical"]
            and "obs.price_observation" in result["diff"]["changed_tables"]
            and result["protected_before"] == result["protected_after"]
            and result["bronze_inventory_verified"]
        )
        result.update(
            counterproof_passed=passed,
            deliberately_changed_values=changed,
            uid=os.getuid(),
            network=network,
            human_reviewed=False,
            model_qualified=False,
            finished_at=datetime.now(UTC).isoformat(),
            wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )
        path = Path("/out") / ("false-parser-" + uuid4().hex + ".json")
        with path.open("x") as output:
            json.dump(result, output, indent=2, default=str)
        print(
            json.dumps(
                {
                    "report": str(path),
                    "counterproof_passed": passed,
                    "price_rows_before": before["count"],
                    "price_rows_after": after["count"],
                    "changed_tables": sorted(result["diff"]["changed_tables"]),
                }
            )
        )
        if not passed:
            raise SystemExit(1)
finally:
    rtfp_archive.parse_persisted = original
    engine.dispose()
