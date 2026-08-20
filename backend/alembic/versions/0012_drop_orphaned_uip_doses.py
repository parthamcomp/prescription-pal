"""Delete vaccination_doses rows orphaned by the UIP -> IAP schedule switch

Revision ID: 0012_drop_orphaned_uip_doses
Revises: 0011_prescription_child_height
Create Date: 2026-08-21

The vaccination schedule was switched from India's UIP schedule to the
IAP-ACVIP 2023 timetable (see vaccination_schedule_iap.json) - a different
set of milestones/doses with different scheduled_slug values (e.g. UIP's
"opv-1"/"penta-1"/"je-1" have no equivalent slug in the IAP schedule). Any
dose a user had already checked off under the old schedule is now an
orphan: the row still exists, but VaccineRow only ever renders a slug the
*current* schedule defines, so it's invisible on the Vaccination tab and
would silently keep counting toward nothing. This is a one-time data
cleanup, not a schema change: deletes every vaccination_doses row whose
scheduled_slug isn't one of the 44 slugs the IAP schedule actually defines
as of this migration.

The valid-slug list is hardcoded rather than read from the live JSON on
purpose - if the schedule is revised again later (a slug renamed or
dropped), this migration must keep deleting against the IAP-launch slug
set it was written for, not whatever the schedule happens to contain by
the time this migration runs.

Not reversible - see downgrade().
"""
from alembic import op
from sqlalchemy import bindparam, text

revision = "0012_drop_orphaned_uip_doses"
down_revision = "0011_prescription_child_height"
branch_labels = None
depends_on = None

_IAP_SLUGS = [
    "bcg", "opv-birth", "hepb-1",
    "dtp-1", "ipv-1", "hib-1", "hepb-2", "rota-1", "pcv-1",
    "dtp-2", "ipv-2", "hib-2", "hepb-3", "rota-2", "pcv-2",
    "dtp-3", "ipv-3", "hib-3", "hepb-4", "rota-3", "pcv-3",
    "influenza-1", "influenza-2", "typhoid-conjugate", "mmr-1", "hepa-1",
    "mmr-2", "varicella-1", "pcv-booster",
    "dtp-b1", "hib-b1", "ipv-b1",
    "hepa-2", "varicella-2",
    "dtp-b2", "ipv-b2", "mmr-3",
    "hpv-1", "hpv-2", "tdap-10y",
    "hpv-catchup-1", "hpv-catchup-2", "hpv-catchup-3",
    "td-16-18y",
]


def upgrade() -> None:
    bind = op.get_bind()
    stmt = text("DELETE FROM vaccination_doses WHERE scheduled_slug NOT IN :slugs").bindparams(
        bindparam("slugs", expanding=True)
    )
    bind.execute(stmt, {"slugs": _IAP_SLUGS})


def downgrade() -> None:
    # Data cleanup, not reversible - the deleted rows' original
    # date_administered values are gone. No-op on purpose.
    pass
