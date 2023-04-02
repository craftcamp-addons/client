from dynaconf import Dynaconf

settings = Dynaconf(
    settings_files=["settings.json", "user_settings.json"],
)
