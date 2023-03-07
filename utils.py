from typing import TypeVar

import lz4.frame
import msgpack
from nats.aio.msg import Msg
from pydantic import ValidationError

BaseModelType = TypeVar("BaseModelType", bound="BaseModel")


def unpack_msg(msg: Msg, message_type: BaseModelType) -> BaseModelType | None:
    try:
        data = msgpack.unpackb(msg.data)
        return message_type.parse_obj(data)
    except ValidationError:
        return None


def pack_msg(msg: BaseModelType) -> bytes:
    return msgpack.packb(msg.dict())
