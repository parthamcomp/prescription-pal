"""prescriptions.image_keys + processing_jobs.image_keys/saved

Revision ID: 0005_prescription_photos
Revises: 0004_account_extras
Create Date: 2026-08-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_prescription_photos"
down_revision = "0004_account_extras"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prescriptions gain their own list of object-storage keys (in page
    # order) so the original photo(s) can be viewed again after review -
    # previously the uploaded image was only ever reachable via the
    # ProcessingJob that produced it, and nothing linked the two after save.
    op.add_column(
        "prescriptions",
        sa.Column(
            "image_keys", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )

    # processing_jobs.image_key (single string) becomes image_keys (a list),
    # so one job can OCR multiple pages of the same visit into one merged
    # extraction. Backfill existing single-image jobs into a one-element
    # list before dropping the old column.
    op.add_column(
        "processing_jobs",
        sa.Column("image_keys", postgresql.JSONB(), nullable=True),
    )
    op.execute(
        """
        UPDATE processing_jobs
        SET image_keys = CASE
            WHEN image_key IS NOT NULL AND image_key != ''
            THEN jsonb_build_array(image_key)
            ELSE '[]'::jsonb
        END
        """
    )
    op.alter_column(
        "processing_jobs",
        "image_keys",
        nullable=False,
        server_default="[]",
    )
    op.drop_column("processing_jobs", "image_key")

    # Whether this job's extraction was ever turned into a saved
    # Prescription - lets the UI show only genuinely-pending uploads instead
    # of every job that ever ran.
    op.add_column(
        "processing_jobs",
        sa.Column(
            "saved", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("processing_jobs", "saved")

    op.add_column(
        "processing_jobs", sa.Column("image_key", sa.String(500), server_default="")
    )
    op.execute(
        """
        UPDATE processing_jobs
        SET image_key = COALESCE(image_keys->>0, '')
        """
    )
    op.drop_column("processing_jobs", "image_keys")

    op.drop_column("prescriptions", "image_keys")
