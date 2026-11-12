from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid
import secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import jwt

from app.models.user import User
from app.models.assignment import DeliveryAssignment
from app.models.revoked_token import RevokedToken
from app.models.enums import UserRole, AssignmentStatus
from app.core.security import get_password_hash, decode_token
from app.core.config import settings
from app.schemas.user import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeWorkloadResponse,
    EmployeeInviteResponse,
    AcceptInviteRequest,
    EmployeeDashboardResponse
)

ROLE_RANK = {
    UserRole.SUPER_ADMIN: 4,
    UserRole.ORG_ADMIN: 3,
    UserRole.BRANCH_MANAGER: 2,
    UserRole.DELIVERY_AGENT: 1,
    UserRole.CUSTOMER: 0,
}


class EmployeeService:
    @staticmethod
    def create_employee(db: Session, current_user: User, data: EmployeeCreate) -> User:
        caller_rank = ROLE_RANK.get(current_user.role, 0)
        target_rank = ROLE_RANK.get(data.role, 0)

        # Acceptance: Only an authorized role can assign roles, and never above or equal to its own privilege level
        if current_user.role != UserRole.SUPER_ADMIN and target_rank >= caller_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Privilege ceiling violation: Role '{current_user.role.value}' cannot assign role '{data.role.value}'"
            )

        org_id = current_user.organization_id if current_user.role != UserRole.SUPER_ADMIN else (data.organization_id or 1)

        # Branch managers can only add delivery agents to their own branch
        if current_user.role == UserRole.BRANCH_MANAGER:
            if data.role != UserRole.DELIVERY_AGENT:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Branch Managers can only onboard Delivery Agents"
                )
            data.branch_id = current_user.branch_id

        clean_email = data.email.strip().lower()
        existing = db.query(User).filter(User.email == clean_email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )

        raw_password = data.password or secrets.token_urlsafe(16)

        new_emp = User(
            email=clean_email,
            hashed_password=get_password_hash(raw_password),
            full_name=data.full_name.strip(),
            phone=data.phone.strip() if data.phone else None,
            role=data.role,
            organization_id=org_id,
            branch_id=data.branch_id,
            is_active=True
        )
        db.add(new_emp)
        db.commit()
        db.refresh(new_emp)
        return new_emp

    @staticmethod
    def list_employees(
        db: Session,
        current_user: User,
        branch_id: Optional[int] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None
    ) -> List[User]:
        query = db.query(User).filter(
            User.role.in_([UserRole.ORG_ADMIN, UserRole.BRANCH_MANAGER, UserRole.DELIVERY_AGENT])
        )

        if current_user.role != UserRole.SUPER_ADMIN:
            query = query.filter(User.organization_id == current_user.organization_id)

        if current_user.role == UserRole.BRANCH_MANAGER:
            query = query.filter(User.branch_id == current_user.branch_id)
        elif branch_id:
            query = query.filter(User.branch_id == branch_id)

        if role:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        return query.order_by(User.full_name.asc()).all()

    @staticmethod
    def get_employee(db: Session, current_user: User, employee_id: int) -> User:
        emp = db.query(User).filter(User.id == employee_id).first()
        if not emp or emp.role == UserRole.CUSTOMER:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

        if current_user.role != UserRole.SUPER_ADMIN and emp.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

        if current_user.role == UserRole.BRANCH_MANAGER and emp.branch_id != current_user.branch_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

        return emp

    @staticmethod
    def update_employee(db: Session, current_user: User, employee_id: int, data: EmployeeUpdate) -> User:
        emp = EmployeeService.get_employee(db, current_user, employee_id)
        caller_rank = ROLE_RANK.get(current_user.role, 0)
        target_current_rank = ROLE_RANK.get(emp.role, 0)

        # Cannot modify an employee whose current role is equal or higher (except Super Admin)
        if current_user.role != UserRole.SUPER_ADMIN and target_current_rank >= caller_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Privilege ceiling violation: Cannot modify employee with role '{emp.role.value}'"
            )

        # Cannot elevate an employee to a role equal or higher than caller
        if data.role is not None:
            new_rank = ROLE_RANK.get(data.role, 0)
            if current_user.role != UserRole.SUPER_ADMIN and new_rank >= caller_rank:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Privilege ceiling violation: Role '{current_user.role.value}' cannot assign role '{data.role.value}'"
                )

        # If deactivating, employee is locked out immediately
        if data.is_active is False:
            emp.is_active = False

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(emp, key, value)

        db.commit()
        db.refresh(emp)
        return emp

    @staticmethod
    def create_employee_invite(db: Session, current_user: User, employee_id: int) -> EmployeeInviteResponse:
        """
        Generates a one-time cryptographic invitation link for secure credential provisioning.
        No plaintext password is created, displayed, or emailed.
        """
        emp = EmployeeService.get_employee(db, current_user, employee_id)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=24)
        jti = uuid.uuid4().hex

        payload = {
            "sub": str(emp.id),
            "email": emp.email,
            "type": "invite",
            "jti": jti,
            "exp": int(expires_at.timestamp())
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        return EmployeeInviteResponse(
            employee_id=emp.id,
            email=emp.email,
            invite_token=token,
            invite_url=f"/set-password?token={token}",
            expires_at=expires_at,
            message="One-time invitation token generated. Send this link to the employee to set their credentials."
        )

    @staticmethod
    def accept_employee_invite(db: Session, req: AcceptInviteRequest) -> dict:
        """
        Validates the one-time invite token, sets employee password, and blacklists the token.
        """
        try:
            payload = decode_token(req.invite_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invitation token"
            )

        if payload.get("type") != "invite":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token is not an invitation token"
            )

        jti = payload.get("jti")
        if jti:
            revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
            if revoked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invitation link has already been used"
                )

        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee account not found or deactivated"
            )

        user.hashed_password = get_password_hash(req.new_password)

        # Single-use enforcement: blacklist token jti
        if jti:
            exp = payload.get("exp")
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(days=1)
            revoked_record = RevokedToken(
                jti=jti,
                token_type="invite",
                user_id=user.id,
                expires_at=expires_at,
                revocation_reason="Invite accepted and consumed"
            )
            db.add(revoked_record)

        db.commit()
        return {"message": "Password configured successfully. You may now sign in."}

    @staticmethod
    def get_employee_workload(db: Session, current_user: User, employee_id: int) -> EmployeeWorkloadResponse:
        emp = EmployeeService.get_employee(db, current_user, employee_id)

        active_count = db.query(DeliveryAssignment).filter(
            DeliveryAssignment.employee_id == employee_id,
            DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
        ).count()

        completed_count = db.query(DeliveryAssignment).filter(
            DeliveryAssignment.employee_id == employee_id,
            DeliveryAssignment.status == AssignmentStatus.COMPLETED
        ).count()

        return EmployeeWorkloadResponse(
            employee_id=emp.id,
            full_name=emp.full_name,
            role=emp.role,
            active_assignments_count=active_count,
            completed_assignments_count=completed_count
        )

    @staticmethod
    def get_employee_dashboard(db: Session, current_user: User, employee_id: int) -> EmployeeDashboardResponse:
        emp = EmployeeService.get_employee(db, current_user, employee_id)

        active_count = db.query(DeliveryAssignment).filter(
            DeliveryAssignment.employee_id == employee_id,
            DeliveryAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
        ).count()

        completed_count = db.query(DeliveryAssignment).filter(
            DeliveryAssignment.employee_id == employee_id,
            DeliveryAssignment.status == AssignmentStatus.COMPLETED
        ).count()

        failed_count = db.query(DeliveryAssignment).filter(
            DeliveryAssignment.employee_id == employee_id,
            DeliveryAssignment.status == AssignmentStatus.FAILED
        ).count()

        return EmployeeDashboardResponse(
            employee_id=emp.id,
            full_name=emp.full_name,
            email=emp.email,
            role=emp.role,
            branch_id=emp.branch_id,
            is_active=emp.is_active,
            active_assignments_count=active_count,
            completed_assignments_count=completed_count,
            failed_assignments_count=failed_count
        )
