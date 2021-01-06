from support.configuration import CALL_COUNTER_FILEPATH
from collections import Counter
import json
from time import time
import traceback
import logging

logger = logging.getLogger('support.CallCounter')

class CallCounter():

    instance = None
    CALL_COUNTER_FILEPATH = CALL_COUNTER_FILEPATH
    
    @classmethod
    def set_call_counter_filepath(cls, new_path):
        cls.CALL_COUNTER_FILEPATH = new_path
    
    def __new__(cls,*args, **kwargs):
        if cls.instance:
            return cls.instance
        else:
            cls.instance = super().__new__(cls,*args, **kwargs)
            return cls.instance        

    def __init__(self) -> None:
        with open(CallCounter.CALL_COUNTER_FILEPATH, "r") as f:
            data = json.load(f)
            counter: Counter = Counter(data)
        self.counter: Counter = counter

    def add_call(self) -> None:
        minute_timestamp: int = int(time()) // 3600 * 3600

        self.counter[str(minute_timestamp)] += 1

    def dump_data(self, *args) -> int:
        try:
            logger.info("Saving call counter cache...")
            with open(CallCounter.CALL_COUNTER_FILEPATH, "w") as f:
                json.dump(self.counter, f)
                logger.info("Saved call counter successfully")
                return 1
        except Exception as e:
            logger.info("Something went wrong saving call counter")
            logger.error(e)
            traceback.print_exc()
            return 0