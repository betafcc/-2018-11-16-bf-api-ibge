import json
import logging
import posixpath
from functools import lru_cache
from urllib.parse import urlparse

import requests
from parsel import Selector
from sh import node, pandoc

from .util import camel, commonprefix, deep_merge


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


class Scraper:
    def __init__(self, url=None):
        self.document = self.get(url or self.url)

    @staticmethod
    @lru_cache(None)
    def get(url):
        return Selector(requests.get(url).text, base_url=url)


class ServicoDadosScraper(Scraper):
    url = "https://servicodados.ibge.gov.br/api/docs"

    def parse(self):
        base = self.parse_base()

        for slug, info in base.items():
            for version, spec in info["versions"].items():
                url = spec["externalDocs"]["url"]

                if slug == "malhas":  # malhas special case
                    scraper = ApiDadosMalhasScraper
                else:
                    scraper = ApiDadosScraper

                logger.info(f'parsing "{slug}" version "{version}" at "{url}"')

                info["versions"][version] = deep_merge(spec, scraper(url).parse())

        return base

    def parse_base(self):
        return {
            self.parse_slug(node): self.parse_info(node)
            for node in self.find_services()
        }

    def find_services(self):
        return self.document.css(".c-wrapper")

    @classmethod
    def parse_slug(cls, service_node):
        return service_node.css(".headline::attr(id)").get()

    @classmethod
    def parse_info(cls, service_node):
        return {
            "headline": "".join(service_node.css(".headline *::text").getall()).strip(),
            "subhead": "".join(service_node.css(".subhead *::text").getall()).strip(),
            "versions": cls.parse_versions(service_node),
        }

    @classmethod
    def parse_versions(cls, service_node):
        return {
            a.css("::text")
            .get()
            .strip(): {
                "info": {"version": a.css("::text").get().strip()},
                "externalDocs": {
                    "description": "Página oficial",
                    "url": a.css("::attr(href)").get(),
                },
            }
            for a in service_node.css(".services-wrapper a")
        }


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
                    "paths",
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

    def parse_paths(self):
        lis = self.document.css("#scrollingNav ul li[data-name]")

        return dict(map(self._parse_paths_endpoint, lis))

    def _parse_paths_endpoint(self, li):
        li = li.attrib
        operation_id = li["data-name"]

        #     return (self._parse_paths_path(operation_id), operation_id)
        return (
            self._parse_paths_path(operation_id),
            {
                "get": {
                    "tags": [li["data-group"]],
                    "summary": self._parse_paths_summary(operation_id),
                    "description": self._parse_paths_description(operation_id),
                    "operationId": operation_id,
                    "parameters": self._parse_paths_parameters(operation_id),
                    "responses": self._parse_paths_responses(operation_id),
                }
            },
        )

    def _parse_paths_path(self, operation_id):
        return (
            self.document.css(f"article[data-name={operation_id}] code .pln::text")
            .get()
            .split(self.parse_base_path())[-1]
        )

    def _parse_paths_summary(self, operation_id):
        return self.document.css(f"article[data-name={operation_id}] h1::text").get()

    def _parse_paths_description(self, operation_id):
        return self.document.css(
            f'article[data-name="{operation_id}"] p.marked::text'
        ).get()

    def _parse_paths_parameters(self, operation_id):
        # turns out, theres no need to actually parse de DOM
        # as the schema is hidden in a script tag for each endpoint
        _ = (
            self.document.css(f"article[data-name={operation_id}]")
            .css("#methodsubtable script")
            .re(r"var\sschemaWrapper\s=\s({[\s\S]+});")
        )
        _ = map(json.loads, _)
        _ = list(_)

        return _

    def _parse_paths_responses(self, operation_id):
        _ = (
            self.document.css(f"article[data-name={operation_id}]")
            .xpath('.//*[starts-with(@id, "responses")]//script')
            .re(r"var\sschemaWrapper\s=\s({[\s\S]+});")[0]
        )
        _ = json.loads(_)

        return {200: _}

    def parse_definitions(self):
        # The definitions are hidden in the first script tag
        # but are set line by line like so:
        # var defs = {};
        # defs.Ufs = {...};
        # defs.Macrorregiao = {...};
        # need to grab all the code and run in JS somehow
        _ = self.document.xpath(".//script").re(r"(var\sdefs\s=\s{}[\s\S]+)</script>")[
            0
        ]
        _ = _ + "process.stdout.write(JSON.stringify(defs))"
        _ = node(_in=_)
        _ = json.loads(str(_))

        return _


class ApiDadosMalhasScraper(ApiDadosScraper):
    """
    Special case for /api/v2/malhas

    It's the only that doesn't provide info in responses,
    also, the `produces` entry is filled here by hand
    """

    def parse_produces(self):
        return ["image/svg+xml", "application/vnd.geo+json", "application/json"]

    def _parse_paths_responses(self, operation_id):
        if operation_id == "idGet":
            return {"description": "Malha renderizada"}
        raise
