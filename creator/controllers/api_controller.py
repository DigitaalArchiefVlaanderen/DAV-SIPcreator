import os
import json

import requests

from ..utils.series import Series
from ..utils.state_utils.sip import SIP
from ..utils.sip_status import SIPStatus
from ..utils.status.api_item_status import APIItemStatus
from ..utils.configuration import Configuration, Environment

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
            reraise=True,
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
            reraise=True,
        ).json()

        return response["Organisation"]["Id"]

    @staticmethod
    def get_series(configuration: Configuration, search: str = None) -> list[Series]:
        environment = configuration.active_environment

        access_token = APIController._get_access_token(
            environment, reraise=True, warn=True
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
    def get_import_template(configuration: Configuration, series_id: str) -> str:
        environment = configuration.active_environment

        access_token = APIController._get_access_token(
            environment, reraise=True, warn=True
        )

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
            reraise=True,
        )

        storage_location = configuration.misc.save_location
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

    # TODO: replace with from files once possible
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

    @staticmethod
    def get_sip_status_from_dossiers(sip: SIP) -> SIPStatus:
        environment = sip.environment
        access_token = APIController._get_access_token(
            environment, reraise=True, warn=False
        )

        base_url = environment.api_url
        endpoint = "edepot/api/v1/records"
        file_endpoint = "edepot/api/v1/dossiers/{dossierId}/documents"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "q": f"+(Dynamic.SipReferenceCode:*{sip.edepot_sip_id}) AND +(RecordType:Dossier)",
            "NrOfResults": 100,
            "StartIndex": 0,
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

            # As long as a sip is still being processed, nothing gets returned it seems
            if response["TotalNrOfResults"] == 0:
                return SIPStatus.PROCESSING

            for dossier_dict in response["Results"]:
                dossier_status = dossier_dict["Administrative"]["RecordStatus"]

                api_status = APIItemStatus(raw_status=dossier_status)

                # If the status is not valid, nor published, nor concept, assume it's invalid
                if api_status.is_processing:
                    return SIPStatus.PROCESSING
                elif api_status.is_invalid:
                    return SIPStatus.REJECTED
                
                # If the dossier is valid, it's still possible stukken in there are invalid
                dossier_id = dossier_dict["Dynamic"]["DossierReferenceCode"].split("/")[-1]

                file_response = APIController._perform_request(
                    request_type=requests.get,
                    url=f"{base_url}/{file_endpoint.format(dossierId=dossier_id)}",
                    headers=headers,
                    reraise=True,
                    warn=False,
                ).json()

                for file_result in file_response:
                    file_status = file_result["Status"]["Status"]

                    # TODO: make use of this once it actually returns useful results
                    # reasons = file_result["Context"]["Reasons"]

                    file_api_status = APIItemStatus(raw_status=file_status)

                    # If the status is not valid, nor published, nor concept assume it's invalid
                    if file_api_status.is_processing:
                        return SIPStatus.PROCESSING
                    elif file_api_status.is_invalid:
                        return SIPStatus.REJECTED
                    

            if (response["StartIndex"] + 1) * params["NrOfResults"] > response[
                "TotalNrOfResults"
            ]:
                break

            params["StartIndex"] = params["StartIndex"] + params["NrOfResults"]

        # If there is stuff here, but none of it is invalid (or processing), we assume everything is okay
        return SIPStatus.ACCEPTED
