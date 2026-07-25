"""
Email Verification & Account Recovery Integration Tests — Phase 3 Step 11.
"""

import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.models.email_verification_token import EmailVerificationToken
from app.repositories.user_repository import UserRepository
from app.modules.auth.email.exceptions import (
    InvalidVerificationTokenException,
    ExpiredVerificationTokenException,
    EmailRateLimitException,
    AccountAlreadyVerifiedException,
)
from app.modules.auth.email.providers import MockEmailProvider, ConsoleProvider
from app.modules.auth.email.service import EmailVerificationService


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def test_user():
    """Seeds a temporary user record for integration tests."""
    async with AsyncSessionLocal() as session:
        # Fetch school and role
        school_stmt = select(School).limit(1)
        school_res = await session.execute(school_stmt)
        school = school_res.scalar_one()

        role_stmt = select(Role).where(Role.code == "STUDENT")
        role_res = await session.execute(role_stmt)
        role = role_res.scalar_one()

        email = f"email_test_{uuid.uuid4().hex[:8]}@demoschool.edu"
        username = f"emailtest_{uuid.uuid4().hex[:8]}"

        user = User(
            first_name="Email",
            last_name="Tester",
            username=username,
            email=email,
            password_hash=hash_password("ValidSecret123!"),
            school_id=school.id,
            role_id=role.id,
            status="inactive",
            email_verified=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    yield {
        "id": user.id,
        "email": email,
        "username": username,
    }

    # Cleanup after test runs
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user.id)
        res = await session.execute(stmt)
        u = res.scalar_one_or_none()
        if u:
            await session.delete(u)
            await session.commit()


@pytest.mark.asyncio
async def test_send_verification_email_success(test_user):
    """Verifies that requesting a verification email generates token and dispatches email via provider."""
    async with AsyncSessionLocal() as session:
        service = EmailVerificationService(session)
        
        # Inject mock provider
        mock_provider = MockEmailProvider()
        service.provider = mock_provider

        # 1. Send verification email
        await service.send_verification_email(test_user["email"])

        # 2. Check token generated in database
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == test_user["id"]
        )
        res = await session.execute(stmt)
        tokens = res.scalars().all()
        assert len(tokens) == 1
        assert tokens[0].used is False
        assert tokens[0].expires_at > datetime.now(timezone.utc)

        # 3. Check mock provider received the email dispatch
        assert len(mock_provider.sent_emails) == 1
        sent = mock_provider.sent_emails[0]
        assert sent["to_email"] == test_user["email"]
        assert "Activate Your School ERP" in sent["subject"]
        assert "verify-email?token=" in sent["html_content"]


@pytest.mark.asyncio
async def test_verify_email_success_activates_account(test_user):
    """Verifies that validating a correct token activates the user and sends welcome email."""
    async with AsyncSessionLocal() as session:
        service = EmailVerificationService(session)
        mock_provider = MockEmailProvider()
        service.provider = mock_provider

        # 1. Generate token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
        token_record = EmailVerificationToken(
            user_id=test_user["id"],
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        session.add(token_record)
        await session.commit()

        # Clear provider mock list (since we just created the token manually)
        mock_provider.sent_emails.clear()

        # 2. Verify token
        activated_user = await service.verify_email_token(raw_token)
        assert activated_user.email_verified is True
        assert activated_user.is_active is True
        assert activated_user.status == "active"

        # 3. Confirm welcome email sent
        assert len(mock_provider.sent_emails) == 1
        assert "Welcome to School ERP SaaS" in mock_provider.sent_emails[0]["subject"]

        # 4. Re-query token from DB and verify it is marked used
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
        res = await session.execute(stmt)
        tok = res.scalar_one()
        assert tok.used is True


@pytest.mark.asyncio
async def test_verify_email_invalid_token():
    """Verifies that an incorrect/unknown token throws InvalidVerificationTokenException."""
    async with AsyncSessionLocal() as session:
        service = EmailVerificationService(session)

        with pytest.raises(InvalidVerificationTokenException):
            await service.verify_email_token("not_a_valid_token_string")


@pytest.mark.asyncio
async def test_verify_email_expired_token(test_user):
    """Verifies that expired verification tokens are rejected."""
    async with AsyncSessionLocal() as session:
        service = EmailVerificationService(session)

        # 1. Generate expired token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        token_record = EmailVerificationToken(
            user_id=test_user["id"],
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        session.add(token_record)
        await session.commit()

        # 2. Verify token
        with pytest.raises(ExpiredVerificationTokenException):
            await service.verify_email_token(raw_token)


@pytest.mark.asyncio
async def test_replay_attack_prevention(test_user):
    """Verifies that a verification token cannot be used twice."""
    async with AsyncSessionLocal() as session:
        service = EmailVerificationService(session)

        # 1. Generate token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
        token_record = EmailVerificationToken(
            user_id=test_user["id"],
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        session.add(token_record)
        await session.commit()

        # 2. First verify -> Success
        await service.verify_email_token(raw_token)

        # 3. Second verify -> Fails as Invalid (since used=True)
        with pytest.raises(InvalidVerificationTokenException):
            await service.verify_email_token(raw_token)


@pytest.mark.asyncio
async def test_rate_limiting_enforcement(test_user):
    """Verifies that consecutive email requests within cooldown period are blocked."""
    async with AsyncSessionLocal() as session:
        service = EmailVerificationService(session)
        service.provider = MockEmailProvider()

        # 1. Send first email -> Success
        await service.send_verification_email(test_user["email"])

        # 2. Immediately send second email -> Throws rate limit exception
        with pytest.raises(EmailRateLimitException):
            await service.send_verification_email(test_user["email"])


@pytest.mark.asyncio
async def test_console_provider_integration(test_user):
    """Verifies that the Console email provider doesn't raise any runtime exceptions."""
    async with AsyncSessionLocal() as session:
        service = EmailVerificationService(session)
        service.provider = ConsoleProvider()
        # Should execute successfully without errors
        await service.send_verification_email(test_user["email"])
