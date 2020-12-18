import pytest
from logic.logic import SearchEngine, EpisodeHandler
from model.models import Episode, EpisodeTopic, Show
from support.configuration import CACHE_FILEPATH, RAW_EP_FILEPATH, PROCD_EP_FILEPATH
from support.apiclient import SpreakerAPIClient
from support.WordCounter import WordCounter
import json
from unittest.mock import patch


############## fixtures ##############

@pytest.fixture
def raw_ep():
    with open(RAW_EP_FILEPATH, 'r') as f:
        raw_ep = json.load(f)

    return raw_ep

@pytest.fixture
def mock_client(episode_procd: Episode):
    with patch.object(SpreakerAPIClient, 'get_episode_info') as mock_method:
        mock_method.return_value = {'response': {'episode': {'description': episode_procd.description_raw}}}
        yield SpreakerAPIClient('testtoken')

@pytest.fixture
def episode_procd():
    with open(PROCD_EP_FILEPATH, 'r') as f:
        procd_ep = json.load(f)
    episode = Episode(
        procd_ep['episode_id'],
        procd_ep['title'],
        procd_ep['published_at'],
        procd_ep['site_url'],
        procd_ep['description_raw']
    )
    episode.topics = [EpisodeTopic(a['label'], a['url']) for a in procd_ep['topics']]

    return episode

@pytest.fixture
def episode_handler(mock_client):
    return EpisodeHandler(mock_client, Show('test_id'), WordCounter())

############## SearchEngine ##############

class TestSearchEngine:

    def test_normalize_string(self):

        set_words = {
            ("ciao", "ciao"),
            ("ciao*%$)/%$ciao", "ciaociao"),
            ("ne", "ne"),
            ("La vita è bella", "la vita e bella"),
            ("Passerà", "passera"),
            ("Corfù", "corfu"),
            ("Ma però così proprio non si può", "ma pero cosi proprio non si puo"),
            ("$%$=CI$$aO", "ciao"),
            ("   strippami   ", "strippami"),
            ("niente  doppi     o tripli     o più    spazi", "niente doppi o tripli o piu spazi")
        }

        for tuple_ in set_words:
            assert SearchEngine.normalize_string(tuple_[0]) == tuple_[1]
    
    def test_scan_episode(self, episode_procd):
        babbo_res = max(SearchEngine.scan_episode(episode_procd, 'babbo'), key=lambda x: x[2])
        celeste_res = max(SearchEngine.scan_episode(episode_procd, 'celestepedone'), key=lambda x: x[2])
        kenobit_res = max(SearchEngine.scan_episode(episode_procd, 'kenobit'), key=lambda x: x[2])

        assert babbo_res[1].label == "A Babbo Morto - Zerocalcare"
        assert celeste_res[1].label == "Luca Celestepedone"
        assert kenobit_res[1].label == "Kenobisboch su Twitch!!"

        babbo_res_alt = max(SearchEngine.scan_episode(episode_procd, 'zerocalcare'), key=lambda x: x[2])
        celeste_res_alt = max(SearchEngine.scan_episode(episode_procd, 'luca'), key=lambda x: x[2])
        kenobit_res_alt = max(SearchEngine.scan_episode(episode_procd, 'twitch'), key=lambda x: x[2])

        assert babbo_res[1].label == babbo_res_alt[1].label
        assert celeste_res[1].label == celeste_res_alt[1].label
        assert kenobit_res[1].label == kenobit_res_alt[1].label

    def test_compare_string(self):

        dict_str = {
            "uccello": {
                "uccellox",
                "uccellino",
                "uccelletto",
                "uccullo"
            }
        }

        set_res = set()
        for str_, set_words in dict_str.items():
            for w in set_words:
                set_res.add((w, SearchEngine.compare_strings(str_, w)[0]))
                

        assert max(set_res, key=lambda x: x[1])[0] == "uccellox"

    def test_generate_sorted_topics(self, episode_procd):

        episodes = {'42314321': episode_procd}
        text = 'babbo'

        ls_eps, normalized_text = SearchEngine.generate_sorted_topics(episodes, text)

        assert len(ls_eps) == len(episode_procd.topics)
        assert ls_eps[0][1].label == 'A Babbo Morto - Zerocalcare'
        assert max(ls_eps, key=lambda x: x[2])[2] == ls_eps[0][2]
        assert min(ls_eps, key=lambda x: x[2])[2] == ls_eps[-1][2]

############## EpisodeHandler ##############

class TestEpisodeHandler:

    def test_convert_raw_ep(self, mock_client, episode_procd, raw_ep):

        episode_handler = EpisodeHandler(mock_client, Show('fdsafs'), WordCounter())
        episode = episode_handler.convert_raw_ep(raw_ep)
        
        assert episode.title == episode_procd.title
        assert episode.episode_id == episode_procd.episode_id
        assert episode.published_at == episode_procd.published_at
        assert episode.site_url == episode_procd.site_url
        
    def test_convert_date(self, episode_handler):

        not_it_date = "2020-12-01 23:56:54"
        it_date = "01/12/2020"

        res = episode_handler.convert_to_italian_date_format(not_it_date)

        assert it_date == res

    def test_format_episode_line(self, episode_handler):

        title_A = "120: Hard Chiacchiere feat. Kenobit"
        title_B = "ep 120: Hard Chiacchiere feat. Kenobit"

        url = "unurlacaso"

        expected = "Episodio 120: <a href='unurlacaso'> Hard Chiacchiere feat. Kenobit</a>"

        res_A = episode_handler.format_episode_title_line(url, title_A)
        res_B = episode_handler.format_episode_title_line(url, title_B)

        assert expected == res_A
        assert expected == res_B
