from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.user import User
from app.models.assignment import DeliveryAssignment
from app.models.enums import UserRole, AssignmentStatus
from app.core.security import get_password_hash
from app.schemas.user import EmployeeCreate, EmployeeUpdate, EmployeeWorkloadResponse


class EmployeeService:
    @staticmethod
    def create_employee(db: Session, current_user: User, data: EmployeeCreate) -> User:
        org_id = current_user.organization_id if current_user.role != UserRole.SUPER_ADMIN else (data.organization_id or 1)
        
        # Branch managers can only add delivery agents to their own branch
        if current_user.role == UserRole.BRANCH_MANAGER:
            if data.role != UserRole.DELIVERY_AGENT:
                raise HTTPException(status_code=403, detail="Branch Managers can only onboard Delivery Agents")
            data.branch_id = current_user.branch_id

        existing = db.query(User).filter(User.email == data.email.lower()).first()
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        new_emp = User(
            email=data.email.lower(),
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
            phone=data.phone,
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
            raise HTTPException(status_code=404, detail="Employee not found")

        if current_user.role != UserRole.SUPER_ADMIN and emp.organization_id != current_user.organization_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        if current_user.role == UserRole.BRANCH_MANAGER and emp.branch_id != current_user.branch_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        return emp

    @staticmethod
    def update_employee(db: Session, current_user: User, employee_id: int, data: EmployeeUpdate) -> User:
        emp = EmployeeService.get_employee(db, current_user, employee_id)

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(emp, key, value)

        db.commit()
        db.refresh(emp)
        return emp

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

