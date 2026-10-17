"""Add crop calendar versioning, seasonal recommendation support and documented market links (ADR-086, SPECS §26, R4.7).

Revision ID: 0015_crop_calendar_versioning
Revises: 0014_geospatial_weather_and_crop_calendar
"""

from alembic import op

revision: str = "0015_crop_calendar_versioning"
down_revision: str = "0014_geospatial_weather_and_crop_calendar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    -- 1. Drop existing static unique constraint
    ALTER TABLE ref.crop_calendar DROP CONSTRAINT IF EXISTS uq_crop_calendar;

    -- 2. Add versioning, typing and market link columns
    ALTER TABLE ref.crop_calendar
        ADD COLUMN IF NOT EXISTS calendar_version TEXT NOT NULL DEFAULT 'v1.0',
        ADD COLUMN IF NOT EXISTS calendar_type TEXT NOT NULL DEFAULT 'traditional_baseline',
        ADD COLUMN IF NOT EXISTS campaign TEXT NOT NULL DEFAULT 'baseline_permanent',
        ADD COLUMN IF NOT EXISTS variety TEXT,
        ADD COLUMN IF NOT EXISTS eligible_for_alerts BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS superseded_by UUID REFERENCES ref.crop_calendar(calendar_id),
        ADD COLUMN IF NOT EXISTS basin_code TEXT,
        ADD COLUMN IF NOT EXISTS market_links JSONB DEFAULT '[]'::jsonb;

    -- 3. Check constraints
    ALTER TABLE ref.crop_calendar
        ADD CONSTRAINT ck_crop_calendar_type
        CHECK (calendar_type IN ('traditional_baseline', 'seasonal_recommendation'));

    -- 4. Partial unique index to guarantee single active entry per cycle
    CREATE UNIQUE INDEX IF NOT EXISTS uq_crop_calendar_active
        ON ref.crop_calendar (product_id, location_id, season_name, crop_regime)
        WHERE is_active = TRUE;

    -- 5. Query index for active cycles by product and location
    CREATE INDEX IF NOT EXISTS idx_crop_calendar_active
        ON ref.crop_calendar (product_id, location_id, is_active);

    COMMENT ON COLUMN ref.crop_calendar.calendar_type IS 'traditional_baseline | seasonal_recommendation';
    COMMENT ON COLUMN ref.crop_calendar.campaign IS 'baseline_permanent | YYYY/YYYY';
    COMMENT ON COLUMN ref.crop_calendar.market_links IS 'Documented trade corridors linking production basin to consumer markets with proof status';
    COMMENT ON COLUMN ref.crop_calendar.eligible_for_alerts IS 'False if unverified or missing source reference';
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS ref.idx_crop_calendar_active;
    DROP INDEX IF EXISTS ref.uq_crop_calendar_active;
    ALTER TABLE ref.crop_calendar DROP CONSTRAINT IF EXISTS ck_crop_calendar_type;

    ALTER TABLE ref.crop_calendar
        DROP COLUMN IF EXISTS market_links,
        DROP COLUMN IF EXISTS basin_code,
        DROP COLUMN IF EXISTS superseded_by,
        DROP COLUMN IF EXISTS is_active,
        DROP COLUMN IF EXISTS eligible_for_alerts,
        DROP COLUMN IF EXISTS variety,
        DROP COLUMN IF EXISTS campaign,
        DROP COLUMN IF EXISTS calendar_type,
        DROP COLUMN IF EXISTS calendar_version;

    ALTER TABLE ref.crop_calendar
        ADD CONSTRAINT uq_crop_calendar UNIQUE (product_id, location_id, season_name, crop_regime);
    """)
