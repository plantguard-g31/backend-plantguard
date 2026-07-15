from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional


# ===== AUTHENTICATION SCHEMAS =====

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")
    confirm_password: str = Field(..., min_length=8, max_length=128, description="Must match password")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ===== TOKEN RESPONSE (Returned by POST /auth/login) =====
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str  # <-- ADDED: Flutter needs this to silently refresh sessions
    token_type: str = "bearer"
    expires_in: int
    role: str  # <-- NEW: Tells Flutter if user is "farmer" or "admin"
    is_super_admin: bool = False  # <-- NEW: Tells Flutter if admin can create other admins


# ===== USER RESPONSE (Returned by GET /user/me) =====
class UserResponse(BaseModel):
    """Returned by GET /user/me - includes all user profile data"""
    id: str
    name: str
    email: str
    role: str
    is_super_admin: bool = False  # <-- NEW: Exposes the Super Admin flag to Flutter
    language_pref: str
    profile_picture_url: Optional[str] = None  # Can be null if user hasn't uploaded a photo

    class Config:
        from_attributes = True


class ProfilePhotoResponse(BaseModel):
    """Returned by POST /user/profile-photo after successful upload"""
    message: str
    profile_picture_url: str

# =====CHANGE PASSWORD SCHEMA
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=128, description="Your current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="Your new password must be minimum 8 characters")
    confirm_new_password: str = Field(..., min_length=8, max_length=128, description="Must match new password")


    @model_validator(mode='after')
    def passwords_must_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("Password Does not Match.")
        return self
# ===== Forget Password Schema ======
class ForgotPasswordRequest(BaseModel):
    """Farmer enter their mail to receive a 6-digit reset code"""
    email: EmailStr


# ===== Reser Password Schema ======
class ResetPasswordRequest(BaseModel):
    """Farmer enter the email, OTP code, and new password to complete reset"""
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code sent to your email")
    new_password: str = Field(..., min_length=8, max_length=128, description="Your new password must be minimum 8 characters")
    confirm_new_password: str = Field(..., min_length=8, max_length=128, description="Must match new password")
    
    @model_validator(mode='after')
    def passwords_must_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("Password Does not Match.")
        return self
    
    