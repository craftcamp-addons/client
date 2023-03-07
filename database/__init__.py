import asyncio
import contextlib

import sqlalchemy_utils
from sqlalchemy import create_engine, select, or_

from database.base import Base
from database.number import NumberStatus, Number

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from config import settings

engine = create_async_engine(settings.database.url)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def check_tables(e: AsyncEngine, b: DeclarativeBase):
    async with e.begin() as conn:
        await conn.run_sync(b.metadata.create_all)


asyncio.run(check_tables(engine, Base))


@contextlib.asynccontextmanager
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_actual_numbers(session: AsyncSession, limit: int) -> list[Number]:
    return (await session.execute(
        select(Number).where(
            or_(Number.status == NumberStatus.CREATED, Number.status == NumberStatus.SECONDCHECK)).order_by(
            Number.status).limit(limit)
    )).scalars().all()


async def get_handled_numbers(session: AsyncSession, limit: int) -> list[Number]:
    return (await session.execute(
        select(Number).where(Number.status == NumberStatus.COMPLETED).limit(limit)
    )).scalars().all()
