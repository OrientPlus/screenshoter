import asyncio
import signal
import sys
from typing import Optional
from aio_pika.abc import AbstractIncomingMessage

from rabbit.broker import (
    RabbitMQClient,
    QUEUE_SCREENSHOT_JOBS,
    QUEUE_STORAGE_JOBS,
    QUEUE_STATUS_UPDATES,
)

from rabbit.models import ScreenshotJob, StorageJob, JobStatus
from screenshoter.playwrt import ScreenshotCapture
from common.logger import get_logger

PAGE_TIMEOUT_MS = 30_000
SCREENSHOT_TIMEOUT_MS = 20_000


class ScreenshotService:
    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._rabbit: Optional[RabbitMQClient] = None
        self._capture: Optional[ScreenshotCapture] = None

    async def start(self) -> None:
        self._rabbit = await RabbitMQClient.wait_for_broker()
        await self._rabbit.declare_all_queues()

        self._capture = ScreenshotCapture()
        await self._capture.start()

        await self._rabbit.consume(QUEUE_SCREENSHOT_JOBS, self._process_job)

        self._logger.info("Successfully connected to RabbitMQ")

    async def stop(self) -> None:
        if self._capture:
            await self._capture.stop()
        if self._rabbit:
            await self._rabbit.disconnect()

        self._logger.info("Successfully disconnected from RabbitMQ")

    async def _process_job(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            try:
                data = RabbitMQClient.parse_message(message)
                job = ScreenshotJob(**data)
            except Exception as e:
                self._logger.exception("Exception during broker message processing")
                return

            await self._handle_job(job)

    async def _handle_job(self, job: ScreenshotJob) -> None:
        await self._rabbit.publish_status(job.job_id, JobStatus.CAPTURING)

        try:
            image_bytes: bytes = await self._capture.take(
                url=job.url,
                selector=job.selector,
            )
            self._logger.info("Screenshot received successfully")
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            await self._rabbit.publish_status(
                job.job_id,
                JobStatus.FAILED,
                detail=error_msg,
            )
            self._logger.exception("Exception during screenshot capture: %s", error_msg)

            return

        storage_payload = StorageJob(
            job_id=job.job_id,
            image_hex=image_bytes.hex(),
        )

        try:
            await self._rabbit.publish(
                QUEUE_STORAGE_JOBS,
                storage_payload.model_dump(),
            )

            self._logger.info("The image was transferred to the 'storage' service")

            await self._rabbit.publish_status(job.job_id, JobStatus.UPLOADING)
        except Exception as e:
            self._logger.exception("Exception during the publication of a message to the broker")


    async def __aenter__(self) -> "ScreenshotService":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()


async def entrypoint() -> None:
    service = ScreenshotService()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_signal() -> None:
        stop_event.set()

    if sys.platform != "win32":
        # Unix
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)
    else:
        # Windows
        def handler(signum, frame):
            loop.call_soon_threadsafe(stop_event.set)

        signal.signal(signal.SIGINT, handler)

        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handler)

    async with service:
        await stop_event.wait()


if __name__ == "__main__":
    asyncio.run(entrypoint())
