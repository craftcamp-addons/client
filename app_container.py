import asyncio
import logging
from typing import Optional

import nats.errors
from nats.aio.client import Client
from nats.aio.msg import Msg
from pydantic import BaseModel

import utils
from config import settings
from database import check_tables
from errors import DisconnectedException
from handlers.base import BaseHandler
from handlers.data_handler import DataHandler
from handlers.heartbeat_handler import HeartbeatHandler
from parser.parser import Parser
from services.data_sender_service import SenderService


class InitMessage(BaseModel):
    id: Optional[int]
    username: str


class AppContainer:
    user_id: int | None = None
    sender_service: SenderService | None = None
    parser: Parser | None = None
    nc: Client | None = None
    handlers: list[BaseHandler] = []
    logger: logging.Logger = logging.getLogger("__main__")

    def __init__(self):
        self.handlers = [
            DataHandler(logging.getLogger("DataHandler")),
            HeartbeatHandler(logging.getLogger("HeartbeatHandler"))
        ]

    async def connect(self):
        try:
            self.nc = await nats.connect(settings.server.url)
            return True
        except (nats.errors.TimeoutError, nats.errors.NoServersError):
            self.logger.error("Нет подключений")
            return False
        except Exception as e:
            self.logger.error(e)
            return False

    async def authenticate(self) -> int:
        await self.ping_server()
        init_response: Msg | None = await \
            self.nc.request(subject='server.init',
                            payload=utils.pack_msg(InitMessage(username=settings.name)),
                            timeout=10
                            )

        init_message = utils.unpack_msg(init_response, InitMessage)
        if init_message is None:
            raise DisconnectedException("Ошибка аутентификации")

        self.logger.info(
            f"Пользователь {init_message.id}:{init_message.username} успешно подключен"
        )
        return init_message.id

    async def ping_server(self):
        while True:
            if await self.connect():
                break

    async def get_nc(self) -> Client:
        if self.nc is None:
            await self.ping_server()
        return self.nc

    # TODO: Причесать код, разделить на правильные сервисы и распараллелить процесс отгрузки\парсинга
    async def run(self):
        self.parser = Parser()
        while True:
            try:
                user_id: int = await self.authenticate()
                self.sender_service = SenderService(user_id, self.get_nc)

                self.parser.set_sender(self.sender_service)
                await asyncio.gather(
                    *[handler.subscribe(user_id, self.get_nc) for handler in self.handlers]
                )
                self.logger.info("Подписочка на обновления есть, запускаю сервисы")
                await check_tables()

                await self.parser.start_parsing()

            except Exception as e:
                self.logger.error(e)
            finally:
                await asyncio.sleep(10)
