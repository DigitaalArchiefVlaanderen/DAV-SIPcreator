import numpy as np
from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["analog"]


class BeschrijvingCheck(BaseCheck):
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        rows = range(changed_range.row_start, changed_range.row_end + 1)
        row_list = list(rows)
        values = raw_data.iloc[row_list, col].astype(str)

        cell_tooltips = np.full(len(values), None, dtype=object)

        empty_mask = values == ""
        cell_tooltips[empty_mask.values] = UI_TEXT["beschrijving_empty_error"]

        non_empty = ~empty_mask
        all_values = raw_data.iloc[:, col].astype(str)

        for i, row in enumerate(row_list):
            if not non_empty.iloc[i]:
                continue

            value = values.iloc[i]
            duplicates = (all_values == value).sum()

            if duplicates > 1:
                cell_tooltips[i] = UI_TEXT["beschrijving_duplicate_error"]

        return [
            (row, col, values.iloc[i], cell_tooltips[i], None)
            for i, row in enumerate(rows)
        ]
