from dynaconf import Dynaconf
from pydantic import BaseSettings, Field, AnyUrl
from singleton_decorator import singleton

settings = Dynaconf(
    settings_files=['settings.json'],
)