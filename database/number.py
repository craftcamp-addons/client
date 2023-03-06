import enum

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import mapped_column, Mapped, relationship

from database.base import Base


class NumberStatus(enum.Enum):
    CREATED = 0
    IN_WORK = 1
    COMPLETED = 2
    SECONDCHECK = 3
    ERROR = 4


class Number(Base):
    __tablename__ = 'numbers'

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(nullable=False)
    number: Mapped[str] = mapped_column(unique=True)
    status: Mapped[NumberStatus] = mapped_column(default=NumberStatus.CREATED)
