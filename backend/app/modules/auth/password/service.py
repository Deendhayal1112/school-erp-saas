"""
Password Management Service.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.password import hash_password, verify_password
from app.models.password_history import PasswordHistory
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.modules.auth.password.exceptions import (
    ExpiredResetTokenException,
    InvalidCurrentPasswordException,
    InvalidResetTokenException,
    PasswordReuseException,
)
from app.modules.auth.password.validators import validate_password_policy
from app.repositories.user_repository import UserRepository


class PasswordService:
    """
    Handles secure password lifecycle management, password history compliance,
    and password reset flows.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def change_password(self, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
        """
        Securely changes a user's password.
        Validates current password, checks complexity policies, prevents reuse,
        hashes the new password, logs history, and invalidates active sessions.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise InvalidCurrentPasswordException("User not found.")

        # 1. Verify current password
        if not verify_password(current_password, user.password_hash):
            raise InvalidCurrentPasswordException("Current password is incorrect.")

        # 2. Validate new password complexity/policy
        validate_password_policy(new_password)

        # 3. Prevent password reuse of last N passwords
        await self._check_password_history(user, new_password)

        # 4. Hash and save new password
        old_hash = user.password_hash
        hashed_pwd = hash_password(new_password)
        user.password_hash = hashed_pwd
        user.password_changed_at = datetime.now(UTC)

        # 5. Invalidate active sessions (by updating password_changed_at,
        # which invalidates tokens issued prior to it)

        # 6. Save current password to history
        await self._add_to_history(user.id, old_hash)

        self.session.add(user)
        await self.session.commit()

    async def generate_reset_token(self, email: str) -> str:
        """
        Generates a secure reset token for forgot-password flow.
        Follows OWASP advice to never leak email existence.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        user = await self.user_repo.get_by_email(email)
        if not user:
            # Silent return to prevent email enumeration
            return raw_token

        # Create reset token record
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        self.session.add(reset_token)
        await self.session.commit()

        return raw_token

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        """
        Resets a user's password using a valid, unexpired reset token.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Find matching unexpired, unused token
        stmt = (
            select(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used.is_(False)
            )
        )
        result = await self.session.execute(stmt)
        token_record = result.scalar_one_or_none()

        if not token_record:
            raise InvalidResetTokenException("Invalid or already used reset token.")

        if token_record.expires_at < datetime.now(UTC):
            token_record.used = True
            self.session.add(token_record)
            await self.session.commit()
            raise ExpiredResetTokenException("Password reset token has expired.")

        # Load user
        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user:
            raise InvalidResetTokenException("User associated with this token not found.")

        # Validate password policy
        validate_password_policy(new_password)

        # Prevent reuse
        await self._check_password_history(user, new_password)

        # Update user password
        old_hash = user.password_hash
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        user.failed_login_count = 0
        user.locked_until = None

        # Add old password to history
        await self._add_to_history(user.id, old_hash)

        # Mark token as used
        token_record.used = True

        self.session.add(user)
        self.session.add(token_record)
        await self.session.commit()

    async def _check_password_history(self, user: User, new_password: str) -> None:
        """Checks new password against user's historical hashes."""
        # Check active password first
        if verify_password(new_password, user.password_hash):
            raise PasswordReuseException("New password cannot be the same as the current password.")

        # Query history
        stmt = (
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user.id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(settings.PASSWORD_HISTORY_LENGTH)
        )
        res = await self.session.execute(stmt)
        history_items = res.scalars().all()

        for item in history_items:
            if verify_password(new_password, item.password_hash):
                raise PasswordReuseException("Password was used recently and cannot be reused.")

    async def _add_to_history(self, user_id: uuid.UUID, password_hash: str) -> None:
        """Adds a password hash to history and handles automatic cleanup of overflow."""
        history_item = PasswordHistory(
            user_id=user_id,
            password_hash=password_hash
        )
        self.session.add(history_item)

        # Cleanup old history records exceeding PASSWORD_HISTORY_LENGTH
        stmt = (
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
        )
        res = await self.session.execute(stmt)
        all_history = res.scalars().all()

        # If it exceeds history length, delete oldest ones
        if len(all_history) >= settings.PASSWORD_HISTORY_LENGTH:
            # We are about to add one, so prune any beyond length - 1
            excess_items = all_history[settings.PASSWORD_HISTORY_LENGTH - 1:]
            for item in excess_items:
                await self.session.delete(item)
