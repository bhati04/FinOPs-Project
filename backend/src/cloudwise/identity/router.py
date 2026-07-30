"""Identity HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from cloudwise.identity.dependencies import CurrentUser, get_identity_service
from cloudwise.identity.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from cloudwise.identity.service import (
    AuthenticationError,
    IdentityService,
    RegistrationConflictError,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    service: Annotated[IdentityService, Depends(get_identity_service)],
) -> TokenResponse:
    """Register a user as owner of a new organization."""
    try:
        return await service.register(request)
    except RegistrationConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    service: Annotated[IdentityService, Depends(get_identity_service)],
) -> TokenResponse:
    """Authenticate with a generic failure response."""
    try:
        return await service.login(request.email, request.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        ) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    service: Annotated[IdentityService, Depends(get_identity_service)],
) -> TokenResponse:
    """Rotate a refresh token."""
    try:
        return await service.refresh(request.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    service: Annotated[IdentityService, Depends(get_identity_service)],
) -> Response:
    """Revoke a refresh session."""
    await service.logout(request.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: CurrentUser) -> CurrentUserResponse:
    """Return the authenticated tenant context."""
    return CurrentUserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        organization_id=current_user.organization_id,
        organization_name=current_user.organization_name,
        role=current_user.role,
    )
