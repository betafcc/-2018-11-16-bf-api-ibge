from functools import lru_cache
from urllib.parse import urlparse

import requests
from parsel import Selector
from sh import pandoc

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
        # Each top-level field in swagger 2.0 spec should map to one
        # separate method scraping the relevant portion of self.document
        return {
            "swagger": "2.0",
            **{
                camel(key): getattr(self, "parse_" + key)()
                for key in ["info", "external_docs"]
            },
        }

    def parse_info(self):
        return {
            "title": self.document.css("#project h1::text").get(),
            "version": self.document.css(".app-desc").re(r"\s(\d+\.\d+\.\d+)")[0],
            "description": self.parse_info_description(),
        }

    def parse_info_description(self):
        # get description node
        _ = self.document.css(".app-desc ~ div")
        # get inner html
        _ = "".join(_.xpath("node()").extract())
        # to github flavoured markdown
        return pandoc(f="html", to="gfm", columns=80, _in=_).rstrip()

    def parse_external_docs(self):
        return {
            "description": "Documentação oficial",
            "url": self.document.root.base_url,
        }

    def parse_host(self):
        return urlparse(self.parse_urls()[0]).netloc
