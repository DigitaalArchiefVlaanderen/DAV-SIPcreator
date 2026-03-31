import re

import openpyxl
import pandas as pd


class ExcelReadError(Exception):
    pass


def _format_number(value, number_format: str) -> str:
    """Apply an Excel number_format to a numeric value to get the display text."""
    if number_format in (None, "General", "general"):
        # General format: Excel displays integers without decimals
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        return str(value)

    if number_format == "0":
        return str(int(round(value)))

    # Fixed decimal places: "0.00", "0.0", "#,##0.00", etc.
    decimal_match = re.search(r"\.([0#]+)", number_format)
    if decimal_match:
        decimal_places = len(decimal_match.group(1))
        return f"{value:.{decimal_places}f}"

    # Percentage: "0%", "0.00%"
    if "%" in number_format:
        decimal_match = re.search(r"\.([0#]+)", number_format)
        decimal_places = len(decimal_match.group(1)) if decimal_match else 0
        return f"{value * 100:.{decimal_places}f}%"

    # Fallback: same as General
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


class ExcelController:
    @staticmethod
    def read_excel(path: str) -> pd.DataFrame:
        """
        Reads an Excel file and returns its contents as a DataFrame.
        All values are read as display text, matching what Excel shows.
        Dates are formatted as YYYY-MM-DD.

        Raises ExcelReadError if the file cannot be read.
        """
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
            ws = wb.active

            rows = list(ws.iter_rows())

            if not rows:
                wb.close()
                return pd.DataFrame()

            # Deduplicate column names (like pandas does with .1, .2 suffixes)
            raw_headers = [cell.value for cell in rows[0]]
            seen = {}
            headers = []
            for h in raw_headers:
                h_str = str(h) if h is not None else ""
                if h_str in seen:
                    seen[h_str] += 1
                    headers.append(f"{h_str}.{seen[h_str]}")
                else:
                    seen[h_str] = 0
                    headers.append(h_str)

            data = []
            for row in rows[1:]:
                row_data = []
                for cell in row:
                    value = cell.value

                    if value is None:
                        row_data.append("")
                    elif hasattr(value, "strftime"):
                        row_data.append(value.strftime("%Y-%m-%d"))
                    elif isinstance(value, (int, float)):
                        row_data.append(_format_number(value, cell.number_format))
                    else:
                        row_data.append(str(value))

                data.append(row_data)

            wb.close()

            return pd.DataFrame(data, columns=headers).fillna("")
        except ExcelReadError:
            raise
        except Exception as e:
            raise ExcelReadError(str(e)) from e
