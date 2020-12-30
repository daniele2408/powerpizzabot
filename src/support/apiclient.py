from support.configuration import config
from requests import get
from model.custom_exceptions import StatusCodeNot200
from typing import Any, Dict, List

class SpreakerAPIClient:
    BASE_URL: str = config["URLS"].get("BASE_URL")
    GET_USER_SHOWS_URL: str = BASE_URL + config["URLS"].get("GET_USER_SHOWS")
    GET_SHOW_EPISODES_URL: str = BASE_URL + config["URLS"].get("GET_SHOW_EPISODES")
    GET_SINGLE_EPISODE_URL: str = BASE_URL + config["URLS"].get("GET_SINGLE_EPISODE")
    GET_SHOW_URL: str = BASE_URL + config["URLS"].get("GET_SHOW")

    def __init__(self, token: str) -> None:
        self.headers = {"Authorization": f"Bearer {token}"}

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
                raise StatusCodeNot200(
                    f"get_show_episodes loop #{n_loop} result status != 200"
                )
            res_json = response.json()
            episodes.extend(res_json["response"]["items"])
            if res_json["response"]["next_url"] is None:
                stop_loop = True
            else:
                url = res_json["response"]["next_url"]
        return episodes

    def get_last_n_episode(self, show_id: str, n: int) -> List[Dict]:
        url = (
            SpreakerAPIClient.GET_SHOW_EPISODES_URL.format(show_id)
            + f"?limit={n}&sorting=newest"
        )
        res = get(url)
        if res.status_code != 200:
            raise StatusCodeNot200("get_last_n_episode result status != 200")
        return res.json()["response"]["items"]

    def get_episode_info(self, episode_id: str) -> Dict:
        response = get(SpreakerAPIClient.GET_SINGLE_EPISODE_URL.format(episode_id))
        if response.status_code != 200:
            raise StatusCodeNot200("")
        return response.json()
