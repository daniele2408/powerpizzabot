from requests import get
import configparser
import pathlib
import os
import logging
import json
import traceback
import re
from datetime import datetime
from fuzzywuzzy import fuzz
from collections import namedtuple, defaultdict
from functools import lru_cache, wraps
from unidecode import unidecode

from telegram import ChatAction, ParseMode, Update
from telegram.ext import (CommandHandler, Defaults, Filters, MessageHandler,
                          Updater, Dispatcher, CallbackContext)
from telegram.ext.updater import Updater as extUpdater
from telegram.ext import messagequeue as mq
from telegram.utils.request import Request
from telegram.bot import Bot   

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("main_bot")

SRC_FOLDER = pathlib.Path(__file__).parent.absolute()
config = configparser.ConfigParser()

if os.environ.ge("PPB_ENV") == "prod":
    config.read(os.path.join(SRC_FOLDER, 'config_prod.ini'))
else:
    config.read(os.path.join(SRC_FOLDER, 'config.ini'))


CACHE_FILEPATH = os.path.join(SRC_FOLDER, config["PATH"].get("CACHE_FILENAME"))
ADMINS = set([int(admin_id) for key, admin_id in config.items("ADMINS")])

#TODO: sistemare about, start, help, i comandi da mandare a fatherbot, il wot
#TODO: un check al limite per il flood https://github.com/python-telegram-bot/python-telegram-bot/wiki/Avoiding-flood-limits#using-mq-with-queuedmessage-decorator

class ValueOutOfRange(Exception):
    pass

class ValueNotValid(Exception):
    pass


class MQBot(Bot):
    '''A subclass of Bot which delegates send method handling to MQ'''
    def __init__(self, *args, is_queued_def=True, mqueue=None, **kwargs):
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

def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(self, update, context, *args, **kwargs):
        context.bot.send_chat_action(
            chat_id=update.effective_message.chat_id, action=ChatAction.TYPING
        )
        return func(self, update, context, *args, **kwargs)

    return command_func


class EpisodeTopic:

    def __init__(self, label, url):
        self.label = label
        self.url = url

class Episode:

    def __init__(self, episode_id, title, published_at, site_url, description_raw): 
        self.episode_id = episode_id
        self.title = title
        self.published_at = published_at
        self.site_url = site_url
        self.description_raw = description_raw
        self.topics = []


    def populate_topics(self):
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

    def __init__(self, show_id):
        self.show_id = show_id
        self._episodes = dict()

    @property
    def episodes(self):
        return self._episodes

    @episodes.setter
    def set_episodes(self, episodes):
        for episode in episodes:
            episode.populate_topics()
            self._episodes[episode.episode_id] = episode

    def get_episode(self, episode_id):
        return self._episodes.get(episode_id, False)

    def add_episode(self, episode):
        self._episodes[episode.episode_id] = episode

    def add_episodes(self, episodes):
        for ep in episodes:
            self.add_episode(ep)

    def get_last_episode_timestamp(self):
        return max(self._episodes, key=lambda x: x.published_at).published_at

    def get_episode_ids(self):
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

def cache_updater(show):

    try:
        with open(CACHE_FILEPATH, 'w') as cachefile:
            cache = json.dump(show.episodes, cachefile)
    except (IOError, ValueError):
        logger.error("Cache update failed.")
        traceback.print_exc()

class SpreakerAPIClient:
    BASE_URL = config["URLS"].get("BASE_URL")
    GET_USER_SHOWS_URL = BASE_URL + config["URLS"].get("GET_USER_SHOWS")
    GET_SHOW_EPISODES_URL = BASE_URL + config["URLS"].get("GET_SHOW_EPISODES")
    GET_SINGLE_EPISODE_URL = BASE_URL + config["URLS"].get("GET_SINGLE_EPISODE")
    GET_SHOW_URL = BASE_URL + config["URLS"].get("GET_SHOW")

    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"}

    def get_show(self, show_id):
        try:
            return get(SpreakerAPIClient.GET_SHOW_URL.format(show_id)).json()
        except Exception as e:
            logger.error(e)
            traceback.print_exc()

    def get_user_shows(self, user_id):
        try:
            return get(SpreakerAPIClient.GET_USER_SHOWS_URL.format(user_id)).json()
        except Exception as e:
            logger.error(e)
            traceback.print_exc()

    
    def get_show_episodes(self, show_id):
        try:
            stop_loop = False
            episodes = list()
            url = SpreakerAPIClient.GET_SHOW_EPISODES_URL.format(show_id) + "?limit=100"
            while not stop_loop:
                res = get(url).json()
                episodes.extend(res['response']['items'])
                if res['response']['next_url'] is None:
                    stop_loop = True
                else:
                    url = res['response']['next_url']

            return episodes
        except Exception as e:
            logger.error(e)
            traceback.print_exc()

    def get_last_n_episode(self, show_id, n):
        try:
            url = SpreakerAPIClient.GET_SHOW_EPISODES_URL.format(show_id) + f"?limit={n}&sorting=newest"
            res = get(url).json()
            return res['response']['items']
        except Exception as e:
            logger.error(e)
            traceback.print_exc()


    def get_episode_info(self, episode_id):
        try:
            return get(SpreakerAPIClient.GET_SINGLE_EPISODE_URL.format(episode_id)).json()
        except Exception as e:
            logger.error(e)
            traceback.print_exc()        

class EpisodeHandler:

    #TODO: considera un singletone con __new__ e chiamarlo da dentro search()

    def __init__(self, client: SpreakerAPIClient, show: Show):
        self.client = client
        self.show = show

    @cache_decorator
    def get_episodes(self):
        episodes = self.client.get_show_episodes(self.show.show_id)

        for episode in episodes:
            ep_id = episode['episode_id']
            episode['description'] = self.client.get_episode_info(ep_id)['response']['episode']['description']

        return episodes


    def collect_episodes(self):
        episodes = self.get_episodes()

        list_episodes = list()
        for ep in episodes:
            list_episodes.append(Episode(ep['episode_id'], ep['title'], ep['published_at'], ep['site_url'], ep['description']))

        self.show.set_episodes = list_episodes
    
    @staticmethod
    def convert_to_italian_date_format(date_str):
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')

    @staticmethod
    def format_episode_title_line(site_url, title):
        pre_colons, post_colons = title.split(':', 1)
        number_ep = re.findall("[0-9]+", pre_colons)
        return f"Episodio {number_ep[0]}: <a href='{site_url}'>{post_colons}</a>"
        
    def search_text_in_episodes(self, text, n, m, show_tech=False):
        sorted_tuple_episodes = SearchEngine.get_episodes_topic(self.show.episodes, text)
        filter_episodes = [tpl for tpl in sorted_tuple_episodes if tpl[2] >= m][:n]
        
        if len(filter_episodes):
            return self.format_response(filter_episodes, show_tech)
        else:
            return f"Spiacente! Nessun match con le impostazioni correnti (minimo {m}% di matching score)"


    def format_response(self, first_eps_sorted, show_tech):

        message = ""
        i = 1
        for tuple_ in first_eps_sorted:
            ep = self.show.get_episode(tuple_[0])
            message += f"""
------------ MATCH #{i} -- SCORE {tuple_[2]}% ------------
Topic: <a href="{tuple_[4]}">{tuple_[1].label}</a>
{self.format_episode_title_line(ep.site_url, ep.title)}
Data: {self.convert_to_italian_date_format(ep.published_at)}"""
            message += f"\nTechnique: {tuple_[3]}\n" if show_tech else "\n"
            i += 1

        return message


    def retrieve_new_episode(self, *args):
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
    def get_episodes_topic(cls, episodes, text):
        episodes_topic = list()
        for ep in episodes.values():
            episodes_topic.extend(cls.scan_episode(ep, text))

        return sorted(episodes_topic, key=lambda x: (-x[2], len(x[1].label)))

    @staticmethod
    def normalize_string(s):
        s = unidecode(s.lower())
        s = re.sub('[^A-Za-z0-9 ]+', '', s)
        s = re.sub('[ ]+', ' ', s).strip()
        return s

    @classmethod
    def compare_strings(cls, descr, text_input):
        token_set = (fuzz.token_set_ratio(descr, text_input), 'token_set')
        token_sort = (fuzz.token_sort_ratio(descr, text_input), 'token_sort')
        if len(text_input.split(" ")) == 1:
            max_partial = (max([fuzz.ratio(text_input, word) for word in descr.split(" ")]), 'max_simple_ratio')
        else:
            max_partial = (0, None)

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
    def scan_episode(cls, episode, text):
        ls_res = list()
        for topic in episode.topics:
            match_score, technique = cls.compare_strings(cls.normalize_string(topic.label), cls.normalize_string(text))
            ls_res.append((episode.episode_id, topic, match_score, technique, topic.url))
        return ls_res

def error_callback(update: Update, context: CallbackContext) -> None:
    try:
        raise context.error
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
    except Exception as e:
        logger.error(e)
        traceback.print_exc()

def handle_text_messages(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("This is not a command! Send me /help to show the command list")

class UserConfig:

    def __init__(self, n, m):
        self.n = n
        self.m = m

class SearchConfigs:

    user_data = defaultdict(lambda: UserConfig(5, 0))

    @classmethod
    def get_user_cfg(cls, chat_id):
        return cls.user_data[chat_id]

    @classmethod
    def get_user_show_first_n(cls, chat_id):
        return cls.user_data[chat_id].n

    @classmethod
    def get_user_show_min_threshold(cls, chat_id):
        return cls.user_data[chat_id].m

    @classmethod
    def set_user_cfg(cls, chat_id, value, field):
        if field == 'n':
            cls.user_data[chat_id].n = value
        elif field == 'm':
            cls.user_data[chat_id].m = value
        else:
            raise ValueError("User config field not valid.")

    @classmethod
    def normalize_user_data(cls):
        data = dict()
        for chat_id, user_cfg in cls.user_data.items():
            data[chat_id] = {'n': user_cfg.n, 'm': user_cfg.m}

        return data

    @classmethod
    def dump_data(cls):
        try:
            with open(os.path.join(SRC_FOLDER, config['PATH'].get('USERS_CFG_FILENAME')), 'w') as f:
                json.dump(cls.normalize_user_data(), f)
        except Exception as e:
            logger.error(e)
            traceback.print_exc()

    @classmethod
    def init_data(cls):
        try:
            with open(os.path.join(SRC_FOLDER, config['PATH'].get('USERS_CFG_FILENAME')), 'r') as f:
                data = json.load(f)

                for chat_id, payload in data.items():
                    cls.user_data[int(chat_id)] = UserConfig(payload['n'], payload['m'])


        except Exception as e:
            logger.error(e)
            traceback.print_exc()

class FacadeBot:

    def __init__(self, episode_handler: EpisodeHandler):
        self.episode_handler = episode_handler
        self.job = None
        self.job_dump_cfg = None

    @staticmethod
    def is_admin(chat_id):
        return chat_id in ADMINS

    @send_typing_action
    def search(self, update, context):
        chat_id = update.effective_message.chat_id
        text = context.args
        user_cfg = SearchConfigs.get_user_cfg(chat_id)

        message = self.episode_handler.search_text_in_episodes(" ".join(text), user_cfg.n, user_cfg.m, self.is_admin(chat_id))
        update.effective_message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    @staticmethod
    def sanitize_digit(args, min_, max_):
        res = re.compile('^[0-9]+$').match(" ".join(args))
        if res is None:
            raise ValueNotValid("Il valore inviato non ha un formato corretto, inserire un numero intero appartenente all'intervallo previsto.")
        else:
            value = int(res.group(0))
            if min_ > value or max_ < value:
                raise ValueOutOfRange(f"Il valore inviato non è nell'intervallo previsto [{min_},{max_}].")
            else:
                return value

    def set_minimum_score(self, update, context):
        chat_id = update.effective_message.chat_id
        value = self.sanitize_digit(context.args, 0, 100)
        
        if value != -1:
            SearchConfigs.set_user_cfg(chat_id, value, 'm')
            update.effective_message.reply_text(f"Ho impostato {value}% come soglia minima di match score")

    def set_top_results(self, update, context):
        chat_id = update.effective_message.chat_id
        value = self.sanitize_digit(context.args, 3, 10)
        
        if value != -1:
            SearchConfigs.set_user_cfg(chat_id, value, 'n')
            update.effective_message.reply_text(f"D'ora in poi ti mostrerò i primi {value} risultati della ricerca")

    def setup_scheduler_check_new_eps(self, job_queue):

        self.job = job_queue.run_repeating(
            callback=self.episode_handler.retrieve_new_episode,
            interval = 60 * 60,
            first = 0
        )

        # TODO: fare un job che dumpi periodicamente (ogni 15 min?) le cfg utente


    def dump_data(self, update, context):
        SearchConfigs.dump_data()

    def start(self, update, context):
        update.effective_message.reply_text(
            "Ciao! Sono un bot per ricercare argomenti trattati dal podcast di Sio, Lorro e Nick: Power Pizza!\n\nIl comando\n`\help`\nti mostrerà i comandi disponibili, oppure prova direttamente a inviare\n`\s Hollow Knight`\no qualsiasi altro argomento ti venga in mente.",
            parse_mode=ParseMode.MARKDOWN
        )

    def help(self, update, context):
        update.effective_message.reply_text(
            "`/s <testo>`\nper ricercare un argomento tra quelli elencati negli scontrini delle puntate.\n\n`/top <n>`\nper far apparire solo i primi n messaggi nella ricerca\n\n`/min <n>`\nper modificare la soglia minima di match score dei risultati.",
            parse_mode=ParseMode.MARKDOWN
        )

    def about(self, update, context):
        update.effective_message.reply_text(
            "Ciao! Sono un bot per ricercare argomenti trattati dal podcast di Sio, Lorro e Nick: Power Pizza!\n\nIl comando `\help` ti mostrerà i comandi disponibili, oppure prova direttamente a inviare `\s Hollow Knight` o qualsiasi altro argomento ti venga in mente.",
            parse_mode=ParseMode.MARKDOWN
        )

def main():

    logger.info(f"Booting up using {os.environ.get("PPB_ENV")} version")

    SearchConfigs.init_data()

    client = SpreakerAPIClient(config['SECRET'].get('api_token'))

    power_pizza = Show(config['POWER_PIZZA'].get('SHOW_ID'))

    TOKEN_BOT = config['SECRET'].get("bot_token")
    q = mq.MessageQueue(all_burst_limit=29, all_time_limit_ms=1017)
    request = Request(con_pool_size=8)
    testbot = MQBot(TOKEN_BOT, request=request, mqueue=q)
    updater = extUpdater(bot=testbot, use_context=True)

    episode_handler = EpisodeHandler(client, power_pizza)
    episode_handler.collect_episodes()

    facade_bot = FacadeBot(episode_handler)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("s", facade_bot.search))
    dp.add_handler(CommandHandler("min", facade_bot.set_minimum_score))
    dp.add_handler(CommandHandler("top", facade_bot.set_top_results))
    dp.add_handler(CommandHandler("dump", facade_bot.dump_data, filters=Filters.user(username="@itsaprankbro")))

    dp.add_handler(CommandHandler("start", facade_bot.start))
    dp.add_handler(CommandHandler("help", facade_bot.help))
    dp.add_handler(CommandHandler("about", facade_bot.about))

    dp.add_error_handler(error_callback)

    facade_bot.setup_scheduler_check_new_eps(dp.job_queue)

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':

    main()