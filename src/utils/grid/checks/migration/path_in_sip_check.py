from collections.abc import Callable

from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName, RowType, SIPType
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["migration"]


class PathInSipCheck(BaseCheck):
    def __init__(self, type_provider: Callable[[], str]) -> None:
        self._type_provider = type_provider

    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        active_type = self._type_provider()

        if active_type == SIPType.ONROEREND_ERFGOED:
            return self._check_dossier_in_grid(raw_data, col, changed_range)

        results: list[BulkResult] = []

        for row in range(changed_range.row_start, changed_range.row_end + 1):
            value = str(raw_data.iat[row, col])

            if "/" in value:
                results.append((row, col, None, UI_TEXT["path_in_sip_slash_error"], None))

        return results

    @staticmethod
    def _check_dossier_in_grid(raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        if ColumnName.TYPE not in raw_data.columns or ColumnName.DOSSIER_REF not in raw_data.columns:
            return []

        type_col = raw_data.columns.get_loc(ColumnName.TYPE)
        ref_col = raw_data.columns.get_loc(ColumnName.DOSSIER_REF)

        dossier_paths = {
            str(raw_data.iat[row, col]).strip()
            for row in range(len(raw_data))
            if str(raw_data.iat[row, type_col]).strip() == RowType.DOSSIER
        }

        results: list[BulkResult] = []

        for row in range(changed_range.row_start, changed_range.row_end + 1):
            if str(raw_data.iat[row, type_col]).strip() != RowType.STUK:
                continue

            dossier_ref = str(raw_data.iat[row, ref_col]).strip()
            if dossier_ref not in dossier_paths:
                results.append((row, col, None, UI_TEXT["dossier_not_in_grid"], None))

        return results
