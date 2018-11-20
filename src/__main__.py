import sys

from src import ServicoDadosScraper
from src.util import yaml


if __name__ == "__main__":
    yaml(ServicoDadosScraper().parse()).dump(sys.stdout)
