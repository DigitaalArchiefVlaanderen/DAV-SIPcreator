"""
This is a file containing helper scripts that need access to the Application instance or the current state
"""
import os
import time
from typing import Any

from PySide6 import QtCore, QtWidgets

from src.utils.base_object import BaseObject
from src.utils.constants import BASE_SIP_NAME, UI_TEXT_ELEMENTS


def set_widget_warning_style(widget: QtWidgets.QWidget, tooltip: str = "") -> None:
    font = widget.font()
    font.setBold(True)
    widget.setFont(font)
    widget.setStyleSheet("color: red;")
    widget.setToolTip(tooltip)


def clear_widget_warning_style(widget: QtWidgets.QWidget) -> None:
    font = widget.font()
    font.setBold(False)
    widget.setFont(font)
    widget.setStyleSheet("")
    widget.setToolTip("")


class Helper(BaseObject):
    def get_all_sip_names(self, sip_type: type = None) -> set[str]:
        from src.utils.data_objects.analog.sip import AnalogSIP
        from src.utils.data_objects.migration.sip import MigrationSIP

        db_names = set()

        if sip_type is None or sip_type not in (AnalogSIP, MigrationSIP):
            db_location = self.application.configuration.sip_db_location
        elif sip_type is AnalogSIP:
            db_location = self.application.configuration.analoog_location
        else:
            db_location = self.application.configuration.overdrachtslijsten_location

        if os.path.exists(db_location):
            for _, _, files in os.walk(db_location):
                db_names = {os.path.splitext(f)[0] for f in files}
                break

        if sip_type is not None:
            memory_names = {
                sip.name
                for sip_list in self.application.sips.get(sip_type, {}).values()
                for sip in sip_list
            }
        else:
            memory_names = {
                sip.name
                for sip_type_dict in self.application.sips.values()
                for sip_list in sip_type_dict.values()
                for sip in sip_list
            }

        return db_names | memory_names

    def get_next_sip_name(self, sip_type: type = None) -> str:
        next_sip_number = 1
        all_sip_names = self.get_all_sip_names(sip_type=sip_type)

        while (next_sip_name := BASE_SIP_NAME.format(number=next_sip_number)) in all_sip_names:
            next_sip_number += 1

        return next_sip_name

    def is_sip_name_available(self, name: str, sip_type: type = None, exclude_sip=None) -> bool:
        all_names = self.get_all_sip_names(sip_type=sip_type)

        if exclude_sip is not None:
            all_names.discard(exclude_sip.name)

        return name not in all_names

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
            self.application.notify_user_signal.emit(
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

