from pydantic import BaseModel, EmailStr, Field

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

class UserResponse(BaseModel):
    # id as string - we convert UUID to str in the endpoint
    id: str
    name:str
    email: str
    role: str
    language_pref: str