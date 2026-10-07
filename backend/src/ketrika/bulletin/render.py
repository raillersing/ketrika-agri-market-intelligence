"""Rendering engine producing substituted Markdown, HTML and WeasyPrint PDF (SPECS §20)."""

from __future__ import annotations

import html
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import jinja2
import weasyprint

from ketrika.core.bronze import get_s3_client
from ketrika.core.logging import get_logger
from ketrika.core.settings import get_settings

logger = get_logger(__name__)

PLACEHOLDER_SUB_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def substitute_facts(
    prose: str,
    facts: dict[str, dict[str, Any]],
    period_start: date,
    period_end: date,
) -> str:
    """Substitute placeholders {{fXXX}} with human-readable display values."""
    mapping: dict[str, str] = {
        "period_start": period_start.strftime("%d/%m/%Y"),
        "period_end": period_end.strftime("%d/%m/%Y"),
    }
    for k, v in facts.items():
        mapping[k] = str(v.get("display", ""))

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return mapping.get(key, match.group(0))

    return PLACEHOLDER_SUB_REGEX.sub(repl, prose)


def markdown_to_html(md_text: str) -> str:
    """Clean, deterministic conversion from Markdown to HTML."""
    lines = md_text.split("\n")
    html_lines: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Close list if not in a list line
        if in_list and not stripped.startswith("- "):
            html_lines.append("</ul>")
            in_list = False

        if not stripped:
            continue

        if stripped.startswith("# "):
            html_lines.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{html.escape(stripped[4:])}</h3>")
        elif stripped == "---":
            html_lines.append("<hr>")
        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item_text = html.escape(stripped[2:])
            # Replace **bold** with <strong>bold</strong>
            item_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", item_text)
            html_lines.append(f"  <li>{item_text}</li>")
        else:
            p_text = html.escape(stripped)
            p_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p_text)
            html_lines.append(f"<p>{p_text}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def render_html(
    markdown_content: str,
    facts: dict[str, dict[str, Any]],
    period_start: date,
    period_end: date,
) -> str:
    """Render full printable HTML bulletin with Jinja2."""
    templates_dir = Path(__file__).resolve().parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=False,
    )
    template = env.get_template("bulletin.html.j2")

    html_body = markdown_to_html(markdown_content)

    rendered = template.render(
        period_start=period_start.strftime("%d/%m/%Y"),
        period_end=period_end.strftime("%d/%m/%Y"),
        html_body=html_body,
        facts=facts,
    )
    return rendered


def render_pdf(html_content: str) -> bytes:
    """Render PDF document using WeasyPrint with A4 print CSS rules."""
    html_obj = weasyprint.HTML(string=html_content)
    pdf_bytes: bytes = html_obj.write_pdf()
    return pdf_bytes


def save_bulletin_artifacts(
    bulletin_id: uuid.UUID,
    html_content: str,
    pdf_bytes: bytes,
) -> tuple[str, str]:
    """Store HTML and PDF artifacts into S3 / MinIO storage."""
    settings = get_settings()
    s3 = get_s3_client()
    bucket = settings.s3_bucket_bronze

    html_key = f"bulletins/{bulletin_id}/bulletin.html"
    pdf_key = f"bulletins/{bulletin_id}/bulletin.pdf"

    s3.put_object(
        Bucket=bucket,
        Key=html_key,
        Body=html_content.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )
    s3.put_object(
        Bucket=bucket,
        Key=pdf_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    logger.info(
        "bulletin_artifacts_saved",
        bulletin_id=str(bulletin_id),
        html_key=html_key,
        pdf_key=pdf_key,
        pdf_size_bytes=len(pdf_bytes),
    )
    return html_key, pdf_key
