import asyncio
import logging

from app_container import AppContainer
from log import init_logging


async def main() -> None:
    init_logging()
    logger = logging.getLogger(__name__)
    app = AppContainer()

    try:
        await app.run()
    except KeyboardInterrupt:
        logger.info("Клиент закрыт")
    except Exception as e:
        logger.exception(f"Ошибка клиента: {e}")


if __name__ == '__main__':
    asyncio.run(main())
