"""Independent read-only audit. No collection, publication, migration or external call."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ketrika.core.settings import get_settings
from ketrika.ml.dataset import build_as_of_dataset


def main() -> None:
    report: dict[str, Any] = {
        "commit": "b7e63ee4738edd02b29771dff46aeb8720d051a3",
        "captured_at": datetime.now(UTC).isoformat(),
        "api": [],
        "sql": {},
    }
    client = httpx.Client(base_url="http://localhost:8000", timeout=25)
    login = client.post(
        "/v1/auth/login", json={"email": "admin@ketrika.local", "password": "change-me"}
    )
    login.raise_for_status()
    token = login.json()["token"]
    client.cookies.clear()
    routes = [
        "/v1/health",
        "/v1/prices",
        "/v1/prices?source=wb_rtfp_mdg&from=2026-01-01&to=2026-10-01",
        "/v1/prices/latest?product=rice_milled&level=1",
        "/v1/prices/latest?product=RICE_WHITE_LOCAL&level=1",
        "/v1/stocks",
        "/v1/trade",
        "/v1/macro",
        "/v1/economic/dashboard",
        "/v1/kpis/market-health",
        "/v1/forecasts",
        "/v1/forecasts/runs",
        "/v1/forecasts/performance",
        "/v1/forecasts/abstentions",
        "/v1/weather/anomalies?from=2026-01-01",
        "/v1/climate/summary",
        "/v1/climate/anomalies?from=2026-01-01",
        "/v1/climate/forecasts",
        "/v1/climate/calendars",
        "/v1/climate/events",
        "/v1/climate/facultative-status",
        "/v1/supply/peak-forecast",
        "/v1/supply/peak-forecast?crop=UNKNOWN&zone_code=UNKNOWN&campaign=bad",
        "/v1/supply/sufficiency",
        "/v1/supply/scenarios/templates",
        "/v1/alerts",
        "/v1/bulletins",
        "/v1/sources",
        "/v1/sources/collection-options",
        "/v1/admin/review",
    ]
    # Collections GETs reconcile interrupted runs, so deliberately do not request them.
    for path in routes:
        for authenticated in (False, True):
            try:
                response = client.get(
                    path,
                    headers={"Authorization": "Bearer " + token} if authenticated else {},
                    cookies={},
                )
                try:
                    body = response.json()
                except ValueError:
                    body = response.text[:200]
                # No user identifiers, cookies or tokens are retained.
                report["api"].append(
                    {
                        "path": path,
                        "authenticated": authenticated,
                        "status": response.status_code,
                        "length": len(body) if isinstance(body, list) else None,
                        "sample": body[:2] if isinstance(body, list) else body,
                    }
                )
            except httpx.HTTPError as error:
                report["api"].append(
                    {"path": path, "authenticated": authenticated, "error": type(error).__name__}
                )
    engine = create_engine(get_settings().database_url)
    queries = {
        "price_by_source_kind": "SELECT sr.source_id,p.observed_or_imputed,count(*) AS total,count(*) FILTER(WHERE p.superseded_by IS NULL) AS current,count(*) FILTER(WHERE p.superseded_by=p.observation_id) AS self_linked,min(p.period_start) AS earliest,max(p.period_start) AS latest FROM obs.price_observation p JOIN meta.source_record sr USING(source_record_id) GROUP BY 1,2 ORDER BY 1,2",
        "gold_state": "SELECT matviewname,ispopulated FROM pg_matviews WHERE schemaname='gold' ORDER BY 1",
        "stock_columns": "SELECT column_name FROM information_schema.columns WHERE table_schema='obs' AND table_name='stock_observation' ORDER BY ordinal_position",
        "price_columns": "SELECT column_name FROM information_schema.columns WHERE table_schema='obs' AND table_name='price_observation' ORDER BY ordinal_position",
        "record_columns": "SELECT column_name FROM information_schema.columns WHERE table_schema='meta' AND table_name='source_record' ORDER BY ordinal_position",
        "source_status": "SELECT source_id,status FROM meta.source WHERE source_id NOT LIKE 'test_%' AND source_id NOT LIKE 'dummy_%' AND source_id NOT LIKE 'fixture_%' ORDER BY 1",
        "current_price_duplicates": "SELECT natural_key,count(*) FROM obs.price_observation WHERE superseded_by IS NULL GROUP BY 1 HAVING count(*)>1",
        "table_inventory": "SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema IN ('obs','ml','ops','meta') AND table_type='BASE TABLE' ORDER BY 1,2",
        "ref_aliases": "SELECT origin,count(*) FROM ref.location_alias GROUP BY 1",
    }
    for name, sql in queries.items():
        try:
            with engine.connect() as connection, connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                report["sql"][name] = [
                    dict(row) for row in connection.execute(text(sql)).mappings()
                ]
        except Exception as error:
            report["sql"][name] = {
                "error": type(error).__name__,
                "detail": str(error).split("[SQL:")[0][:300],
            }
    for schema, table in [
        ("obs", "stock_observation"),
        ("obs", "trade_flow"),
        ("obs", "weather_observation"),
        ("obs", "macro_observation"),
        ("obs", "weather_forecast"),
        ("obs", "event"),
        ("ml", "forecast"),
        ("ml", "model_run"),
        ("ml", "forecast_evaluation"),
        ("ops", "alert"),
        ("ops", "bulletin"),
    ]:
        try:
            with engine.connect() as connection, connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                report["sql"][schema + "." + table] = connection.scalar(
                    text(f"SELECT count(*) FROM {schema}.{table}")
                )
        except Exception as error:
            report["sql"][schema + "." + table] = {"error": type(error).__name__}
    # Exercise the actual dataset SQL path rather than the raw_records unit-test path.
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            with Session(bind=connection) as session:
                dataset = build_as_of_dataset(datetime.now(UTC), session=session)
                report["as_of_dataset"] = {"count": dataset.observations_count}
    except Exception as error:
        report["as_of_dataset"] = {
            "error": type(error).__name__,
            "detail": str(error).split("[SQL:")[0][:500],
        }
    client.close()
    engine.dispose()
    Path(sys.argv[1]).write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False))
    print(
        json.dumps(
            {
                "api_probes": len(report["api"]),
                "sql_checks": len(report["sql"]),
                "as_of_dataset": report.get("as_of_dataset"),
            }
        )
    )


if __name__ == "__main__":
    main()
