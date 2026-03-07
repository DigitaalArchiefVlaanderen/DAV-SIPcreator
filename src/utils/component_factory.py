from src.utils.base_object import BaseObject
from src.utils.data_objects.digital.sip import SIP

from src.window.base_window import Window

from src.widget.components.digital.dossier_widget import DossierWidget
from src.widget.components.digital.sip_listitem_widget import SipListitemWidget

class ComponentFactory(BaseObject):
    """
        This factory is meant to be used to generate components on the fly.
        This factory does not keep reference to the component, nor will it set any signals.
    """
    # Digital
    def create_dossier_widgets(self, parent_window: Window, dossier_paths: list[str]) -> list[DossierWidget]:
        return [DossierWidget(parent_window=parent_window, path=p) for p in dossier_paths]
    
    def create_sip_list_item(self, parent_window: Window, sip: SIP) -> SipListitemWidget:
        return SipListitemWidget(parent_window=parent_window, sip=sip)
    

    