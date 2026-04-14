import json
import os
from dataclasses import dataclass
from enum import Enum

from src.utils.constants import (
    CONFIG_KEY_BESTANDSCONTROLE,
    CONFIG_KEY_ENVIRONMENTS,
    CONFIG_KEY_ROLES,
    CONFIG_KEY_SIP_STORAGE,
    CONFIG_KEY_TYPE_SIPS,
    CONFIG_SECTION_MISC,
    DEFAULT_PROD_API_URL,
    DEFAULT_PROD_FTPS_URL,
    DEFAULT_TI_API_URL,
    DEFAULT_TI_FTPS_URL,
    KLANT_ROLE,
    PROD_ENVIRONMENT_NAME,
    ROLE_DEPOTMEDEWERKER,
    TI_ENVIRONMENT_NAME,
    ConfigKey,
    SaveLocations,
    SIPType,
)


class ConfigurationVersion(Enum):
    V1 = 1
    V2 = 2
    V3 = 3
    V4 = 4
    V5 = 5


@dataclass
class Environment:
    name: str

    api_url: str
    api_username: str
    api_password: str
    api_client_id: str
    api_client_secret: str

    ftps_url: str
    ftps_username: str
    ftps_password: str
    ftps_port: str

    def has_api_credentials(self) -> bool:
        return all(
            v != ""
            for v in (
                self.api_url,
                self.api_username,
                self.api_password,
                self.api_client_id,
                self.api_client_secret,
            )
        )

    def has_ftps_credentials(self) -> bool:
        return all(
            v != ""
            for v in (
                self.ftps_url,
                self.ftps_username,
                self.ftps_password,
                self.ftps_port,
            )
        )

    @staticmethod
    def get_default(name: str) -> "Environment":
        return Environment(
            name=name,
            api_url="",
            api_username="",
            api_password="",
            api_client_id="",
            api_client_secret="",
            ftps_url="",
            ftps_username="",
            ftps_password="",
            ftps_port="21",
        )

    def get_api_info(self) -> dict:
        return dict(
            url=self.api_url,
            username=self.api_username,
            password=self.api_password,
            client_id=self.api_client_id,
            client_secret=self.api_client_secret,
        )

    def get_ftps_info(self) -> dict:
        return dict(
            url=self.ftps_url,
            username=self.ftps_username,
            password=self.ftps_password,
            port=self.ftps_port,
        )

    def to_json(self) -> dict:
        return {ConfigKey.API: self.get_api_info(), ConfigKey.FTPS: self.get_ftps_info()}

    def get_serie_register_uri(self) -> str:
        return self.api_url.replace("digitaalarchief", "serieregister") + "/id/serie"


@dataclass
class Misc:
    environments_activity: dict[str, bool]
    role_activity: dict[str, bool]
    type_activity: dict[str, bool]
    save_location: str
    bestandscontrole_lijst_location: str

    @staticmethod
    def get_default(root_path: str) -> "Misc":
        return Misc(
            environments_activity={
                TI_ENVIRONMENT_NAME: False,
                PROD_ENVIRONMENT_NAME: True,
            },
            role_activity={
                KLANT_ROLE: True,
                ROLE_DEPOTMEDEWERKER: False,
            },
            type_activity={
                SIPType.DIGITAAL: True,
                SIPType.MIGRATIE: False,
                SIPType.ONROEREND_ERFGOED: False,
                SIPType.ANALOOG: False,
            },
            save_location=os.path.join(root_path, SaveLocations.DEFAULT_BASE_SAVE_LOCATION),
            bestandscontrole_lijst_location="",
        )

    def to_json(self) -> dict:
        return {
            CONFIG_KEY_ENVIRONMENTS: self.environments_activity,
            CONFIG_KEY_ROLES: self.role_activity,
            CONFIG_KEY_TYPE_SIPS: self.type_activity,
            CONFIG_KEY_SIP_STORAGE: self.save_location,
            CONFIG_KEY_BESTANDSCONTROLE: self.bestandscontrole_lijst_location,
        }


@dataclass
class Configuration:
    environments: list[Environment]
    misc: Misc
    root_path: str
    had_parse_error: bool = False

    def create_locations(self) -> None:
        os.makedirs(self.sip_db_location, exist_ok=True)
        os.makedirs(self.import_templates_location, exist_ok=True)
        os.makedirs(self.overdrachtslijsten_location, exist_ok=True)
        os.makedirs(self.analoog_location, exist_ok=True)
        os.makedirs(self.sips_location, exist_ok=True)
        os.makedirs(self.grid_location, exist_ok=True)

    def save(self) -> None:
        configuration_path = os.path.join(self.root_path, SaveLocations.CONFIGURATION_FILE)

        with open(configuration_path, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=4)

    @staticmethod
    def get_default(root_path: str) -> "Configuration":
        misc = Misc.get_default(root_path)
        ti = Environment.get_default(TI_ENVIRONMENT_NAME)
        prod = Environment.get_default(PROD_ENVIRONMENT_NAME)

        ti.api_url = DEFAULT_TI_API_URL
        ti.ftps_url = DEFAULT_TI_FTPS_URL

        prod.api_url = DEFAULT_PROD_API_URL
        prod.ftps_url = DEFAULT_PROD_FTPS_URL

        return Configuration(
            environments=[ti, prod],
            misc=misc,
            root_path=root_path,
        )

    def to_json(self) -> dict:
        return {CONFIG_SECTION_MISC: self.misc.to_json(), **{env.name: env.to_json() for env in self.environments}}

    @staticmethod
    def from_json(json: dict, root_path: str, version: ConfigurationVersion) -> "Configuration":
        environments = []
        misc = None

        for k, v in json.items():
            if k == CONFIG_SECTION_MISC:
                if version == ConfigurationVersion.V1:
                    misc_default = Misc.get_default(root_path)

                    misc = Misc(
                        environments_activity=v[CONFIG_KEY_ENVIRONMENTS],
                        role_activity=misc_default.role_activity,
                        type_activity=misc_default.type_activity,
                        save_location=v[CONFIG_KEY_SIP_STORAGE],
                        bestandscontrole_lijst_location="",
                    )
                elif version == ConfigurationVersion.V2:
                    types = v[CONFIG_KEY_TYPE_SIPS]
                    types[SIPType.ONROEREND_ERFGOED] = False
                    types[SIPType.ANALOOG] = False

                    misc = Misc(
                        environments_activity=v[CONFIG_KEY_ENVIRONMENTS],
                        role_activity=v[CONFIG_KEY_ROLES],
                        type_activity=types,
                        save_location=v[CONFIG_KEY_SIP_STORAGE],
                        bestandscontrole_lijst_location="",
                    )
                elif version == ConfigurationVersion.V3:
                    types = v[CONFIG_KEY_TYPE_SIPS]
                    types[SIPType.ONROEREND_ERFGOED] = False
                    types[SIPType.ANALOOG] = False

                    misc = Misc(
                        environments_activity=v[CONFIG_KEY_ENVIRONMENTS],
                        role_activity=v[CONFIG_KEY_ROLES],
                        type_activity=types,
                        save_location=v[CONFIG_KEY_SIP_STORAGE],
                        bestandscontrole_lijst_location=v[CONFIG_KEY_BESTANDSCONTROLE],
                    )
                elif version == ConfigurationVersion.V4:
                    types = v[CONFIG_KEY_TYPE_SIPS]
                    types[SIPType.ANALOOG] = False

                    misc = Misc(
                        environments_activity=v[CONFIG_KEY_ENVIRONMENTS],
                        role_activity=v[CONFIG_KEY_ROLES],
                        type_activity=types,
                        save_location=v[CONFIG_KEY_SIP_STORAGE],
                        bestandscontrole_lijst_location=v[CONFIG_KEY_BESTANDSCONTROLE],
                    )
                elif version == ConfigurationVersion.V5:
                    misc = Misc(
                        environments_activity=v[CONFIG_KEY_ENVIRONMENTS],
                        role_activity=v[CONFIG_KEY_ROLES],
                        type_activity=v[CONFIG_KEY_TYPE_SIPS],
                        save_location=v[CONFIG_KEY_SIP_STORAGE],
                        bestandscontrole_lijst_location=v[CONFIG_KEY_BESTANDSCONTROLE],
                    )
            else:
                api = v[ConfigKey.API]
                ftps = v[ConfigKey.FTPS]

                environments.append(
                    Environment(
                        name=k,
                        api_url=api[ConfigKey.URL],
                        api_username=api[ConfigKey.USERNAME],
                        api_password=api[ConfigKey.PASSWORD],
                        api_client_id=api[ConfigKey.CLIENT_ID],
                        api_client_secret=api[ConfigKey.CLIENT_SECRET],
                        ftps_url=ftps[ConfigKey.URL],
                        ftps_username=ftps[ConfigKey.USERNAME],
                        ftps_password=ftps[ConfigKey.PASSWORD],
                        ftps_port=ftps[ConfigKey.PORT],
                    )
                )

        return Configuration(environments=environments, misc=misc, root_path=root_path)

    def get_environment(self, name: str) -> Environment:
        for env in self.environments:
            if env.name == name:
                return env

    @property
    def active_environment(self) -> Environment:
        for env, active in self.misc.environments_activity.items():
            if active:
                return self.get_environment(env)

    @property
    def active_environment_name(self) -> str:
        for env, active in self.misc.environments_activity.items():
            if active:
                return env

    @property
    def active_role(self) -> str:
        for role, active in self.misc.role_activity.items():
            if active:
                return role

    @property
    def active_type(self) -> str:
        for _type, active in self.misc.type_activity.items():
            if active:
                return _type

    @property
    def import_templates_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.IMPORT_TEMPLATES_FOLDER)

    @property
    def overdrachtslijsten_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.OVERDRACHTSLIJSTEN_FOLDER)

    @property
    def analoog_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.ANALOOG_FOLDER)

    @property
    def grid_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.GRID_FOLDER)

    @property
    def sips_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.SIPS_FOLDER)

    @property
    def sip_db_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.SIP_DB_FOLDER)
