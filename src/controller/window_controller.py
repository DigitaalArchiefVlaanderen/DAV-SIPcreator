from PySide6 import QtCore

from src.utils.base_object import BaseObject
from src.utils.data_objects.sip import SIP

from src.window.base_window import Window
from src.window.configuration_window import ConfigurationWindow
from src.window.sip_creator_window import SipCreatorWindow

from src.window.digital.folder_mapping_window import FolderMappingWindow
from src.window.digital.sip_detail_window import SipDetailWindow


class WindowController(BaseObject):
    open_digital_grid_signal = QtCore.Signal(SIP)

    def __init__(self) -> None:
        super().__init__()

        self.sip_creator_window = SipCreatorWindow()

        # Mapping of windows
        self.trackable_windows: dict[SIP, dict[type[Window], Window]] = dict()

        self.application.application_environment_changed_signal.connect(self._close_all_tracked_windows)

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

        # NOTE: we could use another setdefault here
        # But that would mean instantiating the detail window even if we don't need it anymore
        # Since that might take up some time, we avoid that unless we need it
        if window_type in windows_dict:
            return windows_dict[window_type]
        
        # We need it
        window_kwargs["sip"] = sip
        window = windows_dict.setdefault(window_type, window_type(*window_args, **window_kwargs))

        window.show()
        return window

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

