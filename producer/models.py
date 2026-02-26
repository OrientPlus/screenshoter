from pydantic import BaseModel, HttpUrl
from typing import Optional

from rabbit.models import JobStatus

SECRET_KEY = "jwt-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class AuthRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ScreenshotRequest(BaseModel):
    url: HttpUrl
    selector: Optional[str] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    detail: Optional[str] = None


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str = "Screenshot job created"

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
