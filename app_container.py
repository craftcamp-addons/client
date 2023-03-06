import asyncio
import logging

import lz4.frame
import nats.errors
import ormsgpack
from nats.aio.client import Client
from pydantic import BaseModel, ValidationError

from config import settings
from services.data_sender_service import SenderService
from errors import DisconnectedException
from handlers.data_handler import DataHandler
from handlers.base import BaseHandler
from services.heartbeat_service import HeartBeatService
from parser import Parser


class InitMessage(BaseModel):
    id: int


class InitAnswer(InitMessage):
    name: str


class AppContainer:
    sender_service: SenderService | None = None
    heartbeat_service: HeartBeatService | None = None
    parser: Parser | None = None
    nc: Client | None = None
    handlers: list[BaseHandler] = []
    logger: logging.Logger = logging.getLogger("__main__")

    def __init__(self):
        self.handlers = [
            DataHandler(settings.id, logging.getLogger("DataHandler")),
        ]

    async def connect(self):
        try:
            if self.nc is None:
                self.nc = await nats.connect(settings.server.url)
            return True
        except (nats.errors.TimeoutError, nats.errors.NoServersError):
            self.logger.error("Нет подключений")
            return False

    async def authenticate(self):
        await self.ping_server()
        js = self.nc.jetstream()
        await js.publish(subject='init_stream_server', stream='init_stream',
                         payload=lz4.frame.compress(ormsgpack.packb(InitMessage(id=settings.id).dict()))
                         )
        psub = await js.pull_subscribe(subject=f'init_stream_worker.{settings.id}', stream='init_stream',
                                       durable=f'init_stream_worker_{settings.id}')
        try:
            msg = await psub.fetch(batch=1, timeout=settings.server.init_timeout)
            if msg is None:
                raise nats.errors.TimeoutError()
            try:
                data = ormsgpack.unpackb(lz4.frame.decompress(msg[0].data))
                ans: InitAnswer = InitAnswer.parse_obj(data)
            except ValidationError as e:
                raise DisconnectedException("Ошибка валидации при обработке сообщения")
            if ans.id != settings.id:
                raise DisconnectedException("Ошибка аутентификации")
            self.logger.info(f"Пользователь {ans.id}:{ans.name} успешно подключен")
        except nats.errors.TimeoutError:
            self.logger.error("Поток аутентификации закрыт")
            raise DisconnectedException()

        answer: InitAnswer = InitAnswer.parse_obj(ormsgpack.unpackb(lz4.frame.decompress(msg[0].data)))
        if answer.id != settings.id:
            raise DisconnectedException("Ошибка аутентификации")

    async def ping_server(self):
        while True:
            try:
                if await self.connect():
                    break
            except Exception as e:
                self.logger.error(e)

    async def poll(self):
        while True:
            try:

                exceptions = await asyncio.gather(*[handler.poll(self.nc) for handler in self.handlers],
                                                  return_exceptions=True)
                if any([isinstance(exception, DisconnectedException) for exception in exceptions]):
                    await self.authenticate()
            except Exception as e:
                self.logger.error(e)

    async def run(self):
        try:

            await self.authenticate()
            self.sender_service = SenderService()
            self.parser = Parser()
            self.heartbeat_service = HeartBeatService(settings.id, logging.getLogger("HeartBeatService"), self.nc)
            await asyncio.gather(self.parser.start_parsing(self.nc, self.sender_service),
                                 self.heartbeat_service.poll(),
                                 self.poll()
                                 )
        except Exception as e:
            self.logger.exception(e)
