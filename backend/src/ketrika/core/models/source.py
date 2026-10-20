"""Source specification and registry models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Priority = Literal["P0", "P1", "P2", "P3"]
SourceStatus = Literal["planned", "active", "degraded", "disabled"]
AccessMethod = Literal["api", "file", "html", "browser"]
Cadence = Literal["daily", "weekly", "monthly", "quarterly", "annual", "event", "static"]
Partitioning = Literal["static", "monthly", "daily", "per_document", "annual"]
EntrypointKind = Literal["landing", "api", "file", "rss", "index"]
CrawlPermission = Literal[
    "public_open_data", "robots_tos_compliant", "partner_agreement", "forbidden"
]
PiiClass = Literal["none", "indirect", "direct"]
RedistributionAllowed = Literal["yes", "no", "unknown"]
LegalReviewStatus = Literal["not_required", "pending", "approved", "rejected"]
DataKind = Literal[
    "price",
    "stock",
    "trade",
    "production",
    "weather",
    "weather_forecast",
    "event",
    "cpi",
    "boundary",
    "macro",
]


class SourceEntrypoint(BaseModel):
    """Entrypoint URL and type for a data source."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., description="Target URL")
    kind: EntrypointKind = Field(
        ..., description="Entrypoint nature (landing, api, file, rss, index)"
    )
    verified_at: datetime | str | None = Field(
        default=None, description="ISO timestamp of last verified HTTP 200"
    )
    verified: bool = Field(
        default=False,
        description="Whether this URL has been verified (HTTP 200) with proven provenance",
    )


class SourceDefinition(BaseModel):
    """Comprehensive source definition validating registry/sources.yaml."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(
        ..., pattern=r"^[a-z0-9_]+$", description="Unique lowercase snake_case identifier"
    )
    name: str = Field(..., description="Human-readable canonical name")
    owner: str = Field(..., description="Publishing organization or institution")
    source_family: str | None = Field(
        default=None,
        description="Family grouping of sources to prevent false independent confirmations",
    )
    priority: Priority = Field(default="P1", description="Collection and maintenance priority")
    status: SourceStatus = Field(
        default="planned", description="Current connector operational status"
    )
    access_method: AccessMethod = Field(..., description="Protocol or scraping strategy")
    connector: str = Field(..., description="Import path of connector class or factory")
    cadence: Cadence = Field(
        ..., description="Frequency of source updates (deprecated alias for collection_cadence)"
    )
    collection_cadence: Cadence | None = Field(
        default=None, description="Actual frequency of technical crawler runs"
    )
    observation_cadence: Cadence | None = Field(
        default=None, description="Granularity of observations in the data"
    )
    publication_cadence: Cadence | None = Field(
        default=None, description="Frequency of publisher document releases"
    )
    freshness_sla_days: int = Field(..., ge=1, description="Acceptable staleness threshold in days")
    partitioning: Partitioning = Field(..., description="Storage partitioning scheme")
    entrypoints: list[SourceEntrypoint] = Field(..., min_length=1, description="Entrypoint URLs")
    languages: list[str] = Field(
        default_factory=lambda: ["fr"], description="Source text languages"
    )
    licence: str = Field(default="à vérifier", description="Data license or reuse terms")
    tos_url: str | None = Field(default=None, description="URL of terms of service")
    tos_sha256: str | None = Field(
        default=None, description="SHA256 hash of recorded terms of service"
    )
    tos_checked_at: datetime | str | None = Field(
        default=None, description="Timestamp of terms inspection"
    )
    robots_checked_at: datetime | str | None = Field(
        default=None, description="Timestamp of robots.txt check"
    )
    crawl_permission: CrawlPermission = Field(
        default="public_open_data", description="Legal crawl authorization"
    )
    pii_class: PiiClass = Field(
        default="none", description="PII sensitivity class (direct is prohibited)"
    )
    allowed_fields: list[str] = Field(
        default_factory=lambda: ["*"], description="Whitelisted fields"
    )
    max_rps: float = Field(
        default=0.5, gt=0, le=5.0, description="Rate limit (requests per second)"
    )
    daily_request_budget: int = Field(default=500, gt=0, description="Max daily HTTP requests")
    retention_policy: str = Field(default="indefinite", description="Bronze data retention rule")
    attribution_required: bool = Field(
        default=True, description="Whether legal attribution is mandatory"
    )
    redistribution_allowed: RedistributionAllowed = Field(
        default="unknown", description="Redistribution permissions"
    )
    legal_review_status: LegalReviewStatus = Field(
        default="not_required", description="Legal compliance state"
    )

    @field_validator("redistribution_allowed", mode="before")
    @classmethod
    def _coerce_redistribution_allowed(cls, v: object) -> object:
        if isinstance(v, bool):
            return "yes" if v else "no"
        return v

    data_kinds: list[DataKind] = Field(
        ..., min_length=1, description="Categories of market intelligence data"
    )
    notes: str = Field(default="", description="Operational observations and known caveats")


# Backwards compatibility alias
SourceSpec = SourceDefinition
