"""Add supply arrival and stock targets, measurement mode and market type (ADR-089, SPECS §27, R5.2).

Revision ID: 0016_supply_arrival_and_stock_targets
Revises: 0015_crop_calendar_versioning
"""

from alembic import op

revision: str = "0016_supply_arrival_and_stock_targets"
down_revision: str = "0015_crop_calendar_versioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    -- 1. Add target, measurement_mode, market_type and market_code to obs.stock_observation
    ALTER TABLE obs.stock_observation
        ADD COLUMN IF NOT EXISTS target TEXT NOT NULL DEFAULT 'stock_inventory',
        ADD COLUMN IF NOT EXISTS measurement_mode TEXT NOT NULL DEFAULT 'declared_trader',
        ADD COLUMN IF NOT EXISTS market_type TEXT,
        ADD COLUMN IF NOT EXISTS market_code TEXT;

    -- 2. Add check constraints for valid targets and modes
    ALTER TABLE obs.stock_observation
        ADD CONSTRAINT ck_stock_obs_target
        CHECK (target IN ('stock_inventory', 'inflow_arrival', 'harvest_volume', 'outflow_sales'));

    ALTER TABLE obs.stock_observation
        ADD CONSTRAINT ck_stock_obs_measurement_mode
        CHECK (measurement_mode IN ('measured_scale', 'declared_trader', 'estimated_survey'));

    -- 3. Replace old unique index with target-aware partial unique index
    DROP INDEX IF EXISTS obs.stock_obs_current_uk;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_obs_active
        ON obs.stock_observation (natural_key, target)
        WHERE superseded_by IS NULL;

    -- 4. Search index for market flows and stock inventories
    CREATE INDEX IF NOT EXISTS idx_stock_obs_target_market
        ON obs.stock_observation (product_id, location_id, target, period_start);

    COMMENT ON COLUMN obs.stock_observation.target IS 'stock_inventory | inflow_arrival | harvest_volume | outflow_sales (ADR-088)';
    COMMENT ON COLUMN obs.stock_observation.measurement_mode IS 'measured_scale | declared_trader | estimated_survey (ADR-088)';
    COMMENT ON COLUMN obs.stock_observation.market_type IS 'primary_collection | regional_wholesale | terminal_urban | retail_local';
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS obs.idx_stock_obs_target_market;
    DROP INDEX IF EXISTS obs.uq_stock_obs_active;

    ALTER TABLE obs.stock_observation DROP CONSTRAINT IF EXISTS ck_stock_obs_measurement_mode;
    ALTER TABLE obs.stock_observation DROP CONSTRAINT IF EXISTS ck_stock_obs_target;

    ALTER TABLE obs.stock_observation
        DROP COLUMN IF EXISTS market_code,
        DROP COLUMN IF EXISTS market_type,
        DROP COLUMN IF EXISTS measurement_mode,
        DROP COLUMN IF EXISTS target;

    CREATE UNIQUE INDEX IF NOT EXISTS stock_obs_current_uk
        ON obs.stock_observation (natural_key) WHERE superseded_by IS NULL;
    """)
