import re
from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_password_complexity(v: str) -> str:
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must include a lowercase letter")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must include an uppercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must include a digit")
    if not re.search(r"[^\w\s]", v):
        raise ValueError("Password must include a special character")
    return v


# --------------------------- Prescriptions ---------------------------
class Medication(BaseModel):
    name: str = Field("", max_length=200)
    form: str = Field("", max_length=200)
    dosage: str = Field("", max_length=200)
    frequency: str = Field("", max_length=200)
    duration: str = Field("", max_length=200)


class PrescriptionBase(BaseModel):
    doctor_name: str = Field("", max_length=200)
    date_of_visit: Optional[date] = None
    complaint: str = Field("", max_length=5000)
    diagnosis: str = Field("", max_length=5000)
    medications: list[Medication] = Field(default_factory=list)
    child_age: str = Field("", max_length=50)
    child_weight: str = Field("", max_length=50)
    child_id: Optional[UUID] = None
    additional_notes: str = Field("", max_length=5000)
    source_text: str = Field("", max_length=20000)


class PrescriptionCreate(PrescriptionBase):
    # Every record must belong to a child - overrides PrescriptionBase's
    # Optional[UUID] (which PrescriptionOut still uses, since rows created
    # before this requirement existed can have a NULL child_id). The router
    # also checks this id actually belongs to the caller's account, since a
    # Pydantic UUID check alone can't confirm ownership.
    child_id: UUID

    # If this draft came from a reviewed OCR job, linking it back lets the
    # backend carry the job's photo(s) onto the saved record and mark the
    # job as saved (see routers/prescriptions.py::create_prescription) -
    # never accept raw image_keys directly from the client, since that would
    # let a request name arbitrary storage keys instead of only ones the
    # job itself uploaded under this account.
    source_job_id: Optional[UUID] = None


class PrescriptionOut(PrescriptionBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: Optional[datetime] = None


# --------------------------- Auth ---------------------------
CONSENT_VERSION = "v1"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field("", max_length=120)
    consent: bool = False

    _validate_password = field_validator("password")(_validate_password_complexity)


class LoginRequest(BaseModel):
    email: EmailStr
    # Length-capped only, deliberately not complexity-checked - this is
    # verifying an existing credential, not setting a new one, and applying
    # today's complexity rule retroactively would lock out anyone whose
    # password predates it.
    password: str = Field(max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=4000)


class OkResponse(BaseModel):
    ok: bool = True


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: str = ""
    created_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None


class UpdateProfileRequest(BaseModel):
    display_name: str = Field(max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    _validate_new_password = field_validator("new_password")(
        _validate_password_complexity
    )


DELETE_ACCOUNT_PHRASE = "delete my account"


class DeleteAccountRequest(BaseModel):
    confirm: str = Field(max_length=50)


# --------------------------- Household / shared access ---------------------------
class InviteOut(BaseModel):
    token: str
    expires_at: datetime


class JoinRequest(BaseModel):
    token: str = Field(max_length=64)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: str = ""


class HouseholdStatus(BaseModel):
    # Present (non-null) only when the caller is a member of someone else's
    # account - lets the UI show "sharing X's account" vs "you're the owner".
    owner_email: Optional[str] = None
    members: list[MemberOut] = Field(default_factory=list)


# --------------------------- Children ---------------------------
ChildSex = Literal["male", "female"]


class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: Optional[date] = None
    sex: Optional[ChildSex] = None


class ChildUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: Optional[date] = None
    sex: Optional[ChildSex] = None


class ChildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None


# --------------------------- Measurements ---------------------------
HeightUnit = Literal["cm", "in"]
WeightUnit = Literal["kg", "lb"]


class MeasurementCreate(BaseModel):
    child_id: UUID
    measured_on: date
    # Raw value + unit, never trusting the client to have already converted -
    # services/units.py does the one canonical conversion, shared with the
    # OCR extraction path.
    height_value: Optional[float] = Field(None, gt=0, le=250)
    height_unit: HeightUnit = "cm"
    weight_value: Optional[float] = Field(None, gt=0, le=200)
    weight_unit: WeightUnit = "kg"
    source: Literal["manual", "ocr"] = "manual"
    source_job_id: Optional[UUID] = None

    @field_validator("weight_value")
    @classmethod
    def _require_one_measurement(cls, v, info):
        if v is None and info.data.get("height_value") is None:
            raise ValueError("Provide at least a height or a weight")
        return v


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    child_id: UUID
    measured_on: date
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    source: str
    # Computed by the router (needs the child's DOB/sex, which the row alone
    # doesn't carry) - null whenever the child's sex isn't set yet or the
    # age falls outside the WHO 0-5y reference range.
    age_months: Optional[float] = None
    height_percentile: Optional[float] = None
    weight_percentile: Optional[float] = None


class PercentileCurvePoint(BaseModel):
    month: int
    p3: float
    p15: float
    p50: float
    p85: float
    p97: float


class PercentileCurvesOut(BaseModel):
    height_for_age: list[PercentileCurvePoint]
    weight_for_age: list[PercentileCurvePoint]


# --------------------------- Vaccination ---------------------------
class VaccinationDoseCreate(BaseModel):
    child_id: UUID
    scheduled_slug: str = Field(min_length=1, max_length=60)
    date_administered: date


class VaccineStatusOut(BaseModel):
    slug: str
    name: str
    subtitle: str
    given: bool
    date_administered: Optional[date] = None


class MilestoneStatusOut(BaseModel):
    key: str
    label: str
    summary: str
    status: Literal["given", "due", "not_due"]
    overdue: bool
    given_count: int
    total_count: int
    vaccines: list[VaccineStatusOut]


class ScheduleStatusOut(BaseModel):
    milestones: list[MilestoneStatusOut]
    given_count: int
    total_count: int


# --------------------------- Chat ---------------------------
class ChatRequest(BaseModel):
    question: str = Field(max_length=2000)
    # Optional structured filters - narrow the record set before retrieval
    # instead of asking the embedding to infer "which child" or "which
    # dates" from the question text.
    child_id: Optional[UUID] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


ColorKey = str  # "violet" | "mint" | "amber" | "sky"


class FactOut(BaseModel):
    label: str
    value: str
    emphasis: bool = False


class MedTagOut(BaseModel):
    name: str
    color_key: ColorKey


class SourceOut(BaseModel):
    id: str
    kind: str = "prescription"  # this app only ever produces prescription records
    title: str
    prescriber: Optional[str] = None
    date: Optional[str] = None
    page: Optional[int] = None
    thumbnail_url: Optional[str] = None


class FollowUpOut(BaseModel):
    label: str  # short chip text, 2-4 words
    question: str  # full question inserted into the composer on click


class ChatResponse(BaseModel):
    text: str
    med: Optional[MedTagOut] = None
    facts: Optional[list[FactOut]] = None
    safety_note: Optional[str] = None
    sources: list[SourceOut] = Field(default_factory=list)
    follow_ups: list[FollowUpOut] = Field(default_factory=list)
    # True only when `text` actually contains a [[record]] marker - i.e. the
    # answer genuinely cites the child's records, not just that retrieval
    # happened to find something by keyword/embedding similarity. Drives
    # whether the frontend shows a "not based on your records" disclaimer.
    # Defaults to False (not True): rag.py's early-return/degraded paths
    # (no records, budget rejection, LLM unavailable, malformed model JSON)
    # never explicitly set this field, so whatever the default is becomes
    # their answer - and every one of those is a case where the response is
    # definitionally *not* grounded in an actual record. Only the one path
    # that computes a real value (rag.py::answer()'s final return) passes
    # grounded= explicitly; every other path relies on this default being
    # the safe one.
    grounded: bool = False


# --------------------------- Medications (derived) ---------------------------
class MedOut(BaseModel):
    id: str
    name: str
    form: str = ""
    cadence: str
    color_key: ColorKey
    last_seen_at: str
    active: bool


# --------------------------- OCR / Jobs ---------------------------
class JobCreated(BaseModel):
    job_id: UUID
    status: str


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    raw_text: str = ""
    extracted: Optional[dict] = None
    error: str = ""
    saved: bool = False
    created_at: Optional[datetime] = None
