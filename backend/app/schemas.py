from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --------------------------- Prescriptions ---------------------------
class Medication(BaseModel):
    name: str = ""
    form: str = ""
    dosage: str = ""
    frequency: str = ""
    duration: str = ""


class PrescriptionBase(BaseModel):
    doctor_name: str = ""
    date_of_visit: Optional[date] = None
    complaint: str = ""
    diagnosis: str = ""
    medications: list[Medication] = Field(default_factory=list)
    child_age: str = ""
    child_weight: str = ""
    child_id: Optional[UUID] = None
    additional_notes: str = ""
    source_text: str = ""


class PrescriptionCreate(PrescriptionBase):
    pass


class PrescriptionOut(PrescriptionBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: Optional[datetime] = None


# --------------------------- Auth ---------------------------
CONSENT_VERSION = "v1"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = ""
    consent: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


DELETE_ACCOUNT_PHRASE = "delete my account"


class DeleteAccountRequest(BaseModel):
    confirm: str


# --------------------------- Children ---------------------------
class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: Optional[date] = None


class ChildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    date_of_birth: Optional[date] = None


# --------------------------- Chat ---------------------------
class ChatRequest(BaseModel):
    question: str
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
    grounded: bool = True


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
