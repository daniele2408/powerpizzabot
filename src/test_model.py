from model.models import SearchConfigs, UserConfig, Episode, EpisodeTopic
from support.configuration import PROCD_EP_FILEPATH
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

############## Show ##############

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