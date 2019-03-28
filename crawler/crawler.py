import asyncio
import logging
from asyncio import Queue
from collections import deque
from typing import List

from .downloader import Request, Downloader, DownloadError, ConnError
from .proxy import ProxyManager
from .scraper import Scraper

DEFAULT_WORKERS_LIMIT = 4


class Frontier:
    """
    The frontier collects requests from the one or more scrapers and gives out to the crawler on demand.
    """

    def __init__(self):
        self._requests_queue = deque()
        self._known_requests = set()

    def schedule_request(self, req: Request):
        """Registers a new request in case it has not been registered before."""
        if req not in self._known_requests:
            logging.getLogger('crawler').info('Request scheduled: %s' % req.download_params())

            self._known_requests.add(req)
            self._requests_queue.appendleft(req)

    def next_request(self):
        """Returns the next request from the request queue"""
        return self._requests_queue.pop()


class Crawler:
    """
    Crawler регистрирует список скраперов, которые он будет обслуживать,
    извлекает код страниц из запросов с помощью загрузчика
    и отправляет скраперу для распознавание
    """

    def __init__(self, seeds: List[Scraper], workers_limit=None, on_complete=None):
        self._workers_limit = workers_limit or DEFAULT_WORKERS_LIMIT
        self._on_complete = on_complete

        self._queue = Queue()
        self._loop = asyncio.get_event_loop()

        self._init(seeds)

    def _init(self, seeds):
        for s in seeds:
            self._queue.put_nowait(s)

    async def run(self):
        workers = [asyncio.Task(self._work(), loop=self._loop) for _ in range(self._workers_limit)]

        await self._queue.join()

        for w in workers:
            w.cancel()

    async def _work(self):
        while True:
            spider = await self._queue.get()

            frontier = Frontier()
            spider.append_to(frontier)

            async with Downloader() as downloader:
                while True:
                    try:
                        req = frontier.next_request()
                    except IndexError:
                        break

                    try:
                        await self._process_request(req, downloader)
                    except Exception:
                        logging.getLogger('crawler').exception('Unhandled error: %s' % req.url)

            if self._on_complete is not None:
                self._on_complete(spider)

            self._queue.task_done()

    async def _process_request(self, req: Request, downloader: Downloader):
        logging.getLogger('crawler').info('Request started: %s' % req.download_params())

        try:
            resp = await downloader.download(**req.download_params())
        except DownloadError:
            pass
        else:
            await req.callback(resp)

        logging.getLogger('crawler').info('Request finished: %s' % req.download_params())


class StealthCrawler(Crawler):
    def __init__(self, proxy_manager: ProxyManager, seeds: List[Scraper], workers_limit=4, on_complete=None):
        super().__init__(seeds, workers_limit, on_complete)

        self._proxy_manager = proxy_manager

    async def _process_request(self, req: Request, downloader: Downloader):
        proxy = await self._proxy_manager.get()

        try:
            resp = await downloader.download(**req.download_params(), proxy=proxy.address)
        except ConnError:
            # Обработка ошибок сети (таймауты, соединения и т.п.)
            self._proxy_manager.release_unavailable(proxy)
        except DownloadError:
            # Обработка ошибок, не связаных с сетью (http и т.п.)
            self._proxy_manager.release_valid(proxy)
        else:
            self._proxy_manager.release_valid(proxy)

            await req.callback(resp)
