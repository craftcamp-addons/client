import logging
import zipfile
from pathlib import Path
from typing import Sequence

import msgpack
import zmq
import zmq.asyncio as zmq_async
from pydantic import BaseModel

from config import settings
from database import get_session, get_status, Number, get_handled_numbers
from services.base_sender_service import BaseSenderService


class StatusMessage(BaseModel):
    total: int
    completed: int
    error: int
    # secondcheck: int # ???


STATUS = "status"
UPLOAD = "upload"
DOWNLOAD = "download"
ERR = "ERR"
OK = "OK"


class ZmqListenerService:
    """
    Сервис, который, скорее всего будет запущен в отдельной корутине
        Слушает ipc сокет zmq и обрабатывает команды по модели Req/Rep
        TODO: Пока что этот сервис - костыль. Логика в нём собрана в кучу, поэтому refactor this asap
    """
    comm_dir: Path
    sender: BaseSenderService
    logger: logging.Logger

    def __init__(self, comm_dir: Path = settings.zmq.comm_dir,
                 logger: logging.Logger = logging.getLogger("ZmqListenerService")):
        self.comm_dir = Path(comm_dir)
        if not self.comm_dir.exists():
            self.comm_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    async def status(self) -> StatusMessage:
        async with get_session() as session:
            status = await get_status(session)
            return StatusMessage(
                total=status[0],
                completed=status[1],
                error=status[2]
            )

    # Все проверки на валидность номеров производятся на стороне отправителя
    async def upload(self, numbers: list[str]):
        async with get_session() as session:
            try:
                nums = [
                    Number(number=number) for number in numbers
                ]
                session.add_all(nums)
                await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(e)

    async def download(self, filename: str, password: str):
        output_file = Path(filename)
        if not output_file.absolute().exists():
            output_file.parent.mkdir(parents=True, exist_ok=True)
        async with get_session() as session:
            numbers: Sequence[Number] = await get_handled_numbers(session)
            with zipfile.ZipFile(output_file, 'w') as file:
                if password != "":
                    file.setpassword(password.encode())
                for number in numbers:
                    if number.image is not None:
                        file.writestr(
                            (str(number.number) + ".png"), number.image
                        )

    async def start_listening(self):
        context = zmq_async.Context()
        socket = context.socket(zmq.REP)

        port = socket.bind_to_random_port(f"tcp://127.0.0.1", min_port=7000, max_port=7100)
        self.logger.info(f"Начинаю слушать tcp://127.0.0.1:{port}")
        with open(self.comm_dir.absolute() / "port", 'w') as port_file:
            print(port, file=port_file, flush=True)

        message = {}
        while True:
            try:
                message = msgpack.unpackb((await socket.recv_multipart())[0])
                self.logger.debug(f"Получил сообщение: {message}")
                match message:
                    case {"command": command, "data": data}:
                        self.logger.debug("Сообщение с аргументами")
                        if command == UPLOAD:
                            await self.upload(data)
                            await socket.send(msgpack.packb({"command": UPLOAD, "status": OK}))
                            self.logger.debug("Загрузил номера")
                        elif command == DOWNLOAD:
                            await self.download(data['filename'], data['password'])
                            await socket.send(msgpack.packb({"command": DOWNLOAD, "status": OK}))
                            self.logger.debug(f"Выгрузил номера в {data['filename']}")
                    case {"command": command}:
                        self.logger.debug("Сообщение без аргументов")
                        if command == STATUS:
                            self.logger.debug("Статус")
                            await socket.send(msgpack.packb((await self.status()).dict()))
                            self.logger.debug("Отправил статус")

                    case _:
                        self.logger.warning("Не удалось распознать схему запроса")
                        await socket.send(msgpack.packb({"status": ERR}))
                        continue
            except Exception as e:
                await socket.send(msgpack.packb({"status": ERR, "command": message}))
                self.logger.error(e)

    @staticmethod
    async def start():
        listener = ZmqListenerService()
        await listener.start_listening()
