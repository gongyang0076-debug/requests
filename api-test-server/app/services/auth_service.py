from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User


class UserAlreadyExistsError(ValueError):
    """Raised when username or email violates user uniqueness."""


class InvalidCredentialsError(ValueError):
    """Raised when login credentials cannot authenticate a user."""


def register_user(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
) -> User:
    existing_user_id = session.scalar(
        select(User.id).where(or_(User.username == username, User.email == email))
    )
    if existing_user_id is not None:
        raise UserAlreadyExistsError("Username or email already exists")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
    )
    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise UserAlreadyExistsError("Username or email already exists") from exc

    session.refresh(user)
    return user


def authenticate_user(session: Session, *, username: str, password: str) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        raise InvalidCredentialsError("Invalid username or password")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password")

    return user
