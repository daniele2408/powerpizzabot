import pathlib
import os
import configparser
from typing import Set, Tuple

SRC_FOLDER = pathlib.Path(__file__).parent.parent.absolute()
config = configparser.ConfigParser()

if os.environ.get("PPB_ENV") == "prod":
    config.read(os.path.join(SRC_FOLDER, 'config', "config_prod.ini"))
else:
    config.read(os.path.join(SRC_FOLDER, 'config', "config.ini"))

LOG_FILEPATH = os.path.join(SRC_FOLDER, config["PATH"].get("LOGGER_FILEPATH"))
CACHE_FILEPATH: str = os.path.join(SRC_FOLDER, config["PATH"].get("CACHE_FILEPATH"))
WORD_COUNTER_FILEPATH: str = os.path.join(SRC_FOLDER, 'storage', config["PATH"].get("WORD_COUNT_FILENAME"))
LIST_OF_ADMINS: Set[int] = set(
    [int(admin_id) for key, admin_id in config.items("ADMINS")]
)
MINIMUM_SCORE = 50
