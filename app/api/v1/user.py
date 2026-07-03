import io
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image # <-- NEW: For real image validation

from app.db.base import get_db
from app.db.models import User
from app.core.dependencies import get_current_user
from app.services.storage import upload_profile_photo
from app.schemas.auth import UserResponse, ProfilePhotoResponse

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
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only JPEG and PNG images are allowed."
        )

    # ── VALIDATION 2: Check file size (5MB max) ──
    file_bytes = await file.read()
    file_size = len(file_bytes)
    max_size = 5 * 1024 * 1024  # 5MB in bytes

    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 5MB. Your file is {file_size / (1024*1024):.2f}MB."
        )

    # ── VALIDATION 3: Check file extension ──
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required."
        )

    file_extension = file.filename.split(".")[-1].lower()
    if file_extension not in ["jpg", "jpeg", "png"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Use .jpg, .jpeg, or .png"
        )

    # ── VALIDATION 4: REAL IMAGE CHECK (Security) ──
    # A user could rename a virus.exe to virus.jpg. This prevents that.
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # Verify it's a valid, uncorrupted image
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is corrupted or not a valid image."
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
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to upload photo for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload photo. Please try again later."
        )


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