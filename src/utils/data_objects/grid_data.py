from dataclasses import dataclass

from pandas import DataFrame


@dataclass
class GridData:
    __data_as_records: list[dict[str, str]] = None
    __data_as_dict: dict[str, list[str]] = None
    __data_as_df: DataFrame = None

    @property
    def data_as_records(self) -> list[dict[str, str]]:
        if self.__data_as_records is not None:
            return self.__data_as_records

        if self.data_as_df is not None:
            self.__data_as_records = self.data_as_df.to_dict(orient="records")
            return self.__data_as_records

        raise ValueError("Tried to get data where none existed")

    @data_as_records.setter
    def data_as_records(self, data: list[dict[str, str]]) -> None:
        self.__data_as_records = data

    @property
    def data_as_dict(self) -> dict[str, list[str]]:
        if self.__data_as_dict is not None:
            return self.__data_as_dict

        if self.data_as_df is not None:
            self.__data_as_dict = self.data_as_df.to_dict(orient="list")
            return self.__data_as_dict

        raise ValueError("Tried to get data where none existed")

    @data_as_dict.setter
    def data_as_dict(self, data: dict[str, list[str]]) -> None:
        self.__data_as_dict = data

    @property
    def data_as_df(self) -> DataFrame:
        if self.__data_as_df is not None:
            return self.__data_as_df

        if self.__data_as_dict is not None:
            self.__data_as_df = DataFrame(self.__data_as_dict, dtype=str).fillna("").convert_dtypes()
        elif self.__data_as_records is not None:
            self.__data_as_df = DataFrame(self.__data_as_records, dtype=str).fillna("").convert_dtypes()
        else:
            raise ValueError("Tried to get data where none existed")

        return self.__data_as_df

    @data_as_df.setter
    def data_as_df(self, data: DataFrame) -> None:
        self.__data_as_df = data

    @property
    def has_data(self) -> bool:
        conditions = (
            self.__data_as_records is not None,
            self.__data_as_dict is not None,
            self.__data_as_df is not None,
        )

        return any(conditions)
