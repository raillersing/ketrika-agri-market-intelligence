"""Weekly PPN Market Intelligence Bulletin generator module (SPECS §20)."""

from ketrika.bulletin.facts import build_bulletin_facts
from ketrika.bulletin.render import (
    render_html,
    render_pdf,
    save_bulletin_artifacts,
    substitute_facts,
)
from ketrika.bulletin.semantic_guard import validate_semantic_consistency
from ketrika.bulletin.service import (
    approve_bulletin,
    generate_weekly_bulletin,
    get_bulletin,
    send_bulletin_preview_to_mailpit,
)
from ketrika.bulletin.writer import generate_bulletin_prose, validate_prose

__all__ = [
    "approve_bulletin",
    "build_bulletin_facts",
    "generate_bulletin_prose",
    "generate_weekly_bulletin",
    "get_bulletin",
    "render_html",
    "render_pdf",
    "save_bulletin_artifacts",
    "send_bulletin_preview_to_mailpit",
    "substitute_facts",
    "validate_prose",
    "validate_semantic_consistency",
]
