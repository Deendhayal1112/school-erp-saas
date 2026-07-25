import uuid
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import (
    AuthenticationRequiredException,
    InactiveAccountException,
    InactiveSchoolException,
    InvalidBearerTokenException,
    UserNotFoundException,
    decode_authenticated_user,
    validate_bearer_format,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """
    Authenticates requesting users by verifying Bearer headers and decoding signatures.
    Resolves the matching database User ORM instance.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise AuthenticationRequiredException("Authentication required")

    token = validate_bearer_format(auth_header)
    payload = decode_authenticated_user(token)

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as e:
        raise InvalidBearerTokenException("Invalid token subject format") from e

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise UserNotFoundException("User not found")

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Verifies that the resolved user credentials map to active accounts
    and active tenant school systems.
    """
    if current_user.is_deleted:
        raise UserNotFoundException("User not found")

    if not current_user.is_active or current_user.status != "active":
        raise InactiveAccountException("Inactive user account")

    if not current_user.school.is_active:
        raise InactiveSchoolException("Inactive school tenant")

    return current_user


async def get_optional_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User | None:
    """
    Optional authentication handler.
    Returns the resolved User model if a valid Bearer header is present,
    otherwise returns None without raising authentication exceptions.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    try:
        token = validate_bearer_format(auth_header)
        payload = decode_authenticated_user(token)
        user_id = uuid.UUID(payload["sub"])
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)
        if not user or user.is_deleted:
            return None
        return user
    except Exception:
        return None
