import asyncio
import logging
from typing import Callable, Awaitable

import nats.js.errors
from nats.aio.client import Client
from nats.js.kv import KeyValue
from pydantic import BaseModel
from sqlalchemy import delete

import utils
from database import get_session, get_handled_numbers, Number, NumberStatus
from services.base_sender_service import BaseSenderService


class NumberResult(BaseModel):
    user_id: int
    id: int  # server_id
    number: str
    photo: bool = False


class NatsSenderService(BaseSenderService):
    send_timeout: int
    user_id: int
    nc: Callable[[], Awaitable[Client]]

    def __init__(
        self,
        user_id: int,
        get_nc: Callable[[], Awaitable[Client]],
        logger: logging.Logger = logging.getLogger("NatsSenderService"),
    ):
        super().__init__(logger)
        self.send_timeout = 10
        self.user_id = user_id
        self.nc = get_nc

    async def save_number_to_object_store(self, kv: KeyValue, number: Number) -> str:
        try:
            if number.status != NumberStatus.COMPLETED:
                return number.number
            number = await kv.get(number.number)
            await kv.put(number.number, number.image)
        except nats.js.errors.KeyNotFoundError:
            await kv.create(number.number, number.image)
        except Exception as e:
            self.logger.error(e)
            await kv.delete(number.number)
        return number.number

    async def send_data(self):
        async with get_session() as session:
            try:
                js = (await self.nc()).jetstream()
                # TODO: поменять на Object Store, когда его добавят в библиотеку
                kv = await js.create_key_value(bucket="data_store")
                numbers: list[Number] = await get_handled_numbers(session, 5)
                if numbers is None or len(numbers) == 0:
                    return
                self.logger.debug(numbers)
                n = await asyncio.gather(
                    *[
                        self.save_number_to_object_store(kv, number)
                        for number in numbers
                    ],
                    return_exceptions=False,
                )

                self.logger.info(
                    f"Полетела пачка {len([True for number in numbers if number.status == NumberStatus.COMPLETED])}"
                    f" из {len(numbers)} фотачек"
                )

                await asyncio.gather(
                    *[
                        js.publish(
                            subject="server.data",
                            stream="data",
                            payload=utils.pack_msg(
                                NumberResult(
                                    user_id=self.user_id,
                                    id=number.server_id,
                                    number=number.number,
                                    photo=number.status == NumberStatus.COMPLETED,
                                )
                            ),
                        )
                        for number in numbers
                    ]
                )
                await session.execute(delete(Number).where(Number.number.in_(n)))
                await session.commit()
            except Exception as e:
                self.logger.error(e)
                await session.rollback()
            finally:
                await asyncio.sleep(self.send_timeout)
