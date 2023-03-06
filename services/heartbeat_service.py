import asyncio
import datetime
import logging

import nats.errors
from nats.aio.client import Client

from config import settings


class HeartBeatService:
    user_id: str
    logger: logging.Logger
    nc: Client

    def __init__(self, user_id: int, logger: logging.Logger, nc: Client):
        self.user_id = str(user_id)
        self.logger = logger
        self.nc = nc

    async def poll(self):
        js = self.nc.jetstream()
        kv = await js.key_value("connected_users")
        while True:
            try:
                update = await kv.get(self.user_id)
                if update is not None and (update.value == b"not connected" or
                                           ((datetime.datetime.now() - datetime.datetime.fromisoformat(
                                               update.value.decode())) >= datetime.timedelta(
                                               seconds=1))):
                    self.logger.info(f"Сердцестукаю 🗿🗿")
                    await kv.put(self.user_id, datetime.datetime.now().isoformat().encode())
            except nats.errors.TimeoutError:
                continue
