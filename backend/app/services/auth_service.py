from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import jwt

from app.models.user import User, CustomerProfile
from app.models.revoked_token import RevokedToken
from app.models.enums import UserRole
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.schemas.auth import (
    LoginRequest,
    RegisterCustomerRequest,
    PasswordChangeRequest,
    LogoutRequest,
    Token
)


class AuthService:
    @staticmethod
    def register_customer(db: Session, req: RegisterCustomerRequest) -> User:
        # Check if email is already taken
        existing = db.query(User).filter(User.email == req.email.lower()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists"
            )

        hashed_password = get_password_hash(req.password)
        new_user = User(
            email=req.email.lower(),
            hashed_password=hashed_password,
            full_name=req.full_name,
            phone=req.phone,
            role=UserRole.CUSTOMER,
            is_active=True
        )
        db.add(new_user)
        db.flush()

        profile = CustomerProfile(
            user_id=new_user.id,
            company_name=req.company_name,
            gst_number=req.gst_number,
            default_pickup_address=req.default_address,
            default_delivery_address=req.default_address
        )
        db.add(profile)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def login(db: Session, req: LoginRequest) -> Token:
        user = db.query(User).filter(User.email == req.email.lower()).first()
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"}
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated"
            )

        access_token = create_access_token(subject=user.id, role=user.role.value)
        refresh_token = create_refresh_token(subject=user.id)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organization_id=user.organization_id,
            branch_id=user.branch_id
        )

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> Token:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token type")
            user_id = int(payload.get("sub"))
            jti = payload.get("jti")
            exp = payload.get("exp")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

        # Check if refresh token was already revoked / rotated
        if jti:
            revoked_record = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
            if revoked_record:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has already been used or revoked"
                )

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

        # Rotate refresh token: revoke the old one
        if jti:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(days=7)
            revoked = RevokedToken(
                jti=jti,
                token_type="refresh",
                user_id=user.id,
                expires_at=expires_at,
                revocation_reason="rotation"
            )
            db.add(revoked)

        new_access_token = create_access_token(subject=user.id, role=user.role.value)
        new_refresh_token = create_refresh_token(subject=user.id)
        db.commit()

        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organization_id=user.organization_id,
            branch_id=user.branch_id
        )

    @staticmethod
    def logout(
        db: Session,
        access_token: str,
        user: User,
        refresh_token: Optional[str] = None
    ) -> bool:
        """Revokes the current access token and optional refresh token."""
        try:
            payload = decode_token(access_token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(minutes=15)
                db.add(RevokedToken(
                    jti=jti,
                    token_type="access",
                    user_id=user.id,
                    expires_at=expires_at,
                    revocation_reason="logout"
                ))
        except Exception:
            pass

        if refresh_token:
            try:
                r_payload = decode_token(refresh_token)
                r_jti = r_payload.get("jti")
                r_exp = r_payload.get("exp")
                if r_jti:
                    r_expires_at = datetime.fromtimestamp(r_exp, tz=timezone.utc) if r_exp else datetime.now(timezone.utc) + timedelta(days=7)
                    db.add(RevokedToken(
                        jti=r_jti,
                        token_type="refresh",
                        user_id=user.id,
                        expires_at=r_expires_at,
                        revocation_reason="logout"
                    ))
            except Exception:
                pass

        db.commit()
        return True

    @staticmethod
    def change_password(
        db: Session,
        user: User,
        req: PasswordChangeRequest,
        current_token: Optional[str] = None
    ) -> bool:
        if not verify_password(req.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is not correct")
        user.hashed_password = get_password_hash(req.new_password)

        if current_token:
            try:
                payload = decode_token(current_token)
                jti = payload.get("jti")
                exp = payload.get("exp")
                if jti:
                    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(minutes=15)
                    db.add(RevokedToken(
                        jti=jti,
                        token_type="access",
                        user_id=user.id,
                        expires_at=expires_at,
                        revocation_reason="password_change"
                    ))
            except Exception:
                pass

        db.commit()
        return True

