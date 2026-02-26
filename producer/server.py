import uuid
import json
from os import getenv
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError

from datetime import datetime, timedelta
from typing import Dict

from producer.models import *
from rabbit.broker import (
    RabbitMQClient,
    QUEUE_STATUS_UPDATES,
    QUEUE_SCREENSHOT_JOBS
)

from rabbit.models import *
from common.logger import get_logger

security = HTTPBearer()

SECRET_KEY = getenv("JWT_SECRET_KEY", "jwt-secret-key")
ALGORITHM = getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))

class Server:
    def __init__(self):
        self._logger = get_logger(__name__)
        self._runtime_dir = getenv("STORAGE_DIR", "/runtime")
        self.app = FastAPI()

        admin_login = getenv("ADMIN_LOGIN", "admin")
        admin_pass = getenv("ADMIN_PASSWORD", "admin")

        self._users: Dict[str, str] = {admin_login: admin_pass}

        self._jobs: Dict[str, JobStatusResponse] = {}

        self._rabbit: Optional[RabbitMQClient] = None

        self.app.add_event_handler("startup", self._on_startup)
        self.app.add_event_handler("shutdown", self._on_shutdown)

        self.register_routes()

    async def _on_startup(self) -> None:
        self._rabbit = RabbitMQClient()
        await self._rabbit.connect()
        await self._rabbit.declare_all_queues()

        await self._rabbit.consume(QUEUE_STATUS_UPDATES, self._handle_status_update)

        self._logger.info("Successfully connected to RabbitMQ")

    async def _on_shutdown(self) -> None:
        if self._rabbit:
            await self._rabbit.disconnect()

        self._logger.info("Successfully disconnected from RabbitMQ")

    async def _handle_status_update(self, message) -> None:
        async with message.process():
            try:
                data = json.loads(message.body)
                update = StatusUpdate(**data)
                self._jobs[update.job_id] = JobStatusResponse(
                    job_id=update.job_id,
                    status=update.status,
                    detail=update.detail
                )
                self._logger.info("Received a status update for the job %s", update.job_id)
            except Exception as e:
                self._logger.exception("Exception during processing of a message from a broker")

    def register_routes(self) -> None:
        @self.app.post(
            "/auth",
            response_model=AuthResponse,
            responses={
                401: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
            },
            summary="Авторизация. Получение jwt токена",
            tags=["auth"],
        )
        async def auth(request: AuthRequest) -> AuthResponse:
            if request.username is None or request.password is None:
                self._logger.error("Invalid username or password %s:%s", request.username, request.password)
                raise HTTPException(status_code=401, detail="Invalid credentials")

            if request.username not in self._users or self._users[request.username] != request.password:
                self._logger.error("Invalid username or password %s:%s", request.username, request.password)
                raise HTTPException(status_code=403, detail="Invalid credentials")

            access_token = self.create_access_token({"sub": request.username})
            return AuthResponse(access_token=access_token)

        @self.app.post(
            "/screenshot",
            response_model=JobCreatedResponse,
            responses={
                401: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                503: {"model": ErrorResponse}
            },
            summary="Создать задачу на скриншот",
            tags=["Jobs"],
        )
        async def screenshot(
                request: ScreenshotRequest,
                _username: str = Depends(self.verify_token)
        ) -> JobCreatedResponse:
            if self._rabbit is None:
                self._logger.error("The message broker is not initialized")
                raise HTTPException(status_code=401, detail="Message broker unavailable")

            job_id = str(uuid.uuid4())
            job = ScreenshotJob(job_id=job_id, url=str(request.url), selector=request.selector)

            self._jobs[job_id] = JobStatusResponse(
                job_id=job_id,
                status=JobStatus.PENDING,
            )

            try:
                await self._rabbit.publish(
                    QUEUE_SCREENSHOT_JOBS,
                    job.model_dump(),
                )
            except Exception as e:
                self._logger.exception(
                    "Exception during an attempt to post a message to the broker's channel %s",
                    QUEUE_SCREENSHOT_JOBS
                )

            self._logger.info("Job %s created successfully; url: %s", job_id, request.url)

            return JobCreatedResponse(
                job_id=job_id,
                status=JobStatus.PENDING,
            )

        @self.app.get(
            "/screenshot/{job_id}",
            responses={
                200: {
                    "description": (
                            "Статус задачи, в случае, если она еще не выполнена"
                            "Файл скриншота, если задача выполнена"
                    ),
                    "content": {
                        "application/json": {"model": JobStatusResponse},
                        "image/png": {},
                    },
                },
                401: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
                409: {"model": ErrorResponse},
            },
            summary="Получить статус задачи или скриншот, в случае готовности задачи",
            tags=["Jobs"]
        )
        async def get_job(job_id: str, _username=Depends(self.verify_token)):
            job = self._jobs.get(job_id)
            if job is None:
                self._logger.warning("Job %s not found in route '/screenshot/{job_id}'", job_id)
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            if job.status != JobStatus.COMPLETED:
                return job

            file_path = Path(self._runtime_dir) / Path(f"{job.job_id}.png").name

            if not file_path.exists():
                self._logger.error(
                    "Job %s is 'COMPLETED' but file not found in storage: %s", job_id, file_path
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Job completed but file not found: {job.detail}",
                )

            self._logger.info("Serving screenshot file for job %s: %s", job_id, file_path)

            return FileResponse(
                path=str(file_path),
                media_type="image/png",
                filename=f"{job_id}.png",
            )

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})

        return jwt.encode(claims=to_encode, key=SECRET_KEY, algorithm=ALGORITHM)

    def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        token = credentials.credentials

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None or username not in self._users:
                self._logger.warning("Unknown user %s during token validation", username)
                raise HTTPException(status_code=403, detail="Unknown credentials")

            return username

        except JWTError:
            self._logger.exception("Failed to validate the token")
            raise HTTPException(status_code=401, detail="Could not validate credentials")
