import os
import json

from ..utils.path import is_path_exists_or_creatable
from ..utils.configuration import Configuration
from ..utils.version import ConfigurationVersion


class ConfigController:
    def __init__(self, path: str):
        self.configuration_path = path

    def _verify_configuration(self, configuration: dict, version: ConfigurationVersion=ConfigurationVersion.V2) -> bool:
        """Verifies the integrity of the configuration"""
        if "misc" not in configuration:
            return False

        for environment, values in configuration.items():
            if not isinstance(values, dict):
                return False

            # NOTE: misc needs a few things
            if environment == "misc":
                if not "SIP Creator opslag locatie" in values:
                    return False

                if not is_path_exists_or_creatable(
                    values["SIP Creator opslag locatie"]
                ):
                    configuration[environment]["SIP Creator opslag locatie"] = os.path.join(os.getcwd(), "SIP_Creator")

                if version == ConfigurationVersion.V1:
                    tabs = ("Omgevingen",)
                elif version == ConfigurationVersion.V2:
                    tabs = ("Omgevingen", "Rollen", "Type SIPs")

                for tab in tabs:
                    if not tab in values:
                        return False

                    if not isinstance(values[tab], dict):
                        return False

                    active = 0

                    for is_active in values[tab].values():
                        if not isinstance(is_active, bool):
                            return False

                        if is_active:
                            active += 1

                    if active != 1:
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

    def get_configuration(self) -> Configuration:
        if not os.path.exists(self.configuration_path):
            return Configuration.get_default()

        with open(self.configuration_path, "r", encoding="utf-8") as f:
            try:
                configuration = json.load(f)
            except Exception:
                return Configuration.get_default()

            if not self._verify_configuration(configuration):
                # NOTE: something in the config is bad

                # Check if we're just using an older version
                if not self._verify_configuration(configuration, version=ConfigurationVersion.V1):
                    return Configuration.get_default()
                
                # Valid for version 1
                return Configuration.from_json(configuration, version=ConfigurationVersion.V1)

            return Configuration.from_json(configuration, version=ConfigurationVersion.V2)
