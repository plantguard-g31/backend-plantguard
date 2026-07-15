import io
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image 

from app.db.base import get_db
from app.db.models import User, AuditLog
from app.core.dependencies import get_current_user
from app.core.security import hash_password, verify_password
from app.services.storage import upload_profile_photo
from app.schemas.auth import UserResponse, ProfilePhotoResponse, ChangePasswordRequest

router = APIRouter(prefix="/user", tags=["User Profile"])

# Setup logger for this file
logger = logging.getLogger(__name__)


# ==========================================
# 1. GET CURRENT USER PROFILE
# ==========================================
@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Retrieve the current user's profile info.
    Flutter calls this after login to display name and profile photo on Dashboard.
    """
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        is_super_admin=current_user.is_super_admin,
        language_pref=current_user.language_pref,
        profile_picture_url=current_user.profile_picture_url
    )


# ==========================================
# 2. UPLOAD PROFILE PHOTO (WITH ADVANCED SECURITY)
# ==========================================
@router.post("/profile-photo", response_model=ProfilePhotoResponse, status_code=status.HTTP_200_OK)
async def upload_profile_photo_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a profile photo for the authenticated user.
    Includes advanced validation to prevent malicious file uploads.
    """

    # ── VALIDATION 1: Check file type (MIME) ──
    allowed_types = ["image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,  # ✅ CHANGED: 415 is correct for invalid file type
            detail="invalid_magic_bytes"  # ✅ CHANGED: Use error key from ERROR_MESSAGES
        )

    # ── VALIDATION 2: Check file size (5MB max) ──
    file_bytes = await file.read()
    file_size = len(file_bytes)
    max_size = 5 * 1024 * 1024  # 5MB in bytes

    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,  # ✅ CHANGED: 413 is correct for file too large
            detail="file_too_large"  # ✅ CHANGED: Use error key from ERROR_MESSAGES
        )

    # ── VALIDATION 3: Check file extension ──
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_input"  # ✅ CHANGED: Use error key
        )

    file_extension = file.filename.split(".")[-1].lower()
    if file_extension not in ["jpg", "jpeg", "png"]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="invalid_magic_bytes"  # ✅ CHANGED: Use error key
        )

    # ── VALIDATION 4: REAL IMAGE CHECK (Security) ──
    # A user could rename a virus.exe to virus.jpg. This prevents that.
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # Verify it's a valid, uncorrupted image
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="invalid_magic_bytes"  # ✅ CHANGED: Use error key
        )

    # Save user id before try block
    user_id = str(current_user.id)
    
    # ── UPLOAD & SAVE ──
    try:
        photo_url = await upload_profile_photo(
            file_bytes=file_bytes,
            user_id=user_id,
            file_extension=file_extension
        )

        current_user.profile_picture_url = photo_url
        await db.commit()
        await db.refresh(current_user)

        logger.info(f"User {current_user.id} successfully uploaded a profile photo.")

        return ProfilePhotoResponse(
            message="Profile photo uploaded successfully",
            profile_picture_url=photo_url
        )

    except HTTPException:
        raise  # ✅ CORRECT: Re-raise HTTPException so error_handler catches it
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to upload photo for user {user_id}: {str(e)}")
        raise  # ✅ CORRECT: Re-raise so error_handler converts to 500


# ==========================================
# 3. UPDATE LANGUAGE PREFERENCE
# ==========================================
class LanguageUpdate(BaseModel):
    language_pref: str = Field(..., pattern="^(en|ne)$")

@router.put("/language")
async def update_language(
    lang_data: LanguageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """FR-20: Persist farmer's language preference (en or ne)."""
    current_user.language_pref = lang_data.language_pref
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "message": "Language preference updated successfully",
        "language_pref": current_user.language_pref
    }


# ==========================================
# 4. CHANGE PASSWORD
# ==========================================
@router.put("/change-password")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change the current user's password.
    Validates current password and ensures new password meets criteria.
    """
    # Save user_id immediately before any db operations
    user_id = str(current_user.id)
    user_email = current_user.email

    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # ✅ CHANGED: 401 for auth failure
            detail="invalid_current_password"  # ✅ CHANGED: Use error key
        )
    
    # Check new password is different from current password
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password_must_be_different"  # ✅ CHANGED: Use error key
        )
    
    # Hash the new password and update
    try:
        current_user.password_hash = hash_password(password_data.new_password)
        
        # Invalidate any existing refresh tokens (force re-login on all devices)
        current_user.refresh_token = None
        current_user.refresh_token_expiry = None

        # Log the password change event in the audit log
        audit_log = AuditLog(
            user_id=current_user.id,
            event_type="password_change",
            endpoint="/api/v1/user/change-password",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            additional_data={"message": "Password changed successfully"}
        )
        db.add(audit_log)
        await db.commit()

        logger.info(f"User {user_id} changed password successfully.")
        
        return {
            "message": "Password changed successfully. Please log in again with your new password.",
            "requires_relogin": True
        }

    except HTTPException:
        raise  # ✅ ADDED: Re-raise HTTPException so error_handler catches it
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to change password for user {user_id}: {str(e)}")
        raise  # ✅ CHANGED: Re-raise so error_handler converts to 500