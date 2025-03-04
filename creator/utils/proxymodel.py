from typing import Callable

from PySide6 import QtCore

from .tablemodel import TableModel


class CustomSortFilterModel(QtCore.QSortFilterProxyModel):
    SHOW_DOSSIERS_FILTER = "show_dossiers_filter"
    BAD_ROWS_FILTER = "bad_rows"
    ROWS_WITHOUT_SERIES_FILTER = "rows_without_series"

    _ALL_FILTERS = [
        SHOW_DOSSIERS_FILTER,
        BAD_ROWS_FILTER,
        ROWS_WITHOUT_SERIES_FILTER
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.filters = []

    def add_filter(self, _filter: str=None) -> None:
        # Adds the filter to use
        if _filter not in CustomSortFilterModel._ALL_FILTERS:
            return

        if _filter in self.filters:
            return

        self.filters.append(_filter)
        self.invalidateFilter()

    def remove_filter(self, _filter: str=None) -> None:
        if _filter not in self.filters:
            return
        
        self.filters.remove(_filter)
        self.invalidateFilter()

    def clear_filters(self) -> None:
        self.filters = []
        self.invalidateFilter()

    def data_changed_handler(self, start_index: QtCore.QModelIndex, end_index: QtCore.QModelIndex) -> None:
        start_row = start_index.row()
        end_row = end_index.row()

        if end_row < start_row:
            start_row, end_row = end_row, start_row

        for r in range(start_row, end_row):
            # Only trigger the update to happen for each row needed
            self.invalidateFilter(r)

    def filterAcceptsRow(self, source_row: int, _: QtCore.QModelIndex) -> bool:
        """This method gets called at the beginning of the table existing, and every time we call invalidateFilter"""
        # Determines if the row is visible or not
        is_row_visible = True

        # If no filters set, row is always visible
        if len(self.filters) == 0:
            return True

        model: TableModel = self.sourceModel()

        # Get the filter types
        for _filter in self.filters:
            method: Callable[[int], bool] = None

            match _filter:
                case CustomSortFilterModel.SHOW_DOSSIERS_FILTER:
                    method = model.row_is_dossier
                case CustomSortFilterModel.BAD_ROWS_FILTER:
                    method = model.row_is_bad
                case CustomSortFilterModel.ROWS_WITHOUT_SERIES_FILTER:
                    method = model.row_has_no_series

            is_row_visible = is_row_visible and method(source_row)

        return is_row_visible
