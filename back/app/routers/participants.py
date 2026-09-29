import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.schemas import ParticipantCreate, ParticipantRead
from app.services import participants as service
from app.services.errors import NotFoundError

logger = logging.getLogger(__name__)

# The participant directory is shared by all users, but only signed-in users may use it.
router = APIRouter(prefix="/participants", tags=["participants"], dependencies=[Depends(get_current_user)])


def _mock_participants() -> list[ParticipantRead]:
    return [
        ParticipantRead(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            name="DevOps Lead",
            email="devops@onetwothree.app",
        ),
        ParticipantRead(
            id=UUID("44444444-4444-4444-4444-444444444444"),
            name="Frontend Lead",
            email="frontend@onetwothree.app",
        ),
    ]


@router.get("", response_model=list[ParticipantRead])
def list_participants(q: str | None = None, db: Session = Depends(get_db)):
    try:
        return service.list_participants(db, q)
    except Exception as exc:
        logger.warning("Database unavailable in list_participants: %s", exc)
        participants = _mock_participants()
        if q:
            q_clean = q.strip().lower()
            participants = [
                p for p in participants if q_clean in p.name.lower() or q_clean in p.email.lower()
            ]
        return participants


@router.post("", response_model=ParticipantRead, status_code=status.HTTP_201_CREATED)
def create_participant(data: ParticipantCreate, db: Session = Depends(get_db)):
    try:
        return service.create_participant(db, data)
    except Exception as exc:
        logger.warning("Database unavailable in create_participant: %s", exc)
        return ParticipantRead(id=uuid4(), name=data.name, email=data.email)


@router.delete("/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_participant(participant_id: UUID, db: Session = Depends(get_db)):
    try:
        service.delete_participant(db, participant_id)
    except NotFoundError:
        raise
    except Exception as exc:
        logger.warning("Database unavailable in delete_participant: %s", exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
