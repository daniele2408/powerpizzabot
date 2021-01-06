import pathlib
import os
import configparser
from typing import Set, Tuple

SRC_FOLDER = pathlib.Path(__file__).parent.parent.absolute()
config = configparser.ConfigParser()

if os.environ.get("PPB_ENV") == "prod":
    config.read(os.path.join(SRC_FOLDER, "config", "config_prod.ini"))
elif os.environ.get("PPB_ENV") in set(["test", "unittest"]):
    config.read(os.path.join(SRC_FOLDER, "config", "config.ini"))
else:
    raise ValueError("PPB_ENV not populated")  # fic test

LOG_FILEPATH = os.path.join(SRC_FOLDER, config["PATH"].get("LOGGER_FILEPATH"))

CACHE_FILEPATH: str = os.path.join(SRC_FOLDER, config["PATH"].get("CACHE_FILEPATH"))

WORD_COUNTER_FILEPATH: str = os.path.join(
    SRC_FOLDER, config["PATH"].get("WORD_COUNT_FILEPATH")
)
CALL_COUNTER_FILEPATH: str = os.path.join(
    SRC_FOLDER, config["PATH"].get("CALL_COUNT_FILEPATH")
)

USERS_CFG_FOLDER: str = os.path.join(
    SRC_FOLDER,
    config["PATH"].get("USERS_CFG_FOLDER")
)
USERS_CFG_FILEPATH: str = os.path.join(
    USERS_CFG_FOLDER,
    config["PATH"].get("USERS_CFG_FILENAME")
)
LIST_OF_ADMINS: Set[int] = set(
    [int(admin_id) for key, admin_id in config.items("ADMINS")]
)
MINIMUM_SCORE = 50

RAW_EP_FILEPATH = os.path.join(SRC_FOLDER, config["TEST"].get("RAW_EP_FILEPATH"))
PROCD_EP_FILEPATH = os.path.join(SRC_FOLDER, config["TEST"].get("PROCD_EP_FILEPATH"))
THREE_RAW_EPS_FILEPATH = os.path.join(
    SRC_FOLDER, config["TEST"].get("THREE_RAW_EPS_FILEPATH")
)
SNIPPET_TXT_FILEPATH = os.path.join(
    SRC_FOLDER, config["TEST"].get("SNIPPET_TXT_FILEPATH")
)

CREATOR_TELEGRAM_ID = config["SECRET"].get("CREATOR_TELEGRAM_ID")