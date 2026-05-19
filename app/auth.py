import os
from datetime import datetime, timezone

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hash_password(password):
    return pwd_context.hash(password)


def verify_password(password, password_hash):
    return pwd_context.verify(password, password_hash)


def authenticate_user(db: Session, username, password):
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def session_secret():
    return os.environ.get("CHORE_BANK_SECRET", "change-this-local-dev-secret")


def create_user(db: Session, username, display_name, password, role):
    now = now_iso()
    user = User(
        username=username.strip().lower(),
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    return user
