import logging
import sys
from pathlib import Path

from src import ServicoDadosScraper
from src.util import yaml


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

    out_dir = Path(__file__).resolve().parent.parent / "apis"
    out_dir.mkdir(exist_ok=True)

    todas = yaml(ServicoDadosScraper().parse())

    file = out_dir / "todas.yaml"
    logger.info(f'writing "todas" to "{file}"')
    todas.dump(file)

    for slug in todas:
        for version, spec in todas[slug]['versions'].items():
            file = out_dir / (f'{slug}{version}.yaml')
            logger.info(f'writing "{slug}" to "{file}"')
            spec.dump(file)
