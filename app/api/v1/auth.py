from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.db.base import get_db
from app.db.models import User, PasswordResetToken, AuditLog
from app.schemas.auth import UserCreate, UserLogin, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, generate_otp
from app.core.dependencies import get_current_user
from app.services.email_service import send_otp_email


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
    user.refresh_token = refresh_data["refresh_token"]
    user.refresh_token_expiry = refresh_data["expires_at"] 
    await db.commit()

    # 4. Return both to the app
    return {
        "access_token": access_data["access_token"],
        "refresh_token": refresh_data["refresh_token"],
        "token_type": "bearer",
        "expires_in": 30 * 60,
        "role": user.role,
        "is_super_admin": user.is_super_admin
    }

@router.post("/refresh")
async def refresh_access_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Accepts a Refresh Token, validates it against the Database,
    and issues a brand new Access Token + Refresh Token (Token Rotation).
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
        is_expired = True
        if user and user.refresh_token_expiry is not None:
            is_expired = user.refresh_token_expiry < datetime.utcnow()

        # 4. Validate User, Token Match, and Expiration
        if not user or user.refresh_token != request.refresh_token or is_expired:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token. Please login again.")

        # 5. TOKEN ROTATION: Issue new access + refresh tokens
        access_data = create_access_token(user_id=str(user.id), role=user.role)
        refresh_data = create_refresh_token(user_id=str(user.id), role=user.role)
        
        # 6. Save the NEW refresh token to database (old one is now invalid)
        user.refresh_token = refresh_data["refresh_token"]
        user.refresh_token_expiry = refresh_data["expires_at"]
        await db.commit()

        # 7. Return both new tokens + role info
        return {
            "access_token": access_data["access_token"],
            "refresh_token": refresh_data["refresh_token"],
            "token_type": "bearer",
            "expires_in": 30 * 60,
            "role": user.role,
            "is_super_admin": user.is_super_admin
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"REFRESH ERROR: {e}") 
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

@router.post("/logout", status_code=200)
async def logout_user(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Logs out the user by deleting their Refresh Token from the database.
    """
    current_user.refresh_token = None
    current_user.refresh_token_expiry = None
    await db.commit()
    return {"message": "Logged out successfully"}

# ==========================================
# FORGOT PASSWORD — Step 1 of Password Reset
# ==========================================
@router.post("/forgot-password", status_code=200)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    request: Request,                        # ← To capture IP address for audit log
    db: AsyncSession = Depends(get_db)
):
    """
    Farmer enters their email. If the email exists in our system:
    - Generate a 6-digit OTP code
    - Store it in password_reset_tokens table (expires in 15 minutes)
    - Send it via email using Resend
    - Log the event to audit_logs
    
    CRITICAL SECURITY RULE:
    We return the SAME response whether the email exists or not.
    This prevents "email enumeration" — hackers cannot discover which
    emails are registered in our system by testing different addresses.
    """
    
    email = request_data.email.strip().lower()
    
    # 1. Check if this email exists in our system
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    
    # 2. ONLY if the user exists, generate and send the OTP
    if user:
        try:
            # Generate a cryptographically secure 6-digit code
            otp_code = generate_otp()
            
            # Calculate expiry time (15 minutes from now)
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            
            # Store the OTP in the database
            reset_token = PasswordResetToken(
                email=email,
                otp_code=otp_code,
                expires_at=expires_at,
                is_used=False
            )
            db.add(reset_token)
            
            # Send the email via Resend
            email_sent = send_otp_email(email, otp_code)
            
            if not email_sent:
                # If email fails, we still commit the token but log the failure
                print(f"  WARNING: OTP generated but email failed to send to {email}")
            
            # Log the attempt to audit_logs (security trail)
            audit_log = AuditLog(
                user_id=user.id,
                event_type="password_reset_requested",
                endpoint="/api/v1/auth/forgot-password",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent", "Unknown"),
                additional_data={
                    "email": email,
                    "email_sent_successfully": email_sent,
                    "otp_expires_at": expires_at.isoformat()
                }
            )
            db.add(audit_log)
            
            await db.commit()
            
            if email_sent:
                print(f" OTP sent successfully to {email}")
            else:
                print(f" OTP generated but email delivery failed for {email}")
                
        except Exception as e:
            # Never let email failures crash the endpoint
            print(f" Error in forgot-password flow: {e}")
            await db.rollback()
    
    else:
        # User doesn't exist — log the attempt anyway (for security monitoring)
        print(f"ℹ Forgot password requested for non-existent email: {email}")
    
    # 3. ALWAYS return the same response (prevents email enumeration)
    return {
        "message": "If this email is registered, you will receive a reset code shortly.",
        "message_ne": "यदि यो इमेल दर्ता भएको छ भने, तपाईंले छिट्टै रिसेट कोड प्राप्त गर्नुहुनेछ।"
    }


# ==========================================
# RESET PASSWORD — Step 2 of Password Reset
# ==========================================
@router.post("/reset-password", status_code=200)
async def reset_password(
    request_data: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Farmer enters email + OTP code + new password.
    Backend validates the code, updates password, and invalidates all sessions.
    
    Error Codes:
    - 400: Invalid or expired OTP code
    - 404: Email not found in system
    - 422: Validation error (passwords don't match, code not 6 digits, etc.)
    """
    
    email = request_data.email.strip().lower()
    otp_code = request_data.otp_code
    
    # 1. Find the OTP in the database
    result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.email == email)
        .where(PasswordResetToken.otp_code == otp_code)
        .where(PasswordResetToken.is_used == False)
        .order_by(PasswordResetToken.created_at.desc())  # Get the most recent one
    )
    reset_token = result.scalars().first()
    
    # 2. Validate the OTP
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid or expired reset code. Please request a new code.",
                "message_ne": "अमान्य वा समाप्त रिसेट कोड। कृपया नयाँ कोड अनुरोध गर्नुहोस्।"
            }
        )
    
    # 3. Check if expired
    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Reset code has expired. Please request a new code.",
                "message_ne": "रिसेट कोड समाप्त भएको छ। कृपया नयाँ कोड अनुरोध गर्नुहोस्।"
            }
        )
    
    # 4. Find the user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Email not found in our system.",
                "message_ne": "हाम्रो प्रणालीमा इमेल फेला परेन।"
            }
        )
    
    # 5. Update the password
    try:
        # Hash the new password
        user.password_hash = hash_password(request_data.new_password)
        
        # Invalidate all refresh tokens (force re-login on all devices)
        user.refresh_token = None
        user.refresh_token_expiry = None
        
        # Mark the OTP as used (single-use protection)
        reset_token.is_used = True
        
        # Log to audit_logs
        audit_log = AuditLog(
            user_id=user.id,
            event_type="password_reset_completed",
            endpoint="/api/v1/auth/reset-password",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent", "Unknown"),
            additional_data={
                "email": email,
                "otp_code": otp_code,
                "reset_successful": True
            }
        )
        db.add(audit_log)
        
        await db.commit()
        
        print(f" Password reset successful for {email}")
        
        return {
            "message": "Password reset successful. Please login with your new password.",
            "message_ne": "पासवर्ड रिसेट सफल भयो। कृपया तपाईंको नयाँ पासवर्डसँग लगइन गर्नुहोस्।"
        }
        
    except Exception as e:
        print(f" Error in reset-password flow: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to reset password. Please try again.",
                "message_ne": "पासवर्ड रिसेट गर्न असफल भयो। कृपया पुन: प्रयास गर्नुहोस्।"
            }
        )