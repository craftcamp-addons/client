import base64
import logging
from pathlib import Path

from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from parser.xpaths import user_header_xpath, qr_code_xpath

logger = logging.getLogger(__name__)


class BasicLogInImpl:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def log_in(self, timeout: int, screenshot_filename: Path) -> bool:
        self.driver.get("https://web.whatsapp.com")
        try:
            qr_code = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, qr_code_xpath))
            )
            canvas_base64 = self.driver.execute_script("return arguments[0].toDataURL('image/png').substring(21);",
                                                       qr_code)
            screenshot_filename.write_bytes(base64.b64decode(canvas_base64))
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
