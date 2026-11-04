from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.database.session import get_db
from app.core.config import settings
from app.core.security import decode_token
from app.models.user import User
from app.models.branch import Branch
from app.models.parcel import Parcel
from app.models.vehicle import Vehicle
from app.models.revoked_token import RevokedToken
from app.models.enums import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_current_token(token: str = Depends(oauth2_scheme)) -> str:
    """Returns raw JWT string from Authorization Bearer header."""
    return token


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        token_type = payload.get("type")
        if token_type != "access":
            raise credentials_exception
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
        jti = payload.get("jti")
    except jwt.PyJWTError:
        raise credentials_exception

    # Enforce revoked tokens check
    if jti:
        is_revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
        if is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"}
            )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


class RoleChecker:
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{user.role.value}'"
            )
        return user


# Common role dependencies
require_super_admin = RoleChecker([UserRole.SUPER_ADMIN])
require_org_admin = RoleChecker([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN])
require_branch_manager_or_higher = RoleChecker([
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.BRANCH_MANAGER
])
require_staff = RoleChecker([
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.DELIVERY_AGENT
])
require_customer = RoleChecker([UserRole.CUSTOMER])


# --- REUSABLE TENANT & BRANCH ISOLATION HELPERS ---

def get_tenant_organization_id(user: User) -> Optional[int]:
    """Returns the organization ID for tenant-scoped operations, or None for SUPER_ADMIN."""
    if user.role == UserRole.SUPER_ADMIN:
        return None
    return user.organization_id


def verify_branch_tenant(db: Session, current_user: User, branch_id: int) -> Branch:
    """
    Retrieves branch by ID, verifying tenant isolation.
    Returns 404 if not found or belongs to another organization (preventing existence leak).
    """
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    
    if current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.organization_id or branch.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
        if current_user.role in [UserRole.BRANCH_MANAGER, UserRole.DELIVERY_AGENT]:
            if current_user.branch_id and current_user.branch_id != branch.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


def verify_parcel_tenant(db: Session, current_user: User, tracking_number: str) -> Parcel:
    """
    Retrieves parcel by tracking number, enforcing role and tenant isolation.
    Returns 404 if not found or unauthorized (preventing existence leak).
    """
    parcel = db.query(Parcel).filter(Parcel.tracking_number == tracking_number).first()
    if not parcel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    if current_user.role == UserRole.SUPER_ADMIN:
        return parcel

    if current_user.role == UserRole.CUSTOMER:
        if parcel.customer_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
        return parcel

    # Staff roles: ORG_ADMIN, BRANCH_MANAGER, DELIVERY_AGENT
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    origin_org_id = parcel.origin_branch.organization_id if parcel.origin_branch else None
    dest_org_id = parcel.dest_branch.organization_id if parcel.dest_branch else None

    if origin_org_id != current_user.organization_id and dest_org_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    if current_user.role == UserRole.BRANCH_MANAGER:
        if current_user.branch_id and current_user.branch_id not in [parcel.origin_branch_id, parcel.dest_branch_id]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    return parcel


def verify_vehicle_tenant(db: Session, current_user: User, vehicle_id: int) -> Vehicle:
    """
    Retrieves vehicle by ID, enforcing tenant isolation.
    Returns 404 if not found or belongs to another organization.
    """
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    if current_user.role == UserRole.SUPER_ADMIN:
        return vehicle

    if not current_user.organization_id or vehicle.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
        if vehicle.branch_id and vehicle.branch_id != current_user.branch_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    return vehicle


def verify_employee_tenant(db: Session, current_user: User, employee_id: int) -> User:
    """
    Retrieves employee by ID, enforcing tenant isolation.
    Returns 404 if not found or belongs to another organization.
    """
    emp = db.query(User).filter(User.id == employee_id, User.role != UserRole.CUSTOMER).first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if current_user.role == UserRole.SUPER_ADMIN:
        return emp

    if not current_user.organization_id or emp.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if current_user.role == UserRole.BRANCH_MANAGER and current_user.branch_id:
        if emp.branch_id and emp.branch_id != current_user.branch_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    return emp
