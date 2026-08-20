"""prescriptions.child_height + measurements.source_prescription_id

Revision ID: 0011_prescription_child_height
Revises: 0010_vaccination_doses
Create Date: 2026-08-20

Product decision: growth data is no longer entered through a separate
"optional growth data" panel during upload/edit - child_height joins the
existing child_weight as a normal free-text prescription field, and both
feed the Percentiles chart automatically (in addition to the existing
manual +Add measurement path). source_prescription_id links a
prescription-derived measurement back to the record that produced it, so
re-saving that record updates (rather than duplicates) its measurement,
and clearing the height/weight text deletes it - see
routers/prescriptions.py::_sync_growth_measurement.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_prescription_child_height"
down_revision = "0010_vaccination_doses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prescriptions",
        sa.Column("child_height", sa.String(50), nullable=False, server_default=""),
    )
    op.add_column(
        "measurements",
        sa.Column(
            "source_prescription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_measurements_source_prescription_id",
        "measurements",
        ["source_prescription_id"],
    )
    op.alter_column(
        "measurements", "source", type_=sa.String(15), existing_type=sa.String(10)
    )


def downgrade() -> None:
    op.alter_column(
        "measurements", "source", type_=sa.String(10), existing_type=sa.String(15)
    )
    op.drop_index("ix_measurements_source_prescription_id", table_name="measurements")
    op.drop_column("measurements", "source_prescription_id")
    op.drop_column("prescriptions", "child_height")
