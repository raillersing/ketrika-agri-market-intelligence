"""Downgrade only the unreviewed global milled-rice/local-rice equivalence."""

from alembic import op

revision = "0028_ambiguous_milled_rice_alias"
down_revision = "0027_quarantined_normalization_copies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ DECLARE changed integer; BEGIN
          UPDATE ref.product_alias a SET confidence=0.8
          FROM ref.product p
          WHERE a.product_id=p.product_id AND p.product_code='RICE_WHITE_LOCAL'
            AND a.alias_norm='rice_milled' AND a.source_id IS NULL
            AND NOT a.human_reviewed AND a.confidence>0.8;
          GET DIAGNOSTICS changed = ROW_COUNT;
          IF changed>0 THEN
            REFRESH MATERIALIZED VIEW gold.trade_monthly WITH NO DATA;
            REFRESH MATERIALIZED VIEW gold.import_dependency WITH NO DATA;
          END IF;
        END $$;
    """)


def downgrade() -> None:
    raise RuntimeError("Refusing to restore an unverified rice-origin equivalence")
