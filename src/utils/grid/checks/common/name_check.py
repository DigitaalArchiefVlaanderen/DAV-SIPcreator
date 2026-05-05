import numpy as np
from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS, BusinessRules, ColumnName, RowType
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["common"]


class NameCheck(BaseCheck):
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        all_values = raw_data.iloc[:, col].astype(str)
        all_rows = range(len(all_values))

        cell_tooltips = np.full(len(all_values), None, dtype=object)
        wide_tooltips = np.full(len(all_values), None, dtype=object)

        too_long = all_values.str.len() > BusinessRules.NAME_MAX_LENGTH
        cell_tooltips[too_long.values] = UI_TEXT["name_too_long_error"]

        has_type = ColumnName.TYPE in raw_data.columns

        if has_type:
            type_col = raw_data.columns.get_loc(ColumnName.TYPE)
            types = raw_data.iloc[:, type_col].astype(str)

            is_dossier = types == RowType.DOSSIER
            ok_length = ~too_long

            empty_dossier = is_dossier & ok_length & (all_values == "")
            cell_tooltips[empty_dossier.values] = UI_TEXT["name_empty_dossier_error"]

            non_empty_dossier = is_dossier & ok_length & (all_values != "")
            dossier_names = all_values[non_empty_dossier]
            duplicate_mask = dossier_names.duplicated(keep=False)
            duplicate_indices = dossier_names.index[duplicate_mask]
            wide_tooltips[duplicate_indices] = UI_TEXT["name_duplicate_error"]

        return [(row, col, None, cell_tooltips[row], wide_tooltips[row]) for row in all_rows]
