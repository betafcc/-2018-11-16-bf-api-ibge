from pathlib import Path

import fire
import requests

from . import api_docs
from .util import yaml


def specs_base():
    return api_docs.asyaml().dump()


def list_specs(specs_base: str):
    for slug_name, info in yaml.load(specs_base).items():
        for version, incomplete_spec in info["versions"].items():
            yield _slug(slug_name=slug_name, version=version)


_slug = "{slug_name}_v{version}".format
_split_slug = lambda s: s.split("_v")


def fetch(slug, specs_base):
    slug_name, version = _split_slug(slug)
    url = yaml.load(specs_base)[slug_name].versions[version].externalDocs.url

    return requests.get(url).text


if __name__ == "__main__":
    fire.Fire()
