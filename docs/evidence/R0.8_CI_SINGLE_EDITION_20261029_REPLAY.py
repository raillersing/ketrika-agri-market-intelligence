"""ADR145: replay existing authentic bytes, one edition, no gate/model claim."""

import hashlib
import json
import os
import runpy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.core.models.db import SourceRecord
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification_reports import source_fingerprint
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild_qualification import (
    require_destination,
    require_network_none,
    run_offline_replay,
    versioned_recompute_receipt,
)

started = datetime.now(UTC).isoformat()
assert os.getuid() != 0
fingerprint = source_fingerprint(Path("/workspace"))
assert fingerprint == "b928b1f4c2dd80b307bd608b89cbe233b9e48a84f89f02b49b4ee286a46ecc0b"
require_network_none()
engine = create_engine(get_settings().database_url)
store = runpy.run_path("/workspace/backend/scripts/price_preview.py")["store"]()
with Session(engine) as session:
    require_destination(session)
    assert sorted(session.scalars(select(SourceRecord.source_id))) == ["wb_rtfp_mdg"] * 2
    init_gold_views(session)
    refresh_gold_views(session, reader=BronzeProofReader(store))
    session.commit()
    result = run_offline_replay(session, store)
    result["versioned_recompute"] = versioned_recompute_receipt(session)
    assert result["versioned_recompute"]["min_points_required"] == 36
    result.update(
        source_commit="6dad3cd99055bde9018e4af408231a56c3cbc51c",
        source_fingerprint=fingerprint,
        started_at=started,
        finished_at=datetime.now(UTC).isoformat(),
        dataset="authentic published WB historical sample; one edition, partial",
        available_editions=1,
        genuine_revisions_qualified=False,
        complete_r08_qualified=False,
        r09_qualified=False,
        model_qualified=False,
        human_reviewed=False,
        source_freshness_qualified=False,
        wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    assert source_fingerprint(Path("/workspace")) == fingerprint
    output = Path("/out") / ("single-edition-replay-" + uuid4().hex + ".json")
    with output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
    print(
        json.dumps(
            {
                "report": str(output),
                "replay_passed": result["replay_passed"],
                "stats": result["replay_stats"],
                "changed_tables": result["diff"]["changed_tables"],
                "versioned_recompute": result["versioned_recompute"],
                "complete_r08_qualified": False,
            }
        )
    )
    if not result["replay_passed"]:
        raise SystemExit(1)
engine.dispose()
