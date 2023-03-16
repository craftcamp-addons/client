import logging
from typing import Callable, Awaitable

import sqlalchemy.exc
from nats.aio.client import Client
from nats.aio.msg import Msg
from pydantic import BaseModel

import utils
from database import get_session, Number
from handlers.base import BaseHandler


class NumberTask(BaseModel):
    id: int  # server_id
    number: str


class DataHandler(BaseHandler):
    stream_name: str = "data"

    def __init__(self, logger: logging.Logger):
        super().__init__(logger, "data")

    async def subscribe(self, user_id: int, nc: Callable[[], Awaitable[Client]]):
        await (await nc()).subscribe(
            subject=self.subject + str(user_id),
            cb=self.handle_message
        )

    async def handle(self, msg: Msg):
        task: NumberTask | None = utils.unpack_msg(msg, NumberTask)
        if task is None:
            self.logger.error(f"Пустое сообщение: {msg}")
            return

        self.logger.debug(f"Получен новый номер: {task.number}")

        async with get_session() as session:
            try:
                numbers = Number(server_id=task.id, number=task.number)
                session.add(numbers)
                await session.commit()
                await msg.respond(utils.pack_msg(task))
            except sqlalchemy.exc.IntegrityError as e:
                self.logger.debug(e)
        self.logger.debug(f"Сохранен {numbers} номер")
