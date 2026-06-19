from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import User
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/user", tags=["User Settings"])

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