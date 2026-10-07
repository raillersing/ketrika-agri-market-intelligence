"""Weekly PPN Market Intelligence Bulletin generator module (SPECS §20)."""

from ketrika.bulletin.facts import build_bulletin_facts
from ketrika.bulletin.render import (
    render_html,
    render_pdf,
    save_bulletin_artifacts,
    substitute_facts,
)
from ketrika.bulletin.service import generate_weekly_bulletin
from ketrika.bulletin.writer import generate_bulletin_prose, validate_prose

__all__ = [
    "build_bulletin_facts",
    "generate_bulletin_prose",
    "generate_weekly_bulletin",
    "render_html",
    "render_pdf",
    "save_bulletin_artifacts",
    "substitute_facts",
    "validate_prose",
]
