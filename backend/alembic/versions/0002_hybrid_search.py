"""hybrid search: generated tsvector column + GIN index

Revision ID: 0002_hybrid_search
Revises: 0001_init
Create Date: 2026-07-26

"""
from alembic import op

revision = "0002_hybrid_search"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GENERATED ALWAYS ... STORED keeps this column in sync with `document`
    # on every insert/update - the app never writes to it directly.
    op.execute(
        "ALTER TABLE prescriptions "
        "ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(document, ''))) STORED"
    )
    op.execute(
        "CREATE INDEX ix_prescriptions_search_vector "
        "ON prescriptions USING GIN (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_prescriptions_search_vector")
    op.execute("ALTER TABLE prescriptions DROP COLUMN IF EXISTS search_vector")
