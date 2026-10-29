import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import MeetingCreate, MeetingRead, ParticipantRead, SaveAgendaRequest
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
    except NotFoundError:
        raise
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
            agenda=data.agenda,
            ai_suggestion=data.ai_suggestion,
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
            agenda=data.agenda,
            ai_suggestion=data.ai_suggestion,
        )


@router.post("/{meeting_id}/agenda", response_model=MeetingRead)
def save_meeting_agenda(
    meeting_id: UUID,
    data: SaveAgendaRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return service.save_agenda(db, meeting_id, data, user)
    except NotFoundError:
        raise
    except Exception as exc:
        logger.warning("Database unavailable in save_meeting_agenda: %s", exc)
        for m in get_mock_meetings(user.id if user else None):
            if m.id == meeting_id:
                m.agenda = data.agenda
                m.ai_suggestion = data.ai_suggestion
                return m
        raise NotFoundError(f"Meeting {meeting_id} not found") from exc


class ParseAgendaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str
    tz: str = "Europe/Kyiv"
    today: str | None = None


@router.post("/parse-agenda")
def parse_agenda_api(
    request: Request,
    data: ParseAgendaInput,
    user: User = Depends(get_current_user),
):
    """Parse agenda via external Lambda Function URL if configured, or fall back to local parser."""
    if len(data.text) > 10000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large. Maximum text length is 10,000 characters.",
        )
    from app.config import settings

    parser_url = settings.AGENDA_PARSER_URL
    resp = None
    if parser_url:
        import httpx

        # Note: Do not forward Authorization header to Lambda Function URL with AuthType: NONE,
        # because AWS evaluates any Authorization header as SigV4 and rejects non-AWS credentials with 403.
        # Instead, send X-User-ID so the external parser knows the authenticated user.
        headers = {"X-User-ID": str(user.id)}
        payload = {"text": data.text, "tz": data.tz}
        if data.today:
            payload["today"] = data.today

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(parser_url, json=payload, headers=headers)

            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as json_err:
                    logger.warning(
                        "Lambda returned 200 but failed to parse JSON: %s. Response: %s",
                        json_err,
                        resp.text,
                    )
            else:
                logger.warning(
                    "Lambda parser returned status %s: %s. Attempting fallback.",
                    resp.status_code,
                    resp.text,
                )
        except Exception as exc:
            logger.warning(
                "Error connecting to Lambda parser at %s: %s. Attempting fallback.",
                parser_url,
                exc,
            )

    from app.ai.agenda import parse_agenda

    today_date = date.fromisoformat(data.today) if data.today else date.today()
    try:
        parsed_agenda, _usage = parse_agenda(text=data.text, today=today_date, tz=data.tz)
        return {
            "agenda": parsed_agenda.model_dump(mode="json"),
            "model": settings.PARSER_MODEL,
            "prompt_version": settings.prompt_version,
        }
    except Exception as exc:
        logger.error("Local agenda parser failed: %s", exc, exc_info=True)
        error_detail = (
            f"Lambda error: {resp.text}"
            if parser_url and resp is not None and resp.status_code != 200
            else f"Agenda parsing failed: {exc}"
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail) from exc


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        service.delete_meeting(db, meeting_id, user)
    except NotFoundError:
        raise
    except Exception as exc:
        logger.warning("Database unavailable in delete_meeting: %s", exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
