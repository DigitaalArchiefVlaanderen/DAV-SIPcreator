from PySide6 import QtCore

from src.utils.constants import ColumnName, RowType
from src.utils.data_objects.sip import SIP
from src.utils.grid.checks.digital.empty_row_check import mark_empty_rows
from src.utils.grid.checks.migration import LocationGroupCheck, PathInSipCheck
from src.utils.grid.table.common import CommonDataVerificationTable

DISABLED_COLUMNS = [
    ColumnName.TYPE,
    ColumnName.DOSSIER_REF,
    ColumnName.ANALOOG,
]


class MigrationDataVerificationTable(CommonDataVerificationTable):
    def __init__(self, sip: SIP, editable: bool = True) -> None:
        super().__init__(sip, editable)

        location_check = LocationGroupCheck()
        path_in_sip_check = PathInSipCheck(type_provider=lambda: self.application.configuration.active_type)
        self.COLUMN_VALIDATORS = {
            **self.COLUMN_VALIDATORS,
            ColumnName.ORIGINEEL_DOOSNUMMER: location_check,
            ColumnName.PATH_IN_SIP: path_in_sip_check,
        }

        self._infer_missing_type_and_dossier_ref()
        self.re_mark_disabled_columns()

    def re_mark_disabled_columns(self) -> None:
        for col in DISABLED_COLUMNS:
            if col in self.raw_data.columns:
                self.disable_column(col)

        mark_empty_rows(self)

    def setData(self, index, value: str, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role != QtCore.Qt.ItemDataRole.EditRole:
            return False

        col_name = self.raw_data.columns[index.column()]

        if col_name == ColumnName.PATH_IN_SIP:
            self._auto_update_type_and_dossier_ref(index, str(value))

        return super().setData(index, value, role)

    def _infer_missing_type_and_dossier_ref(self) -> None:
        if ColumnName.PATH_IN_SIP not in self.raw_data.columns:
            return
        if ColumnName.TYPE not in self.raw_data.columns:
            return
        if ColumnName.DOSSIER_REF not in self.raw_data.columns:
            return

        path_col = self.raw_data.columns.get_loc(ColumnName.PATH_IN_SIP)
        type_col = self.raw_data.columns.get_loc(ColumnName.TYPE)
        dossier_ref_col = self.raw_data.columns.get_loc(ColumnName.DOSSIER_REF)

        for row in range(self.raw_data.shape[0]):
            if str(self.raw_data.iat[row, type_col]).strip():
                continue

            value = str(self.raw_data.iat[row, path_col]).strip()

            if not value:
                continue
            elif "/" in value:
                self.raw_data.iat[row, type_col] = RowType.STUK
                self.raw_data.iat[row, dossier_ref_col] = value.split("/", 1)[0]
            else:
                self.raw_data.iat[row, type_col] = RowType.DOSSIER
                self.raw_data.iat[row, dossier_ref_col] = value

    def _auto_update_type_and_dossier_ref(self, index: QtCore.QModelIndex, value: str) -> None:
        if ColumnName.TYPE not in self.raw_data.columns:
            return

        if ColumnName.DOSSIER_REF not in self.raw_data.columns:
            return

        row = index.row()
        type_col = self.raw_data.columns.get_loc(ColumnName.TYPE)
        dossier_ref_col = self.raw_data.columns.get_loc(ColumnName.DOSSIER_REF)

        value = value.strip()

        if not value:
            new_type = ""
            new_ref = ""
        elif "/" in value:
            new_type = RowType.STUK
            new_ref = value.split("/", 1)[0]
        else:
            new_type = RowType.DOSSIER
            new_ref = value

        self.raw_data.iat[row, type_col] = new_type
        self.raw_data.iat[row, dossier_ref_col] = new_ref

        self.dataChanged.emit(
            self.index(row, type_col),
            self.index(row, dossier_ref_col),
        )
