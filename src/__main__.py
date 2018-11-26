from pathlib import Path

import fire
import requests

from . import ApiDocsHome, parse_api_docs_service
from .util import yaml, spec_errors, deep_merge


def specs_base():
    return ApiDocsHome.from_url().asyaml().dump()


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


def parse(slug, html, specs_base, hand_fixes=""):
    slug_name, version = _split_slug(slug)

    with open(html) as fp:
        html = fp.read()

    specs_base = yaml.load(specs_base)

    if hand_fixes:
        try:
            hand_fixes = yaml.load(hand_fixes)
        except FileNotFoundError:
            hand_fixes = yaml({})
    else:
        hand_fixes = yaml({})

    result = deep_merge(
        specs_base[slug_name].versions[version].to_dict(),
        parse_api_docs_service(
            html=html,
            slug_name=slug_name,
            base_url=specs_base[slug_name].versions[version].externalDocs.url,
        ).to_dict(),
        hand_fixes.to_dict(),
    )
    return yaml(result).dump()

    # errors = spec_errors(result)

    # if errors:
    #     raise Exception(spec_errors(result), result)
    # else:
    #     return yaml(result).dump()


if __name__ == "__main__":
    fire.Fire()
