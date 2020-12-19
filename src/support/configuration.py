import pathlib
import os
import configparser
from typing import Set, Tuple

SRC_FOLDER = pathlib.Path(__file__).parent.parent.absolute()
config = configparser.ConfigParser()

if os.environ.get("PPB_ENV") == "prod":
    config.read(os.path.join(SRC_FOLDER, 'config', "config_prod.ini"))
elif os.environ.get("PPB_ENV") == "test":
    config.read(os.path.join(SRC_FOLDER, 'config', "config.ini"))
else:
    config.read(os.path.join(SRC_FOLDER, 'config', "config.ini"))
    # raise ValueError("PPB_ENV not populated")  # fic test

LOG_FILEPATH = os.path.join(SRC_FOLDER, config["PATH"].get("LOGGER_FILEPATH"))
CACHE_FILEPATH: str = os.path.join(SRC_FOLDER, config["PATH"].get("CACHE_FILEPATH"))
WORD_COUNTER_FILEPATH: str = os.path.join(SRC_FOLDER, config["PATH"].get("WORD_COUNT_FILEPATH"))
LIST_OF_ADMINS: Set[int] = set(
    [int(admin_id) for key, admin_id in config.items("ADMINS")]
)
MINIMUM_SCORE = 50

RAW_EP_FILEPATH = os.path.join(SRC_FOLDER, config["TEST"].get("RAW_EP_FILEPATH"))
PROCD_EP_FILEPATH = os.path.join(SRC_FOLDER, config["TEST"].get("PROCD_EP_FILEPATH"))
SNIPPET_TXT_FILEPATH = os.path.join(SRC_FOLDER, config["TEST"].get("SNIPPET_TXT_FILEPATH"))
