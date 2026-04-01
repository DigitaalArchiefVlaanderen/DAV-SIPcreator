import json
import os
import uuid
from collections.abc import Iterable
from contextlib import suppress

import requests

from src.utils.constants import APIResponseKey
from src.utils.data_objects.configuration import Configuration, Environment
from src.utils.data_objects.series import Series, SeriesStatus
from src.utils.data_objects.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus

SIP_STATUS_MAPPING = {
    "Uploaded": SIPStatus.UPLOADED,
    "Processing": SIPStatus.PROCESSING,
    "Accepted": SIPStatus.ACCEPTED,
    "Rejected": SIPStatus.REJECTED,
}


class APIException(Exception):
    pass


class APIAuthenticationError(Exception):
    def __init__(self, environment_name: str):
        self.environment_name = environment_name
        super().__init__(f"Authentication failed for environment '{environment_name}'")


class APIController:
    @staticmethod
    def _perform_request(
        request_type,
        url: str,
        headers: dict = None,
        data: dict = None,
        params: dict = None,
        timeout=10,
    ) -> requests.Response:
        response = request_type(url, headers=headers, data=data, params=params, timeout=timeout)
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

        try:
            response = APIController._perform_request(
                request_type=requests.post,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                data=data,
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                raise APIAuthenticationError(environment.name) from e
            raise

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
            if group[APIResponseKey.TYPE.value] == APIResponseKey.ORGANISATION.value:
                return group[APIResponseKey.ID.value]

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

        return response[APIResponseKey.ORGANISATION.value][APIResponseKey.ID.value]

    @staticmethod
    def get_series(environment: Environment, search: str = None) -> Iterable[list[Series]]:
        access_token = APIController._get_access_token(environment)

        organisation_id = APIController._get_organisation_id(access_token, environment)

        base_url = environment.api_url
        endpoint = "series-register/api/v1/series"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "size": 100,
            "page": 0,
            "status": SeriesStatus.PUBLISHED.value,
            "q": f"+OrganisationId:{organisation_id}",
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

            yield Series.from_list(response[APIResponseKey.CONTENT.value])

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

        os.makedirs(folder_location, exist_ok=True)

        # Write to a unique temp file, then rename — avoids corruption
        # if multiple threads download the same template concurrently
        temp_location = file_location + f".{uuid.uuid4().hex}.tmp"
        with open(temp_location, "wb") as f:
            f.write(response.content)

        try:
            os.replace(temp_location, file_location)
        except PermissionError:
            # Another thread may have the target file open — clean up temp
            with suppress(OSError):
                os.remove(temp_location)

        return file_location

    # TODO: do in background
    @staticmethod
    def get_sip_id(sip: SIP) -> str:
        environment = sip.environment
        access_token = APIController._get_access_token(environment)

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
            ).json()

            sip_objects = response[APIResponseKey.CONTENT.value]

            for sip_object in sip_objects:
                if sip_object["OriginalFilename"] == sip.file_name:
                    return sip_object["Id"]

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1

    @staticmethod
    def get_sip_id_for_name(environment: Environment, zip_name: str) -> str:
        access_token = APIController._get_access_token(environment)

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
            ).json()

            sip_objects = response[APIResponseKey.CONTENT.value]

            # NOTE: we just have to assume the sip name will be unique, since the API is not supporting searching by name/time
            for sip_object in sip_objects:
                if sip_object["OriginalFilename"] == zip_name:
                    return sip_object["Id"]

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1

    @staticmethod
    def get_sip_status_by_id(environment: Environment, edepot_id: str) -> tuple[SIPStatus, str | None]:
        return APIController._fetch_sip_status(environment, edepot_id)

    @staticmethod
    def get_sip_status(sip: SIP) -> tuple[SIPStatus, str | None]:
        return APIController._fetch_sip_status(sip.environment, sip.edepot_sip_id)

    @staticmethod
    def _fetch_sip_status(environment: Environment, edepot_id: str) -> tuple[SIPStatus, str | None]:
        access_token = APIController._get_access_token(environment)

        base_url = environment.api_url
        endpoint = f"edepot/api/v1/sips/{edepot_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = APIController._perform_request(
            request_type=requests.get,
            url=f"{base_url}/{endpoint}",
            headers=headers,
        ).json()

        status = SIP_STATUS_MAPPING.get(response["SipStatus"])
        fail_reason = None

        if status == SIPStatus.REJECTED:
            fail_reasons = []

            for r in response["RecordRejections"]["Rejection"]:
                parts = []

                if r["Row"] is not None:
                    parts.append(f"Rij: {r['Row']}")
                if r["Path"] is not None:
                    parts.append(f"Path in SIP: {r['Path']}")
                if r["Value"] is not None:
                    parts.append(f"Waarde in veld: {r['Value']}")

                parts.append(r["Motivation"])
                fail_reasons.append("\n".join(parts))

            fail_reason = "\n\n".join(fail_reasons)

        return status, fail_reason
