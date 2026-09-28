from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas import UserUpdate


def get_or_create(db: Session, sub: str, email: str, name: str | None) -> User:
    """The user behind a token; created on first sign-in, email kept in sync with Cognito."""
    user = db.scalar(select(User).where(User.cognito_sub == sub))
    if user is None:
        user = User(cognito_sub=sub, email=email, name=name)
        db.add(user)
        db.commit()
    elif user.email != email:
        user.email = email
        db.commit()
    return user


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    user.name = data.name
    db.commit()
    return user
