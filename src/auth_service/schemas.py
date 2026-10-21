from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

Email = Annotated[EmailStr, AfterValidator(str.lower)]
Password = Annotated[str, Field(min_length=8, max_length=128)]
Code = Annotated[str, Field(pattern=r"^\d{6}$")]


class SignUpRequest(BaseModel):
    email: Email
    password: Password


class EmailRequest(BaseModel):
    email: Email


class ConfirmEmailRequest(BaseModel):
    email: Email
    code: Code


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime
