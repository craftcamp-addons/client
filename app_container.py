import asyncio
import logging
from multiprocessing import Pool, Process
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
from services.base_sender_service import BaseSenderService
from services.nats_sender_service import NatsSenderService
from services.zmq_listener_service import ZmqListenerService


def apply_sync(o):
    asyncio.run(o())


class InitMessage(BaseModel):
    id: Optional[int]
    username: str


class AppContainer:
    user_id: int | None = None
    sender_service: BaseSenderService | None = None
    parser: Parser | None = None
    nc: Client | None = None
    zmq_listener: ZmqListenerService | None = None
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

    # TODO: Причесать код, разделить на правильные сервисы и распараллеливать процесс отгрузки\парсинга
    async def run(self):
        self.parser = Parser()
        listener_process = None
        while True:
            tasks: list = []
            try:
                offline_mode: bool = settings.enable_offline_mode

                if offline_mode:
                    self.logger.info("Запуск в режиме оффлайн")

                    listener_process = Process(target=ZmqListenerService.start)
                    listener_process.start()
                else:
                    self.user_id: int = await self.authenticate()
                    self.sender_service = NatsSenderService(self.user_id, self.get_nc)
                    await asyncio.gather(
                        *[handler.subscribe(self.user_id, self.get_nc) for handler in self.handlers]
                    )
                    self.logger.info("Подписался на обновления, запуск сервисов...")

                    self.parser.sender = self.sender_service

                await check_tables()

                tasks.append(self.parser.start())

                errors = await asyncio.gather(*tasks, return_exceptions=True)
                for error in (e for e in errors if isinstance(e, Exception)):
                    self.logger.error(error)

                listener_process.join()
            except Exception as e:
                self.logger.error(e)
            finally:
                await asyncio.sleep(10)
                listener_process.terminate()
