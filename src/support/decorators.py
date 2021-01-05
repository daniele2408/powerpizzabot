from telegram import Update, Bot, ParseMode, ChatAction
from telegram.ext import CallbackContext
from typing import Callable
from functools import wraps
from support.configuration import LIST_OF_ADMINS
import logging

logger = logging.getLogger("decorators")

def send_typing_action(func: Callable) -> Callable:
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(self, update: Update, context: CallbackContext, *args, **kwargs):
        if update.effective_message:
            context.bot.send_chat_action(
                chat_id=update.effective_message.chat_id, action=ChatAction.TYPING
            )
            return func(self, update, context, *args, **kwargs)
        else:
            return func(self, update, context, *args, **kwargs)

    return command_func


def restricted(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        if update.effective_user:
            user_id = update.effective_user.id
            if user_id not in LIST_OF_ADMINS:
                logger.info(f"Unauthorized access denied for {user_id}")
                return
            return func(update, context, *args, **kwargs)
        else:
            logger.info("User is None, can't identify user, access denied")

    return wrapped

def cache_counter_decorator(cls):
    @wraps(cls)
    def wrapper_cache_counter_decorator():
        # Do something before
        try:
            with open(CACHE_COUNTER_FILEPATH, "r") as cachefile:
                cache = json.load(cachefile)
            logger.info("Cache HIT")
            instance = cls(cache)
        except (IOError, ValueError):
            logger.info("Cache MISS")
            traceback.print_exc()
            instance = cls()

        # Do something after

        if not os.path.exists(CACHE_FILEPATH):
            with open(CACHE_FILEPATH, "w") as cachefile:
                json.dump(instance.counter, cachefile)

        return instance

    return wrapper_cache_decorator    