import asyncio
import json
import logging

import aiohttp
from lxml import html

METH_GET = 'GET'
METH_POST = 'POST'


class DownloadError(Exception):
    pass


class ConnError(DownloadError):
    pass


class HttpError(DownloadError):
    pass


class Request:
    def __init__(self, url, callback, method=METH_GET, data=None, headers=None):
        self._url = url
        self._headers = headers
        self._method = method

        self._data = tuple((k, v) for k, v in data.items()) if data is not None else ()

        self.callback = callback

    def __hash__(self):
        return hash((self._url,) + self._data)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        return self._url == other._url and self._data == other._data

    def download_params(self):
        return {
            'method': self._method,
            'url': self._url,
            'data': self._data,
            'headers': self._headers
        }


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

    def get_headers(self):
        return self._r.headers


class Downloader:
    def __init__(self, timeout=10):
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = aiohttp.ClientSession()

    async def download(self, url, method=METH_GET, data=None, headers=None, proxy=None) -> (Response, DownloadError):
        try:
            r = await self._session.request(method=method, url=url, data=data, timeout=self._timeout,
                                            headers=headers, proxy=proxy)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            logging.getLogger('crawler').exception('Error downloading: %s' % url)
            raise ConnError()

        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError:
            logging.getLogger('crawler').exception('Error downloading: %s' % url)
            raise HttpError()
        else:
            await r.text()
        finally:
            r.release()

        return Response(r)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        await self._session.close()
