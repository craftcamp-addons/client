import contextlib
from typing import Sequence

from sqlalchemy import select, or_, and_, text, Row
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

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


# TODO: Вынести в отдельный файл. Оформить так же все запросы (по крайней мере типовые)
async def get_actual_number(session: AsyncSession, offline: bool = False, limit: int = 1) -> Number | None:
    return (await session.execute(
        select(Number).where(and_(
            or_(Number.status == NumberStatus.CREATED, Number.status == NumberStatus.SECONDCHECK),
            (Number.server_id is not None if not offline else True))).order_by(
            Number.status).limit(limit)
    )).scalar_one_or_none()


async def get_handled_numbers(session: AsyncSession, limit: int = 1_000_000_000, offline: bool = False) -> Sequence[
    Number
]:
    return (await session.execute(
        select(Number).where(and_(
            or_(Number.status == NumberStatus.COMPLETED, Number.status == NumberStatus.ERROR),
            (Number.server_id is not None if not offline else True))).limit(limit)
    )).scalars().all()


async def get_status(session: AsyncSession) -> Row:
    return (await session.execute(
        text("""select
            (select count(1) from numbers where server_id is NULL),
            (select count(1) from numbers where server_id is NULL and status like 'COMPLETED'),
            (select count(1) from numbers where server_id is NULL and status like 'ERROR')
        """)
    )).one()
