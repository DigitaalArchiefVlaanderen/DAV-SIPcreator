import os
import json

from ..utils.path import is_path_exists_or_creatable


class ConfigController:
    def __init__(self, path: str):
        self.configuration_path = path

    def _get_default_configuration(self) -> dict:
        return {
            "ti": {
                "API": {
                    "url": "https://digitaalarchief-ti.vlaanderen.be",
                    "username": "",
                    "password": "",
                    "client_id": "",
                    "client_secret": "",
                },
                "FTPS": {
                    "url": "ingest.digitaalarchief-ti.vlaanderen.be",
                    "username": "",
                    "password": "",
                    "port": "21",
                },
            },
            "prod": {
                "API": {
                    "url": "",
                    "username": "",
                    "password": "",
                    "client_id": "",
                    "client_secret": "",
                },
                "FTPS": {
                    "url": "ingest.digitaalarchief.vlaanderen.be",
                    "username": "",
                    "password": "",
                    "port": "21",
                },
            },
            "misc": {
                "SIP Creator opslag locatie": os.path.join(os.getcwd(), "SIP_Creator"),
                "Omgevingen": {
                    "ti": False,
                    "prod": True,
                },
            },
        }

    def _verify_configuration(self, configuration: dict) -> bool:
        """Verifies the integrity of the configuration"""
        if "misc" not in configuration:
            return False

        for environment, values in configuration.items():
            if not isinstance(values, dict):
                return False

            # NOTE: misc needs a few things
            if environment == "misc":
                if (
                    not "SIP Creator opslag locatie" in values
                    or not "Omgevingen" in values
                ):
                    return False

                if not is_path_exists_or_creatable(
                    values["SIP Creator opslag locatie"]
                ):
                    configuration[environment]["SIP Creator opslag locatie"] = os.path.join(os.getcwd(), "SIP_Creator")

                if not isinstance(values["Omgevingen"], dict):
                    return False

                active_envs = 0

                for env_active in values["Omgevingen"].values():
                    if not isinstance(env_active, bool):
                        return False

                    if env_active:
                        active_envs += 1

                if active_envs != 1:
                    return False

                continue

            # NOTE: connection details need both API and FTPS for their environment
            if not "API" in values or not "FTPS" in values:
                return False

            # NOTE: make sure the right fields are present
            if any(
                argument not in values["API"]
                for argument in (
                    "url",
                    "username",
                    "password",
                    "client_id",
                    "client_secret",
                )
            ) or any(
                argument not in values["FTPS"]
                for argument in (
                    "url",
                    "username",
                    "password",
                    "port",
                )
            ):
                return False

        return True

    def get_configuration(self) -> dict:
        if not os.path.exists(self.configuration_path):
            return self._get_default_configuration()

        with open(self.configuration_path, "r", encoding="utf-8") as f:
            try:
                configuration = json.load(f)
            except Exception:
                return self._get_default_configuration()

            if not self._verify_configuration(configuration):
                # NOTE: something in the config is bad
                return self._get_default_configuration()

            return configuration
