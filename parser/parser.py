import asyncio
import logging
from pathlib import Path
from sys import platform
from typing import Protocol, Any
from config import settings

if platform == "linux" and not settings.selenium.headless:
    import xvfbwrapper
from selenium import webdriver
from selenium.common import WebDriverException

from database import get_session, get_actual_number, Number
from parser.basic_log_in_impl import BasicLogInImpl
from parser.basic_parser_impl import BasicParserImpl
from services.base_sender_service import BaseSenderService


class BaseParserImpl(Protocol):
    async def parse(self, number: Number):
        pass


class BaseLogInImpl(Protocol):
    def log_in(self, timeout: int, screenshot_filename: Path) -> bool:
        pass


class Parser:
    display: Any
    parser: BaseParserImpl
    user_logger: BaseLogInImpl
    sender: BaseSenderService | None = None

    driver: webdriver.Chrome | None = None

    whatsapp_logged_in: bool = False
    logger: logging.Logger = logging.getLogger("Parser")

    async def parse(self):
        try:
            if self.driver is None:
                if platform == 'linux' and not settings.selenium.headless:
                    self.display = xvfbwrapper.Xvfb()
                    self.display.start()
                try:
                    options = webdriver.ChromeOptions()
                    # options.add_argument("--headless")
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--allow-profiles-outside-user-dir")
                    options.add_experimental_option("detach", True)
                    options.add_experimental_option("excludeSwitches", ["enable-logging"])
                    options.add_argument("--enable-profile-shortcut-manager")
                    chromedriver_data_dir: Path = Path(
                        settings.selenium.chromedriver_data_dir
                    ).absolute()
                    options.add_argument(
                        f'--user-data-dir={chromedriver_data_dir / "user"}'
                    )
                    options.add_argument("--profile-directory=Profile 1")

                    chromedriver_data_dir: Path = Path(
                        settings.selenium.chromedriver_path
                    ).absolute()
                    self.driver = webdriver.Chrome(
                        executable_path=(
                            chromedriver_data_dir
                            if platform != "win32" and (".exe" not in str(chromedriver_data_dir))
                            else str(chromedriver_data_dir) + ".exe"
                        ),
                        options=options,
                    )
                except WebDriverException as e:
                    self.logger.error(e)
                    raise RuntimeError("Не удалось запустить chromedriver")
                self.parser = BasicParserImpl(
                    self.driver,
                    settings.parser.url,
                    settings.parser.webdriver_timeout,
                    settings.parser.photos_dir,
                )
                self.user_logger = BasicLogInImpl(self.driver)

            async with get_session() as session:
                try:
                    while not self.whatsapp_logged_in:
                        # В headless режиме сделать авторизацию через бота
                        self.logger.info(
                            "Пользователь не авторизован. Ожидаю авторизацию..."
                        )
                        self.whatsapp_logged_in = self.user_logger.log_in(
                            settings.selenium.log_in_timeout,
                            Path(settings.selenium.log_in_screen_filename)
                        )

                    actual_number: Number | None = await get_actual_number(session)
                    if actual_number is None:
                        return

                    self.logger.info(f"Парсинг номера: {actual_number.number}")
                    await self.parser.parse(actual_number)
                    await session.commit()
                except Exception as e:
                    self.logger.error(e)
                    await session.rollback()
                    self.driver.quit()
                    self.driver = None
                    if platform == "linux":
                        self.display.stop()
        except Exception as e:
            self.logger.error(e)

    async def start_parsing(self):
        while True:
            try:
                await self.parse()
                # TODO: Мне кажется можно изменить структуру так, чтобы это было хотя бы немного более... элегантно?
                if self.sender is not None:
                    await self.sender.send_data()
            finally:
                await asyncio.sleep(settings.parser.wait_interval)

    @staticmethod
    async def start():
        parser = Parser()
        try:
            await parser.start_parsing()
        finally:
            if parser.driver is not None:
                parser.driver.quit()
