#!/usr/bin/env python3

import logging
import logging.handlers


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


def init_logger(verbose: int = 0):
    """Function initializing logger."""

    LEVEL = {
        5: logging.DEBUG,
        4: logging.INFO,
        3: logging.WARNING,
        2: logging.ERROR,
        1: logging.CRITICAL,
    }

    level = logging.CRITICAL + 1
    if verbose > 5:
        level = logging.DEBUG
    elif verbose > 0:
        level = LEVEL[verbose]

    ch = logging.StreamHandler()
    ch.setFormatter(CustomFormatter())

    fh = logging.handlers.TimedRotatingFileHandler(
        "./log.txt",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    fh.setFormatter(CustomFormatter(file=True))

    # Remove all root logger handler.
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    logging.basicConfig(
        level=level,
        handlers=[ch, fh],
    )


if __name__ == "__main__":
    logging.critical("Initial Root Logger Level: %d",
                     logging.root.getEffectiveLevel())

    logging.debug("DEBUG Message")
    logging.info("INFO Message")
    logging.warning("WARNING Message")
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
    init_logger(5)

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
