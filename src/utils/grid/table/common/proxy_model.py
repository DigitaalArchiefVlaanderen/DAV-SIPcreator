from enum import Enum

from PySide6 import QtCore

from src.utils.constants import ColumnName, RowType
from src.utils.grid.table.common.data_table import DataTable


class TableFilter(Enum):
    BAD_ROWS = "bad_rows"
    DOSSIERS_ONLY = "dossiers_only"


class SortFilterProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setDynamicSortFilter(False)
        self.active_filters: set[TableFilter] = set()

    def reset_sorting(self) -> None:
        self.sort(-1)

    def toggle_filter(self, table_filter: TableFilter) -> None:
        if table_filter in self.active_filters:
            self.active_filters.remove(table_filter)
        else:
            self.active_filters.add(table_filter)

        self.invalidateFilter()

    def clear_filters(self) -> None:
        self.active_filters.clear()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, _: QtCore.QModelIndex) -> bool:
        if not self.active_filters:
            return True

        model: DataTable = self.sourceModel()

        for table_filter in self.active_filters:
            match table_filter:
                case TableFilter.BAD_ROWS:
                    if source_row not in model.bad_rows:
                        return False

                case TableFilter.DOSSIERS_ONLY:
                    if model.raw_data.iloc[source_row, model.raw_data.columns.get_loc(ColumnName.TYPE.value)] != RowType.DOSSIER:
                        return False

        return True

