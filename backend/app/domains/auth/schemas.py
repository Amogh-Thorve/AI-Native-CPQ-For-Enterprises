import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class PermissionRead(PermissionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True

class RoleCreate(RoleBase):
    permissions: Optional[List[str]] = None

class RoleRead(RoleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    permissions: List[PermissionRead] = []

    class Config:
        from_attributes = True


from pydantic import model_validator

class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True

class UserCreate(UserBase):
    full_name: Optional[str] = None
    password: str
    confirm_password: Optional[str] = None
    role: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def check_name_and_passwords(cls, data: any) -> any:
        if isinstance(data, dict):
            full_name = data.get("full_name")
            if full_name and not data.get("first_name"):
                parts = full_name.strip().split(maxsplit=1)
                data["first_name"] = parts[0]
                data["last_name"] = parts[1] if len(parts) > 1 else ""
            
            if not data.get("first_name"):
                data["first_name"] = ""
            if not data.get("last_name"):
                data["last_name"] = ""

            if "confirm_password" not in data or data["confirm_password"] is None:
                data["confirm_password"] = data.get("password")
        return data

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    password: Optional[str] = None

class UserRead(UserBase):
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    roles: List[RoleBase] = []

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user: UserRead

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None

class LoginRequest(BaseModel):
    # Use str instead of EmailStr so dev/local domains (e.g. @cpq.local) are accepted.
    # Basic format check: must contain exactly one @ with non-empty local and domain parts.
    email: str = Field(..., min_length=3, pattern=r"^[^@]+@[^@]+$")
    password: str

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
    confirm_password: str

class EmailVerificationConfirm(BaseModel):
    token: str

class SessionRead(BaseModel):
    id: uuid.UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class RolePermissionAssign(BaseModel):
    permission_name: str

class UserRoleAssign(BaseModel):
    role_name: str
