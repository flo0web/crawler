import asyncio
import json

import aiohttp
from lxml import html
from multidict import MultiDict

METH_GET = 'GET'
METH_POST = 'POST'


class DownloadError(Exception):
    pass


class ConnError(DownloadError):
    pass


class HttpError(DownloadError):
    pass


def dict_to_tuple(target):
    if not target or target is None:
        return ()

    if isinstance(target, (dict, MultiDict)):
        return tuple((k, dict_to_tuple(v) if isinstance(v, (dict, MultiDict, list)) else v) for k, v in target.items())
    elif isinstance(target, list):
        return tuple((dict_to_tuple(v) if isinstance(v, (dict, MultiDict, list)) else v) for v in target)
    elif isinstance(target, (str, bytes)):
        return target


class Request:
    def __init__(self, url, callback, method=METH_GET, data=None, json=False, headers=None, encoding=None):
        self._url = url
        self._headers = headers
        self._method = method
        self._encoding = encoding

        self._data = data
        self._frozen_data = dict_to_tuple(data)
        self._json = json

        self.callback = callback

    def __hash__(self):
        return hash((self._url,) + self._frozen_data)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        return self._url == other._url and self._data == other._data

    def download_params(self):
        return {
            'method': self._method,
            'url': self._url,
            'data': self._data,
            'json': self._json,
            'headers': self._headers,
            'encoding': self._encoding
        }

    def get_url(self):
        return str(self._url)


class Response:
    """
    Adapter to ensure compatibility of responses from
    third party libraries
    """

    def __init__(self, r, text):
        self._r = r

        self._text = text

        self._html_document = None
        self._json_document = None

    @property
    async def source(self):
        return self._text

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

    async def download(self, url, method=METH_GET, data=None, json=False, headers=None, encoding=None, proxy=None) -> (
            Response, DownloadError):
        try:
            r = await self._session.request(
                method=method,
                url=url,
                data=data if not json else None,
                json=data if json else None,
                timeout=self._timeout,
                headers=headers,
                proxy=proxy
            )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise ConnError()

        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError:
            raise HttpError()
        else:
            text = await r.text(encoding=encoding)
        finally:
            r.release()

        return Response(r, text)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        await self._session.close()
