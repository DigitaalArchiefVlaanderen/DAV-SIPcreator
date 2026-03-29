from PySide6 import QtCore

from src.utils.base_object import BaseObject
from src.utils.data_objects.sip import SIP

from src.window.base_window import Window
from src.window.configuration_window import ConfigurationWindow
from src.window.sip_creator_window import SipCreatorWindow

from src.window.digital.folder_mapping_window import FolderMappingWindow
from src.window.digital.sip_detail_window import SipDetailWindow
from src.window.grid_window import GridWindow


class WindowController(BaseObject):
    open_digital_grid_signal = QtCore.Signal(SIP)

    def __init__(self) -> None:
        super().__init__()

        self.sip_creator_window = SipCreatorWindow()

        # Mapping of windows
        self.trackable_windows: dict[SIP, dict[type[Window], Window]] = dict()

        self.application.application_environment_changed_signal.connect(self._close_all_tracked_windows)

    def close_controller(self) -> None:
        self.sip_creator_window.hide()
        self._close_all_tracked_windows()

    def _close_all_tracked_windows(self) -> None:
        for windows_dict in self.trackable_windows.values():
            for window in windows_dict.values():
                window.close()

        self.trackable_windows.clear()

    def open_sip_creator_window(self) -> SipCreatorWindow:
        self.sip_creator_window.show()

        return self.sip_creator_window

    def open_configuration_window(self) -> ConfigurationWindow:
        # NOTE: we always remake this, since it loads the real time configuration data
        configuration_window = ConfigurationWindow()
        configuration_window.show()

        return configuration_window

    # Helpers
    def __open_from_trackable(self, sip: SIP, window_type: type[Window], *window_args, **window_kwargs) -> Window:
        windows_dict = self.trackable_windows.setdefault(sip, dict())

        if window_type in windows_dict:
            existing = windows_dict[window_type]
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return existing

        window_kwargs["sip"] = sip
        window = window_type(*window_args, **window_kwargs)
        windows_dict[window_type] = window

        window.window_about_to_close_signal.connect(
            lambda: self._untrack_window(sip, window_type)
        )

        window.show()
        return window

    def _untrack_window(self, sip: SIP, window_type: type[Window]) -> None:
        if sip in self.trackable_windows and window_type in self.trackable_windows[sip]:
            del self.trackable_windows[sip][window_type]

    def close_windows_for_sip(self, sip: SIP) -> None:
        if sip not in self.trackable_windows:
            return

        for window in list(self.trackable_windows[sip].values()):
            window.close()

        self.trackable_windows.pop(sip, None)

    # Digital
    def open_folder_mapping_window(self, sip: SIP) -> FolderMappingWindow:
        return self.__open_from_trackable(
            sip=sip,
            window_type=FolderMappingWindow
        )

    def open_sip_detail_window(self, sip: SIP) -> SipDetailWindow:
        return self.__open_from_trackable(
            sip=sip,
            window_type=SipDetailWindow
        )

    def open_grid_window(self, sip: SIP) -> GridWindow:
        return self.__open_from_trackable(
            sip=sip,
            window_type=GridWindow
        )

