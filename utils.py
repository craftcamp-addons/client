from typing import TypeVar

from lzma import decompress, compress
import msgpack
from nats.aio.msg import Msg

BaseModelType = TypeVar("BaseModelType", bound="BaseModel")


def unpack_msg(msg: Msg, message_type: BaseModelType) -> BaseModelType | None:
    try:
        data = msgpack.unpackb(decompress(msg.data))
        return message_type.parse_obj(data)
    except Exception:
        return None


def pack_msg(msg: BaseModelType) -> bytes:
    return compress(msgpack.packb(msg.dict()))
