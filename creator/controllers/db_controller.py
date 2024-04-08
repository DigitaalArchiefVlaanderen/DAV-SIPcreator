import sqlite3 as sql
from PySide6.QtWidgets import QApplication

from typing import List
import json

from ..utils.sql import tables
from ..utils.state_utils.dossier import Dossier
from ..utils.state_utils.sip import SIP
from ..utils.sip_status import SIPStatus
from ..utils.series import Series
from ..utils.configuration import Configuration


# TODO: also move config into the db?
class DBController:
    def __init__(self, db_location: str):
        self.db_location = db_location

        with self.conn as conn:
            conn.execute(tables.create_dossier_table)
            conn.execute(tables.create_series_table)
            conn.execute(tables.create_sip_table)
            conn.execute(tables.create_sip_dossier_link_table)
            conn.commit()

    @property
    def conn(self) -> sql.Connection:
        return sql.connect(self.db_location)

    # Dossiers
    def read_dossiers(self) -> List[Dossier]:
        dossiers = []

        with self.conn as conn:
            cursor = conn.execute(tables.read_all_dossier)

            for path, disabled in cursor.fetchall():
                dossiers.append(Dossier(path=path, disabled=bool(disabled)))

        return dossiers

    def find_dossier(self, path: str) -> Dossier:
        with self.conn as conn:
            cursor = conn.execute(tables.find_dossier, (path,))

            for path, disabled in cursor.fetchall():
                return Dossier(path=path, disabled=bool(disabled))

    def insert_dossier(self, dossier: Dossier):
        # If dossier already exists, enable it again
        if self.find_dossier(dossier.path) is not None:
            self.enable_dossier(dossier=dossier)
            return

        with self.conn as conn:
            conn.execute(tables.insert_dossier, (dossier.path,))
            conn.commit()

    def disable_dossier(self, dossier: Dossier):
        with self.conn as conn:
            conn.execute(tables.disable_dossier, (dossier.path,))
            conn.commit()

        dossier.disabled = True

    def enable_dossier(self, dossier: Dossier):
        with self.conn as conn:
            conn.execute(tables.enable_dossier, (dossier.path,))
            conn.commit()

        dossier.disabled = False

    # Series
    def find_series(self, series_id: str) -> Series:
        with self.conn as conn:
            cursor = conn.execute(tables.get_series_by_id, (series_id,))

            for _id, status, name, valid_from, valid_to in cursor.fetchall():
                return Series(
                    _id=_id,
                    name=name,
                    status=status,
                    valid_from=(
                        None
                        if valid_from == ""
                        else Series.datetime_from_str(valid_from)
                    ),
                    valid_to=(
                        None if valid_to == "" else Series.datetime_from_str(valid_to)
                    ),
                )

    def insert_series(self, series: Series):
        if self.find_series(series_id=series._id) is not None:
            self.update_series(series=series)
            return

        with self.conn as conn:
            conn.execute(
                tables.insert_series,
                (
                    series._id,
                    series.status,
                    series.name,
                    (
                        ""
                        if series.valid_from is None
                        else Series.str_from_datetime(series.valid_from)
                    ),
                    (
                        ""
                        if series.valid_to is None
                        else Series.str_from_datetime(series.valid_to)
                    ),
                ),
            )
            conn.commit()

    def update_series(self, series: Series):
        with self.conn as conn:
            conn.execute(
                tables.update_series,
                (
                    series.status,
                    series.name,
                    (
                        ""
                        if series.valid_from is None
                        else Series.str_from_datetime(series.valid_from)
                    ),
                    (
                        ""
                        if series.valid_to is None
                        else Series.str_from_datetime(series.valid_to)
                    ),
                    series._id,
                ),
            )
            conn.commit()

    # Sips
    def get_sip_count(self) -> int:
        with self.conn as conn:
            cursor = conn.execute(tables.get_sip_count)

            return cursor.fetchone()[0]

    def read_sips(self) -> List[SIP]:
        sips = []

        with self.conn as conn:
            cursor = conn.execute(tables.read_all_sip)

            for (
                _id,
                environment_name,
                name,
                status,
                series_id,
                metadata_file_path,
                mapping_dict,
            ) in cursor.fetchall():
                c = conn.execute(tables.get_dossiers_by_sip_id, (_id,))

                dossiers = []

                for path, *_ in c.fetchall():
                    dossiers.append(Dossier(path=path))

                sips.append(
                    SIP(
                        _id=_id,
                        environment_name=environment_name,
                        dossiers=dossiers,
                        name=name,
                        status=SIPStatus[status],
                        series=self.find_series(series_id=series_id),
                        metadata_file_path=metadata_file_path,
                        mapping=json.loads(mapping_dict),
                    )
                )

        return sips

    def insert_sip(self, sip: SIP):
        with self.conn as conn:
            conn.execute(
                tables.insert_sip,
                (
                    sip._id,
                    sip.environment.name,
                    sip.name,
                    sip.status.name,
                    sip.series._id,
                    sip.metadata_file_path,
                    json.dumps(sip.mapping),
                ),
            )

            for dossier in sip.dossiers:
                conn.execute(tables.insert_sip_dossier_link, (sip._id, dossier.path))

            conn.commit()

    def update_sip(self, sip: SIP):
        with self.conn as conn:
            conn.execute(
                tables.update_sip,
                (
                    sip.environment.name,
                    sip.name,
                    sip.status.name,
                    sip.series._id,
                    sip.metadata_file_path,
                    json.dumps(sip.mapping),
                    sip._id,
                ),
            )

            conn.commit()
