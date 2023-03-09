import logging
from abc import ABC, abstractmethod

from dynaconf import ValidationError
from nats.aio.client import Client
from nats.aio.msg import Msg


class BaseHandler(ABC):
    subject: str
    logger: logging.Logger

    def __init__(self, logger: logging.Logger, stream_name: str):
        self.logger = logger
        self.subject = f"worker.{stream_name}."

    @abstractmethod
    async def subscribe(self, user_id: int, nc: Client):
        pass

    @abstractmethod
    async def handle(self, msg: Msg):
        pass

    async def handle_message(self, msg: Msg):
        try:
            await self.handle(msg)
            await msg.ack()
        except ValidationError as e:
            self.logger.error(f"Ошибка валидации при обработке сообщения: {len(msg.data)} - {e}")
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения: {len(msg.data)} - {e}")
