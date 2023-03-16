import contextlib

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import get_tables

from config import settings
from database.base import Base
from database.number import NumberStatus, Number

engine = create_async_engine(settings.database.url)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def check_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@contextlib.asynccontextmanager
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_actual_number(session: AsyncSession) -> Number | None:
    return (await session.execute(
        select(Number).where(
            or_(Number.status == NumberStatus.CREATED, Number.status == NumberStatus.SECONDCHECK)).order_by(
            Number.status).limit(1)
    )).scalar_one_or_none()


async def get_handled_numbers(session: AsyncSession, limit: int) -> list[Number]:
    return (await session.execute(
        select(Number).where(or_(Number.status == NumberStatus.COMPLETED, Number.status == NumberStatus.ERROR)).limit(limit)
    )).scalars().all()
