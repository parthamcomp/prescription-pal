"""children.sex

Revision ID: 0008_child_sex
Revises: 0007_child_delete_cascades
Create Date: 2026-08-20

Prerequisite for growth percentiles: WHO's LMS reference tables are published
strictly male/female, so the percentile engine needs a child's sex to pick the
right table. Nullable, no CheckConstraint (this codebase has never used one -
enforced as Literal["male","female"] at the Pydantic layer only, matching
existing style). Existing children default to NULL; the growth chart just
prompts to set it before showing percentile curves (graceful degradation, not
a backfill).
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_child_sex"
down_revision = "0007_child_delete_cascades"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("children", sa.Column("sex", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("children", "sex")
