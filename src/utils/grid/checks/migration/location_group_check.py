from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

LOCATION_COLUMNS = (
    ColumnName.ORIGINEEL_DOOSNUMMER,
    ColumnName.LEGACY_LOCATIE_ID,
    ColumnName.LEGACY_RANGE,
    ColumnName.VERPAKKINGSTYPE,
)

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["migration"]


def _get_location_groups(columns: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    base_group = [col for col in LOCATION_COLUMNS if col in columns]

    if len(base_group) == 4:
        groups.append(base_group)

    suffix = 1

    while True:
        spaces = " " * suffix
        suffixed_group = [f"{col}{spaces}" for col in LOCATION_COLUMNS]
        found = [col for col in suffixed_group if col in columns]

        if len(found) != 4:
            break

        groups.append(suffixed_group)
        suffix += 1

    return groups


def validate_location_columns(columns: list[str]) -> str | None:
    """Validate that location columns appear in complete sets and correct order.

    Returns an error message if invalid, None if valid.
    """
    suffix = 0

    while True:
        spaces = " " * suffix if suffix > 0 else ""
        group = [f"{col}{spaces}" for col in LOCATION_COLUMNS]
        found = [col for col in group if col in columns]

        if len(found) == 0:
            break

        if len(found) != 4:
            missing = [col.rstrip() for col in group if col not in columns]
            return (
                f"Onvolledige set locatie kolommen gevonden. "
                f"Ontbrekend: {', '.join(missing)}"
            )

        # Verify order: the 4 columns must appear in the correct relative order
        indices = [columns.index(col) for col in group]
        if indices != sorted(indices) or any(indices[i + 1] - indices[i] != 1 for i in range(3)):
            return (
                "Locatie kolommen staan niet in de juiste volgorde. "
                f"Verwachte volgorde: {', '.join(col.rstrip() for col in LOCATION_COLUMNS)}"
            )

        suffix += 1

    return None


class LocationGroupCheck(BaseCheck):
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        columns = list(raw_data.columns)
        groups = _get_location_groups(columns)

        if not groups:
            return []

        results: list[BulkResult] = []
        rows = range(changed_range.row_start, changed_range.row_end + 1)

        for group_index, group in enumerate(groups):
            group_col_indices = [columns.index(c) for c in group]
            is_first_group = group_index == 0

            for row in rows:
                values = [str(raw_data.iat[row, c]) for c in group_col_indices]
                has_any = any(v.strip() for v in values)
                has_all = all(v.strip() for v in values)

                if is_first_group:
                    # First group: all 4 columns are always required
                    if not has_all:
                        for i, c in enumerate(group_col_indices):
                            if not values[i].strip():
                                results.append(
                                    (row, c, None, UI_TEXT["location_group_required"], None)
                                )
                elif has_any and not has_all:
                    # Subsequent groups: all-or-nothing
                    for i, c in enumerate(group_col_indices):
                        if not values[i].strip():
                            results.append(
                                (row, c, None, UI_TEXT["location_group_incomplete"], None)
                            )

        return results
