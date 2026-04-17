from datetime import datetime

import numpy as np
import pandas as pd
from pandas import DataFrame

from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName, RowType
from src.utils.grid.checks.base_check import BaseCheck, BulkResult, CellRange

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["common"]

DATE_FORMAT = "%Y-%m-%d"
OPENING_COL = ColumnName.OPENINGSDATUM
CLOSING_COL = ColumnName.SLUITINGSDATUM


def parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except (ValueError, TypeError):
        return None


def _check_format(value: str) -> str | None:
    if value == "":
        return None

    date = parse_date(value)

    if date is None:
        return UI_TEXT["date_format_error"]

    if date > datetime.now() and date.year != 9999:
        return UI_TEXT["date_future_error"]

    return None


def _check_series_range(value: str, series_start: datetime | None, series_end: datetime | None) -> str | None:
    date = parse_date(value)

    if date is None:
        return None

    if series_start is not None and date < series_start:
        return UI_TEXT["date_before_series_start_error"]

    if series_end is not None and date > series_end:
        return UI_TEXT["date_after_series_end_error"]

    return None


class DateCheck(BaseCheck):
    def __init__(self, series_provider=None):
        self._series_provider = series_provider

    def _get_series_range(self) -> tuple[datetime | None, datetime | None]:
        if self._series_provider is None:
            return None, None

        series = self._series_provider()

        if series is None:
            return None, None

        return series.valid_from, series.valid_to

    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        rows = range(changed_range.row_start, changed_range.row_end + 1)
        row_list = list(rows)
        col_name = raw_data.columns[col]

        is_opening = col_name == OPENING_COL
        paired_col_name = CLOSING_COL if is_opening else OPENING_COL
        has_paired = paired_col_name in raw_data.columns
        has_type = ColumnName.TYPE in raw_data.columns

        values = raw_data.iloc[row_list, col].fillna("").astype(str)
        cell_tooltips = np.full(len(values), None, dtype=object)
        wide_tooltips = np.full(len(values), None, dtype=object)

        now = pd.Timestamp.now()
        series_start, series_end = self._get_series_range()

        dates = pd.to_datetime(values, format=DATE_FORMAT, errors="coerce")
        non_empty = values != ""
        has_value = non_empty.values
        parsed_ok = dates.notna().values

        bad_format = has_value & ~parsed_ok
        cell_tooltips[bad_format] = UI_TEXT["date_format_error"]

        is_future = parsed_ok & (dates > now).values & (dates.dt.year != 9999).values
        still_ok = has_value & parsed_ok & ~is_future
        cell_tooltips[is_future] = UI_TEXT["date_future_error"]

        if has_type:
            type_col = raw_data.columns.get_loc(ColumnName.TYPE)
            types = raw_data.iloc[row_list, type_col].astype(str).values

            is_dossier = types == RowType.DOSSIER
            empty_val = ~has_value

            dossier_empty = is_dossier & empty_val

            if is_opening:
                cell_tooltips[dossier_empty] = UI_TEXT["date_dossier_opening_empty_error"]
            else:
                cell_tooltips[dossier_empty] = UI_TEXT["date_dossier_closing_empty_error"]

        if has_paired:
            self._check_paired_columns_bulk(
                raw_data, row_list, paired_col_name, is_opening,
                still_ok, has_value, dates, series_start, series_end,
                cell_tooltips, wide_tooltips,
            )

        elif not has_paired:
            if series_start is not None:
                no_error = cell_tooltips == None
                below_start = still_ok & no_error & (dates < pd.Timestamp(series_start)).values
                cell_tooltips[below_start] = UI_TEXT["date_before_series_start_error"]

            if series_end is not None:
                no_error = cell_tooltips == None
                above_end = still_ok & no_error & (dates > pd.Timestamp(series_end)).values
                cell_tooltips[above_end] = UI_TEXT["date_after_series_end_error"]

        if has_type and has_paired and ColumnName.DOSSIER_REF in raw_data.columns:
            self._check_hierarchy_bulk(
                raw_data,
                row_list,
                col,
                is_opening,
                values,
                dates,
                cell_tooltips,
                wide_tooltips,
                series_start,
                series_end,
            )

        return [(row, col, None, cell_tooltips[i], wide_tooltips[i]) for i, row in enumerate(rows)]

    def _check_paired_columns_bulk(
        self,
        raw_data: DataFrame,
        row_list: list[int],
        paired_col_name: str,
        is_opening: bool,
        still_ok: np.ndarray,
        has_value: np.ndarray,
        dates: pd.Series,
        series_start: datetime | None,
        series_end: datetime | None,
        cell_tooltips: np.ndarray,
        wide_tooltips: np.ndarray,
    ) -> None:
        paired_col = raw_data.columns.get_loc(paired_col_name)
        paired_values = raw_data.iloc[row_list, paired_col].fillna("").astype(str)
        paired_dates = pd.to_datetime(paired_values, format=DATE_FORMAT, errors="coerce")
        paired_non_empty = (paired_values != "").values
        paired_parsed_ok = paired_dates.notna().values

        both_valid = still_ok & paired_parsed_ok

        if is_opening:
            order_bad = both_valid & (dates.values > paired_dates.values)
        else:
            order_bad = both_valid & (paired_dates.values > dates.values)

        no_cell_error = cell_tooltips == None
        if is_opening:
            wide_tooltips[order_bad & no_cell_error] = UI_TEXT["date_opening_after_closing_error"]
        else:
            wide_tooltips[order_bad & no_cell_error] = UI_TEXT["date_closing_before_opening_error"]

        no_wide_error = wide_tooltips == None
        no_error = no_cell_error & no_wide_error

        if series_start is not None:
            below_start = still_ok & no_error & (dates < pd.Timestamp(series_start)).values
            cell_tooltips[below_start] = UI_TEXT["date_before_series_start_error"]

        if series_end is not None:
            no_error = (cell_tooltips == None) & (wide_tooltips == None)
            above_end = still_ok & no_error & (dates > pd.Timestamp(series_end)).values
            cell_tooltips[above_end] = UI_TEXT["date_after_series_end_error"]

        no_error = (cell_tooltips == None) & (wide_tooltips == None)
        one_empty = no_error & has_value & ~paired_non_empty

        if is_opening:
            cell_tooltips[one_empty] = UI_TEXT["date_closing_empty_error"]
        else:
            cell_tooltips[one_empty] = UI_TEXT["date_opening_empty_error"]

        no_error = (cell_tooltips == None) & (wide_tooltips == None)
        other_one_empty = no_error & ~has_value & paired_non_empty & paired_parsed_ok

        if is_opening:
            cell_tooltips[other_one_empty] = UI_TEXT["date_opening_empty_error"]
        else:
            cell_tooltips[other_one_empty] = UI_TEXT["date_closing_empty_error"]

    def _check_hierarchy_bulk(
        self,
        raw_data: DataFrame,
        row_list: list[int],
        col: int,
        is_opening: bool,
        values: pd.Series,
        dates: pd.Series,
        cell_tooltips: np.ndarray,
        wide_tooltips: np.ndarray,
        series_start: datetime | None,
        series_end: datetime | None,
    ) -> None:
        type_col = raw_data.columns.get_loc(ColumnName.TYPE)
        dossier_ref_col = raw_data.columns.get_loc(ColumnName.DOSSIER_REF)
        opening_col = raw_data.columns.get_loc(OPENING_COL)
        closing_col = raw_data.columns.get_loc(CLOSING_COL)

        all_types = raw_data.iloc[:, type_col].astype(str)
        all_refs = raw_data.iloc[:, dossier_ref_col].astype(str)

        all_openings_str = raw_data.iloc[:, opening_col].fillna("").astype(str)
        all_closings_str = raw_data.iloc[:, closing_col].fillna("").astype(str)
        all_openings = pd.to_datetime(all_openings_str, format=DATE_FORMAT, errors="coerce")
        all_closings = pd.to_datetime(all_closings_str, format=DATE_FORMAT, errors="coerce")

        now = pd.Timestamp.now()
        series_start_ts = pd.Timestamp(series_start) if series_start else None
        series_end_ts = pd.Timestamp(series_end) if series_end else None

        def is_valid_date(date_series: pd.Series, str_series: pd.Series) -> pd.Series:
            valid = date_series.notna()
            is_future = (date_series > now) & (date_series.dt.year != 9999)
            valid = valid & ~is_future

            if series_start_ts is not None:
                valid = valid & (date_series >= series_start_ts)

            if series_end_ts is not None:
                valid = valid & (date_series <= series_end_ts)

            return valid

        valid_openings = is_valid_date(all_openings, all_openings_str)
        valid_closings = is_valid_date(all_closings, all_closings_str)

        unique_refs = set()

        for i, row in enumerate(row_list):
            row_type = raw_data.iat[row, type_col]

            if row_type not in (RowType.DOSSIER, RowType.STUK):
                continue

            if cell_tooltips[i] is not None or wide_tooltips[i] is not None:
                continue

            ref = raw_data.iat[row, dossier_ref_col]

            if ref in unique_refs:
                continue

            unique_refs.add(ref)

            dossier_mask = (all_types == RowType.DOSSIER) & (all_refs == ref)
            stuk_mask = (all_types == RowType.STUK) & (all_refs == ref)

            dossier_rows = raw_data.index[dossier_mask]

            if len(dossier_rows) == 0:
                continue

            dossier_row_pos = raw_data.index.get_loc(dossier_rows[0])

            stuk_valid_openings = all_openings[stuk_mask & valid_openings]
            stuk_valid_closings = all_closings[stuk_mask & valid_closings]

            if dossier_row_pos not in row_list:
                continue

            dossier_idx = row_list.index(dossier_row_pos)

            if cell_tooltips[dossier_idx] is not None or wide_tooltips[dossier_idx] is not None:
                continue

            dossier_opening = all_openings.iloc[dossier_row_pos]
            dossier_closing = all_closings.iloc[dossier_row_pos]

            if is_opening and len(stuk_valid_openings) > 0 and pd.notna(dossier_opening):
                min_stuk = stuk_valid_openings.min()

                if dossier_opening > min_stuk:
                    wide_tooltips[dossier_idx] = UI_TEXT["date_dossier_opening_after_stuk_error"]

            if not is_opening and len(stuk_valid_closings) > 0 and pd.notna(dossier_closing):
                max_stuk = stuk_valid_closings.max()

                if dossier_closing < max_stuk:
                    wide_tooltips[dossier_idx] = UI_TEXT["date_dossier_closing_before_stuk_error"]
