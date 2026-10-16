"""Isolated historical price preview. Never the production API or a Gold gate."""

import argparse
import hashlib
import html
import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from alembic import command
from ketrika.connectors.base import RawArtifact
from ketrika.connectors.batch_ledger import persist_bronze_batch
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.rtfp_json import PARSER_VERSION, parse_persisted
from ketrika.connectors.stages import BronzeBatch
from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import IngestionRun, PriceObservation, Source, SourceRecord
from ketrika.core.provenance_audit import audit_observation_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.rebuild_bronze import LocalBronzeClient
from ketrika.core.settings import get_settings
from ketrika.normalize.loader import seed_locations, seed_products, seed_units
from ketrika.normalize.price_loader import load_normalized_price
from ketrika.pipelines.rebuild_qualification import require_destination, require_network_none

SOURCE = "wb_rtfp_mdg"
EXPECTED = {
    "study.json": "4a9e254e14c65ca5d3c85d69362f94ca4ccaf46b8e68cfbf88f300df6c122860",
    "sample.json": "bc4a01e5f443898a916678c84213ab29f30534b642f8da3b7ea6ca509c566c15",
}


def store() -> BronzeStore:
    inventory = json.loads(Path("/copy/inventory.json").read_text())
    return BronzeStore(
        bucket_name="price-preview-copy",
        client=LocalBronzeClient(Path("/copy"), "price-preview-copy", inventory["objects"]),
    )


def prepare(session: Session) -> None:
    require_network_none()
    require_destination(session)
    if (
        session.scalar(text("SELECT to_regclass('meta.source_record')")) is not None
        or Path("/copy/inventory.json").exists()
    ):
        raise ValueError("preview_already_initialized_no_overwrite")
    session.rollback()
    config = Config("/workspace/backend/alembic.ini")
    config.set_main_option("script_location", "/workspace/backend/alembic")
    command.upgrade(config, "head")
    seed_units(session, seed_products(session))
    seed_locations(session)
    session.add(
        Source(
            source_id=SOURCE,
            status="active",
            spec={
                "name": "World Bank historical price preview",
                "scope": "partial historical data, not market qualification",
            },
        )
    )
    session.flush()
    run_id = uuid4()
    session.add(
        IngestionRun(
            run_id=run_id, source_id=SOURCE, status="running", started_at=datetime.now(UTC)
        )
    )
    session.flush()
    receipts = json.loads(Path("/packet/acquisition.json").read_text())["receipts"]
    artifacts, objects = [], {}
    for filename, digest in EXPECTED.items():
        receipt = next(item for item in receipts if item["filename"] == filename)
        content = (Path("/packet") / filename).read_bytes()
        if (
            hashlib.sha256(content).hexdigest() != digest
            or receipt["sha256"] != digest
            or receipt["http_status"] != 200
        ):
            raise ValueError("preview_packet_not_expected")
        if not receipt["source_url"].startswith("https://microdata.worldbank.org/"):
            raise ValueError("preview_source_not_official")
        key = f"{SOURCE}/2026/10/{digest}.json"
        with (Path("/copy") / (digest + ".blob")).open("xb") as output:
            output.write(content)
        objects[key] = {"sha256": digest, "size_bytes": len(content)}
        identifier = uuid4()
        session.add(
            SourceRecord(
                source_record_id=identifier,
                source_id=SOURCE,
                source_url=receipt["source_url"],
                retrieved_via="direct",
                object_key=key,
                content_sha256=digest,
                mime_type="application/json",
                http_status=200,
                fetched_at=datetime.fromisoformat(receipt["fetched_at"].replace("Z", "+00:00")),
                parser_version=PARSER_VERSION,
                extraction_status="parsed",
            )
        )
        artifacts.append(
            RawArtifact(
                str(identifier), key, digest, "application/json", receipt["source_url"], True
            )
        )
    session.flush()
    persist_bronze_batch(session, BronzeBatch(SOURCE, run_id, PARSER_VERSION, tuple(artifacts)))
    with Path("/copy/inventory.json").open("x") as output:
        json.dump({"objects": objects}, output)
    reader = BronzeProofReader(store())
    inserted = 0
    for artifact in artifacts:
        for record in parse_persisted(session, artifact, reader).records:
            if not isinstance(record, PriceRecord):
                raise ValueError("preview_price_record_required")
            result = load_normalized_price(session, record, SOURCE, UUID(artifact.source_record_id))
            inserted += result.action == "inserted"
    session.flush()
    audit = audit_observation_provenance(session, reader)
    if not audit.report.passed or inserted != 15:
        raise ValueError("preview_provenance_or_count_invalid")
    session.commit()


def read_prices(session: Session) -> list[dict]:
    session.execute(text("SET TRANSACTION READ ONLY"))
    rows = session.execute(
        select(PriceObservation, SourceRecord)
        .join(SourceRecord, PriceObservation.source_record_id == SourceRecord.source_record_id)
        .where(PriceObservation.superseded_by.is_(None), SourceRecord.source_id == SOURCE)
        .order_by(PriceObservation.period_start)
        .limit(1000)
    ).all()
    return [
        {
            "product": row.product_raw,
            "market": row.location_raw,
            "period": row.period_start.isoformat(),
            "price_raw": row.price_raw,
            "currency": row.currency_raw,
            "unit": row.unit_raw,
            "kind": row.observed_or_imputed,
            "actor": row.actor_level,
            "review": row.review_status,
            "source_record_id": str(reference.source_record_id),
            "source_url": reference.source_url,
            "sha256": reference.content_sha256,
            "context_source_record_id": (row.evidence or {})["provenance"][
                "context_source_record_id"
            ],
        }
        for row, reference in rows
    ]


def render(prices: list[dict]) -> str:
    columns = ("period", "product", "market", "price_raw", "currency", "unit", "kind", "review")
    rows = "".join(
        "<tr>"
        + "".join("<td>" + html.escape(str(item[key])) + "</td>" for key in columns)
        + "</tr>"
        for item in prices
    )
    return (
        '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Ketrika — aperçu prix</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 16px;background:#f5f7fa;color:#172434}table{border-collapse:collapse;background:white;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}.scroll{overflow:auto}a{color:#1455b5}</style><h1>Ketrika · prix historiques</h1><p>Aperçu minimal partiel · Banque mondiale · Madagascar</p><p><strong>Estimations imputées, pas des relevés observés ni des prix actuels.</strong> Acteur inconnu ; pending = normalisation à revoir. Non validé pour une décision actuelle.</p><p>Valeurs brutes conservées ; provenance primaire et contexte vérifiés. <a href="/api/prices">Consulter les données et la provenance JSON</a></p><div class="scroll"><table><tr>'
        + "".join("<th>" + key + "</th>" for key in columns)
        + "</tr>"
        + rows
        + "</table></div></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "report", "serve"))
    action = parser.parse_args().action
    engine = create_engine(get_settings().database_url)
    if action == "prepare":
        with Session(engine) as session:
            prepare(session)
    elif action == "report":
        with Session(engine) as session:
            require_destination(session)
            session.rollback()
            print(
                json.dumps({"scope": "partial historical preview", "prices": read_prices(session)})
            )
    else:

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path not in ("/", "/api/prices"):
                    self.send_error(404)
                    return
                with Session(engine) as session:
                    require_destination(session)
                    session.rollback()
                    prices = read_prices(session)
                data = (
                    json.dumps({"scope": "partial historical preview", "prices": prices})
                    if self.path == "/api/prices"
                    else render(prices)
                )
                body = data.encode()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
                    if self.path == "/api/prices"
                    else "text/html; charset=utf-8",
                )
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
    engine.dispose()


if __name__ == "__main__":
    main()
