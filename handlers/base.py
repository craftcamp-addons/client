import asyncio
import logging
from abc import ABC, abstractmethod

import lz4.frame
import nats.errors
import ormsgpack
from dynaconf import ValidationError
from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.js import JetStreamContext
from nats.js.errors import NotFoundError

from errors import DisconnectedException


class BaseHandler(ABC):
    nc: Client | None
    js: JetStreamContext | None
    stream_name: str
    worker: str
    logger: logging.Logger
    user_id: int

    def __init__(self, user_id: int, logger: logging.Logger, stream_name: str, worker: str = "worker.*"):
        self.user_id = user_id
        self.stream_name = stream_name
        self.logger = logger
        self.worker = worker
        self.nc = None
        self.js = None

    def set_nats(self, nc: Client):
        self.nc = nc
        self.js = nc.jetstream()

    @abstractmethod
    async def handle(self, msg: Msg):
        pass

    async def handle_message(self, msg: Msg):
        try:
            await self.handle(msg)
        except Exception as e:
            self.logger.error(f"Сообщение не удалось обработать: {e}")
        finally:
            await msg.ack()

    def unpack_msg(self, msg: Msg, message_class):
        try:
            data = ormsgpack.unpackb(lz4.frame.decompress(msg.data))
            self.logger.debug(f"Обработка сообщения: {msg.subject} - {len(msg.data)} - {msg.headers}")
            return message_class.parse_obj(data)
        except ValidationError as e:
            self.logger.error(f"Ошибка валидации при обработке сообщения: {len(msg.data)} - {e}")
            return None

    async def init_stream(self):
        js = self.nc.jetstream()
        try:
            stream = await js.stream_info(self.stream_name)
            if stream is not None:
                self.logger.info(f"JetStream существует: {stream.config.name} - {stream.config.subjects}")
        except NotFoundError as e:
            self.logger.warning(f"Поток с именем {self.stream_name} не существует, создаю поток...")
            await js.add_stream(name=self.stream_name,
                                subjects=[f"{self.stream_name}_server", f"{self.stream_name}_{self.worker}"])

    async def poll(self, nc: Client | None) -> None:
        try:
            self.nc = nc
            if self.nc is None:
                raise DisconnectedException("Брокер сообщений не подключен")
            await self.init_stream()
            self.js = self.nc.jetstream()
            await self.js.subscribe(f'{self.stream_name}_worker.{self.user_id}',
                                    durable=f"{self.stream_name}_worker_{self.user_id}", cb=self.handle_message)
            await asyncio.Future()
        except (nats.errors.TimeoutError, nats.errors.ConnectionClosedError):
            raise DisconnectedException("Брокер сообщений не подключен")
        except Exception as e:
            self.logger.error(f"Ошибка сервера при обработке сообщения: {e}")
