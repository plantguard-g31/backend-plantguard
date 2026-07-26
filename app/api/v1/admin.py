from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.db.base import get_db
from app.db.models import User, TreatmentRecord, TreatmentTranslation, AuditLog
from app.core.dependencies import get_current_user
from app.core.security import hash_password

router = APIRouter(prefix="/admin", tags=["Admin"])

# ==========================================
# 1. DEPENDENCIES (Security Gates)
# ==========================================
async def get_current_admin(current_user: User = Depends(get_current_user)):
    """Gate 1: Ensures the logged-in user has the 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user

async def get_super_admin(current_user: User = Depends(get_current_admin)):
    """Gate 2: Ensures the admin is a SUPER admin."""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the Super Admin can create new admin accounts.")
    return current_user

# ==========================================
# 2. PYDANTIC SCHEMAS (Bilingual Support)
# ==========================================
class AdminCreateRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class TreatmentCreateRequest(BaseModel):
    # --- English Fields (Required) ---
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
    
    # --- Nepali Fields (Optional for Admin UI) ---
    disease_name_ne: Optional[str] = None
    application_timing_ne: Optional[str] = None
    safety_instructions_ne: Optional[str] = None

class TreatmentUpdateRequest(BaseModel):
    # --- English Fields ---
    pesticide_name: Optional[str] = None
    dosage_mild: Optional[str] = None
    dosage_moderate: Optional[str] = None
    dosage_severe: Optional[str] = None
    application_timing: Optional[str] = None
    safety_instructions: Optional[str] = None
    pre_harvest_interval_days: Optional[int] = None
    is_active: Optional[bool] = None
    
    # --- Nepali Fields ---
    disease_name_ne: Optional[str] = None
    application_timing_ne: Optional[str] = None
    safety_instructions_ne: Optional[str] = None

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
async def log_admin_action(db: AsyncSession, admin_id: str, event_type: str, target_id: str, changed_fields: dict):
    log_entry = AuditLog(
        user_id=admin_id, event_type=event_type, endpoint="/api/v1/admin",
        additional_data={"target_id": target_id, "changed_fields": changed_fields}
    )
    db.add(log_entry)
    await db.commit()

# ==========================================
# 4. ADMIN HIERARCHY
# ==========================================
@router.post("/create-admin", status_code=status.HTTP_201_CREATED)
async def create_new_admin(
    admin_data: AdminCreateRequest, 
    db: AsyncSession = Depends(get_db), 
    super_admin: User = Depends(get_super_admin)
):
    result = await db.execute(select(User).where(User.email == admin_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    hashed_pw = hash_password(admin_data.password)
    new_admin = User(
        name=admin_data.name, email=admin_data.email, password_hash=hashed_pw,
        role="admin", is_super_admin=False
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    
    await log_admin_action(db, str(super_admin.id), "admin_create_admin", str(new_admin.id), {"new_admin_email": new_admin.email})
    return {"message": "Admin account created successfully.", "admin_id": str(new_admin.id), "email": new_admin.email, "is_super_admin": False}

# ==========================================
# 5. TREATMENT MANAGEMENT (BILINGUAL)
# ==========================================
@router.get("/treatments")
async def list_treatments(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """List all treatment records WITH their Nepali translations."""
    result = await db.execute(select(TreatmentRecord))
    treatments = result.scalars().all()
    
    response_list = []
    for t in treatments:
        # Fetch translation for this record
        trans_result = await db.execute(
            select(TreatmentTranslation).where(
                TreatmentTranslation.treatment_record_id == t.id,
                TreatmentTranslation.language_code == "ne"
            )
        )
        trans = trans_result.scalars().first()
        
        response_list.append({
            "id": str(t.id),
            "disease_name": t.disease_name,
            "crop_type": t.crop_type,
            "severity_level": t.severity_level,
            "pesticide_name": t.pesticide_name,
            "dosage_mild": t.dosage_mild,
            "dosage_moderate": t.dosage_moderate,
            "dosage_severe": t.dosage_severe,
            "application_timing": t.application_timing,
            "safety_instructions": t.safety_instructions,
            "pre_harvest_interval_days": t.pre_harvest_interval_days,
            "source_reference": t.source_reference,
            "is_active": t.is_active,
            # Add Nepali translations if they exist
            "translations": {
                "disease_name_ne": trans.disease_name_translated if trans else None,
                "application_timing_ne": trans.treatment_instructions_translated if trans else None,
                "safety_instructions_ne": trans.safety_warnings_translated if trans else None
            } if trans else None
        })
        
    return response_list

@router.post("/treatments", status_code=status.HTTP_201_CREATED)
async def create_treatment(
    data: TreatmentCreateRequest,
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Create new treatment in English AND Nepali (if provided)."""
    
    # 1. Separate English and Nepali data
    english_data = data.model_dump(exclude={"disease_name_ne", "application_timing_ne", "safety_instructions_ne"})
    
    # 2. Create English Record
    new_treatment = TreatmentRecord(**english_data, is_active=True)
    db.add(new_treatment)
    await db.flush() # Flush to get the new_treatment.id immediately
    
    # 3. Create Nepali Translation (if admin provided it)
    if data.disease_name_ne or data.application_timing_ne or data.safety_instructions_ne:
        translation = TreatmentTranslation(
            treatment_record_id=new_treatment.id,
            language_code="ne",
            disease_name_translated=data.disease_name_ne or data.disease_name, # Fallback to English if missing
            treatment_instructions_translated=data.application_timing_ne or data.application_timing,
            safety_warnings_translated=data.safety_instructions_ne or data.safety_instructions
        )
        db.add(translation)
        
    await db.commit()
    await db.refresh(new_treatment)
    
    await log_admin_action(db, str(admin.id), "admin_create_treatment", str(new_treatment.id), data.model_dump())
    return {"message": "Treatment created successfully (English + Nepali)", "treatment_id": str(new_treatment.id)}

@router.put("/treatments/{treatment_id}")
async def update_treatment(
    treatment_id: str,
    data: TreatmentUpdateRequest,
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Update English fields AND Nepali fields."""
    result = await db.execute(select(TreatmentRecord).where(TreatmentRecord.id == treatment_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    # 1. Update English Fields
    english_update = data.model_dump(exclude_unset=True, exclude={"disease_name_ne", "application_timing_ne", "safety_instructions_ne"})
    for key, value in english_update.items():
        setattr(record, key, value)
        
    # 2. Update/Create Nepali Translation
    nepali_updates = {
        "disease_name_translated": data.disease_name_ne,
        "treatment_instructions_translated": data.application_timing_ne,
        "safety_warnings_translated": data.safety_instructions_ne
    }
    # Filter out None values
    provided_ne = {k: v for k, v in nepali_updates.items() if v is not None}
    
    if provided_ne:
        trans_result = await db.execute(
            select(TreatmentTranslation).where(
                TreatmentTranslation.treatment_record_id == treatment_id,
                TreatmentTranslation.language_code == "ne"
            )
        )
        translation = trans_result.scalars().first()
        
        if translation:
            # Update existing translation
            for key, value in provided_ne.items():
                setattr(translation, key, value)
        else:
            # Create new translation if it didn't exist
            new_trans = TreatmentTranslation(
                treatment_record_id=treatment_id,
                language_code="ne",
                disease_name_translated=provided_ne.get("disease_name_translated", record.disease_name),
                treatment_instructions_translated=provided_ne.get("treatment_instructions_translated", record.application_timing),
                safety_warnings_translated=provided_ne.get("safety_warnings_translated", record.safety_instructions)
            )
            db.add(new_trans)
            
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_update_treatment", treatment_id, data.model_dump(exclude_unset=True))
    return {"message": "Treatment updated successfully"}

@router.delete("/treatments/{treatment_id}")
async def delete_treatment(
    treatment_id: str, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(TreatmentRecord).where(TreatmentRecord.id == treatment_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    record.is_active = False
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_delete_treatment", treatment_id, {"is_active": False})
    return {"message": "Treatment soft-deleted successfully"}

# ==========================================
# 6. USER MANAGEMENT
# ==========================================
@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [
        {"id": str(u.id), "name": u.name, "email": u.email, "role": u.role, "is_active": u.is_active, "is_super_admin": u.is_super_admin} 
        for u in users
    ]

@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin": raise HTTPException(status_code=403, detail="Cannot deactivate an admin account")
        
    user.is_active = False
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_deactivate_user", user_id, {"is_active": False})
    return {"message": "User deactivated successfully"}

@router.patch("/users/{user_id}/reactivate")
async def reactivate_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = True
    await db.commit()
    await log_admin_action(db, str(admin.id), "admin_reactivate_user", user_id, {"is_active": True})
    return {"message": "User reactivated successfully"}

# ==========================================
# 7. AUDIT LOGS VIEWER
# ==========================================
@router.get("/audit-logs")
async def view_audit_logs(limit: int = 50, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit))
    return result.scalars().all()