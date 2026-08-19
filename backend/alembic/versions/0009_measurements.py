"""measurements table

Revision ID: 0009_measurements
Revises: 0008_child_sex
Create Date: 2026-08-20

Growth-chart data. Structured (height_cm/weight_kg) rather than reusing
Prescription.child_weight (free text) - percentile computation needs real
numbers, and a record can now come from two sources: OCR-extracted vitals on
a saved prescription (source="ocr") or manual entry on the Percentiles tab
(source="manual"). ON DELETE CASCADE on both user_id and child_id, matching
Prescription's pattern - a measurement has no meaning without the child it
belongs to.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_measurements"
down_revision = "0008_child_sex"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("children.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("measured_on", sa.Date(), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("source", sa.String(10), nullable=False, server_default="manual"),
        sa.Column(
            "image_keys",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_measurements_user_id", "measurements", ["user_id"])
    op.create_index("ix_measurements_child_id", "measurements", ["child_id"])
    op.create_index(
        "ix_measurements_child_measured_on", "measurements", ["child_id", "measured_on"]
    )


def downgrade() -> None:
    op.drop_index("ix_measurements_child_measured_on", table_name="measurements")
    op.drop_index("ix_measurements_child_id", table_name="measurements")
    op.drop_index("ix_measurements_user_id", table_name="measurements")
    op.drop_table("measurements")
