"""account_links + account_invites (shared family account access)

Revision ID: 0006_household_sharing
Revises: 0005_prescription_photos
Create Date: 2026-08-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_household_sharing"
down_revision = "0005_prescription_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per member granting them full access to owner_user_id's data.
    # member_user_id is unique - a user can be a member of at most one
    # shared account at a time (no nested/multi-household sharing).
    op.create_table(
        "account_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_account_links_owner_user_id", "account_links", ["owner_user_id"])

    op.create_table(
        "account_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_account_invites_token", "account_invites", ["token"], unique=True
    )
    op.create_index(
        "ix_account_invites_owner_user_id", "account_invites", ["owner_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_account_invites_owner_user_id", table_name="account_invites")
    op.drop_index("ix_account_invites_token", table_name="account_invites")
    op.drop_table("account_invites")

    op.drop_index("ix_account_links_owner_user_id", table_name="account_links")
    op.drop_table("account_links")
