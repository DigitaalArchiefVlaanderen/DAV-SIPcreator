import os
import json

import requests

from ..utils.series import Series

from ..widgets.warning_dialog import WarningDialog


class APIController:
    @staticmethod
    def _perform_request(
        request_type,
        url: str,
        headers: dict = None,
        data: dict = None,
        params: dict = None,
        timeout=10,
        reraise=False,
    ) -> dict:
        try:
            response = request_type(
                url, headers=headers, data=data, params=params, timeout=timeout
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            WarningDialog(
                title="Timeout",
                text="De API request duurde te lang, probeer later opnieuw.",
            ).exec()

            if reraise:
                raise exc
        except requests.exceptions.HTTPError as exc:
            WarningDialog(
                title="HTTPError",
                text="Onbekende HTTPError bij het ophalen van API data.\nCredentials zijn mogelijks fout.",
            ).exec()

            if reraise:
                raise exc
        except requests.exceptions.RequestException as exc:
            WarningDialog(
                title="Fout",
                text="Onbekende fout bij het ophalen van API data.\nDe API url is mogelijks fout.",
            ).exec()

            if reraise:
                raise exc

        return response

    @staticmethod
    def _get_connection_details(configuration: dict):
        environment = [
            env for env, active in configuration["misc"]["Omgevingen"].items() if active
        ][0]

        return configuration[environment]["API"]

    @staticmethod
    def _get_access_token(connection_details: dict, reraise=False) -> str:
        base_url = connection_details["url"]
        endpoint = "auth/ropc.php"

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "password",
            "username": connection_details["username"],
            "password": connection_details["password"],
            "scope": "read:sample",
            "client_id": connection_details["client_id"],
            "client_secret": connection_details["client_secret"],
        }

        response = APIController._perform_request(
            request_type=requests.post,
            url=f"{base_url}/{endpoint}",
            headers=headers,
            data=data,
            reraise=reraise,
        )

        return response.json()["access_token"]

    @staticmethod
    def _get_user_group_id(access_token, connection_details: dict) -> str:
        base_url = connection_details["url"]
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
    def get_series(configuration: dict, search: str = None) -> list:
        connection_details = APIController._get_connection_details(configuration)

        try:
            access_token = APIController._get_access_token(
                connection_details, reraise=True
            )
        except Exception:
            return []

        user_group_id = APIController._get_user_group_id(
            access_token, connection_details
        )

        base_url = connection_details["url"]
        endpoint = "series-register/api/v1/series"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "size": 100,
            "page": 0,
            "status": "Submitted",
            "securityGroupId": user_group_id,
        }

        if search is not None:
            params = {"q": search}

        series = []

        while True:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                params=params,
            ).json()

            series += Series.from_list(response["Content"])

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1

        return series

    @staticmethod
    def get_import_template(configuration: dict, series_id: str) -> str:
        connection_details = APIController._get_connection_details(configuration)

        access_token = APIController._get_access_token(connection_details)

        base_url = connection_details["url"]
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

        storage_location = configuration["misc"]["SIP Creator opslag locatie"]
        folder_location = os.path.join(storage_location, "import_templates")
        file_location = os.path.join(folder_location, f"{series_id}.xlsx")

        if not os.path.exists(folder_location):
            os.makedirs(folder_location)

        with open(file_location, "wb") as f:
            f.write(response.content)

            return file_location
