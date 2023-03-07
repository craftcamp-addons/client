import logging

from nats.aio.client import Client
from nats.aio.msg import Msg
from pydantic import BaseModel

import utils
from handlers.base import BaseHandler


class Ping(BaseModel):
    id: int


class HeartbeatHandler(BaseHandler):
    nc: Client

    def __init__(self, user_id: int, logger: logging.Logger):
        super().__init__(user_id, logger, "heartbeat")

    async def subscribe(self, nc: Client):
        self.nc = nc
        await nc.subscribe(subject=self.subject, cb=self.handle_message)

    async def handle(self, msg: Msg):
        ping = utils.unpack_msg(msg, Ping)
        if ping is None or ping.id != self.user_id:
            self.logger.error("Пинг не удался :^(")
        await self.nc.publish(msg.reply, utils.pack_msg(Ping(id=self.user_id)))
