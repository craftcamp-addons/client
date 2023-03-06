import logging

import sqlalchemy.exc
from nats.aio.msg import Msg
from pydantic import BaseModel

from database import get_session, Number
from handlers.base import BaseHandler


class NumberTask(BaseModel):
    id: int  # server_id
    number: str


class NubmersTask(BaseModel):
    numbers: list[NumberTask]


class DataHandler(BaseHandler):
    def __init__(self, user_id: int, logger: logging.Logger):
        super().__init__(user_id, logger, "data_stream")

    async def handle(self, msg: Msg):
        task: NubmersTask = self.unpack_msg(msg, NubmersTask)
        if task is None:
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
                self.logger.debug(e.params)
        self.logger.debug(f"Сохранены {len(numbers)} номера")