"""Remove the historical copilot grant outside Gold (ADR-146).

Revision ID: 0023_copilot_gold_only
Revises: 0022_supersession_cycle_guard
"""

from alembic import op

revision = "0023_copilot_gold_only"
down_revision = "0022_supersession_cycle_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("REVOKE SELECT ON obs.quarantine_ledger FROM copilot_ro")
    op.execute("""
        DO $$
        BEGIN
            IF has_table_privilege('copilot_ro', 'obs.quarantine_ledger', 'SELECT') THEN
                RAISE EXCEPTION 'Copilot SELECT outside Gold persists through inherited privileges; explicit role review required';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Never restore a permission forbidden by the existing Gold-only contract.
    pass
