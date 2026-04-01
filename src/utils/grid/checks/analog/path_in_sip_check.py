import numpy as np
from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["analog"]


class AnalogPathInSipCheck(BaseCheck):
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        all_values = raw_data.iloc[:, col].astype(str)

        cell_tooltips = np.full(len(all_values), None, dtype=object)

        # Empty-cell errors only for the changed range (avoids flagging trailing empty rows)
        changed_rows = set(range(changed_range.row_start, changed_range.row_end + 1))
        for row in changed_rows:
            if row < len(all_values) and all_values.iat[row] == "":
                cell_tooltips[row] = UI_TEXT["path_in_sip_empty_error"]

        # Duplicate check spans all rows (cross-row uniqueness)
        non_empty = all_values != ""
        non_empty_values = all_values[non_empty]
        duplicate_mask = non_empty_values.duplicated(keep=False)
        duplicate_indices = non_empty_values.index[duplicate_mask]
        cell_tooltips[duplicate_indices] = UI_TEXT["path_in_sip_duplicate_error"]

        # Return results for: changed rows + all non-empty rows (to clear stale duplicate markings)
        report_rows = changed_rows | set(non_empty_values.index)
        return [(row, col, None, cell_tooltips[row], None) for row in sorted(report_rows)]
