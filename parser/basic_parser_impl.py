import logging
from io import BytesIO
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from database import Number, NumberStatus
from parser.xpaths import error_button_xpath, on_profile_second_xpath, business_photo_xpath, photo_xpath


class BasicParserImpl:
    url: str
    webdriver: webdriver.Chrome
    wait_timeout: int
    logger: logging.Logger
    photos_dir: Path

    def __init__(self, driver: webdriver.Chrome, url: str, webdriver_timeout: int, photos_dir: str,
                 logger: logging.Logger = logging.getLogger("Parser")):
        super(BasicParserImpl, self).__init__()
        self.url = url
        self.wait_timeout = webdriver_timeout
        self.logger = logger
        self.photos_dir = Path(photos_dir)
        self.webdriver = driver

    async def save_photo(self, element: WebElement, number: Number):
        image = Image.open(BytesIO(element.screenshot_as_png))

        # image = Image.open(self.photos_dir / (number.number + ".png"))
        image_bytes = BytesIO()
        image.resize((image.size[0] // 2, image.size[1] // 2), Image.ANTIALIAS).save(
            image_bytes, "PNG", optimise=True, quality=50)

        number.image = image_bytes.getvalue()
        self.logger.info(f"Фоточку {number.number} сохранил")

    async def parse(self, number: Number) -> None:
        """
        1. Parse number
        2. Set status of the parsing accordingly to the rule:
            Parsing status: 0 - not started, 1 - parsing, 2 - finished, 3 - error. Secondcheck falls to 0 status
        """
        try:
            number.status = NumberStatus.IN_WORK
            self.webdriver.get(self.url.format(number.number))
            try:
                WebDriverWait(self.webdriver, self.wait_timeout).until(
                    EC.element_to_be_clickable((By.XPATH, error_button_xpath)))
                number.status = NumberStatus.ERROR
            except TimeoutException:
                profile_button = WebDriverWait(self.webdriver, self.wait_timeout).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, '_2YnE3')))
                profile_button.click()

                try:
                    second_profile_button = self.webdriver.find_element(
                        By.XPATH, on_profile_second_xpath)
                    second_profile_button.click()
                except NoSuchElementException:
                    second_profile_button = self.webdriver.find_element(
                        By.XPATH, business_photo_xpath)
                    second_profile_button.click()

                photo = WebDriverWait(self.webdriver, self.wait_timeout / 2).until(
                    EC.element_to_be_clickable((By.XPATH, photo_xpath)))
                await self.save_photo(photo, number)
                number.status = NumberStatus.COMPLETED

        except Exception:
            self.logger.error("Parsing error")
            if number.status == NumberStatus.SECONDCHECK:
                number.status = NumberStatus.ERROR
            else:
                number.status = NumberStatus.SECONDCHECK
