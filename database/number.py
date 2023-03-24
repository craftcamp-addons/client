import enum
from typing import Optional

from sqlalchemy.orm import mapped_column, Mapped

from database.base import Base


class NumberStatus(enum.Enum):
    CREATED = 0
    COMPLETED = 2
    SECONDCHECK = 3
    ERROR = 4


class Number(Base):
    __tablename__ = 'numbers'

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    number: Mapped[str] = mapped_column(unique=True)
    status: Mapped[NumberStatus] = mapped_column(default=NumberStatus.CREATED)
    image: Mapped[bytes] = mapped_column(nullable=True)
