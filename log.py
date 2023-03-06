import logging

from config import settings


def init_logging():
    logging.basicConfig(level=settings.logging.level, format=settings.logging.format, datefmt=settings.logging.datefmt)
    logging.getLogger("nats.aio.client").setLevel(logging.FATAL)
    for ignored in settings.logging.ignored:
        logging.getLogger(ignored).setLevel(logging.WARNING)
