from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import User
from app.core.dependencies import get_current_user
from app.schemas.auth import UserResponse


router = APIRouter(prefix="/user", tags=["User Settings"])

@router.get("/me", response_model=UserResponse, tags=["User Profile"])
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """ Retrieve the current user's profile info """
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        language_pref=current_user.language_pref
    )

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