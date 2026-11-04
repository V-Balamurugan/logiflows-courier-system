from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterCustomerRequest,
    TokenRefreshRequest,
    PasswordChangeRequest,
    LogoutRequest,
    Token
)
from app.schemas.user import UserResponse
from app.models.user import User
from app.services.auth_service import AuthService
from app.dependencies.auth_deps import get_current_user, get_current_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterCustomerRequest, db: Session = Depends(get_db)):
    """Registers a new Customer account."""
    return AuthService.register_customer(db, req)


@router.post("/login", response_model=Token)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates credentials and returns JWT access and refresh tokens."""
    return AuthService.login(db, req)


@router.post("/refresh", response_model=Token)
def refresh_token(req: TokenRefreshRequest, db: Session = Depends(get_db)):
    """Exchanges a valid refresh token for a new access token (with refresh token rotation)."""
    return AuthService.refresh_access_token(db, req.refresh_token)


@router.post("/logout")
def logout(
    req: Optional[LogoutRequest] = None,
    current_token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revokes the current access token and optional refresh token."""
    refresh_tok = req.refresh_token if req else None
    AuthService.logout(db, access_token=current_token, user=current_user, refresh_token=refresh_tok)
    return {"message": "Logged out successfully; token revoked"}


@router.get("/me", response_model=UserResponse)
def get_current_profile(current_user: User = Depends(get_current_user)):
    """Returns profile details of the authenticated user."""
    return current_user


@router.put("/change-password")
def change_password(
    req: PasswordChangeRequest,
    current_token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Changes current user password after verifying current credentials and revokes current token."""
    AuthService.change_password(db, current_user, req, current_token=current_token)
    return {"message": "Password updated successfully"}

