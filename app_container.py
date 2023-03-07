import asyncio
import logging

import nats.errors
from nats.aio.client import Client
from nats.aio.msg import Msg
from pydantic import BaseModel

import utils
from config import settings
from errors import DisconnectedException
from handlers.base import BaseHandler
from handlers.data_handler import DataHandler
from handlers.heartbeat_handler import HeartbeatHandler
from parser import Parser
from services.data_sender_service import SenderService


class InitMessage(BaseModel):
    id: int


class InitAnswer(InitMessage):
    name: str


class AppContainer:
    sender_service: SenderService | None = None
    parser: Parser | None = None
    nc: Client | None = None
    handlers: list[BaseHandler] = []
    logger: logging.Logger = logging.getLogger("__main__")

    def __init__(self):
        self.handlers = [
            DataHandler(settings.id, logging.getLogger("DataHandler")),
            HeartbeatHandler(settings.id, logging.getLogger("HeartbeatHandler"))
        ]

    async def connect(self):
        try:
            if self.nc is None:
                self.nc = await nats.connect(settings.server.url)
            return True
        except (nats.errors.TimeoutError, nats.errors.NoServersError):
            self.logger.error("Нет подключений")
            return False
        except Exception as e:
            self.logger.error(e)
            return False

    async def authenticate(self):
        await self.ping_server()
        init_response: Msg | None = await self.nc.request(subject='server.init',
                                                          payload=utils.pack_msg(InitMessage(id=settings.id)),
                                                          timeout=10
                                                          )

        if init_response is None:
            raise DisconnectedException("Ошибка аутентификации")

        self.logger.info(f"Пользователь {settings.id} успешно подключен")

    async def ping_server(self):
        while True:
            if await self.connect():
                break

    async def run(self):
        while True:
            try:
                await self.authenticate()
                self.sender_service = SenderService(self.nc)
                self.parser = Parser()
                self.parser.set_sender(self.sender_service)
                await asyncio.gather(
                    *[handler.subscribe(self.nc) for handler in self.handlers]
                )

                await self.parser.start_parsing()

            except Exception as e:
                self.logger.error(e)
            finally:
                await asyncio.sleep(10)
