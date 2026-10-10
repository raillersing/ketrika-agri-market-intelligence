"""Preserve supplied production lexemes without inventing historical values."""

from sqlalchemy import text

from alembic import op

revision = "0004_production_raw"
down_revision = "0003_weather_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE obs.production_observation ADD COLUMN value_raw TEXT")


def downgrade() -> None:
    populated = op.get_bind().scalar(
        text("SELECT EXISTS(SELECT 1 FROM obs.production_observation WHERE value_raw IS NOT NULL)")
    )
    if populated:
        raise RuntimeError("Production raw downgrade refused: it would discard source lexemes")
    op.execute("ALTER TABLE obs.production_observation DROP COLUMN value_raw")
