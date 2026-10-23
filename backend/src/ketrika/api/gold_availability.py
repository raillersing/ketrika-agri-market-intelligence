"""Distinguish an unpublished cache from a published, genuinely empty result."""

from sqlalchemy.orm import Session

from ketrika.api.errors import ProblemDetailException
from ketrika.gold.compatibility import is_gold_view_populated


def require_gold_view(session: Session, view_name: str) -> None:
    """No refresh, source acquisition, database error or fabricated value escapes."""
    if not is_gold_view_populated(session, view_name):
        raise ProblemDetailException(
            status_code=503,
            title="Données non publiées",
            detail="Les indicateurs demandés ne sont pas disponibles. Consultez Sources.",
            extra={"code": "gold_not_published"},
        )
