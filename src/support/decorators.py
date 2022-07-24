import json
import os
import traceback

from telegram import Update, Bot, ParseMode, ChatAction
from telegram.ext import CallbackContext
from typing import Callable
from functools import wraps
from support.configuration import LIST_OF_ADMINS
from model.custom_exceptions import UpdateEffectiveMsgNotFound
import logging
from hashlib import sha1
import math

logger = logging.getLogger("decorators")

def hash_chat_id(func: Callable) -> Callable:
    
    @wraps(func)
    def wrapped_func(cls, chat_id: int, *args, **kwargs):
        try:
            hashed_chat_id = sha1(bytes(abs(chat_id))).hexdigest()
            return func(cls, hashed_chat_id, *args, **kwargs)
        except MemoryError as me:
            logger.error(f"Chat_id {chat_id} caused a Memory Error, gonna hash bytes(1): {me}")
            return func(cls, sha1(bytes(1)).hexdigest(), *args, **kwargs)

    return wrapped_func

def check_effective_message(func: Callable) -> Callable:
    
    @wraps(func)
    def wrapped_func(self, update: Update, context: CallbackContext):
        if update.effective_message:
            func(self, update, context)
        else:
            raise UpdateEffectiveMsgNotFound(f"update.effective_message None for {func.__name__}")
    
    return wrapped_func

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
