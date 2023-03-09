import asyncio
import logging
import optparse
from pathlib import Path

from app_container import AppContainer
from config import settings
from log import init_logging


async def main() -> None:
    optparser = optparse.OptionParser()
    optparser.add_option('-c', '--config', dest='config', default='settings.json', type="string", help='config file')
    options, args = optparser.parse_args()

    if options.config:
        settings.configure(Path(options.config).absolute())

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
