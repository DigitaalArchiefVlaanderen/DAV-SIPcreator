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
from src.utils.temp_diagnostic_log import log as temp_log

SIP_STATUS_MAPPING = {
    "Uploaded": SIPStatus.UPLOADED,
    "Processing": SIPStatus.PROCESSING,
    "Accepted": SIPStatus.ACCEPTED,
    "Rejected": SIPStatus.REJECTED,
}


def _truncate(value, limit: int = 120) -> str:
    text = repr(value)
    if len(text) > limit:
        return text[:limit] + "...[truncated]"
    return text


class APIException(Exception):
    pass


class APIAuthenticationError(Exception):
    def __init__(self, environment_name: str):
        self.environment_name = environment_name
        super().__init__(f"Authentication failed for environment '{environment_name}'")


class SIPNotFoundError(Exception):
    """Raised when the e-depot returns 404 ENOTFND for a stored SIP id.

    Signals that the cached edepot_id no longer maps to a record in the e-depot
    (e.g. the SIP was wiped server-side, or the id is from a different environment).
    Callers should clear the stale id and attempt to re-resolve it by filename.
    """

    def __init__(self, edepot_id: str):
        self.edepot_id = edepot_id
        super().__init__(f"e-depot SIP not found for id '{edepot_id}'")


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
        method = getattr(request_type, "__name__", str(request_type)).upper()
        temp_log(f"[api] HTTP {method} {url} params={params}")

        response = request_type(url, headers=headers, data=data, params=params, timeout=timeout)

        temp_log(f"[api] HTTP {method} {url} -> {response.status_code} {response.reason}")

        response.raise_for_status()

        return response

    @staticmethod
    def _get_access_token(environment: Environment) -> str:
        temp_log(f"[api] _get_access_token: env={environment.name}, user={environment.api_username}")
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

        token = response.json()["access_token"]
        temp_log(f"[api] _get_access_token: returning token (len={len(token)})")
        return token

    @staticmethod
    def _get_user_group_id(access_token: str, environment: Environment) -> str:
        temp_log(f"[api] _get_user_group_id: env={environment.name}")
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
            if group[APIResponseKey.TYPE] == APIResponseKey.ORGANISATION:
                result = group[APIResponseKey.ID]
                temp_log(f"[api] _get_user_group_id: returning {result}")
                return result

        temp_log("[api] _get_user_group_id: returning None (no organisation group)")
        return None

    @staticmethod
    def _get_organisation_id(access_token: str, environment: Environment) -> str:
        temp_log(f"[api] _get_organisation_id: env={environment.name}")
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

        result = response[APIResponseKey.ORGANISATION][APIResponseKey.ID]
        temp_log(f"[api] _get_organisation_id: returning {result}")
        return result

    @staticmethod
    def get_series(environment: Environment, search: str = None) -> Iterable[list[Series]]:
        temp_log(f"[api] get_series: env={environment.name}, search={search!r}")
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

        total_yielded = 0
        while True:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                params=params,
            ).json()

            batch = Series.from_list(response[APIResponseKey.CONTENT])
            total_yielded += len(batch)
            temp_log(
                f"[api] get_series: yielding batch page={response.get('Page')} "
                f"size={len(batch)} (total so far={total_yielded}, Total={response.get('Total')})"
            )
            yield batch

            if (response["Page"] + 1) * params["size"] >= response["Total"]:
                break

            params["page"] = params["page"] + 1

        temp_log(f"[api] get_series: done, total series yielded={total_yielded}")

    @staticmethod
    def get_import_template(configuration: Configuration, environment: Environment, series_id: str) -> str:
        temp_log(f"[api] get_import_template: env={environment.name}, series_id={series_id}")
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

        temp_log(f"[api] get_import_template: returning {file_location} ({len(response.content)} bytes)")
        return file_location

    @staticmethod
    def get_sip_id(sip: SIP) -> str | None:
        environment = sip.environment
        temp_log(
            f"[api] get_sip_id: env={environment.name}, sip_name={sip.name}, "
            f"sip_type={type(sip).__name__}, file_name={getattr(sip, 'file_name', '?')}"
        )
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
            "sort": "ArchiveDate,desc",
        }

        while True:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                params=params,
            ).json()

            sip_objects = response[APIResponseKey.CONTENT]

            for sip_object in sip_objects:
                if sip_object["OriginalFilename"] == sip.file_name:
                    found = sip_object["Id"]
                    temp_log(f"[api] get_sip_id: returning {found} (matched on page {response.get('Page')})")
                    return found

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1

        temp_log(f"[api] get_sip_id: returning None (no match across {response.get('Total')} SIPs)")
        return None

    @staticmethod
    def get_sip_id_for_name(environment: Environment, zip_name: str) -> str | None:
        temp_log(f"[api] get_sip_id_for_name: env={environment.name}, zip_name={zip_name}")
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
            "sort": "ArchiveDate,desc",
        }

        while True:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
                params=params,
            ).json()

            sip_objects = response[APIResponseKey.CONTENT]

            # NOTE: we just have to assume the sip name will be unique, since the API is not supporting searching by name/time
            for sip_object in sip_objects:
                if sip_object["OriginalFilename"] == zip_name:
                    found = sip_object["Id"]
                    temp_log(
                        f"[api] get_sip_id_for_name: returning {found} "
                        f"(matched on page {response.get('Page')})"
                    )
                    return found

            if (response["Page"] + 1) * 100 > response["Total"]:
                break

            params["page"] = params["page"] + 1

        temp_log(
            f"[api] get_sip_id_for_name: returning None (no match across {response.get('Total')} SIPs)"
        )
        return None

    @staticmethod
    def _is_sip_not_found(error: requests.exceptions.HTTPError) -> bool:
        response = error.response

        if response is None or response.status_code != 404:
            return False

        try:
            body = response.json()
        except ValueError:
            return False

        return isinstance(body, dict) and body.get("Code") == "ENOTFND"

    @staticmethod
    def get_sip_status_by_id(environment: Environment, edepot_id: str) -> tuple[SIPStatus, str | None] | None:
        temp_log(f"[api] get_sip_status_by_id: env={environment.name}, edepot_id={edepot_id}")
        result = APIController._fetch_sip_status(environment, edepot_id)
        temp_log(f"[api] get_sip_status_by_id: returning {_truncate(result)}")
        return result

    @staticmethod
    def get_sip_status(sip: SIP) -> tuple[SIPStatus, str | None] | None:
        temp_log(
            f"[api] get_sip_status: env={sip.environment.name}, sip_name={sip.name}, "
            f"sip_type={type(sip).__name__}, edepot_sip_id={sip.edepot_sip_id}"
        )
        result = APIController._fetch_sip_status(sip.environment, sip.edepot_sip_id)
        temp_log(f"[api] get_sip_status: returning {_truncate(result)}")
        return result

    @staticmethod
    def _fetch_sip_status(environment: Environment, edepot_id: str) -> tuple[SIPStatus, str | None] | None:
        access_token = APIController._get_access_token(environment)

        base_url = environment.api_url
        endpoint = f"edepot/api/v1/sips/{edepot_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = APIController._perform_request(
                request_type=requests.get,
                url=f"{base_url}/{endpoint}",
                headers=headers,
            ).json()
        except requests.exceptions.HTTPError as e:
            if APIController._is_sip_not_found(e):
                temp_log(f"[api] _fetch_sip_status: 404 ENOTFND for edepot_id={edepot_id}, raising SIPNotFoundError")
                raise SIPNotFoundError(edepot_id) from e
            raise

        if "SipStatus" not in response:
            return None

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
