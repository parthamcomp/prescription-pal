"""prescriptions.child_id ON DELETE CASCADE (was SET NULL)

Revision ID: 0007_child_delete_cascades
Revises: 0006_household_sharing
Create Date: 2026-08-19

Product decision: a child profile now owns their prescription records - the
API requires a child to be selected on every new/edited record (see
PrescriptionCreate), so removing a child should remove their records with
it instead of leaving them permanently unassigned and unreachable through
the "always filter/require a child" UI. Existing rows with a NULL child_id
(created before this policy) are left as-is; nothing here backfills them.
"""
from alembic import op

revision = "0007_child_delete_cascades"
down_revision = "0006_household_sharing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "prescriptions_child_id_fkey", "prescriptions", type_="foreignkey"
    )
    op.create_foreign_key(
        "prescriptions_child_id_fkey",
        "prescriptions",
        "children",
        ["child_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "prescriptions_child_id_fkey", "prescriptions", type_="foreignkey"
    )
    op.create_foreign_key(
        "prescriptions_child_id_fkey",
        "prescriptions",
        "children",
        ["child_id"],
        ["id"],
        ondelete="SET NULL",
    )
