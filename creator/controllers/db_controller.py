from PySide6 import QtWidgets
import sqlite3 as sql
import pandas as pd

import json
import os
from typing import List, Iterable

from ..utils.sql import tables
from ..utils.state_utils.dossier import Dossier
from ..utils.state_utils.sip import SIP
from ..utils.sip_status import SIPStatus
from ..utils.series import Series


class NotASIPDBException(Exception):
    pass

class NonUniqueDBException(Exception):
    pass


class DBController:
    def __init__(self, db_location: str):
        # NOTE: import here to avoid import loop
        from ..application import Application
        from ..utils.state import State

        self.application: Application = None
        self.state: State = None

        self.db_location = db_location

        # TODO db: remove what is no longer required
        with self.conn as conn:
            conn.execute(tables.create_dossier_table)
            conn.execute(tables.create_series_table)
            conn.execute(tables.create_sip_table)
            conn.execute(tables.create_sip_dossier_link_table)
            conn.commit()

        # Perform the sequential table updates if needed
        for sip_update in tables.update_sip_table:
            with self.conn as conn:
                try:
                    conn.execute(sip_update)
                    conn.commit()
                except sql.Error:
                    conn.rollback()

    def set_application(self) -> None:
        # NOTE: import here to avoid import loop
        from ..application import Application
        from ..utils.state import State

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

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

        # NOTE: since we might also have transferred some db from someone else
        # We need to read all sip_dbs to make sure we have all dossiers read
        dbs_location = self.state.configuration.sip_db_location

        for db_file in os.listdir(dbs_location):
            path = os.path.join(dbs_location, db_file)

            # skip over non-db files
            if not db_file.endswith(".db"):
                continue

            sip_db_controller = SIPDBController(path)
            
            # check db_file
            if sip_db_controller.is_valid_db():
                new_dossiers = sip_db_controller.read_dossiers()

                for dossier in new_dossiers:
                    if dossier in dossiers:
                        continue

                    # NOTE: always set it to disabled
                    dossier.disabled = True
                    dossiers.append(dossier)

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

    def insert_dossiers(self, dossiers: List[Dossier]):
        with self.conn as conn:
            for dossier in dossiers:
                if self.find_dossier(dossier.path) is not None:
                    conn.execute(tables.enable_dossier, (dossier.path,))
                    continue

                conn.execute(tables.insert_dossier, (dossier.path,))

            conn.commit()

    def disable_dossier(self, dossier: Dossier):
        with self.conn as conn:
            conn.execute(tables.disable_dossier, (dossier.path,))
            conn.commit()

        dossier.disabled = True

    def disable_dossiers(self, dossiers: Iterable[Dossier]):
        with self.conn as conn:
            for dossier in dossiers:
                conn.execute(tables.disable_dossier, (dossier.path,))
            conn.commit()

        for dossier in dossiers:
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
        if series._id == "":
            return

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
    def read_sips(self) -> List[SIP]:
        # read from the dbs_location
        dbs_location = self.state.configuration.sip_db_location
        sips = []

        for db_file in os.listdir(dbs_location):
            path = os.path.join(dbs_location, db_file)

            # skip over non-db files
            if not db_file.endswith(".db"):
                continue

            sip_db_controller = SIPDBController(path)
            
            # check db_file
            if sip_db_controller.is_valid_db():
                sips.append(sip_db_controller.read_sip())
            else:
                raise NotASIPDBException(f"Database laden is gefaald.\nDe database op locatie '{path}' is geen SIP database of is corrupt.")

        return sips

    def read_sips_old(self) -> List[SIP]:
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
                tag_mapping_dict,
                folder_mapping_list,
                edepot_sip_id,
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
                        tag_mapping=json.loads(tag_mapping_dict),
                        folder_mapping=json.loads(folder_mapping_list),
                        edepot_sip_id=edepot_sip_id,
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
                    json.dumps(sip.tag_mapping),
                    json.dumps(sip.folder_mapping),
                    sip.edepot_sip_id,
                ),
            )

            for dossier in sip.dossiers:
                conn.execute(tables.insert_sip_dossier_link, (sip._id, dossier.path))

            conn.commit()

    def update_sip(self, sip: SIP):
        if sip.status == SIPStatus.DELETED:
            return self.delete_sip(sip)

        with self.conn as conn:
            conn.execute(
                tables.update_sip,
                (
                    sip.environment.name,
                    sip.name,
                    sip.status.name,
                    sip.series._id,
                    sip.metadata_file_path,
                    json.dumps(sip.tag_mapping),
                    json.dumps(sip.folder_mapping),
                    sip.edepot_sip_id,
                    sip._id,
                ),
            )

            conn.commit()

    def delete_sip(self, sip: SIP):
        # Delete the sip from the db, including all it's connections
        with self.conn as conn:
            conn.execute(
                tables.delete_series,
                (
                    sip.series._id,
                ),
            )
            conn.execute(
                tables.delete_dossiers_by_sip,
                (
                    sip._id,
                ),
            )
            conn.execute(
                tables.delete_dossier_links_by_sip,
                (
                    sip._id,
                ),
            )
            conn.execute(
                tables.delete_sip,
                (
                    sip._id,
                ),
            )

            conn.commit()

class SIPDBController:
    # NOTE: "data" table is not mentioned here
    TABLES = {
        "SIP": {
            "environment": "TEXT",
            "status": "TEXT",
            "series_json": "TEXT",
            "metadata_file_path": "TEXT",
            "tag_mapping": "TEXT",
            "folder_mapping": "TEXT",
            "edepot_sip_id": "TEXT",
        },
        "dossier": {
            "name": "TEXT",
            "path": "TEXT",
        }
    }

    def __init__(self, db_location: str):
        self.db_location = db_location

    @property
    def conn(self) -> sql.Connection:
        return sql.connect(self.db_location)

    @staticmethod
    def get_sip_count(path: str) -> int:
        count = 0

        for file in os.listdir(path):
            db_location = os.path.join(path, file)

            if file.endswith(".db"):
                if SIPDBController(db_location=db_location).is_valid_db():
                    count += 1

        return count

    def create_db(self, df: pd.DataFrame, sip: SIP) -> None:
        if os.path.exists(self.db_location):
            raise NonUniqueDBException(f"Attempted to create db at '{self.db_location}', but a db already exists")

        if sip.series is None:
            raise ValueError("SIP has no series attached yet, cannot make db")

        with self.conn as conn:
            # NOTE: create tables first
            conn.execute(self.create_table_sql_from_dict("SIP"))
            conn.execute(self.create_table_sql_from_dict("dossier"))

        self.update_data_table(df)

        # NOTE: fill tables with data needed
        self.fill_sip_table(sip=sip)
        self.fill_dossier_table(dossiers=sip.dossiers)

    def create_table_sql_from_dict(self, table_name: str) -> str:
        return f"""
            CREATE TABLE {table_name} (
                {',\n'.join(
                    f"{column_name} {data_type}" for column_name, data_type in self.TABLES[table_name].items()
                )}
            );
        """

    def fill_sip_table(self, sip: SIP) -> None:
        # environment
        # status
        # series_json
        # metadata_file_path
        # tag_mapping
        # folder_mapping
        # edepot_sip_id

        with self.conn as conn:
            conn.execute(
                f"INSERT INTO SIP VALUES (?, ?, ?, ?, ?, ?, ?);",
                (
                    sip.environment_name,
                    sip.status.name,
                    json.dumps(sip.series.to_dict()),
                    sip.metadata_file_path,
                    json.dumps(sip.tag_mapping),
                    json.dumps(sip.folder_mapping),
                    sip.edepot_sip_id,
                )
            )
    
    def fill_dossier_table(self, dossiers: list[Dossier]) -> None:
        # name
        # path

        with self.conn as conn:
            for dossier in dossiers:
                name = os.path.basename(dossier.path)

                conn.execute(
                    f"INSERT INTO dossier VALUES (?, ?);",
                    (
                        name,
                        dossier.path,
                    )
                )

    def update_sip_table(self, sip: SIP) -> None:
        with self.conn as conn:
            conn.execute(
                f"""
                    UPDATE SIP
                    SET environment=?,
                        status=?,
                        series_json=?,
                        metadata_file_path=?,
                        tag_mapping=?,
                        folder_mapping=?,
                        edepot_sip_id=?
                """,
                (
                    sip.environment_name,
                    sip.status.name,
                    json.dumps(sip.series.to_dict()),
                    sip.metadata_file_path,
                    json.dumps(sip.tag_mapping),
                    json.dumps(sip.folder_mapping),
                    sip.edepot_sip_id,
                )
            )

    def read_data_table(self) -> pd.DataFrame:
        with self.conn as conn:
            return pd.read_sql_query(
                "SELECT * FROM data;",
                conn
            )

    def update_data_table(self, df: pd.DataFrame) -> None:
        # NOTE: since we use if_exists="replace" here, we can also replace column names easily (if series updated)
        with self.conn as conn:
            df.to_sql(
                "data",
                conn,
                if_exists="replace",
                index=False
            )


    def is_valid_db(self) -> bool:
        if not os.path.exists(self.db_location):
            return False
        
        if not self.db_location.endswith(".db"):
            return False
        
        try:
            conn = self.conn
            conn.close()
        except:
            return False

        with self.conn as conn:
            # Get all table names
            db_tables = (r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())

            if not "data" in db_tables:
                return False

            for table in db_tables:
                # NOTE: no extra tables allowed
                if table not in self.TABLES:
                    # NOTE: we will not consider the 'data'-table since it is too variable
                    if table == "data":
                        continue

                    return False
                

                columns = {column_name: data_type for column_name, data_type, *_ in conn.execute(f"PRAGMA table_info({table});").fetchall()}

                for column, data_type in self.TABLES[table].items():
                    # NOTE: missing column
                    if column not in columns:
                        return False
                    
                    # NOTE: bad data_type
                    if data_type != columns[column].upper():
                        return False
                    
        return True

    def read_dossiers(self) -> List[Dossier]:
        dossiers = []

        with self.conn as conn:
            result = conn.execute("SELECT path FROM dossier;").fetchall()

            for path, *_ in result:
                dossiers.append(
                    Dossier(
                        path=path,
                    )
                )

        return dossiers

    def read_sip(self) -> SIP:
        with self.conn as conn:
            result = conn.execute("SELECT * FROM SIP;").fetchone()

            environment, status, series_json, metadata_file_path, tag_mapping, folder_mapping, edepot_sip_id = result

            return SIP(
                environment_name=environment,
                dossiers = self.read_dossiers(),
                name=os.path.basename(self.db_location)[:-3],
                status=SIPStatus[status],
                series=Series.from_dict(json.loads(series_json)),
                metadata_file_path=metadata_file_path,
                tag_mapping=json.loads(tag_mapping),
                folder_mapping=json.loads(folder_mapping),
                edepot_sip_id=edepot_sip_id,
            )
