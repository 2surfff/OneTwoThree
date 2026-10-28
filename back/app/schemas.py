from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_serializer,
    field_validator,
    model_validator,
)


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class ParticipantCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        return _blank_to_none(value)


# Lab 6 Agenda Schemas
class AgendaItemSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1)
    duration_minutes: int | None = None
    description: str | None = None


class ActionItemSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    task: str = Field(min_length=1)
    assignee: str | None = None
    due_date: str | None = None


class SaveAgendaRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    agenda: dict[str, Any] | None = None
    ai_suggestion: dict[str, Any] | None = None


class MeetingCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    call_link: HttpUrl | None = None
    place: str | None = Field(default=None, max_length=255)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    participant_ids: list[UUID] = []
    agenda: dict[str, Any] | None = None
    ai_suggestion: dict[str, Any] | None = None

    @field_validator("description", "call_link", "place", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def require_call_link_or_place(self) -> "MeetingCreate":
        if self.call_link is None and self.place is None:
            raise ValueError("Provide a call link, a place, or both")
        return self

    @model_validator(mode="after")
    def ends_after_start(self) -> "MeetingCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("The meeting must end after it starts")
        return self


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    call_link: str | None
    place: str | None
    starts_at: datetime
    ends_at: datetime
    owner_id: UUID | None
    participants: list[ParticipantRead]
    created_at: datetime
    agenda: dict[str, Any] | None = None
    ai_suggestion: dict[str, Any] | None = None

    @field_serializer("starts_at", "ends_at")
    def serialize_datetime(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace("+00:00", "Z")
