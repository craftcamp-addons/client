import asyncio
import logging
from pathlib import Path
from sys import platform
from typing import Protocol

from nats.aio.client import Client
from selenium import webdriver
from selenium.common import WebDriverException
from sqlalchemy import select, func

from config import settings
from services.data_sender_service import SenderService
from database import get_session, get_actual_numbers, Number, NumberStatus
from parser.basic_log_in_impl import BasicLogInImpl
from parser.basic_parser_impl import BasicParserImpl

logger = logging.getLogger(__name__)


class BaseParserImpl(Protocol):
    async def parse(self, number: Number):
        pass


class BaseLogInImpl(Protocol):
    async def log_in(self, timeout: int) -> bool:
        pass


class Parser:
    parser: BaseParserImpl
    user_logger: BaseLogInImpl

    webdriver: webdriver.Chrome

    whatsapp_logged_in: bool = False

    def __init__(self):
        try:
            options = webdriver.ChromeOptions()
            if platform != 'win32':
                options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--allow-profiles-outside-user-dir')
            options.add_argument('--enable-profile-shortcut-manager')
            options.add_argument(f'--user-data-dir={Path(settings.selenium.chromedriver_data_dir) / "user"}')
            options.add_argument('--profile-directory=Profile 1')

            self.webdriver = webdriver.Chrome(settings.selenium.chromedriver_path if platform != 'win32' else
                                              settings.selenium.chromedriver_path + ".exe", options=options)
        except WebDriverException as e:
            logger.error(e)
            raise RuntimeError("Не удалось запустить chromedriver")
        self.parser = BasicParserImpl(self.webdriver, settings.parser.url,
                                      settings.parser.webdriver_timeout,
                                      settings.parser.photos_dir
                                      )
        self.user_logger = BasicLogInImpl(self.webdriver)

    def set_parser(self, parser: BaseParserImpl):
        self.parser = parser

    def set_user_logger(self, user_logger: BaseLogInImpl):
        self.user_logger = user_logger

    @property
    async def current_batch_count(self) -> int:
        async with get_session() as session:
            return (await session.execute(
                select(func.count().label('count')).select_from(Number).where(
                    Number.status == NumberStatus.COMPLETED))).scalar_one()

    async def parse(self):
        async with get_session() as session:
            try:
                batch_limit = settings.parser.batch_size
                logger.info("Парсинг следующей пачки...")

                while not self.whatsapp_logged_in:
                    logger.info("Пользователь не авторизован. Ожидаю авторизацию...")
                    self.whatsapp_logged_in = await self.user_logger.log_in(settings.selenium.log_in_timeout)

                actual_numbers: list[Number] = await get_actual_numbers(session, batch_limit)
                while len(actual_numbers) == 0:
                    logger.info("Ожидается следующая пачка...")
                    actual_numbers = await get_actual_numbers(session, batch_limit)
                    await asyncio.sleep(settings.parser.wait_interval)

                for number in actual_numbers:
                    logger.info(f"Парсинг номера: {number.number}")
                    await self.parser.parse(number)
                    await session.commit()
            except Exception as e:
                logger.error(e)
                await session.rollback()

    async def start_parsing(self, nc: Client, sender: SenderService):
        while True:
            try:
                batch_count = await self.current_batch_count
                if batch_count >= settings.parser.batch_size:
                    logger.info(f"Отправляю {batch_count}")
                    await sender.send_data(nc, batch_count)
                else:
                    await self.parse()
            except Exception as e:
                logger.error(e)
            finally:
                await asyncio.sleep(settings.parser.wait_interval)
