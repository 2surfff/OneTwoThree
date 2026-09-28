from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import MeetingCreate, MeetingRead
from app.services import meetings as service

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingRead])
def list_meetings(db: Session = Depends(get_db)):
    return service.list_meetings(db)


@router.get("/{meeting_id}", response_model=MeetingRead)
def get_meeting(meeting_id: UUID, db: Session = Depends(get_db)):
    return service.get_meeting(db, meeting_id)


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def create_meeting(data: MeetingCreate, db: Session = Depends(get_db)):
    return service.create_meeting(db, data)


@router.put("/{meeting_id}", response_model=MeetingRead)
def update_meeting(meeting_id: UUID, data: MeetingCreate, db: Session = Depends(get_db)):
    return service.update_meeting(db, meeting_id, data)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: UUID, db: Session = Depends(get_db)):
    service.delete_meeting(db, meeting_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
