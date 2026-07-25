from pydantic import BaseModel, Field


class TokenPayload(BaseModel):
    """Schema representing validated claims decoded from a JWT payload."""

    sub: str = Field(..., description="Subject identifier (e.g. User ID)")
    exp: int = Field(..., description="Expiration timestamp (seconds since epoch)")
    iat: int = Field(..., description="Issued-at timestamp (seconds since epoch)")
    type: str = Field(
        ..., description="Token classification type ('access' or 'refresh')"
    )


class AccessToken(BaseModel):
    """Schema representing a single Access Token payload."""

    token: str = Field(..., description="Cryptographically signed access token string")
    token_type: str = Field(
        "bearer", description="Token transport authorization scheme"
    )


class RefreshToken(BaseModel):
    """Schema representing a single Refresh Token payload."""

    token: str = Field(..., description="Cryptographically signed refresh token string")


class TokenResponse(BaseModel):
    """Schema representing a standardized login or refresh response payload."""

    access_token: str = Field(..., description="Signed JSON Web Access Token")
    refresh_token: str = Field(..., description="Signed JSON Web Refresh Token")
    token_type: str = Field("bearer", description="Token authorization type")
    expires_in: int = Field(
        ..., description="Access token duration lifespan in seconds"
    )
