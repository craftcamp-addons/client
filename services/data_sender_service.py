import asyncio
import logging
from pathlib import Path

import aiofiles
import lz4.frame
import ormsgpack
from nats.aio.client import Client
from nats.js.kv import KeyValue
from pydantic import BaseModel
from sqlalchemy import delete

import utils
from config import settings
from database import get_session, get_handled_numbers, Number


class NumberResult(BaseModel):
    id: int  # server_id
    number: str


class NumbersResult(BaseModel):
    user_id: int
    numbers: list[NumberResult]


class SenderService:
    user_id: int
    logger: logging.Logger
    nc: Client

    def __init__(self, nc: Client, logger: logging.Logger = logging.getLogger("SenderService"),
                 user_id: int = settings.id):
        self.user_id = user_id
        self.logger = logger
        self.photos_dir = Path(settings.parser.photos_dir)
        self.nc = nc

    async def save_number_to_object_store(self, kv: KeyValue, number: Number) -> str:
        try:
            await kv.create(number.number, number.image)
            return number.number
        except Exception as e:
            self.logger.error(e)
            await kv.delete(number.number)

    async def send_data(self):
        async with get_session() as session:
            try:
                js = self.nc.jetstream()
                # TODO: switch to object store after releasing OS feature in NATS-PY
                kv = await js.create_key_value(bucket="data_store")
                numbers: list[Number] = await get_handled_numbers(session, 3)
                n = await asyncio.gather(
                    *[self.save_number_to_object_store(kv, number) for number in numbers],
                    return_exceptions=False
                )
                self.logger.info(f"Полетела пачка в {len(numbers)} фотачек")

                await js.publish(subject="server.data", stream="data_stream",
                                 payload=utils.pack_msg(NumbersResult(user_id=self.user_id, numbers=[
                                     NumberResult(id=number.server_id, number=number.number) for number in numbers
                                 ])))
                await session.execute(
                    delete(Number).where(Number.number.in_(n))
                )
                await session.commit()
            except Exception as e:
                self.logger.error(e)
                await session.rollback()
