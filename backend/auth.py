"""User accounts: sign up, log in, and the logged-in user's profile.

Passwords are hashed with Argon2 (pwdlib) and never stored or returned in
plain text. Logging in returns a signed JWT; send it on later requests as
`Authorization: Bearer <token>`.
"""
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models import Competency, User, UserProfile
from schemas import MeOut, ProfileIn, ProfileOut, SignupRequest, TokenResponse, UserOut

load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(hours=24)

password_hash = PasswordHash.recommended()  # Argon2id
# Checked against when an email doesn't exist, so a failed login takes the same
# time either way and doesn't reveal which emails have accounts.
_DUMMY_HASH = password_hash.hash("dummy-password-for-timing")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
router = APIRouter()


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_LIFETIME}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not logged in, or your session has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = db.get(User, int(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise unauthorized from None
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/auth/signup", response_model=TokenResponse, status_code=201, tags=["auth"])
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """Create an account and return a token, so the user is logged in straight away."""
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, password_hash=password_hash.hash(body.password))
    db.add(user)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)
):
    """Log in with email (sent as `username`) and password. Returns a token."""
    user = db.scalar(select(User).where(func.lower(User.email) == form.username.lower()))
    if user is None:
        password_hash.verify(form.password, _DUMMY_HASH)
        valid = False
    else:
        valid = password_hash.verify(form.password, user.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=MeOut, tags=["me"])
def me(user: CurrentUser):
    return MeOut(
        user=UserOut.model_validate(user),
        profile=ProfileOut.model_validate(user.profile) if user.profile else None,
    )


@router.get("/me/profile", response_model=ProfileOut, tags=["me"])
def get_profile(user: CurrentUser):
    if user.profile is None:
        raise HTTPException(status_code=404, detail="No accessibility profile saved yet.")
    return user.profile


@router.put("/me/profile", response_model=ProfileOut, tags=["me"])
def save_profile(body: ProfileIn, user: CurrentUser, db: Session = Depends(get_db)):
    """Create or replace the logged-in user's accessibility profile."""
    codes = list(dict.fromkeys(body.required_competencies))
    known = set(db.scalars(select(Competency.code).where(Competency.code.in_(codes))))
    unknown = [c for c in codes if c not in known]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown competency codes: {unknown}")

    profile = user.profile or UserProfile(user_id=user.id)
    profile.mobility_device = body.mobility_device
    profile.communication_needs = [n.value for n in dict.fromkeys(body.communication_needs)]
    profile.required_competencies = codes
    profile.location = body.location.strip() if body.location else None
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
