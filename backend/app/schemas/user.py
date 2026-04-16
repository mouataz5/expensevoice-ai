import uuid

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool = True

    model_config = {"from_attributes": True}


class UserMapItem(BaseModel):
    id: str
    email: str
    role: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str  # employee | director | accountant | admin


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class ResetPasswordIn(BaseModel):
    new_password: str
