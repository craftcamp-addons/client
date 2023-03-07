import logging

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


class NubmersTask(BaseModel):
    numbers: list[NumberTask]


class DataHandler(BaseHandler):
    stream_name: str = "data_stream"

    def __init__(self, user_id: int, logger: logging.Logger):
        super().__init__(user_id, logger, "data")

    async def subscribe(self, nc: Client):
        js = nc.jetstream()
        await js.subscribe(
            subject=self.subject,
            stream=self.stream_name,
            durable=self.subject,
            cb=self.handle_message
        )

    async def handle(self, msg: Msg):
        task: NubmersTask | None = utils.unpack_msg(msg, NubmersTask)
        if task is None:
            self.logger.error(f"Пустое сообщение: {msg}")
            return

        self.logger.debug(f"Получена новая пачка: {len(task.numbers)}")

        async with get_session() as session:
            try:
                numbers: list[Number] = [
                    Number(server_id=number.id, number=number.number) for number in task.numbers
                ]
                session.add_all(numbers)
                await session.commit()
            except sqlalchemy.exc.IntegrityError as e:
                self.logger.debug(e)
        self.logger.debug(f"Сохранены {len(numbers)} номера")
