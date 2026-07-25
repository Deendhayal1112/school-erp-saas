import uuid
from datetime import UTC, datetime, timedelta

from app.core import jwt, tokens
from app.core.config import settings
from app.core.password import verify_password
from app.exceptions import (
    DeletedUserException,
    InactiveSchoolException,
    InactiveUserException,
    InvalidCredentialsException,
    RefreshTokenException,
    TokenExpiredException,
)
from app.modules.auth.password.exceptions import AccountLockedException
from app.repositories.user_repository import UserRepository
from app.services.base_service import BaseService


class AuthenticationService(BaseService):
    """
    Authentication Service handling all user login, token refresh, and account state checks.
    Decoupled from direct HTTP routing or database connection logic.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repo = user_repository

    async def authenticate_user(self, email: str, password: str) -> dict:
        """
        Authenticates a user by email and password.
        Updates user last login on success and issues access/refresh tokens.
        Tracks failed logins and locks accounts temporarily under policy threshold breaches.
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise InvalidCredentialsException("Incorrect email or password.")

        # 1. Enforce temporary lockout policy if active
        if user.locked_until:
            if user.locked_until > datetime.now(UTC):
                raise AccountLockedException(
                    "This account is temporarily locked due to multiple failed login attempts. "
                    f"Please try again after {user.locked_until.isoformat()}.",
                    unlock_time=user.locked_until
                )
            else:
                # Lockout duration has expired, reset counters automatically
                user.failed_login_count = 0
                user.locked_until = None
                await self.user_repo.update(user)
                await self.user_repo.session.commit()

        # 2. Verify password correctness
        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= settings.ACCOUNT_LOCKOUT_THRESHOLD:
                user.locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
            await self.user_repo.update(user)
            await self.user_repo.session.commit()

            if user.locked_until and user.locked_until > datetime.now(UTC):
                raise AccountLockedException(
                    "This account is temporarily locked due to multiple failed login attempts. "
                    f"Please try again after {user.locked_until.isoformat()}.",
                    unlock_time=user.locked_until
                )
            raise InvalidCredentialsException("Incorrect email or password.")

        # 3. Reset failed login counters on successful credential verification
        if user.failed_login_count > 0 or user.locked_until:
            user.failed_login_count = 0
            user.locked_until = None
            await self.user_repo.update(user)
            await self.user_repo.session.commit()

        # Enforce account and tenant status rules
        self.validate_user_status(user)

        # Generate cryptographic tokens
        access_token = tokens.create_access_token(subject=str(user.id))
        refresh_token = tokens.create_refresh_token(subject=str(user.id))

        # Update login audit trails
        await self.update_last_login(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Validates a refresh token and generates a new pair of access/refresh tokens.
        Checks user status before generating tokens.
        Rejects tokens issued prior to the user's last password change event.
        """
        try:
            payload = jwt.decode_token(refresh_token)
        except jwt.TokenExpiredError as e:
            raise TokenExpiredException("Refresh token has expired.") from e
        except jwt.JWTError as e:
            raise RefreshTokenException("Invalid refresh token.") from e

        # Ensure the token classification is explicitly a refresh token
        if payload.get("type") != "refresh":
            raise RefreshTokenException("Token type must be 'refresh'.")

        user_id = uuid.UUID(payload["sub"])
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise InvalidCredentialsException("User not found.")

        # Re-verify token issuance time against user password change event
        iat_timestamp = payload.get("iat")
        if iat_timestamp and user.password_changed_at:
            token_iat_dt = datetime.fromtimestamp(iat_timestamp, tz=UTC)
            if token_iat_dt < user.password_changed_at.replace(microsecond=0):
                raise RefreshTokenException("Token has been invalidated by a password change.")

        # Re-verify account state and school tenant active status
        self.validate_user_status(user)

        # Issue new token pair (refresh token rotation)
        new_access = tokens.create_access_token(subject=str(user.id))
        new_refresh = tokens.create_refresh_token(subject=str(user.id))

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def logout_user(self, user_id: uuid.UUID) -> None:
        """
        Logs a user out of the platform.
        Can be used to trigger blacklist storage or session audit updates.
        """
        # Stateful logout or caching logic (if added later)
        pass

    def validate_user_status(self, user) -> None:
        """Verifies that the user account and associated tenant school are active."""
        if user.is_deleted:
            raise DeletedUserException("This user account has been soft deleted.")

        if not user.is_active or user.status != "active":
            raise InactiveUserException("This user account is currently deactivated.")

        if not user.school.is_active:
            raise InactiveSchoolException("This school tenant has been deactivated.")

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Updates the user's last login timestamp in the database."""
        now = datetime.now(UTC)
        await self.user_repo.update_last_login(user_id, now)
