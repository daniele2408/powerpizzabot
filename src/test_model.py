import os
os.environ["PPB_ENV"] = "unittest"
from model.models import SearchConfigs, UserConfig, Episode, EpisodeTopic
from support.configuration import PROCD_EP_FILEPATH, SRC_FOLDER
import pytest
import json

############## fixtures ##############

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
def raw_ep():
    with open(RAW_EP_FILEPATH, 'r') as f:
        raw_ep = json.load(f)

    return raw_ep

@pytest.fixture(autouse=True)
def run_before():
    SearchConfigs.DUMP_FOLDER = os.path.join(SRC_FOLDER, 'tests/usr_cfg_test')
    SearchConfigs.USERS_CFG_FILEPATH = os.path.join(SRC_FOLDER, 'tests/usr_cfg_test', 'users_cfg.json')
    SearchConfigs.user_data[1] = UserConfig(5,1)
    SearchConfigs.user_data[2] = UserConfig(10,30)
    SearchConfigs.user_data[3] = UserConfig(3,90)
    yield
    SearchConfigs.user_data.clear()
    filelist = [f for f in os.listdir(SearchConfigs.DUMP_FOLDER)]
    for f in filelist:
        os.remove(os.path.join(SearchConfigs.DUMP_FOLDER, f))

############## Episode ##############

def test_to_dict(episode_procd):

    dict_ = episode_procd.to_dict()

    assert isinstance(dict_, dict)
    assert dict_['episode_id'] == episode_procd.episode_id
    assert dict_['title'] == episode_procd.title
    assert dict_['published_at'] == episode_procd.published_at
    assert dict_['site_url'] == episode_procd.site_url
    assert dict_['description_raw'] == episode_procd.description_raw

    for topic_dict, topic_ep in zip(dict_['topics'], episode_procd.topics):
        assert topic_ep.label == topic_dict['label']
        assert topic_ep.url == topic_dict['url']

def test_from_dict(episode_procd):

    dict_ = episode_procd.to_dict()

    ep_from_dict = Episode.from_dict(dict_)

    assert isinstance(ep_from_dict, Episode)
    assert episode_procd.episode_id == ep_from_dict.episode_id
    assert episode_procd.title == ep_from_dict.title
    assert episode_procd.published_at == ep_from_dict.published_at
    assert episode_procd.site_url == ep_from_dict.site_url
    assert episode_procd.description_raw == ep_from_dict.description_raw

def test_populate_topic(episode_procd):

    episode_procd.topics = list()

    episode_procd.populate_topics()

    assert len(episode_procd.topics) == 14
    assert episode_procd.topics[0].label == 'A Babbo Morto - Zerocalcare'
    assert episode_procd.topics[4].url == 'https://www.youtube.com/watch?v=Vt7u4SSXU5o'
    
    assert all(isinstance(topic.label, str) for topic in episode_procd.topics)
    assert all(isinstance(topic.url, str) for topic in episode_procd.topics)
    
def test_populate_topic_wrong_description(episode_procd):

    episode_procd.topics = list()
    episode_procd.description_raw = 'not a formally correct description'

    episode_procd.populate_topics()

    assert not len(episode_procd.topics)

############## SearchConfig ##############

def test_get_user_cfg():

    assert isinstance(SearchConfigs.get_user_cfg(1), UserConfig)
    assert isinstance(SearchConfigs.get_user_cfg(2), UserConfig)
    assert isinstance(SearchConfigs.get_user_cfg(3), UserConfig)

    assert SearchConfigs.get_user_cfg(1).n == 5
    assert SearchConfigs.get_user_cfg(2).n == 10
    assert SearchConfigs.get_user_cfg(3).n == 3

def test_get_user_show_first_n():

    assert SearchConfigs.get_user_show_first_n(1) == 5
    assert SearchConfigs.get_user_show_first_n(2) == 10
    assert SearchConfigs.get_user_show_first_n(3) == 3

def test_get_user_show_min_threshold():

    assert SearchConfigs.get_user_show_min_threshold(1) == 1
    assert SearchConfigs.get_user_show_min_threshold(2) == 30
    assert SearchConfigs.get_user_show_min_threshold(3) == 90

def test_chek_if_same_value():

    assert SearchConfigs.check_if_same_value(1, 5, 'n')
    assert SearchConfigs.check_if_same_value(1, 1, 'm')
    assert not SearchConfigs.check_if_same_value(1, 999, 'n')
    assert not SearchConfigs.check_if_same_value(1, 999, 'm')

    assert SearchConfigs.check_if_same_value(2, 10, 'n')
    assert SearchConfigs.check_if_same_value(2, 30, 'm')
    assert not SearchConfigs.check_if_same_value(2, 999, 'n')
    assert not SearchConfigs.check_if_same_value(2, 999, 'm')    

    assert SearchConfigs.check_if_same_value(3, 3, 'n')
    assert SearchConfigs.check_if_same_value(3, 90, 'm')
    assert not SearchConfigs.check_if_same_value(3, 999, 'n')
    assert not SearchConfigs.check_if_same_value(3, 999, 'm')

    with pytest.raises(ValueError):
        SearchConfigs.check_if_same_value(1, 5, 'w')

def test_set_user_cfg():

    SearchConfigs.set_user_cfg(1, 999, 'n')
    SearchConfigs.set_user_cfg(1, 99, 'm')

    assert SearchConfigs.get_user_show_first_n(1) == 999
    assert SearchConfigs.get_user_cfg(1).m == 99

    with pytest.raises(ValueError):
        SearchConfigs.set_user_cfg(1, 999, 'w')

def test_normalize_user_data():

    data = SearchConfigs.normalize_user_data()

    assert data[1]['n'] == SearchConfigs.get_user_show_first_n(1)
    assert data[1]['m'] == SearchConfigs.get_user_show_min_threshold(1)

    assert data[2]['n'] == SearchConfigs.get_user_show_first_n(2)
    assert data[2]['m'] == SearchConfigs.get_user_show_min_threshold(2)

    assert data[3]['n'] == SearchConfigs.get_user_show_first_n(3)
    assert data[3]['m'] == SearchConfigs.get_user_show_min_threshold(3)

def test_dump_data():

    SearchConfigs.dump_data()

    SearchConfigs.user_data[1] = UserConfig(10, 20)
    SearchConfigs.user_data[2] = UserConfig(30, 40)

    SearchConfigs.dump_data()

    SearchConfigs.user_data[1] = UserConfig(999, 998)
    SearchConfigs.user_data[2] = UserConfig(111, 112)

    assert SearchConfigs.get_user_show_first_n(1) == 999
    assert SearchConfigs.get_user_show_min_threshold(1) == 998

    assert SearchConfigs.get_user_show_first_n(2) == 111
    assert SearchConfigs.get_user_show_min_threshold(2) == 112

    SearchConfigs.init_data()

    assert SearchConfigs.get_user_show_first_n(1) == 10
    assert SearchConfigs.get_user_show_min_threshold(1) == 20

    assert SearchConfigs.get_user_show_first_n(2) == 30
    assert SearchConfigs.get_user_show_min_threshold(2) == 40
