import asyncio
import logging
from pathlib import Path
from sys import platform
from typing import Protocol

from selenium import webdriver
from selenium.common import WebDriverException

from config import settings
from database import get_session, get_actual_number, Number
from parser.basic_log_in_impl import BasicLogInImpl
from parser.basic_parser_impl import BasicParserImpl
from services.base_sender_service import BaseSenderService

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
    sender: BaseSenderService | None = None

    webdriver: webdriver.Chrome

    whatsapp_logged_in: bool = False

    def __init__(self):
        try:
            options = webdriver.ChromeOptions()
            if platform != 'win32':
                options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--allow-profiles-outside-user-dir')
            options.add_argument('--enable-profile-shortcut-manager')
            chromedriver_data_dir: Path = Path(settings.selenium.chromedriver_data_dir).absolute()
            options.add_argument(f'--user-data-dir={chromedriver_data_dir / "user"}')
            options.add_argument('--profile-directory=Profile 1')

            chromedriver_data_dir: Path = Path(settings.selenium.chromedriver_path).absolute()
            self.webdriver = webdriver.Chrome(chromedriver_data_dir if platform != 'win32' else
                                              str(chromedriver_data_dir) + ".exe", options=options)
        except WebDriverException as e:
            logger.error(e)
            raise RuntimeError("Не удалось запустить chromedriver")
        self.parser = BasicParserImpl(self.webdriver, settings.parser.url,
                                      settings.parser.webdriver_timeout,
                                      settings.parser.photos_dir
                                      )
        self.user_logger = BasicLogInImpl(self.webdriver)

    async def parse(self):
        async with get_session() as session:
            try:
                while not self.whatsapp_logged_in:
                    logger.info("Пользователь не авторизован. Ожидаю авторизацию...")
                    self.whatsapp_logged_in = await self.user_logger.log_in(settings.selenium.log_in_timeout)

                actual_number: Number | None = await get_actual_number(session)
                if actual_number is None:
                    return

                logger.info(f"Парсинг номера: {actual_number.number}")
                await self.parser.parse(actual_number)
                await session.commit()
            except Exception as e:
                logger.error(e)
                await session.rollback()

    async def start(self):
        while True:
            try:
                await self.parse()
                # TODO: Мне кажется можно изменить структуру так, чтобы это было хотя бы немного более... элегантно?
                if self.sender is not None:
                    await self.sender.send_data()
            finally:
                await asyncio.sleep(settings.parser.wait_interval)
