from typing import Iterable
import os
import json

import requests

from src.utils.data_objects.series import Series
from src.utils.data_objects.digital.sip import SIP
from src.utils.data_objects.configuration import Configuration, Environment


class APIException(Exception):
    pass


class APIController:
    @staticmethod
    def _perform_request(
        request_type,
        url: str,
        headers: dict = None,
        data: dict = None,
        params: dict = None,
        timeout=10,
    ) -> dict:
        response = request_type(
            url, headers=headers, data=data, params=params, timeout=timeout
        )
        response.raise_for_status()

        return response

    @staticmethod
    def _get_access_token(environment: Environment) -> str:
        base_url = environment.api_url
        endpoint = "auth/ropc.php"

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "password",
            "username": environment.api_username,
            "password": environment.api_password,
            "scope": "read:sample",
            "client_id": environment.api_client_id,
            "client_secret": environment.api_client_secret,
        }

        response = APIController._perform_request(
            request_type=requests.post,
            url=f"{base_url}/{endpoint}",
            headers=headers,
            data=data,
        )

        return response.json()["access_token"]

    @staticmethod
    def _get_user_group_id(access_token: str, environment: Environment) -> str:
        base_url = environment.api_url
        endpoint = "edepot/api/v1/users/current"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = APIController._perform_request(
            request_type=requests.get,
            url=f"{base_url}/{endpoint}",
            headers=headers,
        ).json()

        for group in response["Groups"]:
            if group["Type"] == "Organisation":
                return group["Id"]

    @staticmethod
    def _get_organisation_id(access_token: str, environment: Environment) -> str:
        base_url = environment.api_url
        endpoint = "edepot/api/v1/users/current"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = APIController._perform_request(
            request_type=requests.get,
            url=f"{base_url}/{endpoint}",
            headers=headers,
        ).json()

        return response["Organisation"]["Id"]

    @staticmethod
    def get_series(environment: Environment, search: str=None) -> Iterable[list[Series]]:
        access_token = APIController._get_access_token(
            environment
        )

        organisation_id = APIController._get_organisation_id(
            access_token, environment
        )

        base_url = environment.api_url
        endpoint = "series-register/api/v1/series"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "size": 100,
            "page": 0,
            "status": "Published",
            "q": f"+OrganisationId:{organisation_id}"
        }

        if search is not None:
            params = {"q": search}

        while True:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                params=params,
            ).json()

            yield Series.from_list(response["Content"])

            if (response["Page"] + 1) * params["size"] >= response["Total"]:
                break

            params["page"] = params["page"] + 1

    @staticmethod
    def get_import_template(configuration: Configuration, environment: Environment, series_id: str) -> str:
        access_token = APIController._get_access_token(environment)

        base_url = environment.api_url
        endpoint = "edepot/api/v1/sips/metadata-template"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        data = {
            "SeriesId": series_id,
        }

        response = APIController._perform_request(
            request_type=requests.post,
            url=f"{base_url}/{endpoint}",
            headers=headers,
            data=json.dumps(data),
        )

        storage_location = configuration.misc.save_location
        folder_location = os.path.join(storage_location, "import_templates")
        file_location = os.path.join(folder_location, f"{series_id}.xlsx")

        if not os.path.exists(folder_location):
            print(1)
            os.makedirs(folder_location)

        with open(file_location, "wb") as f:
            f.write(response.content)

            return file_location

    # TODO: do in background
    @staticmethod
    def get_sip_id(sip: SIP) -> str:
        environment = sip.environment
        access_token = APIController._get_access_token(
            environment, reraise=True, warn=False
        )

        base_url = environment.api_url
        endpoint = "edepot/api/v1/sips"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "size": 100,
            "page": 0,
        }

        while True:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                params=params,
                reraise=True,
                warn=False,
            ).json()

            sip_objects = response["Content"]

            for sip_object in sip_objects:
                if sip_object["OriginalFilename"] == sip.file_name:
                    return sip_object["Id"]

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1

    @staticmethod
    def get_sip_id_for_name(environment: Environment, zip_name: str) -> str:
        access_token = APIController._get_access_token(
            environment, reraise=True, warn=False
        )

        base_url = environment.api_url
        endpoint = "edepot/api/v1/sips"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "size": 100,
            "page": 0,
        }

        while True:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                params=params,
                reraise=True,
                warn=False,
            ).json()

            sip_objects = response["Content"]

            # NOTE: we just have to assume the sip name will be unique, since the API is not supporting searching by name/time
            for sip_object in sip_objects:
                if sip_object["OriginalFilename"] == zip_name:
                    return sip_object["Id"]

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1
