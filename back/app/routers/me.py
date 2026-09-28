from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import UserRead, UserUpdate
from app.services import users as service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserRead)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("", response_model=UserRead)
def update_me(data: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_user(db, user, data)
