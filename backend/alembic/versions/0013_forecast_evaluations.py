"""Add forecast evaluation and matured errors tracking table (ADR-079, SPECS §17.4, R3.8).

Revision ID: 0013_forecast_evaluations
Revises: 0012_forecast_metadata_and_abstentions
"""

from alembic import op

revision: str = "0013_forecast_evaluations"
down_revision: str = "0012_forecast_metadata_and_abstentions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS ml.forecast_evaluation (
        evaluation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        forecast_id UUID NOT NULL REFERENCES ml.forecast(forecast_id) ON DELETE CASCADE,
        model_run_id UUID NOT NULL REFERENCES ml.model_run(model_run_id) ON DELETE CASCADE,
        series_key TEXT NOT NULL,
        product_code TEXT NOT NULL,
        location_pcode TEXT,
        actor_level TEXT NOT NULL,
        target_period DATE NOT NULL,
        horizon SMALLINT NOT NULL,
        evaluation_kind TEXT NOT NULL,
        model_name TEXT NOT NULL,
        is_baseline BOOLEAN NOT NULL DEFAULT FALSE,
        predicted_p50 NUMERIC(18, 4),
        predicted_p10 NUMERIC(18, 4),
        predicted_p90 NUMERIC(18, 4),
        actual_price NUMERIC(18, 4),
        actual_observation_id UUID REFERENCES obs.price_observation(observation_id),
        absolute_error NUMERIC(18, 4),
        percentage_error NUMERIC(8, 4),
        is_covered_80 BOOLEAN,
        evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_forecast_eval_matured
    ON ml.forecast_evaluation (series_key, target_period, horizon);

    CREATE INDEX IF NOT EXISTS idx_forecast_eval_kind
    ON ml.forecast_evaluation (evaluation_kind, model_name);

    CREATE INDEX IF NOT EXISTS idx_forecast_eval_product
    ON ml.forecast_evaluation (product_code, location_pcode);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS ml.forecast_evaluation CASCADE;
    """)
