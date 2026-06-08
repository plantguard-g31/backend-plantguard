import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from app.core.config import get_settings

settings = get_settings()

def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt with automatic salt generation."""
    # bcrypt.gensalt() creates a random salt for each password
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain password against a stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(user_id: str, role: str = "farmer") -> dict:
    """Generate a signed JWT with expiration."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),      # Subject: unique user ID
        "role": role,             # User role (farmer/admin)
        "exp": expire,            # Expiration time
        "iat": datetime.now(timezone.utc)  # Issued at
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "expires_in": settings.JWT_EXPIRE_MINUTES * 60}

def decode_token(token: str) -> dict:
    """Verify and decode a JWT. Raises HTTPException if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )