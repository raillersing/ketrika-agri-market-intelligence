"""Connector registry for Ketrika ingestion pipelines (SPECS §9, MVP_EXECUTION_PLAN T2.6)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ketrika.connectors.dummy_csv import DummyCsvConnector

if TYPE_CHECKING:
    from ketrika.connectors.base import Connector

logger = logging.getLogger(__name__)

_CONNECTOR_REGISTRY: dict[str, type[Connector]] = {
    "dummy_csv": DummyCsvConnector,
}


def register_connector(source_id: str, connector_cls: type[Connector]) -> None:
    """Register a connector class for a source_id."""
    _CONNECTOR_REGISTRY[source_id] = connector_cls
    logger.debug("Registered connector %s for source_id %s", connector_cls.__name__, source_id)


def get_connector_class(source_id: str) -> type[Connector] | None:
    """Lookup connector class by source_id.

    Supports exact match as well as dynamic dummy sources (e.g. dummy_<id>).
    """
    if source_id in _CONNECTOR_REGISTRY:
        return _CONNECTOR_REGISTRY[source_id]
    if source_id.startswith("dummy_"):
        return DummyCsvConnector
    return None


def list_registered_connectors() -> dict[str, type[Connector]]:
    """Return a copy of the registered connectors mapping."""
    return dict(_CONNECTOR_REGISTRY)
