"""Persist revocation across API workers without storing access tokens (ADR-123)."""

from alembic import op

revision = "0019_token_revocation"
down_revision = "0018_gold_scope_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE auth.token_revocation (
            token_sha256 VARCHAR(64) PRIMARY KEY CHECK (length(token_sha256) = 64),
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX token_revocation_expiry_idx ON auth.token_revocation (expires_at)")
    op.execute("REVOKE ALL ON auth.token_revocation FROM PUBLIC, copilot_ro, ketrika_app")
    op.execute("GRANT SELECT, INSERT ON auth.token_revocation TO ketrika_app")


def downgrade() -> None:
    raise RuntimeError("Refusing to discard session revocation history")
