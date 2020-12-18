import pytest
from logic.logic import SearchEngine, EpisodeHandler
from model.models import Episode, EpisodeTopic, Show
from support.configuration import CACHE_FILEPATH
from support.apiclient import SpreakerAPIClient
from support.WordCounter import WordCounter
import json
from unittest.mock import patch

############## utils ##############

def load_cache():
    with open(CACHE_FILEPATH, 'r') as f:
        data = json.load(f)

    return data

############## fixtures ##############

@pytest.fixture
def mock_client():
    with patch.object(SpreakerAPIClient, 'get_episode_info') as mock_method:
        mock_method.return_value = 'pippo'
        yield SpreakerAPIClient('bla')


@pytest.fixture
def episode_procd():
    data = load_cache()
    first_ep = [ep for ep in data if ep['episode_id']==42314321][0]
    episode = Episode(
        first_ep['episode_id'],
        first_ep['title'],
        first_ep['published_at'],
        first_ep['site_url'],
        first_ep['description_raw']
    )
    episode.topics = [EpisodeTopic(a['label'], a['url']) for a in first_ep['topics']]

    return episode

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


class TestEpisodeHandler:

    def test_prova(self, mock_client):
        episode_handler = EpisodeHandler(mock_client, Show('fdsafs'), WordCounter())
        episode_handler.convert_raw_ep({'episode_id':'vlah'})
        assert False