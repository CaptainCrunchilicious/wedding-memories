from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class AdministratorPublic(BaseModel):
    email: EmailStr


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    admin: AdministratorPublic


class CurrentAdministratorResponse(BaseModel):
    authenticated: bool = True
    admin: AdministratorPublic


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"
