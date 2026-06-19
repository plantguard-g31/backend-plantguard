from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import json

from app.db.base import get_db
from app.db.models import User, TreatmentRecord, AuditLog
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])

# Dependency: Only allow users with role="admin"
async def get_current_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user

# Helper function to log admin actions to AUDIT_LOGS (FR-22)
async def log_admin_action(db: AsyncSession, admin_id: str, event_type: str, target_id: str, changed_fields: dict):
    log_entry = AuditLog(
        user_id=admin_id,
        event_type=event_type,
        endpoint="/api/v1/admin",
        additional_data={"target_id": target_id, "changed_fields": changed_fields}
    )
    db.add(log_entry)
    await db.commit()

# --- TREATMENT MANAGEMENT (FR-22) ---

@router.get("/treatments")
async def list_treatments(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """List all treatment records (including soft-deleted ones for admin view)."""
    result = await db.execute(select(TreatmentRecord))
    return result.scalars().all()

@router.post("/treatments", status_code=201)
async def create_treatment(treatment_data: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Create new expert-verified treatment."""
    new_treatment = TreatmentRecord(**treatment_data)
    db.add(new_treatment)
    await db.commit()
    await db.refresh(new_treatment)
    await log_admin_action(db, str(admin.id), "admin_create_treatment", str(new_treatment.id), treatment_data)
    return new_treatment

@router.put("/treatments/{treatment_id}")
async def update_treatment(treatment_id: str, update_data: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Update an existing treatment record."""
    result = await db.execute(select(TreatmentRecord).where(TreatmentRecord.id == treatment_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    for key, value in update_data.items():
        setattr(record, key, value)
        
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_update_treatment", treatment_id, update_data)
    return {"message": "Treatment updated successfully"}

@router.delete("/treatments/{treatment_id}")
async def delete_treatment(treatment_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Soft-delete a treatment record (FR-22: sets is_active=FALSE)."""
    result = await db.execute(select(TreatmentRecord).where(TreatmentRecord.id == treatment_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    record.is_active = False
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_delete_treatment", treatment_id, {"is_active": False})
    return {"message": "Treatment soft-deleted successfully"}

# --- USER MANAGEMENT (FR-22b) ---

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """List all user accounts with their active status."""
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [{"id": str(u.id), "name": u.name, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]

@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
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
async def reactivate_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Reactivate a deactivated farmer account (FR-22b)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = True
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_reactivate_user", user_id, {"is_active": True})
    return {"message": "User reactivated successfully"}

# --- AUDIT LOGS VIEWER (FR-09) ---

@router.get("/audit-logs")
async def view_audit_logs(limit: int = 50, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """View recent audit logs (immutable, admin only)."""
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit))
    return result.scalars().all()