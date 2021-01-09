from logic.logic import EpisodeHandler
from support.configuration import USERS_CFG_FILEPATH, WORD_COUNTER_FILEPATH, CACHE_FILEPATH
from support import CallCounter
import json
import os
from typing import List, Tuple, Dict
from collections import Counter
from model.models import SearchConfigs, Show
from support import WordCounter
from logic.logic import EpisodeHandler
from itertools import groupby

class AnalyticsBackend:

    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance:
            return cls.instance
        else:
            cls.instance = super().__new__(cls)
            return cls.instance        

    def __init__(self, episode_handler: EpisodeHandler, call_counter: CallCounter) -> None:
        self.show = episode_handler.show
        self.word_counter = episode_handler.word_counter
        self.call_counter = call_counter

    def get_users_total_n(self) -> int:
        return len(SearchConfigs.user_data)

    def get_word_counter_top_n(self, n: int) -> List[Tuple[str, int]]:
        return self.word_counter.counter.most_common(n)

    def get_episodes_total_n(self) -> int:
        return len(self.show.get_episode_ids())
    
    @staticmethod
    def is_timestamp_between(date: int, from_: int, to: int) -> bool:
        return date >= from_ and date <= to

    def get_daily_searches(self, from_: int, to: int) -> Counter:

        # have to convert in minutes
        from_ = (from_ // 3600 * 3600)
        to = to // 3600 * 3600 + (3600 * 24 - 1)
        
        counter_time_interval = {int(timestamp): c for timestamp, c in self.call_counter.counter.items() if self.is_timestamp_between(int(timestamp), from_, to)}

        seconds_in_a_day = 60 * 60 * 24
        func_flat_days = lambda x: x // seconds_in_a_day * seconds_in_a_day
        sorted_timestamps = sorted(counter_time_interval.keys(), key=func_flat_days)
        
        dict_groupby: Counter = Counter()
        for timestamp, group in groupby(sorted_timestamps, key=func_flat_days):
            dict_groupby[func_flat_days(timestamp)] += sum([counter_time_interval[timestamp] for timestamp in group])

        return dict_groupby

        


