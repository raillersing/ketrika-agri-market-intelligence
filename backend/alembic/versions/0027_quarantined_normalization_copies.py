"""Quarantine same-source normalization copies of excluded parents (ADR158)."""

from alembic import op

revision = "0027_quarantined_normalization_copies"
down_revision = "0026_trade_alias_resolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("price_observation", "stock_observation", "trade_flow"):
        op.execute(f"""
          INSERT INTO obs.quarantine_ledger
            (table_name,observation_id,source_record_id,reason_code,details)
          SELECT 'obs.{table}',n.observation_id,n.source_record_id,
                 'QUARANTINED_NORMALIZATION_PARENT',
                 jsonb_build_object('adr','ADR-158','parent_observation_id',p.observation_id)
          FROM obs.{table} n JOIN obs.{table} p ON p.superseded_by=n.observation_id
          JOIN obs.quarantine_ledger q ON q.table_name='obs.{table}'
            AND q.observation_id=p.observation_id AND q.revoked_at IS NULL
          WHERE n.source_record_id=p.source_record_id AND n.evidence ? 'reconciled_from'
          ON CONFLICT (table_name,observation_id) WHERE revoked_at IS NULL DO NOTHING
        """)
    op.execute("""
      INSERT INTO obs.quarantine_ledger(table_name,observation_id,reason_code,details)
      SELECT 'ml.forecast',f.forecast_id,'POTENTIALLY_CONTAMINATED_TRAINING',
             jsonb_build_object('adr','ADR-158','scope','matching unverified normalization series')
      FROM ml.forecast f JOIN ml.model_run m USING(model_run_id)
      WHERE EXISTS (
        SELECT 1 FROM obs.price_observation p JOIN obs.quarantine_ledger q
          ON q.table_name='obs.price_observation' AND q.observation_id=p.observation_id
          AND q.reason_code='QUARANTINED_NORMALIZATION_PARENT' AND q.revoked_at IS NULL
        WHERE p.product_id=f.product_id
          AND p.location_id IS NOT DISTINCT FROM f.location_id AND p.actor_level=f.actor_level
          AND p.period_start<=m.data_cutoff
          AND (m.params->>'cohort' IS DISTINCT FROM 'pure_observed' OR p.observed_or_imputed='observed')
      ) ON CONFLICT (table_name,observation_id) WHERE revoked_at IS NULL DO NOTHING;
    """)
    dependencies = {
        "price_observation": (
            "market_coverage",
            "market_health",
            "price_changes",
            "price_monthly_best",
            "price_monthly",
            "price_obs_current",
            "forecast_latest",
        ),
        "stock_observation": ("market_health", "stock_latest"),
        "trade_flow": ("trade_monthly", "import_dependency"),
    }
    for table, views in dependencies.items():
        invalidate = "\n".join(
            f"REFRESH MATERIALIZED VIEW gold.{view} WITH NO DATA;" for view in views
        )
        op.execute(f"""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM obs.quarantine_ledger
                         WHERE table_name='obs.{table}' AND revoked_at IS NULL
                           AND reason_code='QUARANTINED_NORMALIZATION_PARENT') THEN
                {invalidate}
              END IF;
            END $$;
        """)


def downgrade() -> None:
    raise RuntimeError("Refusing to republish quarantined normalization copies")
