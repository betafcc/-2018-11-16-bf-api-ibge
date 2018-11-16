from functools import lru_cache

import requests
from parsel import Selector

from .util import camel


class Scraper:
    def __init__(self, url=None):
        self.document = self.get(url or self.url)

    @staticmethod
    @lru_cache(None)
    def get(url):
        return Selector(requests.get(url).text, base_url=url)


class ApiDadosScraper(Scraper):
    def parse(self):
        return {
            "swagger": "2.0",
            **{camel(key): getattr(self, "parse_" + key)() for key in ["info"]},
        }

    def parse_info(self):
        return {
            "title": self.document.css("#project h1::text").get(),
            "version": self.document.css(".app-desc").re(r"\s(\d+\.\d+\.\d+)")[0],
            # "description": self.parse_info_description(),
        }
