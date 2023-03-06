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

    def __init__(self, logger: logging.Logger = logging.getLogger("sender"),
                 user_id: int = settings.id):
        self.user_id = user_id
        self.logger = logger
        self.photos_dir = Path(settings.parser.photos_dir)

    async def save_number_to_object_store(self, kv: KeyValue, number: Number):
        try:
            photo_file: Path = self.photos_dir / f"{number.number}.png"
            async with aiofiles.open(photo_file, 'rb') as f:
                await kv.create(number.number, await f.read())
            photo_file.unlink(missing_ok=True)
            return number.number

        except Exception as e:
            self.logger.error(e)
            await kv.delete(number.number)

    async def send_data(self, nc: Client, batch_size: int):
        async with get_session() as session:
            try:
                js = nc.jetstream()
                # TODO: switch to object store after releasing OS feature in NATS-PY
                kv = await js.create_key_value(bucket="data_store")
                numbers: list[Number] = await get_handled_numbers(session, batch_size)
                n = await asyncio.gather(
                    *[self.save_number_to_object_store(kv, number) for number in numbers],
                    return_exceptions=False
                )
                self.logger.info(f"Полетела пачка в {len(numbers)} фотачек")
                await session.execute(
                    delete(Number).where(Number.number.in_(n))
                )
                await js.publish(subject="data_stream_server", stream="data_stream",
                                 payload=lz4.frame.compress(
                                     ormsgpack.packb(NumbersResult(user_id=self.user_id, numbers=[
                                         NumberResult(id=number.server_id, number=number.number) for number in numbers
                                     ]).dict()))
                                 )
                await session.commit()
            except Exception as e:
                self.logger.error(e)
                await session.rollback()
