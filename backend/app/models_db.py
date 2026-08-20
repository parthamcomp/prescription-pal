import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    consent_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    children: Mapped[list["Child"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Child(Base):
    __tablename__ = "children"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_children_user_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Nullable, binary only - WHO's growth-percentile LMS tables are published
    # strictly male/female, and the frontend degrades gracefully (prompts to
    # set it) rather than blocking on it. Enforced as Literal["male","female"]
    # at the Pydantic layer only, matching this codebase's existing style.
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="children")
    # passive_deletes=True: without it, SQLAlchemy's unit-of-work emits its
    # own UPDATE ... SET child_id = NULL for any loaded prescriptions before
    # deleting the child (its default behavior for a relationship without an
    # explicit delete cascade) - that runs *instead of* the DB's ON DELETE
    # CASCADE ever firing, since the rows no longer reference this child by
    # the time the DELETE hits. This flag tells the ORM to step aside and
    # let Postgres enforce the FK's ON DELETE CASCADE itself.
    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="child", passive_deletes=True
    )
    # Same passive_deletes=True requirement as prescriptions above - Child
    # deletion goes through repositories/children.py::delete_for_user's ORM
    # db.delete(child), so without this SQLAlchemy would try to null the FK
    # on any loaded rows instead of letting Postgres's ON DELETE CASCADE fire.
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="child", passive_deletes=True
    )
    vaccination_doses: Mapped[list["VaccinationDose"]] = relationship(
        back_populates="child", passive_deletes=True
    )


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    doctor_name: Mapped[str] = mapped_column(String(200), default="")
    date_of_visit: Mapped[date | None] = mapped_column(Date, nullable=True)
    complaint: Mapped[str] = mapped_column(Text, default="")
    diagnosis: Mapped[str] = mapped_column(Text, default="")
    medications: Mapped[list] = mapped_column(JSONB, default=list)
    child_age: Mapped[str] = mapped_column(String(50), default="")
    child_weight: Mapped[str] = mapped_column(String(50), default="")
    child_height: Mapped[str] = mapped_column(String(50), default="")
    # Which child this visit belongs to. The API requires a child on every
    # create/update (see PrescriptionCreate) so there are no new unassigned
    # records going forward; this column stays nullable at the DB level only
    # to avoid breaking rows created before that requirement existed.
    # ON DELETE CASCADE: a child profile is the record's owner in this
    # model, so removing the child removes their prescription history with
    # it rather than leaving orphaned rows - see repositories/children.py.
    child_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("children.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    additional_notes: Mapped[str] = mapped_column(Text, default="")
    source_text: Mapped[str] = mapped_column(Text, default="")
    # Object-storage keys for the original photo(s), in page order. Carried
    # forward from the ProcessingJob that produced this record (see
    # PrescriptionCreate.source_job_id) - empty for manually-typed records
    # or records created before this column existed.
    image_keys: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # RAG: the flattened document + its embedding (nullable until indexed)
    document: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )
    # Full-text search vector, generated and kept in sync by Postgres itself
    # (see migration 0002_hybrid_search) - the app never writes this column.
    # Computed(...) tells SQLAlchemy that too, so it's excluded from
    # INSERT/UPDATE statements instead of sending an explicit NULL, which
    # Postgres rejects for a GENERATED ALWAYS column.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(document, ''))", persisted=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="prescriptions")
    child: Mapped["Child | None"] = relationship(back_populates="prescriptions")


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        # The chart's core query is "this child's measurements in date order" -
        # a composite index on exactly that pair avoids a sort on read.
        Index("ix_measurements_child_measured_on", "child_id", "measured_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("children.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "manual" (added via the Percentiles tab's +Add measurement) or
    # "prescription" (derived from a Prescription's child_height/child_weight
    # free-text fields - see routers/prescriptions.py::_sync_growth_measurement).
    source: Mapped[str] = mapped_column(String(15), default="manual")
    # Links a "prescription"-sourced row back to the record it was derived
    # from, so re-saving that record can find and update (rather than
    # duplicate) the measurement it previously produced, and clearing the
    # height/weight text there can delete it. Null for manually-added rows.
    # ON DELETE CASCADE: a derived measurement has no meaning once the
    # prescription it came from is gone.
    source_prescription_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Object-storage keys of the originating photo(s) - unused now that
    # measurements are either typed directly or derived from a prescription's
    # own text fields, kept only so existing rows written by the earlier
    # OCR-linked flow still deserialize.
    image_keys: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    child: Mapped["Child"] = relationship(back_populates="measurements")


class VaccinationDose(Base):
    __tablename__ = "vaccination_doses"
    __table_args__ = (
        # One dose row per schedule slug per child - the schedule template
        # (backend/app/data/vaccination_schedule_uip.json) already numbers
        # doses as distinct slugs (e.g. "opv-1", "opv-2"), so this constraint
        # is what makes a POST idempotent/upsert-safe rather than needing an
        # extra existence check in the router.
        UniqueConstraint("child_id", "scheduled_slug", name="uq_dose_child_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("children.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # References a slug in the bundled UIP schedule JSON, not a DB row - the
    # schedule template can be revised (a JSON diff) without a migration.
    scheduled_slug: Mapped[str] = mapped_column(String(60), nullable=False)
    date_administered: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    child: Mapped["Child"] = relationship(back_populates="vaccination_doses")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    # One or more object-storage keys, in page order - a multi-page upload
    # is one job whose OCR text gets concatenated across pages before a
    # single extraction call (see worker.py::process_ocr_job).
    image_keys: Mapped[list[str]] = mapped_column(JSONB, default=list)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    extracted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    # Whether this job's extraction was ever turned into a saved
    # Prescription - drives the "pending uploads" list (a job can finish
    # OCR successfully and still never get reviewed/saved if the user
    # navigates away).
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AccountLink(Base):
    """Grants member_user_id full symmetric access to owner_user_id's data
    (children, prescriptions, chat, uploads). member_user_id is unique - a
    user can be a member of at most one shared account at a time."""

    __tablename__ = "account_links"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    member_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AccountInvite(Base):
    __tablename__ = "account_invites"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
