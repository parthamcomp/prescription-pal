"""vaccination_doses table

Revision ID: 0010_vaccination_doses
Revises: 0009_measurements
Create Date: 2026-08-20

A dose row's mere existence means "given" - there is no separate confirmed/
pending flag. The Vaccination tab's "typed a date but haven't checked yet"
state lives in frontend component state only, never persisted (see the plan
doc for the reasoning). scheduled_slug references an entry in the bundled
India UIP schedule JSON (backend/app/data/vaccination_schedule_uip.json), not
a DB row, so the schedule can be revised without a migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_vaccination_doses"
down_revision = "0009_measurements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vaccination_doses",
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
        sa.Column("scheduled_slug", sa.String(60), nullable=False),
        sa.Column("date_administered", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("child_id", "scheduled_slug", name="uq_dose_child_slug"),
    )
    op.create_index("ix_vaccination_doses_user_id", "vaccination_doses", ["user_id"])
    op.create_index("ix_vaccination_doses_child_id", "vaccination_doses", ["child_id"])


def downgrade() -> None:
    op.drop_index("ix_vaccination_doses_child_id", table_name="vaccination_doses")
    op.drop_index("ix_vaccination_doses_user_id", table_name="vaccination_doses")
    op.drop_table("vaccination_doses")
