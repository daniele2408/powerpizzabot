from typing import Dict, List
from support.configuration import CACHE_FILEPATH
from model.models import Episode
import traceback
import json
import logging
import os
from functools import wraps

logger = logging.getLogger("support.Cacher")

class Cacher:

    @classmethod
    def cache_decorator(cls, func):
        @wraps(func)
        def wrapper_cache_decorator(*args, **kwargs):
            try:
                with open(CACHE_FILEPATH, "r") as cachefile:
                    cache = json.load(cachefile)
                cache = {cache_ep_data["episode_id"]:Episode.from_dict(cache_ep_data) for cache_ep_data in cache}
                logger.info("Cache HIT")
            except (IOError, ValueError):
                logger.info("Cache MISS")
                traceback.print_exc()
                cache = func(*args, **kwargs)

            if not os.path.exists(CACHE_FILEPATH):
                with open(CACHE_FILEPATH, "w") as cachefile:
                    json.dump(cls.marshal_episodes_list(cache), cachefile)

            return cache

        return wrapper_cache_decorator

    @classmethod
    def marshal_episodes_list(cls, episodes: Dict[str, Episode]) -> List[Dict]:
        return [episode.to_dict() for episode in episodes.values()]


    @classmethod
    def cache_updater(cls, new_episodes: Dict[str, Episode]) -> None:

        try:
            with open(CACHE_FILEPATH, "r") as cachefile:
                data = json.load(cachefile)
            for ep in cls.marshal_episodes_list(new_episodes):
                data.append(ep)
            with open(CACHE_FILEPATH, "w") as cachefile:
                json.dump(data, cachefile)
                logger.info("Cache updated properly")
        except (IOError, ValueError):
            logger.error("Cache update failed.")
            traceback.print_exc()
