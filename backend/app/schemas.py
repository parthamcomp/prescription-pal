from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --------------------------- Prescriptions ---------------------------
class Medication(BaseModel):
    name: str = ""
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
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = ""


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


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)


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
