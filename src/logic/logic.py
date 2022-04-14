import random

from model.models import Episode
from datetime import datetime
import re
from support.TextRepo import TextRepo
import logging
from support.apiclient import SpreakerAPIClient
from model.models import Show
from model.custom_exceptions import ValueNotValid
from typing import Dict, List
from support.WordCounter import WordCounter
from support.Cacher import Cacher
from typing import Dict, List, Tuple, Set
from model.models import Episode
from unidecode import unidecode
import traceback
import re
from fuzzywuzzy import fuzz
from model.models import EpisodeTopic
from stop_words import get_stop_words
from itertools import combinations

logger = logging.getLogger('logic.logic')

TopicSnippet = Tuple[str, EpisodeTopic, int, str, str, int]

class SearchEngine:

    IT_STOP_WORDS: Set[int] = set(get_stop_words('it'))
    EN_STOP_WORDS: Set[int] = set(get_stop_words('en'))

    @classmethod
    def generate_sorted_topics(
        cls, episodes: Dict[str, Episode], text: str
    ) -> Tuple[List[TopicSnippet], str, int]:
        episodes_topic = list()
        normalized_text = cls.normalize_string(text)

        if not normalized_text:
            raise ValueNotValid("Il testo inviato non contiene caratteri alfanumerici né parole significative, nessun risultato ottenuto.")

        for ep in episodes.values():
            episodes_topic.extend(cls.scan_episode(ep, normalized_text))

        max_score = max(episodes_topic, key=lambda x: x[2])[2]

        return (
            sorted(episodes_topic, key=lambda x: (-x[2], len(x[1].label))),
            normalized_text,
            max_score
        )

    @classmethod
    def normalize_string(cls, s: str) -> str:
        s = unidecode(s.lower())
        s = re.sub("[^A-Za-z0-9 ]+", " ", s)
        for word in s.split(" "):
            if word in cls.EN_STOP_WORDS or word in cls.IT_STOP_WORDS:
                s = re.sub(r"\b{}\b".format(word), "", s)
        s = re.sub("[ ]+", " ", s).strip()

        return s

    @classmethod
    def compare_strings(cls, descr: str, text_input: str) -> Tuple[int, str, int]:

        max_list = list()
        text_input_words = text_input.split(" ")
        combs = list()
        for ngram in range(1, len(text_input_words)+1):
            for combination in combinations(text_input_words, ngram):
                combs.append(combination)

        for word_inputs in combs:
            max_list.append(max([fuzz.ratio("".join(word_inputs), w) for w in descr.split(" ")]))

        return int(sum(max_list) / len(text_input_words)), "mean_most_similar_combo", max(max_list)


    @classmethod
    def scan_episode(cls, episode: Episode, normalized_text: str) -> List[TopicSnippet]:
        ls_res = list()
        for topic in episode.topics:
            match_score, technique, max_score = cls.compare_strings(
                cls.normalize_string(topic.label), normalized_text
            )
            ls_res.append(
                (episode.episode_id, topic, match_score, technique, topic.url, max_score)
            )
        return ls_res


class EpisodeHandler:

    def __init__(
        self, client: SpreakerAPIClient, show: Show, word_counter: WordCounter
    ) -> None:
        self.client = client
        self.show = show
        self.word_counter = word_counter

    @Cacher.cache_decorator
    def collect_episodes(self) -> Dict[str, Episode]:
        episodes = self.client.get_show_episodes(self.show.show_id)
        return self.process_raw_episodes(episodes)

    def add_episodes_to_show(self) -> None:
        self.show.set_episodes = self.collect_episodes()

    def process_raw_episodes(self, raw_episodes: List[Dict]) -> Dict[str, Episode]:
        return {ep["episode_id"]: self.convert_raw_ep(ep) for ep in raw_episodes}

    def convert_raw_ep(self, ep: Dict) -> Episode:
        ep_id = ep["episode_id"]
        ep["description"] = self.client.get_episode_info(ep_id)["response"]["episode"][
            "description"
        ]
        episode = Episode(
            ep["episode_id"],
            ep["title"],
            ep["published_at"],
            ep["site_url"],
            ep["description"],
        )
        episode.populate_topics()
        return episode

    @staticmethod
    def convert_to_italian_date_format(date_str: str) -> str:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")

    @staticmethod
    def format_episode_title_line(site_url: str, title: str) -> str:
        try:
            pre_colons, post_colons = title.split(":", 1)
            number_ep = re.findall("[0-9]+", pre_colons)
            return f"Episodio {number_ep[0]}: <a href='{site_url}'>{post_colons}</a>"
        except Exception as e:
            traceback.print_exc()
            logger.error(e)
            return ""

    def search_text_in_episodes(
        self, text: str, n: int, m: int, is_admin: bool = False
    ) -> Tuple[str, str]:
        sorted_tuple_episodes, normalized_text, max_score = SearchEngine.generate_sorted_topics(
            self.show.episodes, text
        )
        if not is_admin:
            self.word_counter.add_word(normalized_text)

        filter_episodes = [tpl for tpl in sorted_tuple_episodes if tpl[5] >= m and tpl[2] >= max_score * .75][:n]

        if len(filter_episodes):
            return self.format_response(filter_episodes, is_admin), text
        else:
            return TextRepo.MSG_NO_RES, text

    def format_response(
        self, first_eps_sorted: List[TopicSnippet], admin_req: bool
    ) -> str:

        message = ""
        i = 1
        for tuple_ in first_eps_sorted:
            ep = self.show.get_episode(tuple_[0])
            score = f"SCORE {tuple_[2]}" if admin_req else ""
            topic_url = tuple_[4]
            topic_label = tuple_[1].label if topic_url != "@PowerPizzaSearchBot" else tuple_[1].label + " <i>(hey, that's me!)</i>"
            max_score = tuple_[5]
            episode_line = self.format_episode_title_line(ep.site_url, ep.title)
            date = self.convert_to_italian_date_format(ep.published_at)
            message += TextRepo.MSG_RESPONSE.format(
                i, score, topic_url, topic_label, episode_line, date
            )

            technique_used = tuple_[3]
            message += f"\nTechnique: {technique_used}\n" if admin_req else "\n"
            message += f"\nMax Score: {max_score}" if admin_req else ""
            i += 1

        return message

    def retrieve_new_episode(self, *args) -> None:
        logger.info("Gonna check if there are new episodes I missed.")
        keep_checking = True
        n_last_episodes = 2
        while keep_checking:
            last_episodes = self.client.get_last_n_episode(
                self.show.show_id, n_last_episodes
            )

            # equivalent to a take while there's no new episoded, to refactor
            if all(
                last_ep["episode_id"] in self.show.get_episode_ids()
                for last_ep in last_episodes
            ):  # if we already have last n episodes
                keep_checking = False
                logger.info("Cache is already up to date.")
            elif all(
                last_ep["episode_id"] not in self.show.get_episode_ids()
                for last_ep in last_episodes
            ):  # if we have none, check one more
                n_last_episodes += 1
            else:  # we have all but the last one, we gucci
                logger.info(f"Adding {n_last_episodes-1} new episodes!")

                new_episodes = last_episodes[:-1]
                procd_episodes = self.process_raw_episodes(new_episodes)

                self.show.set_episodes = procd_episodes
                Cacher.cache_updater(procd_episodes)

                keep_checking = False

    def save_searches(self, *args):
        return self.word_counter.dump_counter()

    def get_last_episode(self) -> str:
        return self.format_single_episode(self.show.get_last_episode())

    def get_last_episode_number(self) -> int:
        last_ep: Episode = self.show.get_last_episode()
        return last_ep.number

    def format_single_episode(self, ep: Episode) -> str:
        msg = f"Episodio {ep.number}: {ep.title_str} ({self.convert_to_italian_date_format(ep.published_at)})\n\n"
        msg_description = f"{ep.description_raw}\n--------------------------------\n"

        return msg + msg_description

    def get_episode(self, number_ep: int) -> str:
        return self.format_single_episode(self.show.get_episode_by_number(number_ep))

    def get_not_numbered_episode(self) -> str:
        episodes = self.show.get_not_numbered_episodes()
        return self.format_single_episode(random.choice(episodes))

    def get_host_map(self, sort_order:str = "abc") -> str:

        if sort_order == "frequency":
            sort_f = lambda x: (len(x[1]), max(x[1]))
        elif sort_order == "abc":
            sort_f = lambda x: x[0].most_common(1)[0][0].lower()
        elif sort_order == "first_appear":
            sort_f = lambda x: (min(x[1]), x[0].most_common(1)[0][0].lower())
        else:
            sort_f = lambda x: (len(x[1]), max(x[1]))

        sorted_host_count_tuples = list(sorted(
            [(v['names'], v['episodes']) for k, v in self.show.hosts_eps_map.items() if k != ''],
            key=sort_f
        ))
        msg = ""
        for host_names, eps in sorted_host_count_tuples:
            first_two = host_names.most_common(2)
            host = first_two[0][0]
            alias_host = ''
            if len(first_two) > 1 and host.lower() != first_two[1][0].lower():
                alias_host = f'(AKA {first_two[1][0]}) '

            tot_eps = len(eps)
            ls_eps = f"({self.show_max_tot_set_element(eps, sort_order)}{'...' if tot_eps > 5 else ''})\n"
            msg += f"{host} {alias_host}presente in {tot_eps} episodi{'o' if tot_eps == 1 else ''} " + ls_eps

        return msg

    @staticmethod
    def show_max_tot_set_element(s: Set, sort_order: str) -> str:
        elements = []
        ls = sorted(list(s), reverse=(sort_order != "first_appear"))
        for e in ls[:min(5, len(s))]:
            elements.append(str(e))
        return ", ".join(elements)
