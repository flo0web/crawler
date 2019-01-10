import json
import logging

import aiohttp
from lxml import html


class DownloadError(Exception):
    pass


class ConnError(DownloadError):
    pass


class HttpError(DownloadError):
    pass


class Request:
    def __init__(self, url, callback, headers=None):
        self.url = url
        self.callback = callback
        self.headers = headers

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.url == other.url


class Response:
    """
    Adapter to ensure compatibility of responses from
    third party libraries
    """

    def __init__(self, r):
        self._r = r

        self._html_document = None
        self._json_document = None

    @property
    async def source(self):
        return await self._r.text()

    @property
    async def html_document(self):
        if self._html_document is None:
            self._html_document = html.document_fromstring(await self.source)

        return self._html_document

    @property
    async def json_document(self):
        if self._json_document is None:
            self._json_document = json.loads(await self.source)

        return self._json_document

    def get_status_code(self):
        return self._r.status

    def get_history(self):
        return self._r.history

    def get_cookies(self):
        return self._r.cookies

    def get_url(self):
        return str(self._r.url)


class Downloader:
    def __init__(self, timeout=10):
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def download(self, url, headers=None, proxy=None) -> (Response, DownloadError):
        async with aiohttp.ClientSession() as session:
            try:
                r = await session.get(url, timeout=self._timeout, headers=headers, proxy=proxy)
            except aiohttp.ClientError:
                logging.getLogger('crawler').exception('Error downloading: %s' % url)
                raise ConnError()

            try:
                if r is not None:
                    r.raise_for_status()
            except aiohttp.ClientResponseError:
                logging.getLogger('crawler').exception('Error downloading: %s' % url)
                raise HttpError()

            await r.text()

            return Response(r)
