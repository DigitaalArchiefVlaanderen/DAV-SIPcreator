from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName, RowType
from src.utils.grid.table.common.data_table import DataTable

UI_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["digital"]


def mark_empty_rows(table: DataTable) -> None:
    raw_data = table.raw_data

    if ColumnName.TYPE not in raw_data.columns:
        return

    type_col = raw_data.columns.get_loc(ColumnName.TYPE)
    empty_mask = raw_data.iloc[:, type_col] == RowType.GEEN
    path_col_name = ColumnName.PATH_IN_SIP
    has_path = path_col_name in raw_data.columns

    for row_pos in range(len(raw_data)):
        if not empty_mask.iloc[row_pos]:
            continue

        tooltip = UI_TEXT["empty_stuk_warning"]

        if has_path:
            path_value = str(raw_data.iat[row_pos, raw_data.columns.get_loc(path_col_name)])
            is_dossier = "/" not in path_value

            if is_dossier:
                tooltip = UI_TEXT["empty_dossier_warning"]
            else:
                tooltip = UI_TEXT["empty_folder_warning"]

        for col in range(raw_data.shape[1]):
            index = table.index(row_pos, col)
            table.mark_cell(index, warning=True, tooltip=tooltip)
