"""initial schema: users, prescriptions (pgvector), processing_jobs

Revision ID: 0001_init
Revises:
Create Date: 2026-07-23

"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "prescriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("doctor_name", sa.String(200), server_default=""),
        sa.Column("date_of_visit", sa.Date(), nullable=True),
        sa.Column("complaint", sa.Text(), server_default=""),
        sa.Column("diagnosis", sa.Text(), server_default=""),
        sa.Column("medications", postgresql.JSONB(), server_default="[]"),
        sa.Column("child_age", sa.String(50), server_default=""),
        sa.Column("child_weight", sa.String(50), server_default=""),
        sa.Column("additional_notes", sa.Text(), server_default=""),
        sa.Column("source_text", sa.Text(), server_default=""),
        sa.Column("document", sa.Text(), server_default=""),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_prescriptions_user_id", "prescriptions", ["user_id"])
    op.execute(
        "CREATE INDEX ix_prescriptions_embedding ON prescriptions "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="queued"),
        sa.Column("image_key", sa.String(500), server_default=""),
        sa.Column("raw_text", sa.Text(), server_default=""),
        sa.Column("extracted", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_processing_jobs_user_id", "processing_jobs", ["user_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_index("ix_prescriptions_embedding", table_name="prescriptions")
    op.drop_table("prescriptions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
