import asyncio
from typing import List

from .crawler import Crawler
from .scraper import Scraper


async def crawl(scrapers: List[Scraper]):
    crawler = Crawler(seeds=scrapers)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(crawler.run())

    loop.stop()
    loop.run_forever()

    loop.close()

    for scraper in scrapers:
        yield scraper.get_data()
