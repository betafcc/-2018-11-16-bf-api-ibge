import json
import posixpath
from abc import ABCMeta, abstractmethod, abstractproperty
from collections.abc import Mapping
from functools import lru_cache
from urllib.parse import urlparse

import requests
from boltons.cacheutils import cachedproperty
from parsel import Selector
from sh import node, pandoc
from toolz import unique

from .util import call, camel, commonprefix, yaml


def parse_api_docs_service(slug_name, html, base_url):
    if slug_name == "malhas":
        # malhas needs a special case
        return ApiDocsMalhas.from_html(html, base_url)
    return ApiDocsService.from_html(html, base_url)


class Mixins(Mapping, metaclass=ABCMeta):
    def __init__(self, document):
        self.document = document

    @classmethod
    def from_html(cls, html, base_url=None):
        if base_url is None:
            return cls(document=Selector(html))
        else:
            return cls(document=Selector(html, base_url=base_url))


    @classmethod
    def from_url(cls, url=None):
        if url is None:
            url = cls.url
        return cls(document=Selector(requests.get(url).text, base_url=url))

    @abstractmethod
    def to_dict(self) -> dict:
        ...

    @cachedproperty
    def _to_dict(self):
        return self.to_dict()

    def asyaml(self):
        return yaml(self)

    def __len__(self):
        return len(self._to_dict)

    def __iter__(self):
        yield from self._to_dict.keys()

    def __getitem__(self, item):
        return self._to_dict[item]


class ApiDocsHome(Mixins):
    url = "https://servicodados.ibge.gov.br/api/docs"

    def to_dict(self):
        return dict(zip(self.slugs, self.infos))

    @property
    def slugs(self):
        for node in self._service_wrappers:
            yield node.css(".headline::attr(id)").get()

    @property
    def infos(self):
        for node in self._service_wrappers:
            yield {
                "headline": "".join(node.css(".headline *::text").getall()).strip(),
                "subhead": "".join(node.css(".subhead *::text").getall()).strip(),
                "versions": dict(self._versions(node)),
            }

    @property
    def _service_wrappers(self):
        return self.document.css(".c-wrapper")

    def _versions(self, node):
        for a in node.css(".services-wrapper a"):
            version = a.css("::text").get().strip()
            incomplete_spec = {
                "info": {"version": version},
                "externalDocs": {
                    "description": "Documentação oficial",
                    "url": a.css("::attr(href)").get(),
                },
            }

            yield (version, incomplete_spec)


class ApiDocsService(Mixins):
    def to_dict(self):
        return self.spec

    @property
    def spec(self):
        return {
            "swagger": "2.0",
            **{
                camel(key): getattr(self, key)
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

    @property
    def info(self):
        return {
            "title": self.document.css("#project h1::text").get(),
            "version": self.document.css(".app-desc").re(r"\s(\d+\.\d+\.\d+)")[0],
            "description": self._info_description,
        }

    @cachedproperty
    def _info_description(self):
        # get description node
        _ = self.document.css(".app-desc ~ div")
        # get inner html
        _ = "".join(_.xpath("node()").extract())
        # to github flavoured markdown
        return pandoc(f="html", to="gfm", columns=80, _in=_).rstrip()

    @property
    def external_docs(self):
        return {
            "description": "Documentação oficial",
            "url": self.document.root.base_url,
        }

    @property
    def host(self):
        # infer host using first endpoint url
        return urlparse(self._urls[0]).netloc

    @property
    def _urls(self):
        return self.document.css("pre code .pln::text").getall()

    @property
    def base_path(self):
        endpoint_slug = urlparse(self.external_docs["url"]).path.split("/")[-1]
        commom_url = commonprefix(self._urls)

        return urlparse(
            posixpath.join(commom_url.split(endpoint_slug)[0], endpoint_slug)
        ).path

    @property
    def schemes(self):
        return list({urlparse(url).scheme for url in self._urls})

    @property
    def produces(self):
        return ["application/json"]

    @property
    def tags(self):
        _ = self.document.css(
            "#scrollingNav ul li[data-name]::attr(data-group)"
        ).getall()
        _ = unique(_)  # don't use set, keep original order
        _ = [{"name": name} for name in _]

        return _

    @property
    def paths(self):
        acc = {}
        for li in self._paths_lis:
            acc.update(self._paths_endpoint(li))
        return acc

    @property
    def _paths_lis(self):
        return self.document.css("#scrollingNav ul li[data-name]")

    def _paths_endpoint(self, li):
        li = li.attrib
        operation_id = li["data-name"]

        yield (
            self._paths_path(operation_id),
            {
                "get": {
                    "tags": [li["data-group"]],
                    "summary": self._paths_summary(operation_id),
                    "description": self._paths_description(operation_id),
                    "operationId": operation_id,
                    "parameters": self._paths_parameters(operation_id),
                    "responses": self._paths_responses(operation_id),
                }
            },
        )

    def _paths_path(self, operation_id):
        return (
            self.document.css(f"article[data-name={operation_id}] code .pln::text")
            .get()
            .split(self.base_path)[-1]
        ) or "/"

    def _paths_summary(self, operation_id):
        return self.document.css(f"article[data-name={operation_id}] h1::text").get()

    def _paths_description(self, operation_id):
        return self.document.css(
            f'article[data-name="{operation_id}"] p.marked::text'
        ).get()

    def _paths_parameters(self, operation_id):
        # turns out, theres no need to actually parse de DOM
        # as the schema is hidden in a script tag for each endpoint
        _ = (
            self.document.css(f"article[data-name={operation_id}]")
            .css("#methodsubtable script")
            .re(r"var\sschemaWrapper\s=\s({[\s\S]+});")
        )
        _ = map(json.loads, _)
        _ = list(_)

        for el in _:
            if el.get('in') == 'path':
                el['required'] = True

        return _

    def _paths_responses(self, operation_id):
        _ = (
            self.document.css(f"article[data-name={operation_id}]")
            .xpath('.//*[starts-with(@id, "responses")]//script')
            .re(r"var\sschemaWrapper\s=\s({[\s\S]+});")[0]
        )
        _ = json.loads(_)

        return {'200': _}

    @cachedproperty
    def definitions(self):
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


class ApiDocsMalhas(ApiDocsService):
    """
    Special case for /api/v2/malhas

    It's the only that doesn't provide info in responses,
    also, the `produces` entry is filled here by hand
    """

    @property
    def produces(self):
        return ["image/svg+xml", "application/vnd.geo+json", "application/json"]

    def _paths_responses(self, operation_id):
        if operation_id == "idGet":
            return {"description": "Malha renderizada"}
        raise
