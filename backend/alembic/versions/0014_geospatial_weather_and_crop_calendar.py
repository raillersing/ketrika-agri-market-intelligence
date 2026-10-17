"""Add geospatial weather forecast and crop calendar tables and extend weather observation (ADR-080, SPECS §26, R4.1).

Revision ID: 0014_geospatial_weather_and_crop_calendar
Revises: 0013_forecast_evaluations
"""

from alembic import op

revision: str = "0014_geospatial_weather_and_crop_calendar"
down_revision: str = "0013_forecast_evaluations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend obs.weather_observation
    op.execute("""
    ALTER TABLE obs.weather_observation
        ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'final',
        ADD COLUMN IF NOT EXISTS spatial_resolution TEXT,
        ADD COLUMN IF NOT EXISTS coverage_ratio NUMERIC(5, 4),
        ADD COLUMN IF NOT EXISTS raster_source_record_id UUID REFERENCES meta.source_record(source_record_id);

    COMMENT ON COLUMN obs.weather_observation.stage IS 'preliminary | final (double-version provider handling)';
    COMMENT ON COLUMN obs.weather_observation.spatial_resolution IS 'Native resolution of source raster/model e.g. 0.05_deg';
    COMMENT ON COLUMN obs.weather_observation.coverage_ratio IS 'Spatial coverage ratio over polygon 0.0 to 1.0';
    COMMENT ON COLUMN obs.weather_observation.raster_source_record_id IS 'Link to Bronze raster object if derived';
    """)

    # 2. Create obs.weather_forecast
    op.execute("""
    CREATE TABLE IF NOT EXISTS obs.weather_forecast (
        forecast_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source_record_id UUID NOT NULL REFERENCES meta.source_record(source_record_id),
        location_id UUID NOT NULL REFERENCES ref.location(location_id),
        issued_at TIMESTAMPTZ NOT NULL,
        valid_from TIMESTAMPTZ NOT NULL,
        valid_to TIMESTAMPTZ NOT NULL,
        horizon_hours INTEGER NOT NULL,
        variable TEXT NOT NULL,
        model_name TEXT NOT NULL,
        predicted_value NUMERIC(10, 3),
        predicted_p10 NUMERIC(10, 3),
        predicted_p90 NUMERIC(10, 3),
        method TEXT NOT NULL,
        spatial_resolution TEXT,
        unit TEXT NOT NULL,
        ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        evidence JSONB,
        raw_payload JSONB,
        superseded_by UUID REFERENCES obs.weather_forecast(forecast_id) DEFERRABLE INITIALLY DEFERRED
    );

    CREATE INDEX IF NOT EXISTS idx_weather_forecast_lookup
    ON obs.weather_forecast (location_id, issued_at, valid_from, variable);

    CREATE INDEX IF NOT EXISTS idx_weather_forecast_timeline
    ON obs.weather_forecast (variable, valid_from, valid_to);
    """)

    # 3. Create ref.crop_calendar
    op.execute("""
    CREATE TABLE IF NOT EXISTS ref.crop_calendar (
        calendar_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        product_id UUID NOT NULL REFERENCES ref.product(product_id),
        location_id UUID NOT NULL REFERENCES ref.location(location_id),
        season_name TEXT NOT NULL,
        crop_regime TEXT NOT NULL,
        planting_start_month SMALLINT NOT NULL,
        planting_end_month SMALLINT NOT NULL,
        growing_start_month SMALLINT NOT NULL,
        growing_end_month SMALLINT NOT NULL,
        harvest_start_month SMALLINT NOT NULL,
        harvest_end_month SMALLINT NOT NULL,
        peak_harvest_month SMALLINT,
        water_sensitivity_profile JSONB,
        source_reference TEXT NOT NULL,
        verified BOOLEAN NOT NULL DEFAULT TRUE,
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_crop_calendar UNIQUE (product_id, location_id, season_name, crop_regime)
    );

    CREATE INDEX IF NOT EXISTS idx_crop_calendar_lookup
    ON ref.crop_calendar (product_id, location_id, season_name);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS ref.crop_calendar CASCADE;
    DROP TABLE IF EXISTS obs.weather_forecast CASCADE;

    ALTER TABLE obs.weather_observation
        DROP COLUMN IF EXISTS raster_source_record_id,
        DROP COLUMN IF EXISTS coverage_ratio,
        DROP COLUMN IF EXISTS spatial_resolution,
        DROP COLUMN IF EXISTS stage;
    """)
