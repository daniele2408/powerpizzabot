import random

from telegram.ext import messagequeue as mq
from model.custom_exceptions import ValueNotValid, ValueOutOfRange, StatusCodeNot200, UpdateEffectiveMsgNotFound, ArgumentListEmpty
from model.models import SearchConfigs
from telegram import Update, Bot, ParseMode
from telegram.ext import CallbackContext
import re
import logging
import traceback
from support.TextRepo import TextRepo
from model.models import UserConfig
from logic.logic import EpisodeHandler
from support.configuration import LIST_OF_ADMINS, MINIMUM_SCORE
from support.decorators import send_typing_action, check_effective_message
from support.CallCounter import CallCounter
from typing import List, Union, Tuple, Callable
from utility.analytics import AnalyticsBackend
from math import inf
from functools import wraps
from datetime import datetime, timezone

logger = logging.getLogger("support.bot_support")

class MQBot(Bot):
    """A subclass of Bot which delegates send method handling to MQ"""

    def __init__(
        self,
        *args,
        is_queued_def: bool = True,
        mqueue: mq.MessageQueue = None,
        **kwargs,
    ) -> None:
        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or mq.MessageQueue()

    def __del__(self):
        try:
            self._msg_queue.stop()
        except Exception as e:
            logger.error(f"Error in stopping msg_queue, {e}")
            traceback.print_exc()
            pass

    @mq.queuedmessage
    def send_message(self, *args, **kwargs):
        """Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments"""
        return super(MQBot, self).send_message(*args, **kwargs)

def error_callback(update: Update, context: CallbackContext) -> None:
    try:
        # CallbackContext.error: Only present when passed to a error handler registered with, so it's not Optional here
        raise context.error  # type: ignore
    except ValueNotValid as vnv:
        logger.error(vnv)
        if update and update.effective_message:
            update.effective_message.reply_text(vnv.args[0])
    except ValueOutOfRange as voof:
        logger.error(voof)
        if update and update.effective_message:
            update.effective_message.reply_text(voof.args[0])
    except StatusCodeNot200 as scn:
        logger.error(scn)
    except UpdateEffectiveMsgNotFound as uemnf:
        logger.error(uemnf)
    except ArgumentListEmpty as ale:
        logger.error(ale)
    except Exception as e:
        logger.error(e)
        traceback.print_exc()


def handle_text_messages(update: Update, context: CallbackContext) -> None:
    if update.message:
        update.message.reply_text(TextRepo.MSG_NOT_A_CMD)


class FacadeBot:

    dict_host_order = {
        "/host": "abc",
        "/hostf": "frequency",
        "/hosta": "first_appear"
    }

    def __init__(self, episode_handler: EpisodeHandler) -> None:
        self.episode_handler = episode_handler
        self.call_counter = CallCounter()
        self.analytics = AnalyticsBackend(self.episode_handler, self.call_counter)
        self.job = None
        self.job_dump_cfg = None
        self.job_dump_wc = None
        self.job_dump_cc = None

    @staticmethod
    def is_admin(chat_id: int) -> bool:
        return chat_id in LIST_OF_ADMINS

    @send_typing_action
    @check_effective_message
    def search(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator
        chat_id: int = update.effective_message.chat_id

        is_admin = self.is_admin(chat_id)

        if not is_admin:
            self.call_counter.add_call()
        if not context.args:
            update.effective_message.reply_text(
                TextRepo.MSG_SEARCH_EMPTY_INPUT
            )
            return

        text: List[str] = context.args
        user_cfg: UserConfig = SearchConfigs.get_user_cfg(chat_id)

        message, text = self.episode_handler.search_text_in_episodes(
            " ".join(text), user_cfg.n, MINIMUM_SCORE, is_admin
        )

        update.effective_message.reply_text(
            message, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    @staticmethod
    def sanitize_digit(args, min_: Union[int, float], max_: Union[int, float]) -> int:
        join_args = " ".join(args)
        if join_args == "":
            raise ValueNotValid(TextRepo.MSG_TOP_EMPTY_INPUT)

        res = re.compile("^[0-9]+$").match(join_args)
        if res is None:
            raise ValueNotValid(TextRepo.MSG_NOT_VALID_INPUT)
        else:
            value = int(res.group(0))
            if min_ > value or max_ < value:
                raise ValueOutOfRange(TextRepo.MSG_NOT_VALID_RANGE.format(min_, max_))
            else:
                return value

    @staticmethod
    def sanitize_digit_and_subletter(args, min_: Union[int, float], max_: Union[int, float]) -> Tuple[int, str]:
        join_args = " ".join(args)
        if join_args == "":
            raise ValueNotValid(TextRepo.MSG_TOP_EMPTY_INPUT)

        res = re.compile("^[0-9]+(|[a-z])$").match(join_args)
        if res is None:
            raise ValueNotValid(TextRepo.MSG_NOT_VALID_INPUT)
        else:
            res_match = res.group(0)
            int_value = re.compile("[0-9]+").match(res_match)
            if int_value is None:
                raise ValueNotValid(TextRepo.MSG_NOT_VALID_INPUT)
            subnumber_value = re.search('[a-z]', join_args)
            subnumber_value = '' if subnumber_value is None else subnumber_value.group(0)
            value = int(int_value.group(0))
            if min_ > value or max_ < value:
                raise ValueOutOfRange(TextRepo.MSG_NOT_VALID_RANGE.format(min_, max_))
            else:
                return value, subnumber_value


    @staticmethod
    def sanitize_dates(args) -> List[int]:
        res = re.findall(r"[0-9]{6}", " ".join(args))
        if not len(res) and len(res[0]) == len(res[1]) == 6 :
            raise ValueNotValid(TextRepo.MSG_NOT_VALID_DATE)
        else:
            timestamps = list()
            for date in res:
                day = int(date[:2])
                month = int(date[2:4])
                year = int(date[4:])
                is_day = 0 < day <= 31
                is_month = 0 < month <= 12
                is_year = 0 < year <= 99
                if any({not is_day, not is_month, not is_year}):
                    raise ValueNotValid(TextRepo.MSG_NOT_VALID_DATE)
                timestamps.append(int(datetime(year=2000+year, month=month, day=day, tzinfo=timezone.utc).timestamp()))
            if len(timestamps) == 1:
                timestamps.append(int(datetime.now().timestamp()))
            return timestamps

    @check_effective_message
    def set_minimum_score(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        chat_id = update.effective_message.chat_id
        value = self.sanitize_digit(context.args, 1, 100)

        if value != -1:
            is_same = SearchConfigs.check_if_same_value(chat_id, value, "m")
            if is_same:
                update.effective_message.reply_text(
                    TextRepo.MSG_SAME_VALUE.format(value)
                )
                return

            SearchConfigs.set_user_cfg(chat_id, value, "m")
            update.effective_message.reply_text(
                TextRepo.MSG_SET_MIN_SCORE.format(value)
            )

    @check_effective_message
    def set_top_results(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        chat_id = update.effective_message.chat_id
        value = self.sanitize_digit(context.args, 3, 10)

        if value != -1:
            is_same = SearchConfigs.check_if_same_value(chat_id, value, "n")
            if is_same:
                update.effective_message.reply_text(
                    TextRepo.MSG_SAME_VALUE.format(value)
                )
                return
            SearchConfigs.set_user_cfg(chat_id, value, "n")
            update.effective_message.reply_text(
                TextRepo.MSG_SET_FIRST_N.format(value)
            )

    @check_effective_message
    def get_last_ep(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        chat_id = update.effective_message.chat_id
        is_admin = self.is_admin(chat_id)
        if not is_admin:
            self.call_counter.add_call()

        msg_last_ep = self.episode_handler.get_last_episode()

        update.effective_message.reply_text(
            msg_last_ep, disable_web_page_preview=True, parse_mode=ParseMode.HTML
        )

    @check_effective_message
    def get_ep(self, update: Update, context:CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        chat_id = update.effective_message.chat_id
        is_admin = self.is_admin(chat_id)
        if not is_admin:
            self.call_counter.add_call()

        last_ep_number = self.episode_handler.get_last_episode_number()

        if len(context.args) == 1 and context.args[0].lower() == 'lucky':
            msg = self.episode_handler.get_not_numbered_episode()

            update.effective_message.reply_text(
                msg, disable_web_page_preview=True, parse_mode=ParseMode.HTML
            )
            return

        value, subletter = self.sanitize_digit_and_subletter(context.args, 1, last_ep_number)

        if value != -1:

            msg = self.episode_handler.get_episode(value, subletter)

            update.effective_message.reply_text(
                msg, disable_web_page_preview=True, parse_mode=ParseMode.HTML
            )

    @check_effective_message
    def get_ep_random(self, update: Update, context:CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        chat_id = update.effective_message.chat_id
        is_admin = self.is_admin(chat_id)
        if not is_admin:
            self.call_counter.add_call()

        if random.random() <= 0.016:
            msg = "Fortuna! Hai pescato un raro episodio non numerato!\n"
            msg += self.episode_handler.get_not_numbered_episode()
        else:
            msg = self.episode_handler.get_random_episode()

        update.effective_message.reply_text(
            msg, disable_web_page_preview=True, parse_mode=ParseMode.HTML
        )

    @check_effective_message
    def get_eps_host(self, update: Update, context:CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        command_text = update.effective_message.text
        msg = self.episode_handler.get_host_map(self.dict_host_order.get(command_text, "abc"))

        update.effective_message.reply_text(
            msg
        )


    @check_effective_message
    def show_my_config(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        chat_id = update.effective_message.chat_id

        cfg_user = SearchConfigs.get_user_cfg(chat_id)
        update.effective_message.reply_text(
            TextRepo.MSG_PRINT_CFG.format(cfg_user.n, cfg_user.m)
        )

    def schedule_jobs(self, job_queue):

        self.job = job_queue.run_repeating(
            callback=self.episode_handler.retrieve_new_episode,
            interval=60 * 60,
            first=60,
        )

        self.job_dump_cfg = job_queue.run_repeating(
            callback=SearchConfigs.dump_data,
            interval=60 * 60 * 6,
            first=30,
        )

        self.job_dump_wc = job_queue.run_repeating(
            callback=self.episode_handler.save_searches,
            interval=60 * 60,
            first=90
        )

        self.job_dump_cc = job_queue.run_repeating(
            callback=self.call_counter.dump_data,
            interval=60 * 60,
            first=120
        )        

    def dump_data(self, update: Update, context: CallbackContext):
        res_dump_cfg = SearchConfigs.dump_data()
        res_dump_search = self.episode_handler.save_searches()
        res_dump_call = self.call_counter.dump_data()
        return zip([res_dump_cfg, res_dump_search, res_dump_call], ['dump_cfg', 'dump_search', 'dump_call'])

    @check_effective_message
    def start(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        update.effective_message.reply_text(
            TextRepo.MSG_START, parse_mode=ParseMode.MARKDOWN
        )

    @check_effective_message
    def help(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        update.effective_message.reply_text(
            TextRepo.MSG_HELP, parse_mode=ParseMode.MARKDOWN
        )

    @check_effective_message
    def get_users_total_n(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        n = self.analytics.get_users_total_n()

        update.effective_message.reply_text(
            TextRepo.MSG_TOT_USERS.format(n)
        )

    @check_effective_message
    def get_most_common_words(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        value = self.sanitize_digit(context.args, 1, inf)

        most_common_words: List[Tuple[str, int]] = self.analytics.get_word_counter_top_n(value)
        most_common_words_formatted = "\n".join([f"{word} ({n})" for word, n in most_common_words])

        update.effective_message.reply_text(
            TextRepo.MSG_MOST_COMMON_WORDS.format(value, most_common_words_formatted)
        )

    @check_effective_message
    def get_episodes_total_n(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        n = self.analytics.get_episodes_total_n()

        update.effective_message.reply_text(
            TextRepo.MSG_TOT_EPS.format(n)
        )

    @check_effective_message
    def get_daily_logs(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        from_, to_ = self.sanitize_dates(context.args)

        dict_day_count = self.analytics.get_daily_searches(from_, to_)

        msg = ""
        for day, count in dict_day_count.items():
            date = datetime.utcfromtimestamp(day).strftime('%d/%m/%y')
            msg += f"\n{date}: {count}"

        update.effective_message.reply_text(
            TextRepo.MSG_DAILY_REPORT.format(
                datetime.utcfromtimestamp(from_).strftime('%d/%m/%y'),
                datetime.utcfromtimestamp(to_).strftime('%d/%m/%y')
            ) + msg
        )

    @check_effective_message
    def memo(self, update: Update, context: CallbackContext) -> None:
        assert update.effective_message is not None  # for mypy, real check is in decorator

        update.effective_message.reply_text(
            TextRepo.MSG_MEMO_AMDIN,
            parse_mode=ParseMode.MARKDOWN
        )
