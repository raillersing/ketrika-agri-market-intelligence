"""Replay the isolated preview clone, never the serving database (ADR-068/071).

Caller mounts a readonly copy and an independently restored PostgreSQL socket.
Retains a complete machine report, without claiming full R0.8 qualification.
"""

import json
import runpy
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.core.models.db import SourceRecord
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild_qualification import (
    require_destination,
    require_network_none,
    run_offline_replay,
)


def main() -> None:
    require_network_none()
    engine = create_engine(get_settings().database_url)
    store = runpy.run_path("/workspace/backend/scripts/price_preview.py")["store"]()
    with Session(engine) as session:
        require_destination(session)
        sources = list(session.scalars(select(SourceRecord.source_id)))
        if sources != ["wb_rtfp_mdg", "wb_rtfp_mdg"]:
            raise ValueError("preview_clone_source_inventory_invalid")
        init_gold_views(session)
        refresh_gold_views(session, reader=BronzeProofReader(store))
        session.commit()
        result = run_offline_replay(session, store)
        result["dataset"] = "authentic WB historical sample, partial"
        report = Path("/out") / f"replay-{uuid4().hex}.json"
        with report.open("x") as output:
            json.dump(result, output, sort_keys=True, indent=2)
        print(
            json.dumps(
                {
                    "replay_passed": result["replay_passed"],
                    "report": str(report),
                    "stats": result["replay_stats"],
                    "changed_tables": result["diff"]["changed_tables"],
                    "scope": result["scope"],
                }
            )
        )
        if not result["replay_passed"]:
            raise SystemExit(1)
    engine.dispose()


if __name__ == "__main__":
    main()
