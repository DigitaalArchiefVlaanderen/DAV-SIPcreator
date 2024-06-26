import os
from dataclasses import dataclass
from typing import List


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

@dataclass
class Misc:
    environments_activity: dict
    type_activity: dict
    save_location: str

    @staticmethod
    def get_default() -> "Misc":
        return Misc(
            environments_activity=dict(
                ti=False,
                prod=True,
            ),
            save_location=os.path.join(os.getcwd(), "SIP_Creator"),
        )


@dataclass
class Configuration:
    environments: List[Environment]
    misc: Misc

    @staticmethod
    def get_default() -> "Configuration":
        misc = Misc.get_default()
        ti = Environment.get_default("ti")
        prod = Environment.get_default("prod")

        ti.api_url = "https://digitaalarchief-ti.vlaanderen.be"
        ti.ftps_url = "ingest.digitaalarchief-ti.vlaanderen.be"

        prod.ftps_url = "ingest.digitaalarchief.vlaanderen.be"

        return Configuration(
            environments=[ti, prod],
            misc=misc,
        )

    @staticmethod
    def from_json(json: dict) -> "Configuration":
        environments = []
        misc = None

        for k, v in json.items():
            if k == "misc":
                misc = Misc(
                    environments_activity=v["Omgevingen"],
                    type_activity=v["Type SIPs"],
                    save_location=v["SIP Creator opslag locatie"],
                )
            else:
                environments.append(
                    Environment(
                        name=k,
                        api_url=v["API"]["url"],
                        api_username=v["API"]["username"],
                        api_password=v["API"]["password"],
                        api_client_id=v["API"]["client_id"],
                        api_client_secret=v["API"]["client_secret"],
                        ftps_url=v["FTPS"]["url"],
                        ftps_username=v["FTPS"]["username"],
                        ftps_password=v["FTPS"]["password"],
                        ftps_port=v["FTPS"]["port"],
                    )
                )

        return Configuration(environments=environments, misc=misc)


    def to_json(self) -> dict:
        json = {}

        for env in self.environments:
            json[env.name] = {
                "API": {
                    "url": env.api_url,
                    "username": env.api_username,
                    "password": env.api_password,
                    "client_id": env.api_client_id,
                    "client_secret": env.api_client_secret,
                },
                "FTPS": {
                    "url": env.ftps_url,
                    "username": env.ftps_username,
                    "password": env.ftps_password,
                    "port": env.ftps_port,
                },
            }

        json["misc"] = {
            "Omgevingen": self.misc.environments_activity,
            "SIP Creator opslag locatie": self.misc.save_location,
        }

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
    def active_type(self) -> str:
        for _type, active in self.misc.type_activity.items():
            if active:
                return _type
