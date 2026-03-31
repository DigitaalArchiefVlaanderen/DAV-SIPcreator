import numpy as np
from pandas import DataFrame

from src.utils.constants import RRN_LOOSE_PATTERN, RRN_STRICT_PATTERN, UI_TEXT_ELEMENTS
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["common"]


class RRNCheck(BaseCheck):
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        rows = range(changed_range.row_start, changed_range.row_end + 1)
        rrn_series = raw_data.iloc[list(rows), col].astype(str)

        values = rrn_series.copy()
        cell_tooltips = np.full(len(values), None, dtype=object)

        non_empty = values != ""

        # NOTE: Transform loose format to strict
        loose_mask = non_empty & values.str.match(RRN_LOOSE_PATTERN.pattern)
        values[loose_mask] = (
            values[loose_mask].str[:2]
            + "."
            + values[loose_mask].str[2:4]
            + "."
            + values[loose_mask].str[4:6]
            + "-"
            + values[loose_mask].str[6:9]
            + "."
            + values[loose_mask].str[9:]
        )

        # NOTE: Check strict format (only non-empty)
        strict_mask = non_empty & values.str.match(RRN_STRICT_PATTERN.pattern)
        bad_format = non_empty & ~strict_mask
        cell_tooltips[bad_format.values] = UI_TEXT["rrn_format_error"]

        # NOTE: check if it is a valid RRN
        valid_format = non_empty & ~bad_format

        if valid_format.any():
            digits_series = (
                values[valid_format].str[:-2].str.replace(".", "", regex=False).str.replace("-", "", regex=False)
            )
            control = values[valid_format].str[-2:].astype(int)

            # NOTE: for people born after 2000, add a 2 to the digits
            digits_int = digits_series.astype(np.int64)
            digits_2_int = ("2" + digits_series).astype(np.int64)

            valid = (97 - digits_int % 97 == control) | (97 - digits_2_int % 97 == control)
            invalid_mask = valid_format.copy()
            invalid_mask[valid_format] = ~valid
            cell_tooltips[invalid_mask.values] = UI_TEXT["rrn_invalid_error"]

        return [(row, col, values.iloc[i], cell_tooltips[i], None) for i, row in enumerate(rows)]
