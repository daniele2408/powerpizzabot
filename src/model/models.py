import os
import json
import pathlib
import traceback
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import re
import logging
from support.configuration import CACHE_FILEPATH, USERS_CFG_FOLDER, config, USERS_CFG_FILEPATH
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger("model.models")

class EpisodeTopic:
    def __init__(self, label: str, url: str) -> None:
        self.label = label
        self.url = url

class Episode:
    def __init__(
        self,
        episode_id: str,
        title: str,
        published_at: str,
        site_url: str,
        description_raw: str,
    ):
        self.episode_id = episode_id
        self.title = title
        self.published_at = published_at
        self.site_url = site_url
        self.description_raw = description_raw
        self.topics: List[EpisodeTopic] = []

    def to_dict(self) -> Dict[str, Union[str, List[Dict[str, str]]]]:
        return {
            "episode_id": self.episode_id,
            "title": self.title,
            "published_at": self.published_at,
            "site_url": self.site_url,
            "description_raw": self.description_raw,
            "topics": [
                {"label":topic.label, "url":topic.url} for topic in self.topics
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict):
        new_instance = cls(
            data["episode_id"],
            data["title"],
            data["published_at"],
            data["site_url"],
            data["description_raw"],
        )
        new_instance.topics = [EpisodeTopic(topic["label"], topic["url"]) for topic in data["topics"]]
        return new_instance

    def populate_topics(self) -> None:
        ls_tuples_label_url = re.findall(
            "((\\n|\\r\\n).+(\\n|\\r\\n)http(|s).+(\\n|\\r\\n|$))", self.description_raw
        )

        for label_url_tuple in ls_tuples_label_url:
            procd_tuple = [
                el.strip("\r")
                for el in label_url_tuple[0].split("\n")
                if el and el != "\r"
            ]

            if len(procd_tuple) != 2:
                # procd_tuple = [el for el in label_url_tuple[0].split('\r\n') if el]
                # if len(procd_tuple) != 2:
                logger.error(f"Couldn't process tuple {procd_tuple} properly.")

            else:
                label, url = procd_tuple
                self.topics.append(EpisodeTopic(label, url))

class Show:
    def __init__(self, show_id: str) -> None:
        self.show_id = show_id
        self._episodes: Dict[str, Episode] = dict()

    @property
    def episodes(self) -> Dict[str, Episode]:
        return self._episodes

    # https://github.com/python/mypy/issues/1465
    @episodes.setter  # type: ignore
    def set_episodes(self, episodes: Dict[str, Episode]) -> None:
        # not a proper setter implementation, more like add, fix it
        for episode in episodes.values():
            self._episodes[episode.episode_id] = episode

    def get_episode(self, episode_id: str) -> Episode:
        return self._episodes[episode_id]

    def get_episode_ids(self) -> Set[str]:
        return set(self._episodes.keys())

class UserConfig:
    def __init__(self, n, m):
        self.n = n
        self.m = m


class SearchConfigs:

    DATE_FORMAT = "%Y%m%dT%H%M%S"
    user_data: Dict[int, UserConfig] = defaultdict(lambda: UserConfig(5, 1))
    DUMP_FOLDER = USERS_CFG_FOLDER
    USERS_CFG_FILEPATH = USERS_CFG_FILEPATH

    @classmethod
    def get_user_cfg(cls, chat_id: int) -> UserConfig:
        return cls.user_data[chat_id]

    @classmethod
    def get_user_show_first_n(cls, chat_id: int) -> int:
        return cls.user_data[chat_id].n

    @classmethod
    def get_user_show_min_threshold(cls, chat_id: int) -> int:
        return cls.user_data[chat_id].m

    @classmethod
    def check_if_same_value(cls, chat_id: int, value: int, field: str) -> bool:
        if field == "n" and cls.user_data[chat_id].n == value:
            return True
        elif field == "m" and cls.user_data[chat_id].m == value:
            return True
        elif field not in set(["n", "m"]):
            raise ValueError("Wrong config field, choose one between (n,m)")
        else:
            return False

    @classmethod
    def set_user_cfg(cls, chat_id: int, value: int, field: str) -> None:
        if field == "n":
            cls.user_data[chat_id].n = value
        elif field == "m":
            cls.user_data[chat_id].m = value
        else:
            raise ValueError("User config field not valid.")

    @classmethod
    def normalize_user_data(cls) -> Dict:
        data = dict()
        for chat_id, user_cfg in cls.user_data.items():
            data[chat_id] = {"n": user_cfg.n, "m": user_cfg.m}

        return data

    @classmethod
    def dump_data(cls, *args) -> int:
        cls.clean_folder()
        filename_backup = f"backup{datetime.strftime(datetime.now(), cls.DATE_FORMAT)}.json"
        filepath = cls.USERS_CFG_FILEPATH
        filepath_backup = os.path.join(cls.DUMP_FOLDER, filename_backup)
        logger.info(f"I'm doing a dump for usr cfg data, backup {filename_backup}.")
        try:
            with open(filepath_backup, "w") as f:
                json.dump(cls.normalize_user_data(), f)
            with open(filepath, "w") as f:
                json.dump(cls.normalize_user_data(), f)
            return 1
        except Exception as e:
            logger.error(e)
            traceback.print_exc()
            return 0

    @classmethod
    def list_backup_files(cls):
        for filename in os.listdir(cls.DUMP_FOLDER):
            if filename.startswith('backup'):
                yield filename

    @classmethod
    def clean_folder(cls) -> None:
        logger.info("Removing usr cfg older than 3 days...")
        to_delete = set()
        for filename in cls.list_backup_files():
            year = int(filename[6:10])
            month = int(filename[10:12])
            day = int(filename[12:14])
            hour = int(filename[15:17])
            minute = int(filename[17:19])
            second = int(filename[19:21])

            timestamp = datetime(year, month, day, hour, minute, second)

            if (datetime.now() - timestamp).days >= 3:
                to_delete.add(os.path.join(cls.DUMP_FOLDER, filename))

        for file_to_delete in to_delete:
            os.remove(file_to_delete)
    

    @classmethod
    def get_newest_backup(cls):
        files = os.listdir(cls.DUMP_FOLDER)
        paths = [os.path.join(cls.DUMP_FOLDER, basename) for basename in files]
        return max(paths, key=os.path.getctime)

    @classmethod
    def init_data(cls) -> None:
        try:
            last_backup_file = cls.get_newest_backup()
            with open(
                last_backup_file, "r"
            ) as f:
                data = json.load(f)

                for chat_id, payload in data.items():
                    cls.user_data[int(chat_id)] = UserConfig(int(payload["n"]), int(payload["m"]))

        except Exception as e:
            logger.error(e)
            traceback.print_exc()
