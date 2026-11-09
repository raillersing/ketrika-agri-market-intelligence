"""Universal bounded acquisition adapters framework (IA-DATA-03, SPECS §9, §12).

Provides:
- Bounded pagination (offset/limit, page_number, cursor, next_url) with loop detection
- Controlled streaming with hard byte limits and on-the-fly SHA-256 computation
- Resumable checkpoints with conditional headers (ETag, Last-Modified)
- Secret-safe diagnostic logging and SSRF boundary validation
"""

from __future__ import annotations

from ketrika.connectors.adapters.checkpoint import (
    CheckpointStore,
    CollectionCheckpoint,
)
from ketrika.connectors.adapters.pagination import (
    BoundedPaginator,
    PageResult,
    PaginationConfig,
    PaginationStrategy,
)
from ketrika.connectors.adapters.streaming import (
    ControlledStreamReader,
    StreamConfig,
    StreamResult,
)

__all__ = [
    "BoundedPaginator",
    "CheckpointStore",
    "CollectionCheckpoint",
    "ControlledStreamReader",
    "PageResult",
    "PaginationConfig",
    "PaginationStrategy",
    "StreamConfig",
    "StreamResult",
]
