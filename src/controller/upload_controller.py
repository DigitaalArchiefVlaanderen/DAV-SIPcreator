import ftplib
import os
import socket
import time

from src.utils.base_object import BaseObject
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus

UI_TEXT = UI_TEXT_ELEMENTS["errors"]["upload"]


class UploadController(BaseObject):
    # NOTE: we take the locations in here, since the exact location will depend on the application-type as well
    def _validate_upload(self, sip: SIP, sip_location: str, sidecar_location: str) -> bool:
        if not sip.environment.has_ftps_credentials():
            self.application.notify_user_signal.emit(
                UI_TEXT["missing_ftps_credentials_error"]["title"],
                UI_TEXT["missing_ftps_credentials_error"]["text"].format(environment_name=sip.environment.name),
            )
            return False

        if not os.path.exists(sip_location) or not os.path.exists(sidecar_location):
            self.application.notify_user_signal.emit(
                UI_TEXT["missing_files_error"]["title"],
                UI_TEXT["missing_files_error"]["text"],
            )
            return False

        try:
            ftplib.FTP_TLS(
                sip.environment.ftps_url,
                sip.environment.ftps_username,
                sip.environment.ftps_password,
            )
        except ftplib.error_perm:
            self.application.notify_user_signal.emit(
                UI_TEXT["ftps_login_error"]["title"],
                UI_TEXT["ftps_login_error"]["text"].format(environment_name=sip.environment.name),
            )
            return False
        except socket.gaierror:
            self.application.notify_user_signal.emit(
                UI_TEXT["ftps_url_error"]["title"],
                UI_TEXT["ftps_url_error"]["text"].format(environment_name=sip.environment.name),
            )
            return False

        return True

    def _perform_upload(self, sip: SIP, sip_location: str, sidecar_location: str) -> None:
        with ftplib.FTP_TLS(
            sip.environment.ftps_url,
            sip.environment.ftps_username,
            sip.environment.ftps_password,
        ) as session:
            session.prot_p()

            with open(sip_location, "rb") as f:
                session.storbinary(f"STOR {sip.file_name}", f)
            with open(sidecar_location, "rb") as f:
                session.storbinary(f"STOR {sip.sidecar_file_name}", f)

        sip.set_status(SIPStatus.UPLOADED)

    def upload_sip(self, sip: SIP) -> None:
        configuration = self.application.configuration

        sip_location = os.path.join(configuration.sips_location, sip.file_name)
        sidecar_location = os.path.join(configuration.sips_location, sip.sidecar_file_name)

        if not self._validate_upload(sip, sip_location, sidecar_location):
            return

        sip.set_status(SIPStatus.UPLOADING)
        self._perform_upload(sip, sip_location, sidecar_location)
