from pydantic import BaseModel, Field


class TokenPayloadSchema(BaseModel):
    """Schema representing claims parsed from decoded JSON Web Tokens."""

    sub: str = Field(
        ..., description="Subject identity value associated with the session."
    )
    exp: int = Field(..., description="Expiration timestamp (seconds since epoch).")
    iat: int = Field(..., description="Issued-at timestamp (seconds since epoch).")
    type: str = Field(
        ..., description="Token classification type ('access' or 'refresh')."
    )


class AccessTokenSchema(BaseModel):
    """Schema representing a single Access Token payload."""

    token: str = Field(..., description="Signed access JWT token string.")
    token_type: str = Field(
        "bearer", description="Token transport authorization scheme."
    )


class RefreshTokenSchema(BaseModel):
    """Schema representing a single Refresh Token payload."""

    token: str = Field(..., description="Signed refresh JWT token string.")


class TokenRefreshRequest(BaseModel):
    """Schema representing variables required to request a token rotation."""

    refresh_token: str = Field(..., description="Active signed refresh JWT token.")


class TokenRefreshResponse(BaseModel):
    """Schema representing standard output from a successful token rotation."""

    access_token: str = Field(..., description="New signed JSON Web Access Token.")
    refresh_token: str = Field(..., description="New signed JSON Web Refresh Token.")
    token_type: str = Field(
        "bearer", description="Token transport authorization scheme."
    )
    expires_in: int = Field(..., description="New Access Token lifetime in seconds.")


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh actions."""

    refresh_token: str = Field(..., description="Active signed refresh JWT token.")


class RefreshTokenResponse(BaseModel):
    """Response schema for token refresh actions, returning a renewed access token."""

    access_token: str = Field(..., description="New signed JSON Web Access Token.")
    refresh_token: str = Field(..., description="New signed JSON Web Refresh Token.")
    token_type: str = Field(
        "bearer", description="Token transport authorization scheme."
    )
    expires_in: int = Field(..., description="New Access Token lifetime in seconds.")
