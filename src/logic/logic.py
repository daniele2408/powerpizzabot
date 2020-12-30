from model.models import Episode
from datetime import datetime
import re
from support.TextRepo import TextRepo
import logging
from support.apiclient import SpreakerAPIClient
from model.models import Show
from typing import Dict, List
from support.WordCounter import WordCounter
from support.Cacher import Cacher
from typing import Dict, List, Tuple
from model.models import Episode
from unidecode import unidecode
import re
from fuzzywuzzy import fuzz
from model.models import EpisodeTopic

logger = logging.getLogger('logic.logic')

TopicSnippet = Tuple[str, EpisodeTopic, int, str, str]

class SearchEngine:
    @classmethod
    def generate_sorted_topics(
        cls, episodes: Dict[str, Episode], text: str
    ) -> Tuple[List[TopicSnippet], str]:
        episodes_topic = list()
        normalized_text = cls.normalize_string(text)
        for ep in episodes.values():
            episodes_topic.extend(cls.scan_episode(ep, normalized_text))

        return (
            sorted(episodes_topic, key=lambda x: (-x[2], len(x[1].label))),
            normalized_text,
        )

    @staticmethod
    def normalize_string(s: str) -> str:
        s = unidecode(s.lower())
        s = re.sub("[^A-Za-z0-9 ]+", "", s)
        s = re.sub("[ ]+", " ", s).strip()
        return s

    @classmethod
    def compare_strings(cls, descr: str, text_input: str) -> Tuple[int, str]:
        # TODO: /s dark soul prende prima Dark Crystal e poi "5 ORE DI DARK SOULS", non va bene
        # same: DLC di cuphead dà prima Cuphead e poi "DLC di Cuphead rimandato al 2021 because qualità"
        # altra idea per i match: fare un filtro min in base allo score max, se è 100 allora falli vedere fino a 90(?), non mi serve scendere e vedere i 70, se è 80 allora posso far vedere anche gli altri ecc
        # altra cacca: se cerco anello "compagnia dell'anello mi viene per terzo, gestire apostrofo"
        token_set = (fuzz.token_set_ratio(descr, text_input), "token_set")
        token_sort = (fuzz.token_sort_ratio(descr, text_input), "token_sort")
        if len(text_input.split(" ")) == 1:
            max_partial = (
                max([fuzz.ratio(text_input, word) for word in descr.split(" ")]),
                "max_simple_ratio",
            )
        else:
            max_partial = (0, "max_simple_ratio")

        return max((token_set, token_sort, max_partial), key=lambda x: x[0])

        # # da ponderare
        # if best_result[0] >= 80:
        #     return best_result
        # else:
        #     return (
        #         round(best_result[0] * 0.5),
        #         best_result[1],
        #     )  # penalty if measure < 80

    @classmethod
    def scan_episode(cls, episode: Episode, normalized_text: str) -> List[TopicSnippet]:
        ls_res = list()
        for topic in episode.topics:
            match_score, technique = cls.compare_strings(
                cls.normalize_string(topic.label), normalized_text
            )
            ls_res.append(
                (episode.episode_id, topic, match_score, technique, topic.url)
            )
        return ls_res



class EpisodeHandler:

    # TODO: considera un singletone con __new__ e chiamarlo da dentro search()

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
        #TODO: assicurarsi che il pattern sia corretto a priori
        pre_colons, post_colons = title.split(":", 1)
        number_ep = re.findall("[0-9]+", pre_colons)
        return f"Episodio {number_ep[0]}: <a href='{site_url}'>{post_colons}</a>"

    def search_text_in_episodes(
        self, text: str, n: int, m: int, show_tech: bool = False
    ) -> str:
        sorted_tuple_episodes, normalized_text = SearchEngine.generate_sorted_topics(
            self.show.episodes, text
        )
        self.word_counter.add_word(normalized_text)
        filter_episodes = [tpl for tpl in sorted_tuple_episodes if tpl[2] > m][:n]

        if len(filter_episodes):
            return self.format_response(filter_episodes, show_tech)
        else:
            return TextRepo.MSG_NO_RES.format(m)

    def format_response(
        self, first_eps_sorted: List[TopicSnippet], admin_req: bool
    ) -> str:

        message = ""
        i = 1
        for tuple_ in first_eps_sorted:
            ep = self.show.get_episode(tuple_[0])
            score = f"SCORE {tuple_[2]}" if admin_req else ""
            topic_url = tuple_[4]
            topic_label = tuple_[1].label
            episode_line = self.format_episode_title_line(ep.site_url, ep.title)
            date = self.convert_to_italian_date_format(ep.published_at)
            message += TextRepo.MSG_RESPONSE.format(
                i, score, topic_url, topic_label, episode_line, date
            )

            technique_used = tuple_[3]
            message += f"\nTechnique: {technique_used}\n" if admin_req else "\n"
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
        self.word_counter.dump_counter()

