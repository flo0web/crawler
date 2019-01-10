import asyncio
import logging
from asyncio import Queue
from typing import List

from .downloader import Request, Downloader, DownloadError, ConnError
from .proxy import ProxyManager
from .scraper import Scraper

DEFAULT_WORKERS_LIMIT = 4


class Crawler:
    """
    Crawler регистрирует список скраперов, которые он будет обслуживать,
    управляет очередью запросов на извлечение от скраперов,
    извлекает код страниц из запросов с помощью загрузчика
    и отправляет скраперу для распознавание
    """

    def __init__(self, seeds: List[Scraper], workers_limit=None):
        self._seeds = seeds
        self._workers_limit = workers_limit or DEFAULT_WORKERS_LIMIT

        self._queue = Queue()
        self._known_requests = set()

        self._loop = asyncio.get_event_loop()

        self.__downloader = None

    async def run(self):
        for seed in self._seeds:
            seed.append_to(self)

        workers = [asyncio.Task(self._work(), loop=self._loop) for _ in range(self._workers_limit)]

        await self._queue.join()

        for w in workers:
            w.cancel()

    async def _work(self):
        while True:
            req = await self._queue.get()

            try:
                await self._process_request(req)
            except Exception:
                logging.getLogger('crawler').exception('Unhandled error: %s' % req.url)

            self._queue.task_done()

    def schedule_request(self, req: Request):
        if req not in self._known_requests:
            logging.getLogger('crawler').info('Request scheduled: %s' % req.url)

            self._known_requests.add(req)
            self._queue.put_nowait(req)

    async def _process_request(self, req: Request):
        logging.getLogger('crawler').info('Request started: %s' % req.url)

        try:
            resp = await self._downloader.download(req.url, headers=req.headers)
        except DownloadError:
            pass
        else:
            await req.callback(resp)

        logging.getLogger('crawler').info('Request finished: %s' % req.url)

    @property
    def _downloader(self):
        if self.__downloader is None:
            self.__downloader = Downloader()

        return self.__downloader


class StealthCrawler(Crawler):
    def __init__(self, proxy_manager: ProxyManager, seeds: List[Scraper], workers_limit=4):
        super().__init__(seeds, workers_limit)

        self._proxy_manager = proxy_manager

    async def _process_request(self, req: Request):
        proxy = await self._proxy_manager.get()

        try:
            resp = await self._downloader.download(req.url, headers=req.headers, proxy=proxy.address)
        except ConnError:
            # Обработка ошибок сети (таймауты, соединения и т.п.)
            self._proxy_manager.release_unavailable(proxy)
        except DownloadError:
            # Обработка ошибок, не связаных с сетью (http и т.п.)
            self._proxy_manager.release_valid(proxy)
        else:
            self._proxy_manager.release_valid(proxy)

            await req.callback(resp)
