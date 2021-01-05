from support.configuration import USERS_CFG_FILEPATH, WORD_COUNTER_FILEPATH, CACHE_FILEPATH
import json
import os
from typing import List, Tuple
from collections import Counter
from model.models import SearchConfigs, Show
from support import WordCounter
from logic.logic import EpisodeHandler

class AnalyticsBackend:

    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance:
            return cls.instance
        else:
            cls.instance = super().__new__(cls)
            return cls.instance        

    def __init__(self, episode_handler: EpisodeHandler) -> None:
        self.show = episode_handler.show
        self.word_counter = episode_handler.word_counter

    def get_users_total_n(self) -> int:
        return len(SearchConfigs.user_data)

    def get_word_counter_top_n(self, n: int) -> List[Tuple[str, int]]:
        return self.word_counter.counter.most_common(n)

    def get_episodes_total_n(self) -> int:
        return len(self.show.get_episode_ids())