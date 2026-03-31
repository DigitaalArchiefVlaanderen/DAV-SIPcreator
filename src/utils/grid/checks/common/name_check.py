import numpy as np
from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["common"]
NAME_MAX_LENGTH = 255


class NameCheck(BaseCheck):
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        rows = range(changed_range.row_start, changed_range.row_end + 1)
        row_list = list(rows)
        values = raw_data.iloc[row_list, col].astype(str)

        cell_tooltips = np.full(len(values), None, dtype=object)
        wide_tooltips = np.full(len(values), None, dtype=object)

        too_long = values.str.len() > NAME_MAX_LENGTH
        cell_tooltips[too_long.values] = UI_TEXT["name_too_long_error"]

        has_type = ColumnName.TYPE.value in raw_data.columns

        if has_type:
            type_col = raw_data.columns.get_loc(ColumnName.TYPE.value)
            types = raw_data.iloc[row_list, type_col].astype(str)

            is_dossier = types == "dossier"
            ok_length = ~too_long

            empty_dossier = is_dossier & ok_length & (values == "")
            cell_tooltips[empty_dossier.values] = UI_TEXT["name_empty_dossier_error"]

            all_dossier_mask = raw_data.iloc[:, type_col] == "dossier"
            all_names = raw_data.iloc[:, col].astype(str)

            non_empty_dossier = is_dossier & ok_length & (values != "")

            for i in range(len(row_list)):
                if not non_empty_dossier.iloc[i]:
                    continue

                name = values.iloc[i]
                duplicates = (all_dossier_mask & (all_names == name)).sum()

                if duplicates > 1:
                    wide_tooltips[i] = UI_TEXT["name_duplicate_error"]

        return [(row, col, values.iloc[i], cell_tooltips[i], wide_tooltips[i]) for i, row in enumerate(rows)]
