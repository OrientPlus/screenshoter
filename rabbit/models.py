from pydantic import BaseModel
from enum import Enum
from typing import Optional

class ScreenshotJob(BaseModel):
    job_id: str
    url: str
    selector: Optional[str] = None

class StorageJob(BaseModel):
    job_id: str
    image_hex: str

class JobStatus(str, Enum):
    PENDING = "PENDING"
    CAPTURING = "CAPTURING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class StatusUpdate(BaseModel):
    job_id: str
    status: JobStatus
    detail: Optional[str] = None