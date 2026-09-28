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


def create_meeting(db: Session, data: MeetingCreate) -> Meeting:
    participant_ids = list(dict.fromkeys(data.participant_ids))
    participants: list[Participant] = []
    if participant_ids:
        participants = list(db.scalars(select(Participant).where(Participant.id.in_(participant_ids))))
        missing = set(participant_ids) - {p.id for p in participants}
        if missing:
            ids = ", ".join(sorted(str(m) for m in missing))
            raise NotFoundError(f"Participants not found: {ids}")

    meeting = Meeting(
        title=data.title,
        description=data.description,
        call_link=str(data.call_link) if data.call_link else None,
        place=data.place,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        participants=participants,
    )
    db.add(meeting)
    db.commit()
    return get_meeting(db, meeting.id)


def delete_meeting(db: Session, meeting_id: UUID) -> None:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise NotFoundError(f"Meeting {meeting_id} not found")
    db.delete(meeting)
    db.commit()
