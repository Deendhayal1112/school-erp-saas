"""
Email Verification REST Router.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.modules.auth.email.schemas import ResendVerificationRequest, VerifyEmailRequest
from app.modules.auth.email.service import EmailVerificationService
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/auth", tags=["Email Verification"])


async def get_email_service(
    db: AsyncSession = Depends(get_db),
) -> EmailVerificationService:
    """Dependency helper injecting EmailVerificationService instances into endpoints."""
    return EmailVerificationService(db)


@router.post(
    "/send-verification-email",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Request account verification email",
    description="Generates a secure verification link and mails it to the user. Always returns success to protect privacy.",
)
async def send_verification_email(
    request_data: ResendVerificationRequest,
    email_service: EmailVerificationService = Depends(get_email_service),
) -> SuccessResponse:
    await email_service.send_verification_email(request_data.email)
    return SuccessResponse(
        message="If your account is registered, a verification link has been sent to your email address."
    )


@router.post(
    "/verify-email",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify account registration token",
    description="Validates the verification token, activates the user account, and sends welcome confirmation.",
)
async def verify_email(
    request_data: VerifyEmailRequest,
    email_service: EmailVerificationService = Depends(get_email_service),
) -> SuccessResponse:
    await email_service.verify_email_token(request_data.token)
    return SuccessResponse(
        message="Your email address has been verified successfully. Your account is now active."
    )
