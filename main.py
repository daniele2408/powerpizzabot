from requests import get
import configparser
import pathlib
import os
import logging
import sys
import json
import traceback
import re
from datetime import datetime
from fuzzywuzzy import fuzz
from collections import namedtuple, defaultdict
from functools import lru_cache, wraps
from unidecode import unidecode
from threading import Thread

from telegram import ChatAction, ParseMode, Update
from telegram.ext import (CommandHandler, Defaults, Filters, MessageHandler,
                          Updater, Dispatcher, CallbackContext)
from telegram.ext.updater import Updater as extUpdater
from telegram.ext import messagequeue as mq
from telegram.utils.request import Request
from telegram.bot import Bot   

from TextRepo import TextRepo

from typing import Callable, List, Dict, Set, Tuple, Union, Any

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("main_bot")

SRC_FOLDER = pathlib.Path(__file__).parent.absolute()
config = configparser.ConfigParser()

if os.environ.get("PPB_ENV") == "prod":
    config.read(os.path.join(SRC_FOLDER, 'config_prod.ini'))
else:
    config.read(os.path.join(SRC_FOLDER, 'config.ini'))


CACHE_FILEPATH: str = os.path.join(SRC_FOLDER, config["PATH"].get("CACHE_FILENAME"))
LIST_OF_ADMINS: Set[int] = set([int(admin_id) for key, admin_id in config.items("ADMINS")])

# definition of some types

TopicSnippet = Tuple[str, EpisodeTopic, int, str, str]

#TODO: sistemare about, start, help, i comandi da mandare a fatherbot, il wot

class ValueOutOfRange(Exception):
    pass

class ValueNotValid(Exception):
    pass

class StatusCodeNot200(Exception):
    pass

class UpdateEffectiveMsgNotFound(Exception):
    pass

class ArgumentListEmpty(Exception):
    pass

class MQBot(Bot):
    '''A subclass of Bot which delegates send method handling to MQ'''
    def __init__(self, *args, is_queued_def: bool = True, mqueue: mq.MessageQueue = None, **kwargs) -> None:
        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or mq.MessageQueue()

    def __del__(self):
        try:
            self._msg_queue.stop()
        except:
            pass

    @mq.queuedmessage
    def send_message(self, *args, **kwargs):
        '''Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments'''
        return super(MQBot, self).send_message(*args, **kwargs)

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
            return

    return wrapped

class EpisodeTopic:

    def __init__(self, label: str, url: str) -> None:
        self.label = label
        self.url = url

class Episode:

    def __init__(self, episode_id: str, title: str, published_at: str, site_url: str, description_raw: str): 
        self.episode_id = episode_id
        self.title = title
        self.published_at = published_at
        self.site_url = site_url
        self.description_raw = description_raw
        self.topics: List[EpisodeTopic] = []


    def populate_topics(self) -> None:
        ls_tuples_label_url = re.findall('((\\n|\\r\\n).+(\\n|\\r\\n)http(|s).+(\\n|\\r\\n|$))', self.description_raw)

        for label_url_tuple in ls_tuples_label_url:
            procd_tuple = [el.strip('\r') for el in label_url_tuple[0].split('\n') if el and el != '\r']

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
    @episodes.setter  #type: ignore
    def set_episodes(self, episodes: List[Episode]) -> None:
        for episode in episodes:
            episode.populate_topics()
            self._episodes[episode.episode_id] = episode

    def get_episode(self, episode_id: str) -> Episode:
        return self._episodes[episode_id]

    def add_episode(self, episode: Episode) -> None:
        self._episodes[episode.episode_id] = episode

    def add_episodes(self, episodes: List[Episode]) -> None:
        for ep in episodes:
            self.add_episode(ep)

    def get_episode_ids(self) -> Set[str]:
        return set(self._episodes.keys())


def cache_decorator(func):
    @wraps(func)
    def wrapper_cache_decorator(*args, **kwargs):
        # Do something before
        try:
            with open(CACHE_FILEPATH, 'r') as cachefile:
                cache = json.load(cachefile)
            logger.info("Cache HIT")
        except (IOError, ValueError):
            logger.info("Cache MISS")
            traceback.print_exc()
            cache = func(*args, **kwargs)
        
        # Do something after

        if not os.path.exists(CACHE_FILEPATH):
            with open(CACHE_FILEPATH, 'w') as cachefile:
                json.dump(cache, cachefile)

        return cache
    return wrapper_cache_decorator

def cache_updater(show: "Show"):

    try:
        with open(CACHE_FILEPATH, 'w') as cachefile:
            json.dump(show.episodes, cachefile)
    except (IOError, ValueError):
        logger.error("Cache update failed.")
        traceback.print_exc()

class SpreakerAPIClient:
    BASE_URL: str = config["URLS"].get("BASE_URL")
    GET_USER_SHOWS_URL: str = BASE_URL + config["URLS"].get("GET_USER_SHOWS")
    GET_SHOW_EPISODES_URL: str = BASE_URL + config["URLS"].get("GET_SHOW_EPISODES")
    GET_SINGLE_EPISODE_URL: str = BASE_URL + config["URLS"].get("GET_SINGLE_EPISODE")
    GET_SHOW_URL: str = BASE_URL + config["URLS"].get("GET_SHOW")

    def __init__(self, token: str) -> None:
        self.headers = {"Authorization": f"Bearer {token}"}  # TODO: ma questo lo stiamo ad usare o no??

    def get_show(self, show_id: str) -> Any:
        result = get(SpreakerAPIClient.GET_SHOW_URL.format(show_id))
        if result.status_code != 200:
            raise StatusCodeNot200("get_show result status != 200")
        return result.json()


    def get_user_shows(self, user_id: str) -> Dict:
        result = get(SpreakerAPIClient.GET_USER_SHOWS_URL.format(user_id))
        if result.status_code != 200:
            raise StatusCodeNot200("get_user_shows result status != 200")
        return result.json()            

    
    def get_show_episodes(self, show_id: str) -> List[Dict]:

        stop_loop = False
        episodes = list()
        url = SpreakerAPIClient.GET_SHOW_EPISODES_URL.format(show_id) + "?limit=100"
        n_loop = 0
        while not stop_loop:
            n_loop += 1
            response = get(url)
            if response.status_code != 200:
                raise StatusCodeNot200(f"get_show_episodes loop #{n_loop} result status != 200")
            res_json = response.json()
            episodes.extend(res_json['response']['items'])
            if res_json['response']['next_url'] is None:
                stop_loop = True
            else:
                url = res_json['response']['next_url']
        return episodes

    def get_last_n_episode(self, show_id: str, n: int) -> Dict:
        url = SpreakerAPIClient.GET_SHOW_EPISODES_URL.format(show_id) + f"?limit={n}&sorting=newest"
        res = get(url)
        if res.status_code != 200:
            raise StatusCodeNot200("get_last_n_episode result status != 200")
        return res.json()['response']['items']


    def get_episode_info(self, episode_id: str) -> Dict:
        response = get(SpreakerAPIClient.GET_SINGLE_EPISODE_URL.format(episode_id))
        if response.status_code != 200:
            raise StatusCodeNot200("")
        return response.json()

class EpisodeHandler:

    #TODO: considera un singletone con __new__ e chiamarlo da dentro search()

    def __init__(self, client: SpreakerAPIClient, show: Show) -> None:
        self.client = client
        self.show = show

    @cache_decorator
    def get_episodes(self) -> List[Dict]:
        episodes = self.client.get_show_episodes(self.show.show_id)

        for episode in episodes:
            ep_id = episode['episode_id']
            episode['description'] = self.client.get_episode_info(ep_id)['response']['episode']['description']

        return episodes


    def collect_episodes(self) -> None:
        episodes = self.get_episodes()

        list_episodes = list()
        for ep in episodes:
            list_episodes.append(Episode(ep['episode_id'], ep['title'], ep['published_at'], ep['site_url'], ep['description']))

        self.show.set_episodes = list_episodes
    
    @staticmethod
    def convert_to_italian_date_format(date_str: str) -> str:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')

    @staticmethod
    def format_episode_title_line(site_url: str, title: str) -> str:
        pre_colons, post_colons = title.split(':', 1)
        number_ep = re.findall("[0-9]+", pre_colons)
        return f"Episodio {number_ep[0]}: <a href='{site_url}'>{post_colons}</a>"
        
    def search_text_in_episodes(self, text: str, n: int, m: int, show_tech: bool = False) -> str:
        sorted_tuple_episodes = SearchEngine.get_episodes_topic(self.show.episodes, text)
        filter_episodes = [tpl for tpl in sorted_tuple_episodes if tpl[2] > m][:n]
        
        if len(filter_episodes):
            return self.format_response(filter_episodes, show_tech)
        else:
            return TextRepo.MSG_NO_RES.format(m)

    def format_response(self, first_eps_sorted: List[TopicSnippet], show_tech: bool) -> str:

        message = ""
        i = 1
        for tuple_ in first_eps_sorted:
            ep = self.show.get_episode(tuple_[0])
            score = tuple_[2]
            topic_url = tuple_[4]
            topic_label = tuple_[1].label
            episode_line = self.format_episode_title_line(ep.site_url, ep.title)
            date = self.convert_to_italian_date_format(ep.published_at)
            message += TextRepo.MSG_RESPONSE.format(
                i, score, topic_url, topic_label, episode_line, date
            )
            
            technique_used = tuple_[3]
            message += f"\nTechnique: {technique_used}\n" if show_tech else "\n"
            i += 1

        return message


    def retrieve_new_episode(self, *args) -> None:
        logger.info("Gonna check if there are new episodes I missed.")
        keep_checking = True
        n_last_episodes = 2
        while keep_checking:
            last_episodes = self.client.get_last_n_episode(self.show.show_id, n_last_episodes)

            # equivalent to a take while there's no new episoded, to refactor
            if all(last_ep['episode_id'] in self.show.get_episode_ids() for last_ep in last_episodes): # if we already have last n episodes
                keep_checking = False
                logger.info("Cache is already up to date.")
            elif all(last_ep['episode_id'] not in self.show.get_episode_ids() for last_ep in last_episodes): # if we have none, check one more
                n_last_episodes += 1
            else:  # we have all but the last one, we gucci
                logger.info(f"Adding {n_last_episodes-1} new episodes!")
                self.show.add_episodes(last_episodes[:-1])
                cache_updater(self.show)


class SearchEngine:

    @classmethod
    def get_episodes_topic(cls, episodes: Dict[str, Episode], text: str) -> List[TopicSnippet]:
        episodes_topic = list()
        for ep in episodes.values():
            episodes_topic.extend(cls.scan_episode(ep, text))

        return sorted(episodes_topic, key=lambda x: (-x[2], len(x[1].label)))

    @staticmethod
    def normalize_string(s: str) -> str:
        s = unidecode(s.lower())
        s = re.sub('[^A-Za-z0-9 ]+', '', s)
        s = re.sub('[ ]+', ' ', s).strip()
        return s

    @classmethod
    def compare_strings(cls, descr: str, text_input: str) -> Tuple[int, str]:
        token_set = (fuzz.token_set_ratio(descr, text_input), 'token_set')
        token_sort = (fuzz.token_sort_ratio(descr, text_input), 'token_sort')
        if len(text_input.split(" ")) == 1:
            max_partial = (max([fuzz.ratio(text_input, word) for word in descr.split(" ")]), 'max_simple_ratio')
        else:
            max_partial = (0, 'max_simple_ratio')

        best_result = max((
            token_set,
            token_sort,
            max_partial
        ), key=lambda x: x[0])

        if text_input in descr:
            return best_result
        else:
            return (round(best_result[0] * 0.5), best_result[1])  # penalty if no substring


    @classmethod
    def scan_episode(cls, episode: Episode, text: str) -> List[TopicSnippet]:
        ls_res = list()
        for topic in episode.topics:
            match_score, technique = cls.compare_strings(cls.normalize_string(topic.label), cls.normalize_string(text))
            ls_res.append((episode.episode_id, topic, match_score, technique, topic.url))
        return ls_res

def error_callback(update: Update, context: CallbackContext) -> None:
    try:
        # CallbackContext.error: Only present when passed to a error handler registered with, so it's not Optional here
        raise context.error  # type: ignore 
    except ValueNotValid as vnv:
        logger.error(vnv)
        if update and update.effective_message:
            update.effective_message.reply_text(
                vnv.args[0]
            )
    except ValueOutOfRange as voof:
        logger.error(voof)
        if update and update.effective_message:
            update.effective_message.reply_text(
                voof.args[0]
            )
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

class UserConfig:

    def __init__(self, n, m):
        self.n = n
        self.m = m

class SearchConfigs:

    DATE_FORMAT = "%Y%m%dT%H%M%S"
    user_data: Dict[int, UserConfig] = defaultdict(lambda: UserConfig(5, 1))

    @classmethod
    def get_user_cfg(cls, chat_id: int) -> "UserConfig":
        return cls.user_data[chat_id]

    @classmethod
    def get_user_show_first_n(cls, chat_id: int) -> int:
        return cls.user_data[chat_id].n

    @classmethod
    def get_user_show_min_threshold(cls, chat_id: int) -> int:
        return cls.user_data[chat_id].m

    @classmethod
    def check_if_same_value(cls, chat_id: int, value: int, field: str) -> bool:
        if field == 'n' and cls.user_data[chat_id].n == value:
            return True
        elif field == 'm' and cls.user_data[chat_id].m == value:
            return True
        else:
            return False

    @classmethod
    def set_user_cfg(cls, chat_id: int, value: int, field: str) -> None:
        if field == 'n':
            cls.user_data[chat_id].n = value
        elif field == 'm':
            cls.user_data[chat_id].m = value
        else:
            raise ValueError("User config field not valid.")

    @classmethod
    def normalize_user_data(cls) -> Dict:
        data = dict()
        for chat_id, user_cfg in cls.user_data.items():
            data[chat_id] = {'n': user_cfg.n, 'm': user_cfg.m}

        return data

    @classmethod
    def dump_data(cls, is_back_up: bool = False) -> int:
        filename = f"backup{datetime.strftime(datetime.now(), cls.DATE_FORMAT)}.json" if is_back_up else config['PATH'].get('USERS_CFG_FILENAME')
        filepath = os.path.join(SRC_FOLDER, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(cls.normalize_user_data(), f)
                return 1
        except Exception as e:
            logger.error(e)
            traceback.print_exc()
            return 0

    @classmethod
    def backup_job(cls, context):
        cls.dump_data(is_back_up=context.job.context)

    @classmethod
    def init_data(cls) -> None:
        try:
            with open(os.path.join(SRC_FOLDER, config['PATH'].get('USERS_CFG_FILENAME')), 'r') as f:
                data = json.load(f)

                for chat_id, payload in data.items():
                    cls.user_data[int(chat_id)] = UserConfig(payload['n'], payload['m'])


        except Exception as e:
            logger.error(e)
            traceback.print_exc()

class FacadeBot:

    def __init__(self, episode_handler: "EpisodeHandler") -> None:
        self.episode_handler = episode_handler
        self.job = None
        self.job_dump_cfg = None

    @staticmethod
    def is_admin(chat_id: int) -> bool:
        return chat_id in LIST_OF_ADMINS

    @send_typing_action
    def search(self, update: Update, context: CallbackContext) -> None:
        if not context.args:
            raise ArgumentListEmpty("No arguments sent.")
        if update.effective_message:
            chat_id = update.effective_message.chat_id
            text: List[str] = context.args
            user_cfg = SearchConfigs.get_user_cfg(chat_id)

            message = self.episode_handler.search_text_in_episodes(" ".join(text), user_cfg.n, user_cfg.m, self.is_admin(chat_id))
            update.effective_message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            raise UpdateEffectiveMsgNotFound("update.effective_message None for /search")

    @staticmethod
    def sanitize_digit(args, min_: int, max_: int) -> int:
        res = re.compile('^[0-9]+$').match(" ".join(args))
        if res is None:
            raise ValueNotValid(TextRepo.MSG_NOT_VALID_INPUT)
        else:
            value = int(res.group(0))
            if min_ > value or max_ < value:
                raise ValueOutOfRange(TextRepo.MSG_NOT_VALID_RANGE.format(min_, max_))
            else:
                return value

    def set_minimum_score(self, update: Update, context: CallbackContext) -> None:
        if update.effective_message:
            chat_id = update.effective_message.chat_id
            value = self.sanitize_digit(context.args, 1, 100)
            
            if value != -1:
                is_same = SearchConfigs.check_if_same_value(chat_id, value, 'm')
                if is_same:
                    update.effective_message.reply_text(TextRepo.MSG_SAME_VALUE.format(value))
                    return

                SearchConfigs.set_user_cfg(chat_id, value, 'm')
                update.effective_message.reply_text(TextRepo.MSG_SET_MIN_SCORE.format(value))
        else:
            raise UpdateEffectiveMsgNotFound("update.effective_message None for /min")                

    def set_top_results(self, update: Update, context: CallbackContext) -> None:
        
        if update.effective_message:
            chat_id = update.effective_message.chat_id
            value = self.sanitize_digit(context.args, 3, 10)
            
            if value != -1:
                is_same = SearchConfigs.check_if_same_value(chat_id, value, 'n')
                if is_same:
                    update.effective_message.reply_text(TextRepo.MSG_SAME_VALUE.format(value))
                    return            
                SearchConfigs.set_user_cfg(chat_id, value, 'n')
                update.effective_message.reply_text(TextRepo.MSG_SET_FIRST_N.format(value))
        else:
            raise UpdateEffectiveMsgNotFound("update.effective_message None for /top")                

    def show_my_config(self, update: Update, context: CallbackContext) -> None:
        if update.effective_message: #TODO: use a decorator
            chat_id = update.effective_message.chat_id

            cfg_user = SearchConfigs.get_user_cfg(chat_id)
            update.effective_message.reply_text(TextRepo.MSG_PRINT_CFG.format(cfg_user.n, cfg_user.m))
        else:
            raise UpdateEffectiveMsgNotFound("update.effective_message None for /mycfg")

    def setup_scheduler_check_new_eps(self, job_queue):

        self.job = job_queue.run_repeating(
            callback=self.episode_handler.retrieve_new_episode,
            interval = 60 * 60,
            first = 0
        )

        self.job = job_queue.run_repeating(
            callback=SearchConfigs.backup_job,
            interval = 60 * 60 * 6,
            first = 0,
            context=True
        )

        # TODO: counter delle stringhe ricercate?
        # TODO: finire type hint e lanciare mypy

    def dump_data(self, update: Update, context: CallbackContext) -> None:
        SearchConfigs.dump_data()

    def start(self, update: Update, context: CallbackContext) -> None:
        if update.effective_message:
            update.effective_message.reply_text(
                TextRepo.MSG_START,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            raise UpdateEffectiveMsgNotFound("update.effective_message None for /start")        

    def help(self, update: Update, context: CallbackContext) -> None:
        if update.effective_message:
            update.effective_message.reply_text(
                TextRepo.MSG_START,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            raise UpdateEffectiveMsgNotFound("update.effective_message None for /help")            


def main():

    init_message_config = f"Booting up using {os.environ.get('PPB_ENV')} version"

    logger.info(init_message_config)

    SearchConfigs.init_data()

    client = SpreakerAPIClient(config['SECRET'].get('api_token'))

    power_pizza = Show(config['POWER_PIZZA'].get('SHOW_ID'))

    TOKEN_BOT = config['SECRET'].get("bot_token")
    q = mq.MessageQueue(all_burst_limit=29, all_time_limit_ms=1017)
    request = Request(con_pool_size=8)
    testbot = MQBot(TOKEN_BOT, request=request, mqueue=q)
    updater = extUpdater(bot=testbot, use_context=True)

    for admin in LIST_OF_ADMINS:
        updater.bot.send_message(chat_id=admin, text=init_message_config)

    episode_handler = EpisodeHandler(client, power_pizza)
    episode_handler.collect_episodes()

    facade_bot = FacadeBot(episode_handler)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("s", facade_bot.search))
    dp.add_handler(CommandHandler("min", facade_bot.set_minimum_score))
    dp.add_handler(CommandHandler("top", facade_bot.set_top_results))
    dp.add_handler(CommandHandler("mycfg", facade_bot.show_my_config))
    dp.add_handler(CommandHandler("dump", facade_bot.dump_data, filters=Filters.user(username="@itsaprankbro")))

    dp.add_handler(CommandHandler("start", facade_bot.start))
    dp.add_handler(CommandHandler("help", facade_bot.help))

    dp.add_error_handler(error_callback)

    facade_bot.setup_scheduler_check_new_eps(dp.job_queue)

    def stop_and_restart():
        logger.info("Stop and restaring bot...")
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def kill_bot():
        logger.info("Shutting down bot...")
        updater.stop()

    @restricted
    def restart(update, context):
        res_save = SearchConfigs.dump_data()
        if res_save:  # save success
            update.message.reply_text("Data saved successfully")
        else:
            update.message.reply_text("Something went wrong saving data...")

        update.message.reply_text("Bot is restarting...")
        Thread(target=stop_and_restart).start()

    @restricted
    def kill(update, context):
        res_save = SearchConfigs.dump_data()
        if res_save:  # save success
            update.message.reply_text("Data saved successfully")
        else:
            update.message.reply_text("Something went wrong saving data...")
        update.message.reply_text("See you, space cowboy...")
        Thread(target=kill_bot).start()

    # handler restarter
    dp.add_handler(
        CommandHandler("restart", restart, filters=Filters.user(username="@itsaprankbro"))
    )
    dp.add_handler(
        CommandHandler("killme", kill, filters=Filters.user(username="@itsaprankbro"))
    )

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':

    main()