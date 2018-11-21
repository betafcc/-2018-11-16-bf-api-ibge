import logging
import sys
from pathlib import Path

from src import ServicoDadosScraper
from src.util import yaml





if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)


    __dir = Path(__file__).resolve().parent.parent

    todas = yaml(ServicoDadosScraper().parse())

    file = __dir / 'todas.yaml'
    logger.info(f'writing "todas" to "{file}"')
    todas.dump(file)

    for slug in todas:
        file = __dir / (slug + '.yaml')
        logger.info(f'writing "{slug}" to "{file}"')
        todas[slug].dump(file)
    # path = cwd / 'todas.yaml'
    # logger.info('escrevendo {}')
