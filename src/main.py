import configparser
import json
import logging
import os
import pathlib
import re
import sys
import traceback
from collections import Counter, defaultdict, namedtuple
from datetime import datetime
from functools import lru_cache, wraps
from threading import Thread

from fuzzywuzzy import fuzz
from requests import get
from telegram import ChatAction, ParseMode, Update
from telegram.bot import Bot
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Defaults,
    Dispatcher,
    Filters,
    MessageHandler,
    Updater,
)
from telegram.ext import messagequeue as mq
from telegram.ext.updater import Updater as extUpdater
from telegram.utils.request import Request
from unidecode import unidecode

from support.TextRepo import TextRepo

from model.models import SearchConfigs, Show
from logic.logic import EpisodeHandler
from support.configuration import SRC_FOLDER, config, LOG_FILEPATH, CACHE_FILEPATH, LIST_OF_ADMINS, MINIMUM_SCORE, CREATOR_TELEGRAM_ID
from support.apiclient import SpreakerAPIClient
from support.bot_support import MQBot, FacadeBot
from support.WordCounter import WordCounter
from support.bot_support import error_callback
from support.decorators import restricted

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("main_bot")
handler = logging.handlers.RotatingFileHandler(
              LOG_FILEPATH, maxBytes=100000, backupCount=5)
handler.setFormatter(logging.Formatter("{asctime} - {name} - {levelname} - {message}", style='{'))

logger.addHandler(handler)

def main():

    init_message_config = f"Booting up using {os.environ.get('PPB_ENV')} version"
    logger.info(init_message_config)

    SearchConfigs.init_data()

    client = SpreakerAPIClient(config["SECRET"].get("api_token"))
    power_pizza = Show(config["POWER_PIZZA"].get("SHOW_ID"))

    TOKEN_BOT = config["SECRET"].get("bot_token")
    q = mq.MessageQueue(all_burst_limit=29, all_time_limit_ms=1017)
    request = Request(con_pool_size=8)
    testbot = MQBot(TOKEN_BOT, request=request, mqueue=q)
    updater = extUpdater(bot=testbot, use_context=True)

    for admin in LIST_OF_ADMINS:
        updater.bot.send_message(chat_id=admin, text=init_message_config)

    episode_handler = EpisodeHandler(client, power_pizza, WordCounter())
    episode_handler.add_episodes_to_show()

    facade_bot = FacadeBot(episode_handler)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("s", facade_bot.search))
    dp.add_handler(CommandHandler("top", facade_bot.set_top_results))
    dp.add_handler(CommandHandler("last", facade_bot.get_last_ep))
    dp.add_handler(CommandHandler("get", facade_bot.get_ep))
    dp.add_handler(CommandHandler("random", facade_bot.get_ep_random))
    dp.add_handler(CommandHandler("host", facade_bot.get_eps_host))
    dp.add_handler(CommandHandler("hostf", facade_bot.get_eps_host))
    dp.add_handler(CommandHandler("hosta", facade_bot.get_eps_host))
    dp.add_handler(
        CommandHandler(
            "dump", facade_bot.dump_data, filters=Filters.user(username=CREATOR_TELEGRAM_ID)
        )
    )

    # analytics commands
    dp.add_handler(CommandHandler("nu", facade_bot.get_users_total_n, filters=Filters.user(username=CREATOR_TELEGRAM_ID)))
    dp.add_handler(CommandHandler("ncw", facade_bot.get_most_common_words, filters=Filters.user(username=CREATOR_TELEGRAM_ID)))
    dp.add_handler(CommandHandler("neps", facade_bot.get_episodes_total_n, filters=Filters.user(username=CREATOR_TELEGRAM_ID)))
    dp.add_handler(CommandHandler("qry", facade_bot.get_daily_logs, filters=Filters.user(username=CREATOR_TELEGRAM_ID)))
    
    dp.add_handler(CommandHandler("memo", facade_bot.memo, filters=Filters.user(username=CREATOR_TELEGRAM_ID)))

    dp.add_handler(CommandHandler("start", facade_bot.start))
    dp.add_handler(CommandHandler("help", facade_bot.help))

    dp.add_error_handler(error_callback)

    facade_bot.schedule_jobs(dp.job_queue)

    def stop_and_restart():
        logger.info("Stop and restarting bot...")
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def kill_bot():
        logger.info("Shutting down bot...")
        updater.stop()

    @restricted
    def restart(update, context):
        result_dump = facade_bot.dump_data(update, context)

        for res_dump, name_dump in result_dump:
            update.message.reply_text(
                f"{name_dump} save " + "success." if res_dump else "fail."
            )

        update.message.reply_text("Bot is restarting...")
        Thread(target=stop_and_restart).start()

    @restricted
    def kill(update, context):
        result_dump = facade_bot.dump_data(update, context)

        for res_dump, name_dump in result_dump:
            update.message.reply_text(
                f"{name_dump} save " + "success." if res_dump else "fail."
            )

        update.message.reply_text("See you, space cowboy...")
        Thread(target=kill_bot).start()

    # handler restarter
    dp.add_handler(
        CommandHandler(
            "restart", restart, filters=Filters.user(username=CREATOR_TELEGRAM_ID)
        )
    )
    dp.add_handler(
        CommandHandler("killme", kill, filters=Filters.user(username=CREATOR_TELEGRAM_ID))
    )

    updater.start_polling()

    updater.idle()


if __name__ == "__main__":

    main()
