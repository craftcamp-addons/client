import asyncio
import logging
from pathlib import Path

from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from parser.xpaths import user_header_xpath

logger = logging.getLogger(__name__)


class BasicLogInImpl:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    async def log_in(self, timeout: int) -> bool:
        self.driver.get("https://web.whatsapp.com")
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, user_header_xpath))
            )
            logger.info("Успешный вход")
            return True
        except TimeoutException:
            logger.error("Не удалось войти, попробуйте еще раз")
            return False
        except Exception as e:
            logger.error(e)
            raise e
