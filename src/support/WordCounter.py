from support.configuration import SRC_FOLDER, config, WORD_COUNTER_FILEPATH
import os
import json
from collections import Counter
import logging

logger = logging.getLogger('support.WordCounter')

class WordCounter:
    instance = None
    WORD_COUNTER_FILEPATH = WORD_COUNTER_FILEPATH
    
    @classmethod
    def set_word_counter_filepath(cls, new_path):
        cls.WORD_COUNTER_FILEPATH = new_path
    
    def __new__(cls,*args, **kwargs):
        if cls.instance:
            return cls.instance
        else:
            cls.instance = super().__new__(cls,*args, **kwargs)
            return cls.instance        

    def __init__(self) -> None:
        with open(WordCounter.WORD_COUNTER_FILEPATH, "r") as f:
            data = json.load(f)
            counter: Counter = Counter(data)
        self.counter: Counter = counter

    def add_word(self, word):
        self.counter[word] += 1

    def dump_counter(self):
        try:
            logger.info("Saving word counter cache...")
            with open(WordCounter.WORD_COUNTER_FILEPATH, "w") as f:
                json.dump(self.counter, f)
                logger.info("Saved word counter successfully")
                return 1
        except Exception as e:
            logger.info("Something went wrong saving word counter")
            logger.error(e)
            traceback.print_exc()
            return 0
