import asyncio
import json
from typing import Callable, Awaitable, Optional

import aio_pika
from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue

from rabbit.models import StatusUpdate, JobStatus

from common.logger import get_logger

RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"

QUEUE_SCREENSHOT_JOBS = "screenshot_jobs"
QUEUE_STORAGE_JOBS = "storage_jobs"
QUEUE_STATUS_UPDATES = "status_updates"


class RabbitMQClient:
    def __init__(self, url: str = RABBITMQ_URL) -> None:
        self._logger = get_logger(__name__)

        self._url = url
        self._connection: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._queues: dict[str, AbstractQueue] = {}

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        self._logger.info("The 'RabbitMQClient' service has successfully connected to the broker")

    async def disconnect(self) -> None:
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

        self._logger.info("'RabbitMQClient' service successfully disconnected from the broker")

    async def declare_queue(self, name: str) -> aio_pika.abc.AbstractQueue:
        if self._channel is None:
            self._logger.error("The broker object has not been initialized")
            raise RuntimeError("Not connected to RabbitMQ")

        if name not in self._queues:
            self._queues[name] = await self._channel.declare_queue(name, durable=True)

        return self._queues[name]

    async def declare_all_queues(self) -> None:
        for queue_name in (
                QUEUE_SCREENSHOT_JOBS,
                QUEUE_STORAGE_JOBS,
                QUEUE_STATUS_UPDATES,
        ):
            await self.declare_queue(queue_name)
        self._logger.info("All queues have been declared successfully")

    async def publish(self, queue_name: str, payload: dict) -> None:
        if self._channel is None:
            self._logger.error("The broker object has not been initialized")
            raise RuntimeError("Not connected to RabbitMQ")

        body = json.dumps(payload).encode()
        await self.declare_queue(queue_name)

        message = Message(
            body=body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._channel.default_exchange.publish(
            message,
            routing_key=queue_name,
        )
        self._logger.info("Published message to queue: %s", queue_name)

    async def publish_status(
            self,
            job_id: str,
            status: JobStatus,
            detail: Optional[str] = None
    ) -> None:
        update = StatusUpdate(
            job_id=job_id,
            status=status,
            detail=detail,
        )

        await self.publish(QUEUE_STATUS_UPDATES, update.model_dump())
        self._logger.info("Status update for job %s has been published", job_id)

    async def consume(
            self,
            queue_name: str,
            callback: Callable[[AbstractIncomingMessage], Awaitable[None]],
            no_ack: bool = False
    ) -> str:
        queue = await self.declare_queue(queue_name)
        tag = await queue.consume(callback, no_ack=no_ack) # TODO проверить ack в хендлерах

        return tag

    @staticmethod
    def parse_message(message: AbstractIncomingMessage) -> dict:
        try:
            return json.loads(message.body)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON: {message.body!r}"
            ) from e

    @classmethod
    async def wait_for_broker(
            cls,
            url: str = RABBITMQ_URL,
            retries: int = 12,
            delay: float = 5.0,
    ) -> "RabbitMQClient":
        for attempt in range(1, retries + 1):
            try:
                client = cls(url)
                await client.connect()

                return client
            except Exception as e:
                if attempt < retries:
                    await asyncio.sleep(delay)

        raise RuntimeError(f"Failed to connect to RabbitMQ after {retries} attempts")

    async def __aenter__(self) -> "RabbitMQClient":
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        await self.disconnect()
