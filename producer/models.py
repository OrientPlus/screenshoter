from pydantic import BaseModel, HttpUrl, Field
from typing import Optional

from rabbit.models import JobStatus

class AuthRequest(BaseModel):
    username: str = Field(
        examples=["admin"]
    )
    password: str = Field(
        examples=["admin"]
    )

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ScreenshotRequest(BaseModel):
    url: HttpUrl = Field(
        examples=["https://habr.com/ru/companies/wunderfund/articles/683880/"]
    )
    selector: Optional[str] = Field(
        default=None,
        examples=["div.tm-page__main_has-sidebar.tm-page__main"]
    )

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
