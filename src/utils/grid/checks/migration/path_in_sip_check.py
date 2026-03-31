from collections.abc import Callable

from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["migration"]


class PathInSipCheck(BaseCheck):
    def __init__(self, type_provider: Callable[[], str]) -> None:
        self._type_provider = type_provider

    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        active_type = self._type_provider()

        if active_type == "onroerend_erfgoed":
            return []

        results: list[BulkResult] = []

        for row in range(changed_range.row_start, changed_range.row_end + 1):
            value = str(raw_data.iat[row, col])

            if "/" in value:
                results.append(
                    (
                        row,
                        col,
                        value,
                        UI_TEXT["path_in_sip_slash_error"],
                        None,
                    )
                )

        return results
