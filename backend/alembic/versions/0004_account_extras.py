"""users.consent_accepted_at/consent_version + password_changed_at

Revision ID: 0004_account_extras
Revises: 0003_children
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa

revision = "0004_account_extras"
down_revision = "0003_children"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users", sa.Column("consent_version", sa.String(20), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "consent_version")
    op.drop_column("users", "consent_accepted_at")
