import os
import json

import requests

from ..utils.series import Series
from ..utils.state_utils.sip import SIP
from ..utils.sip_status import SIPStatus
from ..utils.configuration import Environment

from ..widgets.warning_dialog import WarningDialog


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
        reraise=True,
        warn=True,
    ) -> dict:
        try:
            response = request_type(
                url, headers=headers, data=data, params=params, timeout=timeout
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            if warn:
                WarningDialog(
                    title="Timeout",
                    text="De API request duurde te lang, probeer later opnieuw.",
                ).exec()

            if reraise:
                raise APIException("Timeout")
        except requests.exceptions.HTTPError:
            if warn:
                WarningDialog(
                    title="HTTPError",
                    text="Onbekende HTTPError bij het ophalen van API data.\nCredentials zijn mogelijks fout.",
                ).exec()

            if reraise:
                raise APIException("HTTPError")
        except requests.exceptions.RequestException:
            if warn:
                WarningDialog(
                    title="Fout",
                    text="Onbekende fout bij het ophalen van API data.\nDe API url is mogelijks fout.",
                ).exec()

            if reraise:
                raise APIException("Request fout")

        return response

    # TODO: do this manually everywhere, cus we want to decide which environment to use before we do the call
    @staticmethod
    def _get_connection_details(configuration: dict):
        environment = [
            env for env, active in configuration["misc"]["Omgevingen"].items() if active
        ][0]

        return configuration[environment]["API"]

    # TODO: depricate this
    @staticmethod
    def _get_access_token_old(connection_details: dict, reraise=True) -> str:
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
    def _get_access_token(environment: Environment, reraise=True, warn=True) -> str:
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
            reraise=reraise,
            warn=warn,
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
            reraise=True,
        ).json()

        for group in response["Groups"]:
            if group["Type"] == "Organisation":
                return group["Id"]

    @staticmethod
    def get_series(configuration: dict, search: str = None) -> list:
        connection_details = APIController._get_connection_details(configuration)

        access_token = APIController._get_access_token_old(
            connection_details, reraise=True
        )

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
                reraise=True,
            ).json()

            series += Series.from_list(response["Content"])

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1

        return series

    @staticmethod
    def get_import_template(configuration: dict, series_id: str) -> str:
        connection_details = APIController._get_connection_details(configuration)

        access_token = APIController._get_access_token_old(
            connection_details, reraise=True
        )

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
            reraise=True,
        )

        storage_location = configuration["misc"]["SIP Creator opslag locatie"]
        folder_location = os.path.join(storage_location, "import_templates")
        file_location = os.path.join(folder_location, f"{series_id}.xlsx")

        if not os.path.exists(folder_location):
            os.makedirs(folder_location)

        with open(file_location, "wb") as f:
            f.write(response.content)

            return file_location

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
    def get_sip_status(sip: SIP) -> SIPStatus:
        environment = sip.environment
        access_token = APIController._get_access_token(
            environment, reraise=True, warn=False
        )

        base_url = environment.api_url
        endpoint = f"edepot/api/v1/sips/{sip.edepot_sip_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = APIController._perform_request(
            request_type=requests.get,
            url=f"{base_url}/{endpoint}",
            headers=headers,
            reraise=True,
            warn=False,
        ).json()

        status = None
        fail_reason = None

        match response["SipStatus"]:
            case "Uploaded":
                status = SIPStatus.UPLOADED
            case "Processing":
                status = SIPStatus.PROCESSING
            case "Accepted":
                status = SIPStatus.ACCEPTED
            case "Rejected":
                status = SIPStatus.REJECTED

                fail_reasons = []

                for r in response["RecordRejections"]["Rejection"]:
                    fail_reason_row = []

                    if r["Row"] is not None:
                        fail_reason_row.append(f"Rij: {r['Row']}")

                    if r["Path"] is not None:
                        fail_reason_row.append(f"Path in SIP: {r['Path']}")

                    if r["Value"] is not None:
                        fail_reason_row.append(f"Waarde in veld: {r['Value']}")

                    fail_reason_row.append(r["Motivation"])
                    fail_reasons.append("\n".join(fail_reason_row))

                fail_reason = "\n\n".join(fail_reasons)

        return status, fail_reason
