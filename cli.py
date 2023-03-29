import contextlib
import logging
import optparse
import os
import re
from pathlib import Path
from typing import Iterator, Optional

import msgpack
import zmq
from pydantic import BaseModel

import log


class StatusModel(BaseModel):
    total: int
    completed: int
    error: int

    def __str__(self):
        return f"Status:\n\tTotal:\t{self.total}\n\tCompleted:\t{self.completed}\n\tError:\t{self.error}\n"


class ResponseModel(BaseModel):
    status: str
    command: Optional[str]

    def __str__(self):
        return f"\nStatus: {self.status}\n\tCommand: {self.command}\n"


@contextlib.contextmanager
def create_socket(ctx: zmq.Context) -> Iterator[zmq.Socket]:
    comm_dir = Path(os.getcwd()) / "comm"
    if not comm_dir.exists() or not (comm_dir / 'port').exists():
        raise FileNotFoundError("Пожалуйста, запустите парсер и поместите данный файл в папку с парсером")

    port: int = -1
    try:
        port = int((comm_dir / "port").read_text())
    except Exception:
        raise RuntimeError(f"Пожалуйста, не трогайте файл {comm_dir.absolute() / 'port'}")
    socket = ctx.socket(zmq.REQ)
    socket.set(zmq.RCVTIMEO, 10000)
    socket.set(zmq.SNDTIMEO, 10000)
    with socket.connect(f"tcp://127.0.0.1:{port}"):
        yield socket


def download(ctx: zmq.Context, filename: str, password: str):
    logger = logging.getLogger("DOWNLOAD")
    with create_socket(ctx) as socket:  # type: zmq.Socket
        socket.send(
            msgpack.packb({"command": "download", "data": {"filename": filename, "password": password}}))

        response = ResponseModel.parse_obj(msgpack.unpackb(socket.recv()))
        if response.status == "ERR":
            logger.error(response)
        else:
            logger.info(response)


def upload(ctx: zmq.Context, filename: str):
    logger = logging.getLogger("UPLOAD")
    phone_regex: re.Pattern = re.compile(r"(\+?)[1-9][0-9]{7,14}")

    with create_socket(ctx) as socket:  # type: zmq.Socket
        buffer = []

        def send_buffer():
            socket.send(msgpack.packb({"command": "upload", "data": buffer}))
            response: ResponseModel = ResponseModel.parse_obj(msgpack.unpackb(socket.recv()))
            if response.status == "ERR":
                raise RuntimeError(f"Ошибка сервера: {response.command}")

        with open(Path(filename).absolute(), 'r') as file:
            for line in file:
                if phone_regex.match(line):
                    if len(buffer) >= 16:
                        send_buffer()
                        buffer.clear()
                    else:
                        buffer.append(line)
                else:
                    logger.warning(f"Номера: {buffer} не загружены")
                    buffer.clear()

            if len(buffer) > 0:
                send_buffer()


def status(ctx: zmq.Context):
    logger = logging.getLogger("STATUS")
    with create_socket(ctx) as socket:  # type: zmq.Socket
        socket.send(msgpack.packb({"command": "status"}))
        message = msgpack.unpackb(socket.recv())
        try:
            status_message = StatusModel.parse_obj(message)
            logger.info(status_message)
        except ValueError:
            response = ResponseModel.parse_obj(message)
            logger.error(response)


def main():
    log.init_logging()
    logger = logging.getLogger("MAIN")
    main_parser = optparse.OptionParser(epilog="Используйте одну из опций")

    download_group = optparse.OptionGroup(main_parser, "Опции загрузки архива с фотографиями")
    download_group.add_option("-d", "--download", action="store_true", dest="download")
    download_group.add_option("-a", "--archive", dest="archive", help="Название конечного архива (.zip)")
    download_group.add_option("-p", "--password", dest="password", default="", help="Пароль для конечного архива")

    upload_group = optparse.OptionGroup(main_parser, "Опции подгрузки номеров")
    upload_group.add_option("-u", "--upload", action="store_true", dest="upload")
    upload_group.add_option("-f", "--filename", dest="filename",
                            help="Название файла из которого будут выгружены номера")

    main_parser.add_option("-s", "--status", dest="status", action="store_true",
                           help="Получить статус парсинга (может пока не очень работать)")

    main_parser.add_option_group(download_group)
    main_parser.add_option_group(upload_group)

    (options, arguments) = main_parser.parse_args()
    if not any([options.download, options.upload, options.status]):
        main_parser.print_help()
        return

    ctx = zmq.Context()
    try:
        if options.download:
            if not options.archive:
                main_parser.print_help()
                print("ERROR: Аргумент archive обязателен")
                return
            download(ctx, options.archive, options.password)
            return
        if options.upload:
            if not options.filename:
                main_parser.print_help()
                print("ERROR: Аргумент filename обязателен")
                return
            upload(ctx, options.filename)
            return
        if options.status:
            status(ctx)
            return

        main_parser.print_help()
    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    main()
