from dataclasses import dataclass
from enum import Enum
import json
import os
from typing import List

from src.utils.constants import SaveLocations, ConfigKey


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
            ftps_port="21"
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
        return {
            ConfigKey.API.value: self.get_api_info(),
            ConfigKey.FTPS.value: self.get_ftps_info()
        }

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
    def get_default() -> "Misc":
        return Misc(
            environments_activity=dict(
                ti=False,
                prod=True,
            ),
            role_activity=dict(
                klant=True,
                depotmedewerker=False,
            ),
            type_activity=dict(
                digitaal=True,
                migratie=False,
                onroerend_erfgoed=False,
                analoog=False,
            ),
            save_location=os.path.join(os.getcwd(), SaveLocations.DEFAULT_BASE_SAVE_LOCATION.value),
            bestandscontrole_lijst_location=""
        )

    def to_json(self) -> dict:
        return {
            "Omgevingen": self.environments_activity,
            "Rollen": self.role_activity,
            "Type SIPs": self.type_activity,
            "SIP Creator opslag locatie": self.save_location,
            "Bestandscontrole lijst locatie": self.bestandscontrole_lijst_location
        }

@dataclass
class Configuration:
    environments: List[Environment]
    misc: Misc

    def create_locations(self) -> None:
        # NOTE: creates all required folders
        os.makedirs(self.sip_db_location, exist_ok=True)
        os.makedirs(self.import_templates_location, exist_ok=True)
        os.makedirs(self.overdrachtslijsten_location, exist_ok=True)
        # os.makedirs(self.grid_location, exist_ok=True)
        os.makedirs(self.analoog_location, exist_ok=True)
        os.makedirs(self.sips_location, exist_ok=True) 

    def save(self) -> None:
        with open(SaveLocations.CONFIGURATION_FILE.value, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=4)

    @staticmethod
    def get_default() -> "Configuration":
        misc = Misc.get_default()
        ti = Environment.get_default("ti")
        prod = Environment.get_default("prod")

        ti.api_url = "https://digitaalarchief-ti.vlaanderen.be"
        ti.ftps_url = "ingest.digitaalarchief-ti.vlaanderen.be"

        prod.api_url = "https://digitaalarchief.vlaanderen.be"
        prod.ftps_url = "ingest.digitaalarchief.vlaanderen.be"

        return Configuration(
            environments=[ti, prod],
            misc=misc,
        )

    def to_json(self) -> dict:
        return {
            "misc": self.misc.to_json(),
            **{
                env.name: env.to_json()
                for env in self.environments
            }
        }

    @staticmethod
    def from_json(json: dict, version: ConfigurationVersion) -> "Configuration":
        environments = []
        misc = None

        for k, v in json.items():
            if k == "misc":
                if version == ConfigurationVersion.V1:
                    misc_default = Misc.get_default()

                    misc = Misc(
                        environments_activity=v["Omgevingen"],
                        role_activity=misc_default.role_activity,
                        type_activity=misc_default.type_activity,
                        save_location=v["SIP Creator opslag locatie"],
                        bestandscontrole_lijst_location="",
                    )
                elif version == ConfigurationVersion.V2:
                    types = v["Type SIPs"]
                    types["onroerend_erfgoed"] = False
                    types["analoog"] = False

                    misc = Misc(
                        environments_activity=v["Omgevingen"],
                        role_activity=v["Rollen"],
                        type_activity=types,
                        save_location=v["SIP Creator opslag locatie"],
                        bestandscontrole_lijst_location="",
                    )
                elif version == ConfigurationVersion.V3:
                    types = v["Type SIPs"]
                    types["onroerend_erfgoed"] = False
                    types["analoog"] = False

                    misc = Misc(
                        environments_activity=v["Omgevingen"],
                        role_activity=v["Rollen"],
                        type_activity=types,
                        save_location=v["SIP Creator opslag locatie"],
                        bestandscontrole_lijst_location=v["Bestandscontrole lijst locatie"],
                    )
                elif version == ConfigurationVersion.V4:
                    types = v["Type SIPs"]
                    types["analoog"] = False

                    misc = Misc(
                        environments_activity=v["Omgevingen"],
                        role_activity=v["Rollen"],
                        type_activity=types,
                        save_location=v["SIP Creator opslag locatie"],
                        bestandscontrole_lijst_location=v["Bestandscontrole lijst locatie"],
                    )
                elif version == ConfigurationVersion.V5:
                    misc = Misc(
                        environments_activity=v["Omgevingen"],
                        role_activity=v["Rollen"],
                        type_activity=v["Type SIPs"],
                        save_location=v["SIP Creator opslag locatie"],
                        bestandscontrole_lijst_location=v["Bestandscontrole lijst locatie"],
                    )
            else:
                api = v[ConfigKey.API.value]
                ftps = v[ConfigKey.FTPS.value]

                environments.append(
                    Environment(
                        name=k,
                        api_url=api[ConfigKey.URL.value],
                        api_username=api[ConfigKey.USERNAME.value],
                        api_password=api[ConfigKey.PASSWORD.value],
                        api_client_id=api[ConfigKey.CLIENT_ID.value],
                        api_client_secret=api[ConfigKey.CLIENT_SECRET.value],
                        ftps_url=ftps[ConfigKey.URL.value],
                        ftps_username=ftps[ConfigKey.USERNAME.value],
                        ftps_password=ftps[ConfigKey.PASSWORD.value],
                        ftps_port=ftps[ConfigKey.PORT.value],
                    )
                )

        return Configuration(environments=environments, misc=misc)

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
        return os.path.join(self.misc.save_location, SaveLocations.IMPORT_TEMPLATES_FOLDER.value)
    
    @property
    def overdrachtslijsten_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.OVERDRACHTSLIJSTEN_FOLDER.value)
    
    @property
    def analoog_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.ANALOOG_FOLDER.value)
    
    @property
    def grid_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.GRID_FOLDER.value)

    @property
    def sips_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.SIPS_FOLDER.value)
        
    @property
    def sip_db_location(self) -> str:
        return os.path.join(self.misc.save_location, SaveLocations.SIP_DB_FOLDER.value)

