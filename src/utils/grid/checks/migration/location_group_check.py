from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

LOCATION_COLUMNS = (
    ColumnName.ORIGINEEL_DOOSNUMMER.value,
    ColumnName.LEGACY_LOCATIE_ID.value,
    ColumnName.LEGACY_RANGE.value,
    ColumnName.VERPAKKINGSTYPE.value,
)

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["migration"]


def _get_location_groups(columns: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    base_group = [col for col in LOCATION_COLUMNS if col in columns]

    if len(base_group) == 4:
        groups.append(base_group)

    suffix = 1

    while True:
        suffixed_group = [f"{col}_{suffix}" for col in LOCATION_COLUMNS]
        found = [col for col in suffixed_group if col in columns]

        if len(found) != 4:
            break

        groups.append(suffixed_group)
        suffix += 1

    return groups


class LocationGroupCheck(BaseCheck):
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        columns = list(raw_data.columns)
        groups = _get_location_groups(columns)

        if not groups:
            return []

        results: list[BulkResult] = []
        rows = range(changed_range.row_start, changed_range.row_end + 1)

        for group in groups:
            group_col_indices = [columns.index(c) for c in group]

            for row in rows:
                values = [str(raw_data.iat[row, c]) for c in group_col_indices]
                has_any = any(v.strip() for v in values)
                has_all = all(v.strip() for v in values)

                if has_any and not has_all:
                    for i, c in enumerate(group_col_indices):
                        if not values[i].strip():
                            results.append(
                                (
                                    row,
                                    c,
                                    values[i],
                                    UI_TEXT["location_group_incomplete"],
                                    None,
                                )
                            )

        return results
