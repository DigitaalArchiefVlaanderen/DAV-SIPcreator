from src.utils.constants import ColumnName
from src.utils.data_objects.sip import SIP
from src.utils.grid.table.common import CommonDataVerificationTable


DISABLED_COLUMNS = [
    ColumnName.PATH_IN_SIP.value,
    ColumnName.TYPE.value,
    ColumnName.DOSSIER_REF.value,
    ColumnName.ANALOOG.value,
]


class DigitalDataVerificationTable(CommonDataVerificationTable):
    def __init__(self, sip: SIP, editable: bool = True) -> None:
        super().__init__(sip, editable)

        for col in DISABLED_COLUMNS:
            if col in self.raw_data.columns:
                self.disable_column(col)
