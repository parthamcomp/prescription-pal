"""children table + prescriptions.child_id

Revision ID: 0003_children
Revises: 0002_hybrid_search
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_children"
down_revision = "0002_hybrid_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "children",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_children_user_name"),
    )
    op.create_index("ix_children_user_id", "children", ["user_id"])

    # Nullable: existing prescriptions predate this table and start
    # unassigned - there is no reliable way to auto-match them to a child
    # from free-text age/weight alone. ON DELETE SET NULL: removing a child
    # profile should orphan their prescriptions, not delete medical history.
    op.add_column(
        "prescriptions",
        sa.Column(
            "child_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("children.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_prescriptions_child_id", "prescriptions", ["child_id"])


def downgrade() -> None:
    op.drop_index("ix_prescriptions_child_id", table_name="prescriptions")
    op.drop_column("prescriptions", "child_id")
    op.drop_index("ix_children_user_id", table_name="children")
    op.drop_table("children")
