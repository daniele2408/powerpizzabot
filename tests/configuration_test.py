import pathlib
import os
import configparser
from typing import Set, Tuple

SRC_TEST_FOLDER = pathlib.Path(__file__).parent.absolute()
config = configparser.ConfigParser()
config.read(os.path.join(SRC_TEST_FOLDER, "config_test.ini"))

RAW_EP_FILEPATH = os.path.join(SRC_TEST_FOLDER, config["TEST"].get("RAW_EP_FILEPATH"))
PROCD_EP_FILEPATH = os.path.join(SRC_TEST_FOLDER, config["TEST"].get("PROCD_EP_FILEPATH"))
THREE_RAW_EPS_FILEPATH = os.path.join(
    SRC_TEST_FOLDER, config["TEST"].get("THREE_RAW_EPS_FILEPATH")
)
SNIPPET_TXT_FILEPATH = os.path.join(
    SRC_TEST_FOLDER, config["TEST"].get("SNIPPET_TXT_FILEPATH")
)