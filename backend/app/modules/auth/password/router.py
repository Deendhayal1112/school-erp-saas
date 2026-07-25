"""
Password Management REST Router.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.models.user import User
from app.modules.auth.password.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.modules.auth.password.service import PasswordService
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/auth", tags=["Password Management"])


async def get_password_service(db: AsyncSession = Depends(get_db)) -> PasswordService:
    """Dependency helper injecting PasswordService instances into endpoints."""
    return PasswordService(db)


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Change user password",
    description="Updates the authenticated user's password. Prevents reuse and invalidates current sessions.",
)
async def change_password(
    request_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    password_service: PasswordService = Depends(get_password_service),
) -> SuccessResponse:
    await password_service.change_password(
        user_id=current_user.id,
        current_password=request_data.current_password,
        new_password=request_data.new_password,
    )
    return SuccessResponse(message="Password changed successfully.")


@router.post(
    "/forgot-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a password reset link",
    description="Initiates the password recovery workflow. Never leaks whether an email address exists.",
)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    password_service: PasswordService = Depends(get_password_service),
) -> SuccessResponse:
    # Generates reset token silently (does not send emails in this step as per requirements)
    await password_service.generate_reset_token(request_data.email)
    # Always return standard success envelope to avoid email validation discovery
    return SuccessResponse(
        message="If your email is registered in our system, you will receive a password reset link shortly."
    )


@router.post(
    "/reset-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password using recovery token",
    description="Resets the password using a valid, unused cryptographic recovery token.",
)
async def reset_password(
    request_data: ResetPasswordRequest,
    password_service: PasswordService = Depends(get_password_service),
) -> SuccessResponse:
    await password_service.reset_password(
        raw_token=request_data.reset_token,
        new_password=request_data.new_password,
    )
    return SuccessResponse(message="Password has been reset successfully.")
