import logging
from abc import ABC


class BaseSenderService(ABC):
    logger: logging.Logger

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def send_data(self):
        raise NotImplementedError
