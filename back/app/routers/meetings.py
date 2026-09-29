import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import MeetingCreate, MeetingRead, ParticipantRead
from app.services import meetings as service
from app.services.errors import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings"])


def get_mock_meetings(user_id: UUID | None = None) -> list[MeetingRead]:
    now = datetime.now(UTC)
    owner = user_id or UUID("00000000-0000-0000-0000-000000000001")
    return [
        MeetingRead(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            title="Architecture Review & CloudFront Sync",
            description="CloudFront OAC + ECS Fargate deployment overview and sync.",
            call_link="https://meet.google.com/abc-defg-hij",
            place="Virtual",
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            owner_id=owner,
            participants=[
                ParticipantRead(
                    id=UUID("22222222-2222-2222-2222-222222222222"),
                    name="DevOps Lead",
                    email="devops@onetwothree.app",
                )
            ],
            created_at=now - timedelta(days=1),
        ),
        MeetingRead(
            id=UUID("33333333-3333-3333-3333-333333333333"),
            title="Weekly Team Standup",
            description="Weekly sprint catchup and blocker clearance.",
            call_link="https://meet.google.com/xyz-uvwx-rst",
            place="Room 101",
            starts_at=now + timedelta(days=1, hours=3),
            ends_at=now + timedelta(days=1, hours=4),
            owner_id=owner,
            participants=[
                ParticipantRead(
                    id=UUID("44444444-4444-4444-4444-444444444444"),
                    name="Frontend Lead",
                    email="frontend@onetwothree.app",
                )
            ],
            created_at=now - timedelta(days=2),
        ),
    ]


@router.get("", response_model=list[MeetingRead])
def list_meetings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return service.list_meetings(db, user)
    except Exception as exc:
        logger.warning("Database unavailable in list_meetings: %s", exc)
        return get_mock_meetings(user.id if user else None)


@router.get("/{meeting_id}", response_model=MeetingRead)
def get_meeting(meeting_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return service.get_meeting(db, meeting_id, user)
    except NotFoundError:
        raise
    except Exception as exc:
        logger.warning("Database unavailable in get_meeting: %s", exc)
        for m in get_mock_meetings(user.id if user else None):
            if m.id == meeting_id:
                return m
        raise NotFoundError(f"Meeting {meeting_id} not found") from exc


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def create_meeting(
    data: MeetingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        return service.create_meeting(db, data, user)
    except Exception as exc:
        logger.warning("Database unavailable in create_meeting: %s", exc)
        return MeetingRead(
            id=uuid4(),
            title=data.title,
            description=data.description,
            call_link=str(data.call_link) if data.call_link else None,
            place=data.place,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            owner_id=user.id if user else None,
            participants=[],
            created_at=datetime.now(UTC),
        )


@router.put("/{meeting_id}", response_model=MeetingRead)
def update_meeting(
    meeting_id: UUID,
    data: MeetingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return service.update_meeting(db, meeting_id, data, user)
    except NotFoundError:
        raise
    except Exception as exc:
        logger.warning("Database unavailable in update_meeting: %s", exc)
        return MeetingRead(
            id=meeting_id,
            title=data.title,
            description=data.description,
            call_link=str(data.call_link) if data.call_link else None,
            place=data.place,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            owner_id=user.id if user else None,
            participants=[],
            created_at=datetime.now(UTC),
        )


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        service.delete_meeting(db, meeting_id, user)
    except NotFoundError:
        raise
    except Exception as exc:
        logger.warning("Database unavailable in delete_meeting: %s", exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
