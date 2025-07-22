import pandas as pd

class ExcelController:
    @staticmethod
    def read_excel(path: str) -> pd.DataFrame:
        df = pd.read_excel(path, engine="openpyxl")

        date_cols = []

        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime("%Y-%m-%d")
                date_cols.append(col)

        df2 = pd.read_excel(path, dtype=str, engine="openpyxl")
        for col in date_cols:
            df2[col] = df[col]

        return df2.fillna("")