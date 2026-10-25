"""Exercise three real local captures on a distinct internal network, with no DB/S3."""

import json
import time
from datetime import UTC, date, datetime
from uuid import uuid4

import httpx

from ketrika.alerts.notifier import send_pipeline_failure_email, send_smtp_alert
from ketrika.bulletin.service import send_bulletin_preview_to_mailpit
from ketrika.core.models.db import Alert, Bulletin
from ketrika.core.settings import Settings


def main() -> None:
    with httpx.Client(base_url="http://mailpit:8025", timeout=5, trust_env=False) as client:
        for _ in range(30):
            try:
                response = client.get("/api/v1/messages")
                response.raise_for_status()
                break
            except httpx.HTTPError:
                time.sleep(1)
        else:
            raise RuntimeError("Dedicated capture service unavailable")
        before = response.json()["total"]
        settings = Settings(app_env="test", smtp_host="mailpit", smtp_port=1025)
        alert = Alert(
            alert_id=uuid4(),
            rule_code="SYNTHETIC_AU05",
            title="Local capture test",
            dedupe_key="SYNTHETIC_AU05",
            state="open",
            severity="low",
            evidence={},
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        bulletin = Bulletin(
            bulletin_id=uuid4(), period_start=date(2026, 10, 1), period_end=date(2026, 10, 7)
        )
        results = {
            "alert": send_smtp_alert(alert, settings=settings),
            "incident": send_pipeline_failure_email(
                "SYNTHETIC_AU05", "test-run", "test only", settings=settings
            ),
            "preview": send_bulletin_preview_to_mailpit(bulletin, "<p>Synthetic capture only</p>"),
        }
        assert all(results.values()), results
        after = client.get("/api/v1/messages")
        after.raise_for_status()
        data = after.json()
        assert data["total"] - before == 3
        assert len({message["ID"] for message in data["messages"]}) >= 3
        print(
            json.dumps(
                {
                    "passed": True,
                    "scope": "dedicated internal SMTP capture, synthetic messages",
                    "results": results,
                    "new_captures": 3,
                    "message_ids": [message["ID"] for message in data["messages"][:3]],
                }
            )
        )


if __name__ == "__main__":
    main()
