from app.core.dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.db.models import User
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, UserResponse
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):

    # 0. Validate password confirmation
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Password does not match"
        )

    # 1. Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 2. Hash password & create user
    hashed_pw = hash_password(user_data.password)
    new_user = User(name=user_data.name, email=user_data.email, hashed_password=hashed_pw, role="farmer")
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    
    return UserResponse(
        id=str(new_user.id),  # ← Convert UUID to string here
        name=new_user.name,
        email=new_user.email,
        role=new_user.role,
        language_pref=new_user.language_pref
    )

@router.post("/login", response_model=TokenResponse)
async def login_user(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    # 1. Find user by email
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalars().first()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")
    
    # 2. Issue JWT
    return create_access_token(user_id=str(user.id), role=user.role)

# Refresh Token and Logout
@router.post("/refresh")
async def refresh_token(current_user: User = Depends(get_current_user)):

    """
    Issues a fresh JWT access Token. (Stateless rotation: validation existing token, returns new pair.)
    """
    return create_access_token(user_id=str(current_user.id), role=current_user.role)

@router.post("/logout", status_code=200)
async def logout_user(current_user: User = Depends(get_current_user)):
    """
    Logs out the current user.
    """
    # Implementation for logout (e.g., invalidate token, clear session)
    return {"message": "Logged out successfully"}

# Added to test rate limit for temporary purposes 
@router.get("/test-rate-limit")
async def test_rate_limit(current_user: User = Depends(get_current_user)):
    return {"message": "Rate limit test successful", "user": current_user.email}