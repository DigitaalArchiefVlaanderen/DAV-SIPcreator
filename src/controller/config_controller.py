import json
import os

from src.utils.constants import (
    CONFIG_KEY_BESTANDSCONTROLE,
    CONFIG_KEY_ENVIRONMENTS,
    CONFIG_KEY_ROLES,
    CONFIG_KEY_SIP_STORAGE,
    CONFIG_KEY_TYPE_SIPS,
    CONFIG_SECTION_MISC,
    CONFIGURATION_FILE_NAME,
    ConfigKey,
    SaveLocations,
    SIPType,
)
from src.utils.data_objects.configuration import Configuration, ConfigurationVersion
from src.utils.path import is_path_exists_or_creatable


class ConfigController:
    @staticmethod
    def _verify_configuration(
        configuration: dict, root_path: str, version: ConfigurationVersion = ConfigurationVersion.V4
    ) -> bool:
        if CONFIG_SECTION_MISC not in configuration:
            return False

        for environment, values in configuration.items():
            if not isinstance(values, dict):
                return False

            if environment == CONFIG_SECTION_MISC:
                if CONFIG_KEY_SIP_STORAGE not in values:
                    return False

                if version in (ConfigurationVersion.V5, ConfigurationVersion.V4, ConfigurationVersion.V3):
                    if CONFIG_KEY_BESTANDSCONTROLE not in values:
                        return False

                if not is_path_exists_or_creatable(values[CONFIG_KEY_SIP_STORAGE]):
                    configuration[environment][CONFIG_KEY_SIP_STORAGE] = os.path.join(
                        root_path, SaveLocations.DEFAULT_BASE_SAVE_LOCATION.value
                    )

                if version == ConfigurationVersion.V1:
                    tabs = (CONFIG_KEY_ENVIRONMENTS,)
                else:
                    tabs = (CONFIG_KEY_ENVIRONMENTS, CONFIG_KEY_ROLES, CONFIG_KEY_TYPE_SIPS)

                for tab in tabs:
                    if tab not in values:
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

                    if tab == CONFIG_KEY_TYPE_SIPS and version in (ConfigurationVersion.V5, ConfigurationVersion.V4):
                        if SIPType.ONROEREND_ERFGOED not in values[tab]:
                            return False

                        if version == ConfigurationVersion.V5:
                            if SIPType.ANALOOG not in values[tab]:
                                return False

                continue

            # NOTE: connection details need both API and FTPS for their environment
            if ConfigKey.API.value not in values or ConfigKey.FTPS.value not in values:
                return False

            if any(
                argument not in values[ConfigKey.API.value]
                for argument in (
                    ConfigKey.URL.value,
                    ConfigKey.USERNAME.value,
                    ConfigKey.PASSWORD.value,
                    ConfigKey.CLIENT_ID.value,
                    ConfigKey.CLIENT_SECRET.value,
                )
            ) or any(
                argument not in values[ConfigKey.FTPS.value]
                for argument in (
                    ConfigKey.URL.value,
                    ConfigKey.USERNAME.value,
                    ConfigKey.PASSWORD.value,
                    ConfigKey.PORT.value,
                )
            ):
                return False

        return True

    @staticmethod
    def get_configuration(root_path: str) -> Configuration:
        configuration_path = os.path.join(root_path, CONFIGURATION_FILE_NAME)

        if not os.path.exists(configuration_path):
            return Configuration.get_default(root_path)

        with open(configuration_path, encoding="utf-8") as f:
            try:
                configuration = json.load(f)
            except Exception:
                config = Configuration.get_default(root_path)
                config.had_parse_error = True
                return config

            for v in (
                ConfigurationVersion.V5,
                ConfigurationVersion.V4,
                ConfigurationVersion.V3,
                ConfigurationVersion.V2,
                ConfigurationVersion.V1,
            ):
                if ConfigController._verify_configuration(configuration, root_path, version=v):
                    return Configuration.from_json(configuration, root_path, version=v)

            return Configuration.get_default(root_path)
