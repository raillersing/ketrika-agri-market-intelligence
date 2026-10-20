"""Synthetic test-only stock context, never an extension of the production DTO."""

from uuid import UUID

from ketrika.connectors.records import StockRecord


class SyntheticStockRecord(StockRecord):
    """Keep scenario prices explicit instead of silently ignored Pydantic extras."""

    source_id: str
    natural_key: str
    currency_raw: str
    price_raw: str | None
    price_mga: float | None
    source_record_id: UUID
