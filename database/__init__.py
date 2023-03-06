import contextlib

from sqlalchemy import create_engine, select, or_

from database.base import Base
from database.number import NumberStatus, Number

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

from config import settings

engine = create_async_engine(settings.database.url)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
e = create_engine(settings.database.url)
sync_session = sessionmaker(e, expire_on_commit=False, class_=Session)


@contextlib.contextmanager
def get_sync_session() -> Session:
    with sync_session() as session:
        yield session


async def get_session_() -> AsyncSession:
    async with async_session() as session:
        yield session


@contextlib.asynccontextmanager
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_actual_numbers(session: AsyncSession, limit: int) -> list[Number]:
    return (await session.execute(
        select(Number).where(
            or_(Number.status == NumberStatus.CREATED, Number.status == NumberStatus.SECONDCHECK)).limit(limit)
    )).scalars().all()


async def get_handled_numbers(session: AsyncSession, limit: int) -> list[Number]:
    return (await session.execute(
        select(Number).where(Number.status == NumberStatus.COMPLETED).limit(limit)
    )).scalars().all()
