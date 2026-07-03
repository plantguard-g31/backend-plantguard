from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.db.base import get_db
from app.db.models import User
from app.schemas.auth import UserCreate, UserLogin, UserResponse
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Schema for the refresh request body
class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    if user_data.password != user_data.confirm_password:
        raise HTTPException(status_code=400, detail="password_mismatch")

    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="duplicate_email")

    hashed_pw = hash_password(user_data.password)
    new_user = User(name=user_data.name, email=user_data.email, password_hash=hashed_pw, role="farmer")
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return UserResponse(
        id=str(new_user.id), name=new_user.name, email=new_user.email,
        role=new_user.role, language_pref=new_user.language_pref
    )

@router.post("/login")
async def login_user(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    # 1. Find user
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalars().first()

    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="account_deactivated")

    # 2. Generate BOTH tokens
    access_data = create_access_token(user_id=str(user.id), role=user.role)
    refresh_data = create_refresh_token(user_id=str(user.id), role=user.role)

    # 3. SAVE the Refresh Token to the Database (The "Front Desk Safe")
    # FIX: Changed refresh_token_expires_at -> refresh_token_expiry to match models.py
    user.refresh_token = refresh_data["refresh_token"]
    user.refresh_token_expiry = refresh_data["expires_at"] 
    await db.commit()

    # 4. Return both to the app
    return {
        "access_token": access_data["access_token"],
        "refresh_token": refresh_data["refresh_token"],
        "token_type": "bearer",
        "expires_in": 30 * 60, # 30 minutes in seconds
        "role": user.role,
        "is_super_admin": user.is_super_admin
    }

@router.post("/refresh")
async def refresh_access_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Accepts a Refresh Token, validates it against the Database, 
    and issues a brand new Access Token.
    """
    try:
        # 1. Decode the token to see who it belongs to
        payload = decode_token(request.refresh_token)
        
        # Security check: Ensure it's actually a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type.")
            
        user_id = payload.get("sub")

        # 2. Check the Database
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        # 3. SAFELY CHECK EXPIRATION (Handles NULL dates in database)
        is_expired = True # Default to expired for safety
        # FIX: Changed refresh_token_expires_at -> refresh_token_expiry
        if user and user.refresh_token_expiry is not None:
            is_expired = user.refresh_token_expiry < datetime.utcnow()

        # 4. Validate User, Token Match, and Expiration
        if not user or user.refresh_token != request.refresh_token or is_expired:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token. Please login again.")

        # 5. Issue a brand new Access Token
        return create_access_token(user_id=str(user.id), role=user.role)

    except HTTPException:
        raise
    except Exception as e:
        # For debugging: If it still fails, print the real error to your terminal
        print(f"REFRESH ERROR: {e}") 
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

@router.post("/logout", status_code=200)
async def logout_user(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Logs out the user by deleting their Refresh Token from the database.
    """
    # FIX: Changed refresh_token_expires_at -> refresh_token_expiry
    current_user.refresh_token = None
    current_user.refresh_token_expiry = None
    await db.commit()
    return {"message": "Logged out successfully"}