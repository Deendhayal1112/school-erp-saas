from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.schemas.response import SuccessResponse
from app.services.authentication_service import AuthenticationService

router = APIRouter()


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthenticationService:
    """Dependency helper injecting AuthenticationService instances into endpoints."""
    repo = UserRepository(db)
    return AuthenticationService(repo)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user login credentials",
    description="Validates email/password credentials and issues short-lived Access and long-lived Refresh JWTs.",
    responses={
        200: {"description": "Authentication successful. Tokens returned."},
        401: {"description": "Invalid credentials or deactivated account."},
        422: {"description": "Validation error on credentials structure."},
    },
)
async def login(
    request_data: LoginRequest,
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> LoginResponse:
    auth_data = await auth_service.authenticate_user(
        request_data.email, request_data.password
    )
    return LoginResponse(**auth_data)


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh expiring Access Tokens",
    description="Validates a cryptographic Refresh Token signature and issues a renewed Access and rotated Refresh Token set.",
    responses={
        200: {"description": "Token rotation successful. New tokens issued."},
        401: {"description": "Expired or malformed refresh token signature."},
        422: {"description": "Validation error on token schema format."},
    },
)
async def refresh(
    request_data: RefreshTokenRequest,
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> RefreshTokenResponse:
    refresh_data = await auth_service.refresh_access_token(request_data.refresh_token)
    return RefreshTokenResponse(**refresh_data)


@router.post(
    "/logout",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Terminate active session",
    description="Logs out the currently active authenticated user and schedules session cleanup operations.",
    responses={
        200: {"description": "Session terminated successfully."},
        401: {"description": "Not authenticated. Missing or invalid Bearer token."},
    },
)
async def logout(
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthenticationService = Depends(get_auth_service),
) -> SuccessResponse[None]:
    await auth_service.logout_user(current_user.id)
    return SuccessResponse[None](message="Successfully logged out.")


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current user profile",
    description="Returns metadata profiles and tenant school descriptors for the active authenticated user.",
    responses={
        200: {"description": "User profile resolved successfully."},
        401: {"description": "Not authenticated. Missing or invalid Bearer token."},
        403: {"description": "Deactivated account or deactivated school system."},
    },
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> CurrentUserResponse:
    full_name = f"{current_user.first_name} {current_user.last_name}".strip()
    return CurrentUserResponse(
        id=current_user.id,
        school_id=current_user.school_id,
        email=current_user.email,
        full_name=full_name,
        role=current_user.role.code,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )
