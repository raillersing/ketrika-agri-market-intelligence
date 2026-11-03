"""Keep runtime append-only guards effective against TRUNCATE (ADR155)."""

from alembic import op

revision = "0025_application_no_truncate"
down_revision = "0024_unverified_economic_inputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        REVOKE TRUNCATE ON ALL TABLES IN SCHEMA auth,dq,meta,ml,obs,ops,ref
          FROM ketrika_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA auth,dq,meta,ml,obs,ops,ref
          REVOKE TRUNCATE ON TABLES FROM ketrika_app;
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('auth','dq','meta','ml','obs','ops','ref')
              AND c.relkind IN ('r','p')
              AND has_table_privilege('ketrika_app',c.oid,'TRUNCATE')
          ) OR EXISTS (
            SELECT 1 FROM pg_default_acl d
            LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
            CROSS JOIN LATERAL aclexplode(d.defaclacl) a
            WHERE d.defaclobjtype='r'
              AND (d.defaclnamespace=0 OR n.nspname IN
                   ('auth','dq','meta','ml','obs','ops','ref'))
              AND a.privilege_type='TRUNCATE'
              AND CASE WHEN a.grantee=0 THEN true
                       ELSE pg_has_role('ketrika_app',a.grantee,'USAGE') END
          ) THEN
            RAISE EXCEPTION 'application TRUNCATE requires explicit role review';
          END IF;
        END $$;
    """)


def downgrade() -> None:
    # Reintroducing an append-only bypass is never a safe rollback.
    pass
