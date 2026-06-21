from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# AUTHENTICATION SCHEMAS
class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")
    confirm_password: str = Field(..., min_length=8, max_length=128, description="Must match password")

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

# USER RESPONSE SCHEMAS
class UserResponse(BaseModel):
    """Returned by GET /user/me - includes all user profile data"""
    id: str
    name: str
    email: str
    role: str
    language_pref: str
    profile_picture_url: Optional[str] = None  # Can be null if user hasn't uploaded a photo

    class Config:
        from_attributes = True


class ProfilePhotoResponse(BaseModel):
    """Returned by POST /user/profile-photo after successful upload"""
    message: str
    profile_picture_url: str