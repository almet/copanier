import logging
import logging.handlers
import os

from . import config

request_logger = logging.getLogger("request_logger")
request_logger.setLevel(logging.INFO)
request_logger.addHandler(
    logging.handlers.TimedRotatingFileHandler(
        os.path.join(config.LOG_ROOT, "copanier-requests.log"),
        when="midnight",
        backupCount=10,
    )
)
