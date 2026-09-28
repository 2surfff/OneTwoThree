"""Cognito ID-token verification and the current user.

The frontend signs in with Cognito directly and sends the ID token as `Authorization: Bearer`.
Tokens are checked locally against the pool's signing keys (JWKS), so no call to Cognito is
made per request.
"""

import json
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.services import users as users_service

bearer = HTTPBearer(auto_error=False, description="Cognito ID token")


@dataclass(frozen=True)
class Identity:
    sub: str
    email: str
    name: str | None


# Everyone is this user while auth is disabled (no Cognito pool configured).
LOCAL_IDENTITY = Identity(sub="local-dev", email="dev@localhost", name="Local developer")


@lru_cache
def signing_keys() -> dict[str, Any]:
    """Public keys of the user pool by key ID."""
    if settings.cognito_jwks:
        jwks = json.loads(settings.cognito_jwks)
    else:
        with urllib.request.urlopen(f"{settings.cognito_issuer}/.well-known/jwks.json", timeout=5) as resp:
            jwks = json.load(resp)
    return {key["kid"]: jwt.PyJWK(key).key for key in jwks["keys"]}


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def verify_id_token(token: str) -> Identity:
    try:
        key = signing_keys().get(jwt.get_unverified_header(token).get("kid", ""))
        if key is None:
            raise unauthorized("Unknown signing key")
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise unauthorized(f"Invalid token: {exc}") from exc
    if claims.get("token_use") != "id" or not claims.get("email"):
        raise unauthorized("An ID token with an email is required")
    return Identity(sub=claims["sub"], email=claims["email"].lower(), name=claims.get("name"))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not settings.auth_enabled:
        identity = LOCAL_IDENTITY
    elif credentials is None:
        raise unauthorized("Sign in required")
    else:
        identity = verify_id_token(credentials.credentials)
    return users_service.get_or_create(db, identity.sub, identity.email, identity.name)
