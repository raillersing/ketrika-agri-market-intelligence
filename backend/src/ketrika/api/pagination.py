"""Pagination parameters and helpers for Ketrika API (SPECS §19)."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import Query
from pydantic import BaseModel


class PaginationParams:
    """Dependency for limit and offset pagination."""

    def __init__(
        self,
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of items to return (<= 1000)"
        ),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
    ) -> None:
        self.limit = limit
        self.offset = offset


class PaginatedResponse[T](BaseModel):
    """Generic paginated envelope."""

    total: int
    limit: int
    offset: int
    items: Sequence[T]
