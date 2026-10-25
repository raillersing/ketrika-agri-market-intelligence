"""Notification dispatchers for market intelligence alerts (SMTP Mailpit and Telegram)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ketrika.alerts.transport_policy import permits_local_smtp_capture
from ketrika.core.logging import get_logger
from ketrika.core.models.db import Alert
from ketrika.core.settings import Settings, get_settings

logger = get_logger(__name__)


def format_alert_email_body(alert: Alert) -> tuple[str, str]:
    """Format plaintext and HTML email content for an alert."""
    text_content = f"""[KETRIKA ALERTE MARCHE] - {alert.severity.upper()}

Titre : {alert.title}
Règle : {alert.rule_code}
Clé de déduplication : {alert.dedupe_key}
Statut : {alert.state}
Première détection : {alert.first_seen_at.isoformat()}
Dernière détection : {alert.last_seen_at.isoformat()}

Preuves et métriques :
{alert.evidence}

Consultez le cockpit des alertes : http://localhost:3005/alerts
Ketrika Agri Market Intelligence Madagascar
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px; }}
    .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; max-width: 600px; margin: 0 auto; overflow: hidden; }}
    .header {{ background: #0f172a; color: #ffffff; padding: 16px 24px; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
    .badge-high {{ background: #fee2e2; color: #991b1b; }}
    .badge-medium {{ background: #fef3c7; color: #92400e; }}
    .badge-low {{ background: #e0f2fe; color: #075985; }}
    .body {{ padding: 24px; }}
    .title {{ font-size: 18px; font-weight: 700; margin-bottom: 12px; }}
    .meta {{ font-size: 13px; color: #64748b; margin-bottom: 16px; }}
    .evidence {{ background: #f1f5f9; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 12px; white-space: pre-wrap; }}
    .footer {{ padding: 16px 24px; background: #f8fafc; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2 style="margin: 0; font-size: 16px;">Ketrika Agri Market Intelligence</h2>
    </div>
    <div class="body">
      <span class="badge badge-{alert.severity}">{alert.severity}</span>
      <h3 class="title">{alert.title}</h3>
      <div class="meta">
        <div><strong>Règle :</strong> {alert.rule_code}</div>
        <div><strong>Déduplication :</strong> <code>{alert.dedupe_key}</code></div>
        <div><strong>Dernière détection :</strong> {alert.last_seen_at.strftime("%d/%m/%Y %H:%M UTC")}</div>
      </div>
      <h4>Preuves mécaniques :</h4>
      <div class="evidence">{alert.evidence}</div>
    </div>
    <div class="footer">
      Système autonome de surveillance vivrière PPN Madagascar • <a href="http://localhost:3005/alerts">Accéder au centre d'alertes</a>
    </div>
  </div>
</body>
</html>"""
    return text_content, html_content


def send_smtp_alert(
    alert: Alert,
    recipient: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Send alert email via SMTP (Mailpit in local dev)."""
    cfg = settings or get_settings()
    if not permits_local_smtp_capture(cfg, cfg.smtp_host, cfg.smtp_port):
        logger.info("smtp_capture_refused_h3", alert_id=str(alert.alert_id))
        return False
    dest = recipient or cfg.demo_admin_email

    msg = EmailMessage()
    msg["Subject"] = f"[KETRIKA ALERTE - {alert.severity.upper()}] {alert.title}"
    msg["From"] = cfg.smtp_from
    msg["To"] = dest

    text_body, html_body = format_alert_email_body(alert)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
            server.send_message(msg)
        logger.info(
            "alert_email_sent",
            alert_id=str(alert.alert_id),
            rule=alert.rule_code,
            host=cfg.smtp_host,
            port=cfg.smtp_port,
        )
        return True
    except Exception as exc:
        logger.error(
            "alert_email_failed",
            alert_id=str(alert.alert_id),
            error_class=type(exc).__name__,
        )
        return False


def send_telegram_alert(
    alert: Alert,
    settings: Settings | None = None,
) -> bool:
    """Keep the draft local until an explicit human approval contract exists."""
    logger.info(
        "telegram_send_skipped_h3_gate",
        reason="Human approval is absent; environment flags cannot authorise external delivery",
        alert_id=str(alert.alert_id),
    )
    return False


def dispatch_alert_notifications(
    alert: Alert,
    settings: Settings | None = None,
) -> dict[str, bool]:
    """Dispatch alert to all configured channels (email, telegram)."""
    cfg = settings or get_settings()
    results = {
        "email": send_smtp_alert(alert, settings=cfg),
        "telegram": send_telegram_alert(alert, settings=cfg),
    }
    return results


def send_pipeline_failure_email(
    job_name: str,
    run_id: str,
    error_message: str,
    recipient: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Send pipeline failure notification via SMTP (Mailpit in local dev)."""
    cfg = settings or get_settings()
    if not permits_local_smtp_capture(cfg, cfg.smtp_host, cfg.smtp_port):
        logger.info("smtp_capture_refused_h3", job_name=job_name, run_id=run_id)
        return False
    dest = recipient or cfg.demo_admin_email

    msg = EmailMessage()
    msg["Subject"] = f"[KETRIKA PIPELINE ÉCHEC] {job_name} ({run_id[:8]})"
    msg["From"] = cfg.smtp_from
    msg["To"] = dest

    text_body = f"""[KETRIKA PIPELINE ÉCHEC]
Job / Connecteur : {job_name}
Run ID : {run_id}
Erreur : {error_message}

Consultez Dagster : http://localhost:3010/runs/{run_id}
Consultez le cockpit sources : http://localhost:3005/sources
"""
    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; padding: 20px;">
  <div style="border: 1px solid #e11d48; border-radius: 8px; padding: 20px; max-width: 600px;">
    <h2 style="color: #e11d48; margin-top: 0;">Échec d'exécution du pipeline</h2>
    <p><strong>Job / Connecteur :</strong> {job_name}</p>
    <p><strong>Run ID :</strong> <code>{run_id}</code></p>
    <p><strong>Détail de l'erreur :</strong></p>
    <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto;">{error_message}</pre>
    <p><a href="http://localhost:3010/runs/{run_id}">Voir dans Dagster</a> | <a href="http://localhost:3005/sources">Cockpit Sources</a></p>
  </div>
</body>
</html>"""
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
            server.send_message(msg)
        logger.info(
            "pipeline_failure_email_sent",
            job_name=job_name,
            run_id=run_id,
            host=cfg.smtp_host,
            port=cfg.smtp_port,
        )
        return True
    except Exception as exc:
        logger.error(
            "pipeline_failure_email_failed",
            job_name=job_name,
            run_id=run_id,
            error_class=type(exc).__name__,
        )
        return False
