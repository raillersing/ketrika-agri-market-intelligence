"""Quarantine generated economic inputs without changing source data (ADR152)."""

from pathlib import Path

from alembic import op

revision = "0024_unverified_economic_inputs"
down_revision = "0023_copilot_gold_only"
branch_labels = None
depends_on = None


QUARANTINE = """
WITH unverified AS (
    SELECT source_record_id FROM meta.source_record
    WHERE (source_id = 'douanes_stats' AND source_url =
        'https://www.douanes.gov.mg/stats/import-parity-benchmarks')
       OR (source_id = 'miasa_odr' AND source_url =
        'http://www.agriculture.gov.mg/odr/caloric-substitution-benchmarks')
), candidates AS (
    SELECT 'meta.source_record'::text AS table_name,
           source_record_id AS observation_id, source_record_id,
           'UNVERIFIED_ECONOMIC_INPUTS'::text AS reason_code
    FROM unverified
    UNION ALL
    SELECT 'obs.price_observation', p.observation_id, p.source_record_id,
           'UNVERIFIED_ECONOMIC_INPUTS'
    FROM obs.price_observation p JOIN unverified u USING (source_record_id)
    UNION ALL
    SELECT 'ml.forecast', f.forecast_id, NULL::uuid,
           'POTENTIALLY_CONTAMINATED_TRAINING'
    FROM ml.forecast f JOIN ml.model_run m USING (model_run_id)
    WHERE m.params->>'cohort' IS DISTINCT FROM 'pure_observed'
      AND EXISTS (
        SELECT 1 FROM obs.price_observation p
        JOIN unverified u USING (source_record_id)
        WHERE p.product_id = f.product_id
          AND p.location_id IS NOT DISTINCT FROM f.location_id
          AND p.actor_level = f.actor_level
          AND p.period_start <= m.data_cutoff
      )
)
INSERT INTO obs.quarantine_ledger
    (table_name, observation_id, source_record_id, reason_code, details)
SELECT table_name, observation_id, source_record_id, reason_code,
       jsonb_build_object('adr','ADR-152','source_urls_verified',false,'action','preserve_and_exclude')
FROM candidates
ON CONFLICT (table_name, observation_id) WHERE revoked_at IS NULL DO NOTHING
"""


ACL_GUARD = """
DO $$
DECLARE owner_id oid;
BEGIN
  SELECT relowner INTO owner_id FROM pg_class
    WHERE oid = 'gold.forecast_latest'::regclass;
  IF pg_get_userbyid(owner_id) <> current_user
     OR NOT has_table_privilege('ketrika_app','gold.forecast_latest','SELECT')
     OR NOT has_table_privilege('copilot_ro','gold.forecast_latest','SELECT')
     OR EXISTS (
    SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) a
    WHERE c.oid = 'gold.forecast_latest'::regclass
      AND a.grantee <> owner_id
      AND (a.grantee NOT IN (SELECT oid FROM pg_roles
           WHERE rolname IN ('ketrika_app','copilot_ro'))
           OR a.privilege_type <> 'SELECT' OR a.is_grantable)
  ) THEN
    RAISE EXCEPTION 'forecast ACL requires explicit role review';
  END IF;
END $$
"""


def upgrade() -> None:
    op.execute(ACL_GUARD)
    op.execute(QUARANTINE)
    definition = (Path(__file__).resolve().parents[1] / "sql/0024_forecast_latest.sql").read_text(
        encoding="utf-8"
    )
    op.execute(definition)
    op.execute("GRANT SELECT ON gold.forecast_latest TO ketrika_app,copilot_ro")
    op.execute(ACL_GUARD)


def downgrade() -> None:
    raise RuntimeError("Refusing to republish unverified economic inputs")
