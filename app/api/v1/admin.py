from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.db.base import get_db
from app.db.models import User, TreatmentRecord, AuditLog
from app.core.dependencies import get_current_user
from app.core.security import hash_password

router = APIRouter(prefix="/admin", tags=["Admin"])

# 1. DEPENDENCIES (Security Gates)

async def get_current_admin(current_user: User = Depends(get_current_user)):
    """Gate 1: Ensures the logged-in user has the 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin access required."
        )
    return current_user

async def get_super_admin(current_user: User = Depends(get_current_admin)):
    """Gate 2: Ensures the admin is a SUPER admin (can create other admins)."""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only the Super Admin can create new admin accounts."
        )
    return current_user


# 2. PYDANTIC SCHEMAS (Strict Validation)

class AdminCreateRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class TreatmentCreateRequest(BaseModel):
    disease_name: str
    crop_type: str
    severity_level: str
    pesticide_name: str
    dosage_mild: str
    dosage_moderate: str
    dosage_severe: str
    application_timing: str
    safety_instructions: str
    pre_harvest_interval_days: int
    source_reference: str

class TreatmentUpdateRequest(BaseModel):
    pesticide_name: Optional[str] = None
    dosage_mild: Optional[str] = None
    dosage_moderate: Optional[str] = None
    dosage_severe: Optional[str] = None
    application_timing: Optional[str] = None
    safety_instructions: Optional[str] = None
    pre_harvest_interval_days: Optional[int] = None
    is_active: Optional[bool] = None

# 3. HELPER FUNCTIONS

async def log_admin_action(db: AsyncSession, admin_id: str, event_type: str, target_id: str, changed_fields: dict):
    """Logs an admin action to the AUDIT_LOGS table immutably."""
    log_entry = AuditLog(
        user_id=admin_id,
        event_type=event_type,
        endpoint="/api/v1/admin",
        additional_data={"target_id": target_id, "changed_fields": changed_fields}
    )
    db.add(log_entry)
    await db.commit()

# 4. ADMIN HIERARCHY (Super Admin Only)

@router.post("/create-admin", status_code=status.HTTP_201_CREATED)
async def create_new_admin(
    admin_data: AdminCreateRequest, 
    db: AsyncSession = Depends(get_db), 
    super_admin: User = Depends(get_super_admin) # <-- Protected by Super Admin gate
):
    """
    Creates a new Regular Admin account. 
    Only accessible if the requester is a Super Admin.
    """
    # 1. Check if email already exists
    result = await db.execute(select(User).where(User.email == admin_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    # 2. Hash the password
    hashed_pw = hash_password(admin_data.password)

    # 3. Create the new admin (Notice: is_super_admin is FALSE by default)
    new_admin = User(
        name=admin_data.name,
        email=admin_data.email,
        password_hash=hashed_pw,
        role="admin",
        is_super_admin=False  # <-- CRITICAL: New admins are never Super Admins
    )
    
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)

    # 4. Log the action to Audit Logs
    await log_admin_action(
        db, 
        str(super_admin.id), 
        "admin_create_admin", 
        str(new_admin.id), 
        {"new_admin_email": new_admin.email}
    )

    return {
        "message": "Admin account created successfully.",
        "admin_id": str(new_admin.id),
        "email": new_admin.email,
        "is_super_admin": False
    }

# 5. TREATMENT MANAGEMENT (Any Admin)

@router.get("/treatments")
async def list_treatments(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """List all treatment records (including soft-deleted ones for admin view)."""
    result = await db.execute(select(TreatmentRecord))
    return result.scalars().all()

@router.post("/treatments", status_code=status.HTTP_201_CREATED)
async def create_treatment(
    data: TreatmentCreateRequest, # <-- STRICT SCHEMA (No more raw dict)
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Create new expert-verified treatment."""
    new_treatment = TreatmentRecord(**data.model_dump(), is_active=True)
    db.add(new_treatment)
    await db.commit()
    await db.refresh(new_treatment)
    
    await log_admin_action(db, str(admin.id), "admin_create_treatment", str(new_treatment.id), data.model_dump())
    return new_treatment

@router.put("/treatments/{treatment_id}")
async def update_treatment(
    treatment_id: str, 
    data: TreatmentUpdateRequest, # <-- STRICT SCHEMA (No more raw dict)
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Update an existing treatment record."""
    result = await db.execute(select(TreatmentRecord).where(TreatmentRecord.id == treatment_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    # Only update fields that were actually provided in the request
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
        
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_update_treatment", treatment_id, update_data)
    return {"message": "Treatment updated successfully"}

@router.delete("/treatments/{treatment_id}")
async def delete_treatment(
    treatment_id: str, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Soft-delete a treatment record (FR-22: sets is_active=FALSE)."""
    result = await db.execute(select(TreatmentRecord).where(TreatmentRecord.id == treatment_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    record.is_active = False
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_delete_treatment", treatment_id, {"is_active": False})
    return {"message": "Treatment soft-deleted successfully"}

# 6. USER MANAGEMENT (Any Admin)

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """List all user accounts with their active status and super admin flag."""
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id), 
            "name": u.name, 
            "email": u.email, 
            "role": u.role, 
            "is_active": u.is_active,
            "is_super_admin": u.is_super_admin # <-- Added for frontend visibility
        } 
        for u in users
    ]

@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Deactivate a farmer account (FR-22b)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Cannot deactivate an admin account")
        
    user.is_active = False
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_deactivate_user", user_id, {"is_active": False})
    return {"message": "User deactivated successfully"}

@router.patch("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Reactivate a deactivated farmer account (FR-22b)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = True
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_reactivate_user", user_id, {"is_active": True})
    return {"message": "User reactivated successfully"}

# 7. AUDIT LOGS VIEWER (Any Admin)

@router.get("/audit-logs")
async def view_audit_logs(
    limit: int = 50, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """View recent audit logs (immutable, admin only)."""
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit))
    return result.scalars().all()