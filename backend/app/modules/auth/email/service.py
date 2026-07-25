"""
Email Verification and Recovery Service.
"""

import hashlib
import secrets
import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.email_verification_token import EmailVerificationToken
from app.repositories.user_repository import UserRepository
from app.modules.auth.email.exceptions import (
    InvalidVerificationTokenException,
    ExpiredVerificationTokenException,
    EmailRateLimitException,
    AccountAlreadyVerifiedException,
)
from app.modules.auth.email.providers import get_email_provider
from app.modules.auth.email.templates import (
    VERIFICATION_HTML,
    VERIFICATION_TEXT,
    WELCOME_HTML,
    WELCOME_TEXT,
    render_template,
)

logger = logging.getLogger(__name__)


class EmailVerificationService:
    """
    Coordinates secure verification token lifecycles, account activations,
    recovery notifications, and rate-limited mail delivery.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.provider = get_email_provider()

    async def send_verification_email(self, email: str) -> None:
        """
        Generates and mails a secure email verification token to a user.
        Defends against user enumeration by failing silently if email is unregistered.
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            logger.info(f"Verification request ignored for unregistered email: {email}")
            return

        if user.email_verified:
            # Silently return or raise depending on scenario, but to prevent enumeration, silent return
            logger.info(f"Verification email requested for already verified user: {email}")
            return

        # 1. Enforce rate limiting between successive verification requests
        await self._check_rate_limit(user.id)

        # 2. Generate secure raw token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # 3. Store hashed token record
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES
        )
        token_record = EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False,
        )
        self.session.add(token_record)
        await self.session.commit()

        # 4. Construct verification URL and render template
        action_url = f"{settings.BASE_URL}/verify-email?token={raw_token}"
        html_content, text_content = render_template(
            VERIFICATION_HTML,
            VERIFICATION_TEXT,
            {
                "name": f"{user.first_name} {user.last_name}",
                "action_url": action_url,
                "expire_mins": settings.EMAIL_VERIFICATION_EXPIRE_MINUTES,
            },
        )

        # 5. Dispatch email
        await self.provider.send_email(
            to_email=user.email,
            subject="Activate Your School ERP SaaS Account",
            html_content=html_content,
            text_content=text_content,
        )

    async def verify_email_token(self, raw_token: str) -> User:
        """
        Validates the raw verification token.
        On success, activates the user's account, marks token as used, and sends a Welcome email.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Query token
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used == False,
        )
        res = await self.session.execute(stmt)
        token_record = res.scalar_one_or_none()

        if not token_record:
            raise InvalidVerificationTokenException("Invalid or already used verification token.")

        # Check expiration
        if token_record.expires_at < datetime.now(timezone.utc):
            token_record.used = True
            self.session.add(token_record)
            await self.session.commit()
            raise ExpiredVerificationTokenException("Verification token has expired.")

        # Load user
        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user:
            raise InvalidVerificationTokenException("User associated with this token not found.")

        if user.email_verified:
            # Token is technically unused but user is already verified. Mark token as used.
            token_record.used = True
            self.session.add(token_record)
            await self.session.commit()
            raise AccountAlreadyVerifiedException("Account is already verified.")

        # 1. Activate account
        user.email_verified = True
        user.is_active = True
        user.status = "active"

        # 2. Mark token as used to prevent replay attacks
        token_record.used = True

        self.session.add(user)
        self.session.add(token_record)
        await self.session.commit()
        await self.session.refresh(user)

        # 3. Send welcome email confirmation
        login_url = f"{settings.BASE_URL}/login"
        html_content, text_content = render_template(
            WELCOME_HTML,
            WELCOME_TEXT,
            {
                "name": f"{user.first_name} {user.last_name}",
                "action_url": login_url,
            },
        )

        try:
            await self.provider.send_email(
                to_email=user.email,
                subject="Welcome to School ERP SaaS!",
                html_content=html_content,
                text_content=text_content,
            )
        except Exception as exc:
            logger.error(f"Failed to send welcome email to {user.email}: {exc}")

        return user

    async def _check_rate_limit(self, user_id: uuid.UUID) -> None:
        """Enforces a cooldown period between token resend requests."""
        stmt = (
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id)
            .order_by(EmailVerificationToken.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        last_token = res.scalar_one_or_none()

        if last_token:
            elapsed = (datetime.now(timezone.utc) - last_token.created_at).total_seconds()
            if elapsed < settings.EMAIL_RATE_LIMIT_SECONDS:
                remaining = int(settings.EMAIL_RATE_LIMIT_SECONDS - elapsed)
                raise EmailRateLimitException(
                    f"Please wait {remaining} seconds before requesting another verification email."
                )
