"""Pilot configuration and authenticity guards (SPECS §19, MARKET_INTELLIGENCE_EXECUTION_PLAN R2.4)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.registry import find_repo_root


class PilotProductConfig(BaseModel):
    """Product configuration in the market pilot."""

    product_code: str
    canonical_name_fr: str
    role: str
    category: str
    base_unit: str
    justification: str


class PilotLocationConfig(BaseModel):
    """Geographic zone configuration in the market pilot."""

    pcode: str
    name: str
    admin_level: int
    economic_role: str
    justification: str


class ImpossibleCapability(BaseModel):
    """Explicitly documented impossible capability."""

    capability: str
    status: str = "impossible"
    scope: list[str] = Field(default_factory=list)
    reason: str


class AuthenticityRequirements(BaseModel):
    """Authenticity verification rules for pilot selection."""

    minimum_authentic_sources: int = 1
    allowed_authentic_sources: list[str] = Field(
        default_factory=lambda: ["miasa_odr", "wb_rtfp_mdg", "mincc_ppn", "wfp_hdx_mdg"]
    )
    disallow_synthetic_seed_substitution: bool = True
    blocking_rule: str


class PilotConfig(BaseModel):
    """Complete specification of the market intelligence pilot."""

    pilot_id: str
    version: str
    title: str
    description: str
    products: list[PilotProductConfig]
    locations: list[PilotLocationConfig]
    complementarity_rationale: str
    impossible_capabilities: list[ImpossibleCapability]
    authenticity_requirements: AuthenticityRequirements


class PilotAuthenticityResult(BaseModel):
    """Result of the pilot authentic data verification."""

    is_authentic: bool
    status: str
    authentic_sources_found: list[str]
    authentic_observations_count: int
    synthetic_observations_count: int
    summary_message: str


class PilotNoAuthenticDataError(ValueError):
    """Raised when the pilot has no authentic price data and cannot use synthetic substitutions."""

    def __init__(self, message: str) -> None:
        super().__init__(f"pilot_no_authentic_data: {message}")


def get_default_pilot_config_path() -> Path:
    """Return default path to taxonomy/pilot.yaml."""
    root = find_repo_root()
    return root / "taxonomy" / "pilot.yaml"


def load_pilot_config(config_path: Path | str | None = None) -> PilotConfig:
    """Load and validate the pilot configuration YAML file."""
    path = Path(config_path) if config_path else get_default_pilot_config_path()
    if not path.exists():
        raise FileNotFoundError(f"Pilot configuration file not found at {path}")

    with open(path, encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    if not isinstance(raw_data, dict):
        raise ValueError(f"Invalid YAML structure in {path}")

    return PilotConfig.model_validate(raw_data)


def check_pilot_authenticity(
    session: Session,
    pilot_config: PilotConfig | None = None,
    raise_on_error: bool = False,
) -> PilotAuthenticityResult:
    """Verify that pilot products and locations have authentic price observations.

    Enforces AGENTS.md §4 and R2.4 acceptance criteria:
    - No synthetic seeds or mock data accepted as proof of authentic coverage.
    - At least one authentic qualified source must provide verified observations.
    """
    config = pilot_config or load_pilot_config()
    allowed_sources = set(config.authenticity_requirements.allowed_authentic_sources)
    pilot_products = [p.product_code for p in config.products]
    pilot_locations = [loc.pcode for loc in config.locations]

    # Query observations for pilot products and locations
    query = text(
        """
        SELECT
            sr.source_id,
            po.natural_key,
            count(*)::integer AS count
        FROM obs.price_observation po
        JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
        JOIN ref.product p ON po.product_id = p.product_id
        LEFT JOIN ref.location loc ON po.location_id = loc.location_id
        WHERE p.product_code = ANY(:products)
          AND (loc.pcode = ANY(:pcodes) OR :include_all)
          AND po.superseded_by IS NULL
          AND po.review_status = 'accepted'
        GROUP BY sr.source_id, po.natural_key;
        """
    )

    try:
        rows = session.execute(
            query,
            {
                "products": pilot_products,
                "pcodes": pilot_locations,
                "include_all": False,
            },
        ).fetchall()
    except Exception as exc:
        msg = f"Database query failed while checking pilot authenticity: {exc}"
        if raise_on_error:
            raise PilotNoAuthenticDataError(msg) from exc
        return PilotAuthenticityResult(
            is_authentic=False,
            status="BLOCKED_DATABASE_ERROR",
            authentic_sources_found=[],
            authentic_observations_count=0,
            synthetic_observations_count=0,
            summary_message=msg,
        )

    authentic_count = 0
    synthetic_count = 0
    authentic_sources: set[str] = set()

    for r in rows:
        source_id = str(r[0])
        natural_key = str(r[1])
        cnt = int(r[2])

        is_synthetic = (
            natural_key.startswith("synthetic")
            or natural_key.startswith("test_")
            or source_id not in allowed_sources
        )

        if is_synthetic:
            synthetic_count += cnt
        else:
            authentic_count += cnt
            authentic_sources.add(source_id)

    is_authentic = (
        authentic_count > 0
        and len(authentic_sources) >= config.authenticity_requirements.minimum_authentic_sources
    )

    if not is_authentic:
        status = "BLOCKED_NO_AUTHENTIC_DATA"
        msg = (
            f"Pilot blocked: found {authentic_count} authentic price observations across "
            f"{len(authentic_sources)} sources (required: >0 from {allowed_sources}). "
            f"Found {synthetic_count} synthetic observations (synthetic seeds cannot substitute authentic data)."
        )
        if raise_on_error:
            raise PilotNoAuthenticDataError(msg)
    else:
        status = "QUALIFIED_AUTHENTIC"
        msg = (
            f"Pilot qualified with {authentic_count} authentic observations across "
            f"sources: {sorted(authentic_sources)}."
        )

    return PilotAuthenticityResult(
        is_authentic=is_authentic,
        status=status,
        authentic_sources_found=sorted(authentic_sources),
        authentic_observations_count=authentic_count,
        synthetic_observations_count=synthetic_count,
        summary_message=msg,
    )
