"""Exact price grain (ADR-062); no inference or mutation of historical rows."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date

IDENTITY_VERSION = "price_identity_v2"


@dataclass(frozen=True)
class PriceIdentity:
    source_id: str
    product_raw: str
    variety: str | None
    location_raw: str | None
    actor_level: str
    period_start: date
    period_end: date
    value_kind: str
    unit_raw: str
    currency_raw: str
    observed_or_imputed: str

    def __post_init__(self) -> None:
        for name in ("source_id", "product_raw", "unit_raw", "currency_raw"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 4096:
                raise ValueError(f"price_identity_invalid_{name}")
        for name in ("variety", "location_raw"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or len(value) > 4096):
                raise ValueError(f"price_identity_invalid_{name}")
        if self.actor_level not in {
            "retail",
            "wholesale",
            "farmgate",
            "producer",
            "official_ppn",
            "listing",
            "unknown",
        }:
            raise ValueError("price_identity_invalid_actor")
        if self.value_kind not in {"point", "min", "max", "avg"}:
            raise ValueError("price_identity_invalid_statistic")
        if self.observed_or_imputed not in {"observed", "imputed"}:
            raise ValueError("price_identity_invalid_origin")
        if (
            type(self.period_start) is not date
            or type(self.period_end) is not date
            or self.period_end < self.period_start
        ):
            raise ValueError("price_identity_invalid_period")

    @property
    def natural_key(self) -> str:
        frame = [
            IDENTITY_VERSION,
            self.source_id,
            self.product_raw,
            self.variety,
            self.location_raw,
            self.actor_level,
            self.period_start.isoformat(),
            self.period_end.isoformat(),
            self.value_kind,
            self.unit_raw,
            self.currency_raw,
            self.observed_or_imputed,
        ]
        payload = json.dumps(frame, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        return hashlib.sha256(payload).hexdigest()
