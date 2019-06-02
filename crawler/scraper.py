from .downloader import Request, Response

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/68.0.3440.106 Safari/537.36'
}


class Scraper:
    name = None

    def __init__(self, url):
        self._url = url

        self._frontier = None
        self._data = []

    def append_to(self, frontier):
        self._frontier = frontier

        self._frontier.schedule_request(
            Request(self._url, self._parse, headers=self._get_headers())
        )

    def get_frontier(self):
        return self._frontier

    async def _parse(self, resp: Response):
        raise NotImplemented

    def _get_headers(self):
        headers = dict(DEFAULT_HEADERS)
        return headers

    def get_url(self):
        return self._url

    def get_data(self):
        return self._data

    def __str__(self):
        return self._url

    @classmethod
    def suitable_for(cls, url):
        return cls.name in url
