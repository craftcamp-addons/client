from typing import TypeVar

import lz4.block
import msgpack
from nats.aio.msg import Msg
from pydantic import BaseModel

BaseModelType = TypeVar("BaseModelType", bound="BaseModel")


def unpack_msg(msg: Msg, message_type: BaseModelType) -> BaseModelType | None:
    try:
        data = msgpack.unpackb(lz4.block.decompress(msg.data))
        return message_type.parse_obj(data)
    except Exception:
        return None


def pack_msg(msg: BaseModelType) -> bytes:
    return lz4.block.compress(msgpack.packb(msg.dict()))
