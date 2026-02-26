import sys
import signal
import asyncio
from typing import Optional

from aio_pika.abc import AbstractIncomingMessage

from rabbit.broker import RabbitMQClient, QUEUE_STORAGE_JOBS
from rabbit.models import StorageJob, JobStatus
from storage.filesystem import Storage


class StorageService:
    def __init__(self):
        self._rabbit: Optional[RabbitMQClient] = None
        self._storage: Optional[Storage] = None

    async def start(self) -> None:
        self._rabbit = await RabbitMQClient().wait_for_broker()
        await self._rabbit.declare_all_queues()

        self._storage = Storage()

        await self._rabbit.consume(QUEUE_STORAGE_JOBS, self._on_message)

    async def stop(self) -> None:
        if self._rabbit:
            await self._rabbit.disconnect()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process():
            try:
                data = RabbitMQClient.parse_message(message)
                job = StorageJob(**data)
            except Exception as e:
                return

        await self._handle_job(job)

    async def _handle_job(self, job: StorageJob) -> None:
        loop = asyncio.get_event_loop()

        try:
            await loop.run_in_executor(
                None,
                self._storage.save,
                job,
            )

        except (ValueError, OSError) as e:
            await self._rabbit.publish_status(job.job_id, JobStatus.FAILED,
                                              detail=f"{type(e).__name__}: {e} on save image")
            return

        await self._rabbit.publish_status(job.job_id, JobStatus.COMPLETED)

    async def __aenter__(self) -> "StorageService":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()


async def entrypoint() -> None:
    service = StorageService()
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