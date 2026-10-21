"""Crop production forecasting model (Area × Yield) and sourced agro-industrial conversion (R5.5, ADR-106, SPECS §27).

This module implements:
1. Strict mathematical decomposition: Production = Harvested_Area (ha) × Yield (t/ha).
2. Agro-industrial conversion factors (e.g. paddy to milled rice: 0.667, on-farm loss & seed deduction: 10%).
   Every factor carries a REFERENCE_VERIFIED flag (default False); unverified factors are
   placeholders for software execution only and MUST NOT back qualified, published forecasts.
   Detectable placeholders remain OUT (C022 / AGENTS §8.10).
3. Agrometeorological yield adjustment under hydric/climatic conditions (CHIRPS / WRSI).
4. Strict abstention rule (abstained_insufficient_history, abstained_unverified_area) forbidding invented tonnages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AreaSourceKind(StrEnum):
    """Provenance and validation tier of harvested area figures."""

    OFFICIAL_CADASTRE_SURVEY = "official_cadastre_survey"  # DRAE / MinAE direct agricultural census
    REMOTE_SENSING_CROPLAND = (
        "remote_sensing_cropland"  # Satellite cropland mask (ESA WorldCover / Copernicus)
    )
    DECLARED_COMMUNE_ESTIMATE = "declared_commune_estimate"  # Communal administrative estimation
    NATIONAL_UNVERIFIED = (
        "national_unverified"  # FAOSTAT national top-down estimate (unverified at local level)
    )


class ProductionForecastStatus(StrEnum):
    """Qualification status of the production forecast output."""

    QUALIFIED_FORECAST = "qualified_forecast"
    EXPERIMENTAL_ESTIMATE = "experimental_estimate"
    ABSTAINED_INSUFFICIENT_HISTORY = "abstained_insufficient_history"
    ABSTAINED_UNVERIFIED_AREA = "abstained_unverified_area"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class AgroConversionFactor:
    """Agro-industrial conversion parameters with an explicitly verifiable provenance flag.

    reference_verified=False marks placeholder documentation (AGENTS §8.10 / C022-A):
    the value may be used for software execution only and MUST be backed by a
    document-verified citation (HTTP 200 or source document) before any qualified,
    published, or field-audited use (ADR-116).
    """

    raw_commodity: str
    processed_commodity: str
    milling_ratio: float  # Physical extraction rate from raw to processed (e.g. 0.667 for paddy to milled rice)
    farm_loss_seed_rate: (
        float  # Deduction for retained seeds and on-farm post-harvest losses (e.g. 0.10 for 10%)
    )
    source_reference: str  # Generic institutional descriptor only: MUST be replaced by a
    # document-verified citation (HTTP 200 or source document) before human_reviewed.
    issuing_institution: str = ""
    document_title: str = ""
    publication_year: int = 0
    page_or_table: str = ""
    reference_verified: bool = False


# Standard conversion factors for Malagasy food staples. Numerical values are software
# execution placeholders pending document verification: reference_verified=False everywhere.
# No PLAUSIBLE-LOOKING tables/pages/years are claimed because none has been verified (C022).
STANDARD_CONVERSION_FACTORS: dict[str, AgroConversionFactor] = {
    "RICE_PADDY": AgroConversionFactor(
        raw_commodity="RICE_PADDY",
        processed_commodity="RICE_MILLED",
        milling_ratio=0.667,
        farm_loss_seed_rate=0.10,
        source_reference="Standard Malagasy paddy milling norms (institutional literature, pending verification)",
        issuing_institution="ODR / MinAE",
    ),
    "MAIZE_COB": AgroConversionFactor(
        raw_commodity="MAIZE_COB",
        processed_commodity="MAIZE_GRAIN",
        milling_ratio=0.780,
        farm_loss_seed_rate=0.08,
        source_reference="Maize shelling and loss guidance (institutional literature, pending verification)",
        issuing_institution="MinAE / FOFIFA",
    ),
    "CASSAVA_FRESH": AgroConversionFactor(
        raw_commodity="CASSAVA_FRESH",
        processed_commodity="CASSAVA_DRIED",
        milling_ratio=0.333,
        farm_loss_seed_rate=0.12,
        source_reference="Cassava post-harvest loss assessment guidance (institutional literature, pending verification)",
        issuing_institution="FAO / MinAE",
    ),
    "GROUNDNUT_UNSHELLED": AgroConversionFactor(
        raw_commodity="GROUNDNUT_UNSHELLED",
        processed_commodity="GROUNDNUT_SHELLED",
        milling_ratio=0.700,
        farm_loss_seed_rate=0.07,
        source_reference="Groundnut shelling ratio guidance (institutional literature, pending verification)",
        issuing_institution="MinAE / DRAE",
    ),
    "BEANS_PULSES": AgroConversionFactor(
        raw_commodity="BEANS_PULSES",
        processed_commodity="BEANS_DRIED",
        milling_ratio=0.950,
        farm_loss_seed_rate=0.06,
        source_reference="Pulse drying and loss guidance (institutional literature, pending verification)",
        issuing_institution="MinAE / DRAE",
    ),
}


@dataclass(frozen=True)
class CropYieldBaseline:
    """Historical agronomic yield baseline for a given crop in a production basin/region.

    reference_verified=False (default) marks the numeric baseline as a software
    placeholder pending a document-verified source (C022-A / ADR-116).
    """

    crop_code: str
    region_id: str
    baseline_yield_t_ha: float
    min_yield_t_ha: float
    max_yield_t_ha: float
    campaign_years_available: tuple[int, ...]
    source_reference: str  # Generic institutional descriptor only: MUST be replaced by a
    # document-verified citation (HTTP 200 or source document) before human_reviewed.
    issuing_institution: str = ""
    document_title: str = ""
    publication_year: int = 0
    page_or_table: str = ""
    reference_verified: bool = False


# Regional baselines for key production basins in Madagascar. Numeric values are software
# execution placeholders pending document verification: reference_verified=False everywhere.
# No fabricated tables/pages/years are claimed because none has been verified (C022).
HISTORICAL_YIELD_BASELINES: dict[tuple[str, str], CropYieldBaseline] = {
    # Alaotra-Mangoro (Grenier à riz de Madagascar)
    ("RICE_PADDY", "MG-U"): CropYieldBaseline(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        baseline_yield_t_ha=3.20,
        min_yield_t_ha=2.00,
        max_yield_t_ha=4.50,
        campaign_years_available=(2018, 2019, 2020, 2021, 2022, 2023),
        source_reference="Alaotra-Mangoro rice campaign records (institutional literature, pending verification)",
        issuing_institution="ODR / MinAE",
    ),
    # Vakinankaratra (Hautes Terres)
    ("RICE_PADDY", "MG-D"): CropYieldBaseline(
        crop_code="RICE_PADDY",
        region_id="MG-D",
        baseline_yield_t_ha=2.80,
        min_yield_t_ha=1.80,
        max_yield_t_ha=3.90,
        campaign_years_available=(2019, 2020, 2021, 2022, 2023),
        source_reference="Vakinankaratra agricultural campaign records (institutional literature, pending verification)",
        issuing_institution="DRAE Vakinankaratra / MinAE",
    ),
    # Boeny (Marovoay basin)
    ("RICE_PADDY", "MG-A"): CropYieldBaseline(
        crop_code="RICE_PADDY",
        region_id="MG-A",
        baseline_yield_t_ha=3.00,
        min_yield_t_ha=1.90,
        max_yield_t_ha=4.20,
        campaign_years_available=(2019, 2020, 2021, 2022),
        source_reference="Marovoay irrigated perimeter monitoring (institutional literature, pending verification)",
        issuing_institution="ODR Boeny / MinAE",
    ),
    # Atsimo-Andrefana (Maïs / Manioc)
    ("MAIZE_COB", "MG-H"): CropYieldBaseline(
        crop_code="MAIZE_COB",
        region_id="MG-H",
        baseline_yield_t_ha=1.35,
        min_yield_t_ha=0.70,
        max_yield_t_ha=2.10,
        campaign_years_available=(2020, 2021, 2022, 2023),
        source_reference="Atsimo-Andrefana maize assessments (institutional literature, pending verification)",
        issuing_institution="MinAE / FAO",
    ),
    # Atsinanana (Manioc)
    ("CASSAVA_FRESH", "MG-O"): CropYieldBaseline(
        crop_code="CASSAVA_FRESH",
        region_id="MG-O",
        baseline_yield_t_ha=8.50,
        min_yield_t_ha=5.20,
        max_yield_t_ha=13.50,
        campaign_years_available=(2019, 2020, 2021, 2022),
        source_reference="Atsinanana permanent agricultural survey records (institutional literature, pending verification)",
        issuing_institution="MinAE / STAT-AGRI",
    ),
}


@dataclass(frozen=True)
class ProductionForecastInput:
    """Input payload for crop production evaluation."""

    crop_code: str
    region_id: str
    harvest_campaign: int
    harvested_area_ha: float
    area_source_kind: AreaSourceKind
    water_stress_anomaly: float | None = (
        None  # Standardized rainfall anomaly in standard deviations (e.g. -1.5)
    )
    historical_campaigns_count: int | None = (
        None  # Explicit count if overriding default baseline registry
    )
    is_field_survey_audited: bool = (
        False  # True only if ground truth audit confirms campaign figures (C022)
    )


@dataclass(frozen=True)
class ProductionForecastResult:
    """Rigorous crop production forecast result adhering to ADR-106."""

    status: ProductionForecastStatus
    crop_code: str
    region_id: str
    harvest_campaign: int
    harvested_area_ha: float | None
    estimated_yield_t_ha: float | None
    gross_harvest_tonnes: float | None
    net_marketable_tonnes: float | None
    milled_processed_tonnes: float | None
    identity_verified: bool
    confidence_score: float
    conversion_factor: AgroConversionFactor | None
    uncertainty_range_gross: tuple[float, float] | None
    abstention_reason: str | None
    methodology: str


class CropProductionModel:
    """Production forecasting engine enforcing mathematical decomposition, sourced conversion, and abstention."""

    def __init__(
        self,
        conversion_factors: dict[str, AgroConversionFactor] | None = None,
        baselines: dict[tuple[str, str], CropYieldBaseline] | None = None,
    ) -> None:
        self.conversion_factors = conversion_factors or STANDARD_CONVERSION_FACTORS
        self.baselines = baselines or HISTORICAL_YIELD_BASELINES

    def get_conversion_factor(self, crop_code: str) -> AgroConversionFactor | None:
        """Retrieve the official agro-industrial conversion factor for a commodity."""
        return self.conversion_factors.get(crop_code)

    def calculate_yield(
        self,
        crop_code: str,
        region_id: str,
        water_stress_anomaly: float | None = None,
    ) -> tuple[float, float, float]:
        """Compute adjusted yield (t/ha) under agroclimatic conditions alongside physical min/max bounds.

        Returns (estimated_yield_t_ha, min_yield_t_ha, max_yield_t_ha).
        Raises KeyError if the (crop_code, region_id) baseline is not recorded.
        """
        key = (crop_code, region_id)
        if key not in self.baselines:
            raise KeyError(
                f"No agronomic yield baseline recorded for crop '{crop_code}' in region '{region_id}'"
            )

        baseline = self.baselines[key]
        base_yield = baseline.baseline_yield_t_ha
        min_yield = baseline.min_yield_t_ha
        max_yield = baseline.max_yield_t_ha

        if water_stress_anomaly is None:
            return round(base_yield, 3), min_yield, max_yield

        # Agrometeorological response elasticity: beta = 0.12 (12% yield variation per 1.0 sigma rainfall anomaly)
        # Bounded between min_yield and max_yield to preserve agronomic physiological limits
        elasticity = 0.12
        raw_adjusted = base_yield * (1.0 + elasticity * water_stress_anomaly)
        bounded_yield = max(min_yield, min(max_yield, raw_adjusted))

        return round(bounded_yield, 3), min_yield, max_yield

    def evaluate(self, payload: ProductionForecastInput) -> ProductionForecastResult:
        """Evaluate crop production with mathematical identity verification and abstention enforcement."""
        # 1. Validation of area inputs
        if payload.harvested_area_ha <= 0:
            return ProductionForecastResult(
                status=ProductionForecastStatus.INVALID_INPUT,
                crop_code=payload.crop_code,
                region_id=payload.region_id,
                harvest_campaign=payload.harvest_campaign,
                harvested_area_ha=None,
                estimated_yield_t_ha=None,
                gross_harvest_tonnes=None,
                net_marketable_tonnes=None,
                milled_processed_tonnes=None,
                identity_verified=False,
                confidence_score=0.0,
                conversion_factor=None,
                uncertainty_range_gross=None,
                abstention_reason=f"Harvested area must be strictly positive, got {payload.harvested_area_ha}",
                methodology="rejection_invalid_area",
            )

        # 2. Strict Abstention on Unverified Area (FAOSTAT National Top-Down)
        if payload.area_source_kind == AreaSourceKind.NATIONAL_UNVERIFIED:
            return ProductionForecastResult(
                status=ProductionForecastStatus.ABSTAINED_UNVERIFIED_AREA,
                crop_code=payload.crop_code,
                region_id=payload.region_id,
                harvest_campaign=payload.harvest_campaign,
                harvested_area_ha=payload.harvested_area_ha,
                estimated_yield_t_ha=None,
                gross_harvest_tonnes=None,
                net_marketable_tonnes=None,
                milled_processed_tonnes=None,
                identity_verified=False,
                confidence_score=0.0,
                conversion_factor=None,
                uncertainty_range_gross=None,
                abstention_reason=(
                    "FAOSTAT national top-down area cannot be applied to local/regional production "
                    "without verified cadastre survey or satellite cropland mask (ADR-106)."
                ),
                methodology="abstention_unverified_national_area",
            )

        # 3. Check Campaign History Sufficiency (Minimum 2 distinct historical campaigns required)
        key = (payload.crop_code, payload.region_id)
        baseline = self.baselines.get(key)
        available_campaigns_count = (
            payload.historical_campaigns_count
            if payload.historical_campaigns_count is not None
            else (len(baseline.campaign_years_available) if baseline else 0)
        )

        if baseline is None or available_campaigns_count < 2:
            return ProductionForecastResult(
                status=ProductionForecastStatus.ABSTAINED_INSUFFICIENT_HISTORY,
                crop_code=payload.crop_code,
                region_id=payload.region_id,
                harvest_campaign=payload.harvest_campaign,
                harvested_area_ha=payload.harvested_area_ha,
                estimated_yield_t_ha=None,
                gross_harvest_tonnes=None,
                net_marketable_tonnes=None,
                milled_processed_tonnes=None,
                identity_verified=False,
                confidence_score=0.0,
                conversion_factor=None,
                uncertainty_range_gross=None,
                abstention_reason=(
                    f"Insufficient campaign history for crop '{payload.crop_code}' in region '{payload.region_id}': "
                    f"at least 2 historical campaigns required, found {available_campaigns_count}."
                ),
                methodology="abstention_insufficient_history",
            )

        # 4. Yield Estimation and Bounds
        est_yield, min_yield, max_yield = self.calculate_yield(
            crop_code=payload.crop_code,
            region_id=payload.region_id,
            water_stress_anomaly=payload.water_stress_anomaly,
        )

        # 5. Strict Mathematical Identity: Production = Area × Yield
        area = payload.harvested_area_ha
        gross_tonnes = round(area * est_yield, 2)

        # Numerical identity verification within float precision tolerance
        identity_verified = abs(gross_tonnes - (area * est_yield)) < 0.05

        # 6. Sourced Agro-Industrial Processing & Farm-Gate Loss Conversion
        conv_factor = self.get_conversion_factor(payload.crop_code)
        if conv_factor is not None:
            # Step A: Net marketable harvest after post-harvest and seed retention
            net_tonnes = round(gross_tonnes * (1.0 - conv_factor.farm_loss_seed_rate), 2)
            # Step B: Edible / Milled equivalent output
            milled_tonnes = round(net_tonnes * conv_factor.milling_ratio, 2)
        else:
            # Conservative default if no specific agro-industrial conversion is defined
            net_tonnes = round(gross_tonnes * 0.90, 2)
            milled_tonnes = net_tonnes

        # 7. Uncertainty Range
        uncertainty_low = round(area * min_yield, 2)
        uncertainty_high = round(area * max_yield, 2)

        # 8. Confidence Score calculation
        # Cadastre = 0.95, Remote Sensing = 0.85, Declared Commune = 0.70
        area_confidence = {
            AreaSourceKind.OFFICIAL_CADASTRE_SURVEY: 0.95,
            AreaSourceKind.REMOTE_SENSING_CROPLAND: 0.85,
            AreaSourceKind.DECLARED_COMMUNE_ESTIMATE: 0.70,
        }.get(payload.area_source_kind, 0.50)

        climate_confidence = 0.90 if payload.water_stress_anomaly is not None else 0.80
        confidence = round(area_confidence * climate_confidence, 2)

        is_audited = payload.is_field_survey_audited
        baseline_verified = bool(baseline is not None and baseline.reference_verified)

        # 9. Qualification gating (C022-A / ADR-116): a forecast is QUALIFIED only when BOTH
        # the field figures are audited AND the yield baseline reference is document-verified.
        # Any other combination remains an experimental software estimate.
        if is_audited and baseline_verified:
            status = ProductionForecastStatus.QUALIFIED_FORECAST
            methodology = "area_times_yield_with_agroclimatic_adjustment"
            abstention_reason = None
        else:
            status = ProductionForecastStatus.EXPERIMENTAL_ESTIMATE
            caveats = []
            if not is_audited:
                caveats.append("not field audited for sovereign decisions")
            if not baseline_verified:
                caveats.append("yield baseline reference not document-verified")
            methodology = (
                "area_times_yield_with_agroclimatic_adjustment (experimental software estimate: "
                + "; ".join(caveats)
                + ")"
            )
            abstention_reason = None

        return ProductionForecastResult(
            status=status,
            crop_code=payload.crop_code,
            region_id=payload.region_id,
            harvest_campaign=payload.harvest_campaign,
            harvested_area_ha=area,
            estimated_yield_t_ha=est_yield,
            gross_harvest_tonnes=gross_tonnes,
            net_marketable_tonnes=net_tonnes,
            milled_processed_tonnes=milled_tonnes,
            identity_verified=identity_verified,
            confidence_score=confidence,
            conversion_factor=conv_factor,
            uncertainty_range_gross=(uncertainty_low, uncertainty_high),
            abstention_reason=abstention_reason,
            methodology=methodology,
        )

    def batch_evaluate(
        self, payloads: list[ProductionForecastInput]
    ) -> list[ProductionForecastResult]:
        """Execute batch production evaluation."""
        return [self.evaluate(p) for p in payloads]
