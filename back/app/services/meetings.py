from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Meeting, Participant
from app.schemas import MeetingCreate
from app.services.errors import NotFoundError


def list_meetings(db: Session) -> Sequence[Meeting]:
    query = (
        select(Meeting).options(selectinload(Meeting.participants)).order_by(Meeting.starts_at, Meeting.id)
    )
    return db.scalars(query).all()


def get_meeting(db: Session, meeting_id: UUID) -> Meeting:
    query = select(Meeting).options(selectinload(Meeting.participants)).where(Meeting.id == meeting_id)
    meeting = db.scalar(query)
    if meeting is None:
        raise NotFoundError(f"Meeting {meeting_id} not found")
    return meeting


def _load_participants(db: Session, participant_ids: list[UUID]) -> list[Participant]:
    participant_ids = list(dict.fromkeys(participant_ids))
    if not participant_ids:
        return []
    participants = list(db.scalars(select(Participant).where(Participant.id.in_(participant_ids))))
    missing = set(participant_ids) - {p.id for p in participants}
    if missing:
        ids = ", ".join(sorted(str(m) for m in missing))
        raise NotFoundError(f"Participants not found: {ids}")
    return participants


def _apply(meeting: Meeting, data: MeetingCreate, participants: list[Participant]) -> None:
    meeting.title = data.title
    meeting.description = data.description
    meeting.call_link = str(data.call_link) if data.call_link else None
    meeting.place = data.place
    meeting.starts_at = data.starts_at
    meeting.ends_at = data.ends_at
    meeting.participants = participants


def create_meeting(db: Session, data: MeetingCreate) -> Meeting:
    meeting = Meeting()
    _apply(meeting, data, _load_participants(db, data.participant_ids))
    db.add(meeting)
    db.commit()
    return get_meeting(db, meeting.id)


def update_meeting(db: Session, meeting_id: UUID, data: MeetingCreate) -> Meeting:
    meeting = get_meeting(db, meeting_id)
    _apply(meeting, data, _load_participants(db, data.participant_ids))
    db.commit()
    return get_meeting(db, meeting.id)


def delete_meeting(db: Session, meeting_id: UUID) -> None:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise NotFoundError(f"Meeting {meeting_id} not found")
    db.delete(meeting)
    db.commit()
