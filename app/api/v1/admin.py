from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.db.models import User, TreatmentRecord, AuditLog
from app.core.dependencies import get_current_user
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

# Dependency: Only allow users with role="admin"
async def get_current_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required."
        )
    return current_user

@router.get("/treatments", response_model=list)
async def list_treatments(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List all treatment records (admin only)."""
    result = await db.execute(select(TreatmentRecord))
    return result.scalars().all()

@router.post("/treatments", status_code=201)
async def create_treatment(
    treatment_data: dict,  
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create new expert-verified treatment (admin only)."""
    new_treatment = TreatmentRecord(**treatment_data)
    db.add(new_treatment)
    await db.commit()
    await db.refresh(new_treatment)
    return new_treatment

@router.get("/audit-logs")
async def view_audit_logs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """View recent audit logs (admin only)."""
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()