from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.utils.constants import APIResponseKey


class SeriesStatus(Enum):
    PUBLISHED = "Published"
    SUBMITTED = "Submitted"


@dataclass
class Series:
    _id: str = ""
    name: str = ""

    status: SeriesStatus = None
    valid_from: datetime = None
    valid_to: datetime = None

    @staticmethod
    def datetime_from_str(date_str: str) -> datetime:
        if date_str is None:
            return

        return datetime.strptime(date_str, "%Y-%m-%d")

    @staticmethod
    def str_from_datetime(date: datetime) -> str:
        return date.strftime("%Y-%m-%d")

    @staticmethod
    def from_dict(series: dict):
        validity_period = series[APIResponseKey.VALIDITY_PERIOD]

        valid_from = (
            Series.datetime_from_str(validity_period[APIResponseKey.FROM])
            if APIResponseKey.FROM in validity_period
            else None
        )
        valid_to = (
            Series.datetime_from_str(validity_period[APIResponseKey.TO])
            if APIResponseKey.TO in validity_period
            else None
        )

        return Series(
            _id=series[APIResponseKey.ID],
            name=series[APIResponseKey.CONTENT][APIResponseKey.NAME],
            status=SeriesStatus(series[APIResponseKey.STATUS][APIResponseKey.STATUS]),
            valid_from=valid_from,
            valid_to=valid_to,
        )

    def to_dict(self) -> dict:
        data = {
            APIResponseKey.ID: self._id,
            APIResponseKey.CONTENT: {APIResponseKey.NAME: self.name},
            APIResponseKey.STATUS: {APIResponseKey.STATUS: self.status.value},
            APIResponseKey.VALIDITY_PERIOD: {},
        }

        if self.valid_from is not None:
            data[APIResponseKey.VALIDITY_PERIOD][APIResponseKey.FROM] = self.str_from_datetime(self.valid_from)
        if self.valid_to is not None:
            data[APIResponseKey.VALIDITY_PERIOD][APIResponseKey.TO] = self.str_from_datetime(self.valid_to)

        return data

    @staticmethod
    def from_list(series_list: list) -> list:
        return [Series.from_dict(s) for s in series_list]

    def get_full_name(self) -> str:
        def transform_date(date: datetime):
            # Date comes in as YYYY-MM-DD
            # Date needs to go out as dd mon YYYY
            year, month, day = date.year, date.month, date.day

            match month:
                case 1:
                    month_name = "jan."
                case 2:
                    month_name = "feb."
                case 3:
                    month_name = "mrt."
                case 4:
                    month_name = "apr."
                case 5:
                    month_name = "mei."
                case 6:
                    month_name = "jun."
                case 7:
                    month_name = "jul."
                case 8:
                    month_name = "aug."
                case 9:
                    month_name = "sep."
                case 10:
                    month_name = "oct."
                case 11:
                    month_name = "nov."
                case 12:
                    month_name = "dec."

            return f"{day} {month_name} {year}"

        # Series name is the listed "Name" field including the "ValidityPeriod" when applicable
        validity_string = ""

        if self.valid_from is not None:
            validity_string += f" van {transform_date(self.valid_from)}"

        if self.valid_to is not None:
            validity_string += f" t.e.m {transform_date(self.valid_to)}"

        if self.valid_from is None and self.valid_to is None:
            validity_string = " van ... tot ..."

        validity_string = f"(Geldig{validity_string})"

        return f"{self.name} {validity_string}"

    def __str__(self) -> str:
        return self.get_full_name()

    def __repr__(self) -> str:
        return self.get_full_name()
