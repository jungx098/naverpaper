#!/usr/bin/env python3
"""Module configuring logging."""

import logging
import logging.handlers
from logging import Handler


class CustomFormatter(logging.Formatter):
    """Custom formatter for logging."""

    grey = "\x1b[38;20m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    format_simple = "%(asctime)s %(levelname)-8s %(message)s"
    format_detail = (
        "%(asctime)s %(levelname)-8s %(name)-16s: %(message)s "
        "(%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format_simple + reset,
        logging.INFO: blue + format_simple + reset,
        logging.WARNING: yellow + format_simple + reset,
        logging.ERROR: red + format_simple + reset,
        logging.CRITICAL: bold_red + format_simple + reset,
    }

    FILE_FORMATS = {
        logging.DEBUG: grey + format_detail + reset,
        logging.INFO: blue + format_detail + reset,
        logging.WARNING: yellow + format_detail + reset,
        logging.ERROR: red + format_detail + reset,
        logging.CRITICAL: bold_red + format_detail + reset,
    }

    def __init__(self, file: bool = False):
        super().__init__()
        if file is False:
            self.format_dict = CustomFormatter.FORMATS
        else:
            self.format_dict = CustomFormatter.FILE_FORMATS

    def format(self, record):
        formatter = logging.Formatter(self.format_dict.get(record.levelno))
        return formatter.format(record)


def init_logger(console_logging_level: int = logging.WARNING,
                file_logging_level: int = logging.WARNING,
                filename: str | None = None):
    """Function initializing logger."""

    handlers = []

    console_handler: Handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter())
    console_handler.setLevel(console_logging_level)

    handlers.append(console_handler)

    if filename is not None:
        file_handler: Handler = logging.handlers.TimedRotatingFileHandler(
            filename,
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setFormatter(CustomFormatter(file=True))
        file_handler.setLevel(file_logging_level)

        handlers.append(file_handler)

    # Remove all root logger handler.
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    logging.basicConfig(
        level=min(console_logging_level, file_logging_level),
        handlers=handlers,
    )


if __name__ == "__main__":
    logging.critical("Initial Root Logger Level: %d",
                     logging.root.getEffectiveLevel())

    logging.debug("DEBUG Message")
    logging.info("INFO Message")
    logging.warning("WARNING Message")  # Default logging level
    logging.error("ERROR Message")
    logging.critical("CRITICAL Message")

    logging.critical("Initial Logger List: %d",
                     len(logging.Logger.manager.loggerDict))
    for i, l in enumerate(logging.Logger.manager.loggerDict.values()):
        assert isinstance(l, logging.Logger)
        logging.critical("%d: %s", i, l.name)

    logging.critical("Instantiate a logger: %s", __name__)
    logger = logging.getLogger(__name__)

    logger.critical("Initialize logger")
    init_logger(logging.INFO, logging.DEBUG, "./foo.txt")

    logger.info("Logger List: %d",
                len(logging.Logger.manager.loggerDict.values()))
    for i, l in enumerate(logging.Logger.manager.loggerDict.values()):
        assert isinstance(l, logging.Logger)
        logger.info("%d: %s", i, l.name)

    logger.critical("Initial Root Logger Level: %d",
                    logger.getEffectiveLevel())

    logger.debug("DEBUG Message")
    logger.info("INFO Message")
    logger.warning("WARNING Message")
    logger.error("ERROR Message")
    logger.critical("CRITICAL Message")
