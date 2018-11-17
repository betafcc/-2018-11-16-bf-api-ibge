import json
import posixpath
from functools import lru_cache
from urllib.parse import urlparse

import requests
from parsel import Selector
from sh import node, pandoc

from .util import camel, commonprefix


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
                for key in [
                    "info",
                    "external_docs",
                    "host",
                    "base_path",
                    "schemes",
                    "produces",
                    "tags",
                    # "paths",
                    "definitions",
                ]
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
        # infer host using first endpoint url
        return urlparse(self._parse_urls()[0]).netloc

    def _parse_urls(self):
        return self.document.css("pre code .pln::text").getall()

    def parse_base_path(self):
        name = urlparse(self.parse_external_docs()["url"]).path.split("/")[-1]
        endpoints = self._parse_urls()
        commom_url = commonprefix(endpoints)

        return urlparse(posixpath.join(commom_url.split(name)[0], name)).path

    def parse_schemes(self):
        return list({urlparse(url).scheme for url in self._parse_urls()})

    def parse_produces(self):
        return ["application/json"]

    def parse_tags(self):
        _ = self.document.css(
            "#scrollingNav ul li[data-name]::attr(data-group)"
        ).getall()
        _ = set(_)
        _ = [{"name": name} for name in _]

        return _

    def parse_definitions(self):
        _ = self.document.xpath(".//script").re(r"(var\sdefs\s=\s{}[\s\S]+)</script>")[
            0
        ]
        _ = _ + "process.stdout.write(JSON.stringify(defs))"
        _ = node(_in=_)
        _ = json.loads(str(_))

        return _
