"""
This is a file containing helper scripts that need access to the Application instance or the current state
"""
import os
import time
from typing import Any

from PySide6 import QtCore

from src.utils.base_object import BaseObject
from src.utils.constants import BASE_SIP_NAME, UI_TEXT_ELEMENTS


class Helper(BaseObject):
    def __get_all_sip_names(self) -> list[str]:
        for _, _, files in os.walk(self.application.configuration.sip_db_location):
            return files
    
    def get_next_sip_name(self) -> str:
        next_sip_number = 1
        all_sip_names = self.__get_all_sip_names()

        while (next_sip_name := BASE_SIP_NAME.format(number=next_sip_number)) in all_sip_names:
            next_sip_number += 1

        return next_sip_name

    def get_new_transitioned_db_name(self, old_name: str) -> str:
        return f"new_{old_name}"
        
    def wait_for_signal_or_value(
            self,
            signal: QtCore.Signal, value: Any=None, warning_title: str=None,
            warning_text: str=None, extra_delay=0.2, warn=True
    ) -> None:
        if value:
            return
        
        loop = QtCore.QEventLoop()
        signal.connect(loop.quit)

        if warn and warning_title and warning_text:
            self.application.thread_error_signal.emit(
                warning_title,
                warning_text
            )

        loop.exec()

        # NOTE: sleep some extra time, just in case
        time.sleep(extra_delay)

    def wait_for_series_loaded(self, custom_signal: QtCore.Signal=None, warn=True, extra_delay=0.5) -> None:
        self.wait_for_signal_or_value(
            signal=custom_signal or self.application.series_retriever.finished_signal,
            value=not self.application.series_retrieval_busy,
            warning_title=UI_TEXT_ELEMENTS["warnings"]["series_still_loading_warning"]["title"],
            warning_text=UI_TEXT_ELEMENTS["warnings"]["series_still_loading_warning"]["text"],
            extra_delay=extra_delay,
            warn=warn
        )

