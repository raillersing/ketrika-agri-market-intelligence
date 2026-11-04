"""One source-scoped unambiguous product per trade flow, no publication (ADR157)."""

from pathlib import Path

from alembic import op

revision = "0026_trade_alias_resolution"
down_revision = "0025_application_no_truncate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ DECLARE owner_id oid;
        BEGIN
          SELECT relowner INTO owner_id FROM pg_class
            WHERE oid='gold.trade_monthly'::regclass;
          IF pg_get_userbyid(owner_id) <> current_user OR EXISTS (
            SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a
            WHERE c.oid='gold.trade_monthly'::regclass AND a.grantee <> owner_id
              AND (a.grantee NOT IN (SELECT oid FROM pg_roles
                   WHERE rolname IN ('ketrika_app','copilot_ro'))
                   OR a.privilege_type <> 'SELECT' OR a.is_grantable)
          ) THEN RAISE EXCEPTION 'trade ACL requires explicit role review'; END IF;
        END $$;
    """)
    definition = (
        Path(__file__).resolve().parents[1] / "sql/0026_trade_alias_resolution.sql"
    ).read_text(encoding="utf-8")
    op.execute(definition)
    op.execute("GRANT SELECT ON gold.trade_monthly TO ketrika_app,copilot_ro")


def downgrade() -> None:
    raise RuntimeError("Refusing ambiguous trade aggregation")
