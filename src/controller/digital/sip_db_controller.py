import json
import os
import sqlite3 as sql

import pandas as pd

from src.controller.base_sip_db_controller import BaseSIPDBController

from src.utils.base_object import BaseObject
from src.utils.constants import (
    DB_FILE_EXTENSION,
    UI_TEXT_ELEMENTS,
    UNKNOWN_TRANSFORMED,
    APIResponseKey,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.digital.sip import SIP as DigitalSIP
from src.utils.data_objects.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import Helper

from src.widget.components.digital.dossier_widget import DossierWidget


def _parse_tag_mapping(raw: str) -> list[tuple[str, str]]:
    parsed = json.loads(raw)

    if isinstance(parsed, dict):
        return list(parsed.items())

    return [tuple(pair) for pair in parsed]


class DigitalSIPDBController(BaseSIPDBController):
    SIP_TYPE = DigitalSIP

    def __init__(self) -> None:
        super().__init__()

        # NOTE: this exists to transition old dbs to new ones
        self.old_sip_db_controller = OldDigitalSIPDBController()

    @property
    def db_location(self) -> str:
        return self.application.configuration.sip_db_location

    def create_sip_db(self, sip: SIP, series_id: str = None, series_name: str = None, transformed: str = "") -> None:
        db_path = os.path.join(self.db_location, sip.db_name)

        if os.path.exists(db_path):
            self._warn_db_already_exists(db_path)
            return

        if series_id is None or series_name is None:
            Helper().wait_for_series_loaded(custom_signal=sip.series_changed_signal, warn=False)

            if sip.series is None:
                self.application.notify_user_signal.emit(
                    UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_series_error"]["title"],
                    UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_series_error"]["text"],
                )
                return

            series_id = sip.series._id
            series_name = sip.series.get_full_name()

        if not sip.grid_data.has_data:
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_data_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_data_error"]["text"],
            )
            return

        def _create(conn: sql.Connection) -> None:
            conn.execute(f"""
                CREATE TABLE {DBTableName.SIP.value} (
                    {DBColumnName.NAME.value} text,
                    {DBColumnName.STATUS.value} text,
                    {DBColumnName.ENVIRONMENT_NAME.value} text,
                    {DBColumnName.SERIES_ID.value} text,
                    {DBColumnName.SERIES_NAME.value} text,
                    {DBColumnName.EDEPOT_SIP_ID.value} text,
                    {DBColumnName.DOSSIERS_LIST.value} text,
                    {DBColumnName.TAG_MAPPING.value} text,
                    {DBColumnName.FOLDER_MAPPING.value} text,
                    {DBColumnName.GRID_VALID.value} integer default 0
                )
            """)
            conn.execute(
                f"""
                INSERT INTO {DBTableName.SIP.value}
                ({DBColumnName.NAME.value}, {DBColumnName.STATUS.value}, {DBColumnName.ENVIRONMENT_NAME.value},
                 {DBColumnName.SERIES_ID.value}, {DBColumnName.SERIES_NAME.value}, {DBColumnName.EDEPOT_SIP_ID.value},
                 {DBColumnName.DOSSIERS_LIST.value}, {DBColumnName.TAG_MAPPING.value}, {DBColumnName.FOLDER_MAPPING.value},
                 {DBColumnName.GRID_VALID.value})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    sip.name,
                    sip.status.name,
                    sip.environment.name,
                    series_id,
                    series_name,
                    sip.edepot_sip_id or "",
                    json.dumps([d.path for d in sip.dossiers]),
                    json.dumps(sip.tag_mapping),
                    json.dumps(sip.folder_mapping),
                    int(sip.grid_valid),
                ),
            )

            self._create_sip_creator_table(conn, transformed)

            sip.grid_data.data_as_df.to_sql(DBTableName.DATA.value, conn, index=False, dtype="text")

        self._execute_with_conn(sip.db_name, _create)

    def read_sip_db(self, sip_db_file_name: str) -> tuple[SIP, str, str]:
        """
        Reads a sip from its db.
        Note however that this does not read the data, since we only get that on demand.
        """

        def _read(conn: sql.Connection) -> tuple[SIP, str, str]:
            columns = [col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()]
            has_grid_valid = DBColumnName.GRID_VALID.value in columns

            result = conn.execute(
                f"SELECT {DBColumnName.NAME.value}, {DBColumnName.STATUS.value}, {DBColumnName.ENVIRONMENT_NAME.value}, "
                f"{DBColumnName.SERIES_ID.value}, {DBColumnName.SERIES_NAME.value}, {DBColumnName.EDEPOT_SIP_ID.value}, "
                f"{DBColumnName.DOSSIERS_LIST.value}, {DBColumnName.TAG_MAPPING.value}, {DBColumnName.FOLDER_MAPPING.value}"
                + (f", {DBColumnName.GRID_VALID.value}" if has_grid_valid else "")
                + f" FROM {DBTableName.SIP.value};"
            ).fetchone()

            name, status, environment_name, series_id, series_name, edepot_sip_id, dossiers_list, tag_mapping, folder_mapping = result[:9]
            grid_valid = bool(result[9]) if has_grid_valid else False

            sip = DigitalSIP()
            sip.force_set_name(name)
            sip.set_status(SIPStatus[status])
            sip.environment = self.application.configuration.get_environment(environment_name)

            sip.edepot_sip_id = edepot_sip_id
            sip.saved_series_name = series_name
            sip.set_dossiers([DossierWidget(path=d) for d in json.loads(dossiers_list)])
            sip.tag_mapping = _parse_tag_mapping(tag_mapping)
            sip.folder_mapping = json.loads(folder_mapping)
            sip.set_grid_valid(grid_valid)

            return sip, series_id, series_name

        return self._execute_with_conn(sip_db_file_name, _read)

    def persist_sip(self, sip: SIP) -> None:
        if not self.db_exists(sip.db_name):
            return

        if sip.series is None:
            return

        def _persist(conn: sql.Connection) -> None:
            columns = [col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()]

            if DBColumnName.GRID_VALID.value in columns:
                conn.execute(
                    f"UPDATE {DBTableName.SIP.value} SET {DBColumnName.STATUS.value} = ?, "
                    f"{DBColumnName.SERIES_NAME.value} = ?, {DBColumnName.EDEPOT_SIP_ID.value} = ?, "
                    f"{DBColumnName.GRID_VALID.value} = ?",
                    (sip.status.name, sip.series.get_full_name(), sip.edepot_sip_id or "", int(sip.grid_valid)),
                )
            else:
                conn.execute(
                    f"UPDATE {DBTableName.SIP.value} SET {DBColumnName.STATUS.value} = ?, "
                    f"{DBColumnName.SERIES_NAME.value} = ?, {DBColumnName.EDEPOT_SIP_ID.value} = ?",
                    (sip.status.name, sip.series.get_full_name(), sip.edepot_sip_id or ""),
                )

            self._update_sip_creator_version(conn)

        self._execute_with_conn(sip.db_name, _persist)

    def save_data(self, sip: SIP) -> None:
        self._execute_with_conn(
            sip.db_name,
            lambda conn: sip.grid_data.data_as_df.to_sql(
                DBTableName.DATA.value, conn, if_exists="replace", index=False, dtype="text"
            ),
        )

    def read_sip_data(self, sip_db_file_name: str) -> pd.DataFrame:
        return self._execute_with_conn(
            sip_db_file_name,
            lambda conn: pd.read_sql(f"SELECT * FROM {DBTableName.DATA.value}", conn, dtype=str).fillna(""),
        )

    def _validate_db(self, sip_db_file_name: str) -> bool:
        def _validate(conn: sql.Connection) -> bool:
            db_tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            # Check for old format and transition if needed
            if DBTableName.DATA.value not in db_tables or DBTableName.SIP.value not in db_tables:
                if self.old_sip_db_controller.is_valid_db(sip_db_file_name):
                    return "needs_transition"

                return False

            columns = {
                column_name: data_type.lower()
                for _, column_name, data_type, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()
            }

            expected_columns = {
                "status": "text",
                "environment_name": "text",
                "series_name": "text",
                "edepot_sip_id": "text",
                "dossiers_list": "text",
                "tag_mapping": "text",
                "folder_mapping": "text",
            }

            for column, data_type in expected_columns.items():
                if column not in columns:
                    return False

                if data_type != columns[column]:
                    return False

            return True

        result = self._execute_with_conn(sip_db_file_name, _validate)

        if result == "needs_transition":
            self.transition_old_db(sip_db_file_name)
            return self._validate_db(sip_db_file_name)

        return result

    def transition_old_db(self, old_db_file_name: str) -> str | None:
        sip, series_id, series_name = self.old_sip_db_controller.read_sip_db(old_db_file_name)

        old_db_path = os.path.join(self.db_location, old_db_file_name)
        renamed_old_path = os.path.join(self.db_location, f"old_{old_db_file_name}")
        os.rename(old_db_path, renamed_old_path)

        new_db_path = os.path.join(self.db_location, sip.db_name)

        if os.path.exists(new_db_path):
            return None

        self.create_sip_db(sip=sip, series_id=series_id, series_name=series_name, transformed=UNKNOWN_TRANSFORMED)

        return sip.db_name


class OldDigitalSIPDBController(BaseObject):
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
        },
    }

    def conn(self, sip_db_file_name: str) -> sql.Connection:
        return sql.connect(os.path.join(self.application.configuration.sip_db_location, sip_db_file_name))

    def _execute_with_conn(self, sip_db_file_name: str, func):
        conn = self.conn(sip_db_file_name)

        try:
            result = func(conn)
            conn.commit()

            return result
        except Exception:
            conn.rollback()

            raise
        finally:
            conn.close()

    def is_valid_db(self, sip_db_file_name: str) -> bool:
        if not os.path.exists(os.path.join(self.application.configuration.sip_db_location, sip_db_file_name)):
            return False

        if not sip_db_file_name.endswith(DB_FILE_EXTENSION):
            return False

        try:
            conn = self.conn(sip_db_file_name)
            conn.close()
        except Exception:
            return False

        def _validate(conn: sql.Connection) -> bool:
            db_tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            if "data" not in db_tables:
                return False

            for table in db_tables:
                if table not in self.TABLES:
                    if table == "data":
                        continue

                    return False

                columns = {
                    name: col_type for _, name, col_type, *_ in conn.execute(f"PRAGMA table_info({table});").fetchall()
                }

                for column, data_type in self.TABLES[table].items():
                    if column not in columns:
                        return False

                    if data_type != columns[column].upper():
                        return False

            return True

        return self._execute_with_conn(sip_db_file_name, _validate)

    def read_sip_db(self, sip_db_file_name: str) -> tuple[SIP, str, str]:
        def _read(conn: sql.Connection) -> tuple[SIP, str, str]:
            sip_table_results = conn.execute("select * from SIP").fetchone()

            environment_name, sip_status_label, series_json, _, tag_mapping, folder_mapping, edepot_sip_id = (
                sip_table_results
            )

            sip = DigitalSIP()
            sip.force_set_name(os.path.splitext(sip_db_file_name)[0])
            sip.environment = self.application.configuration.get_environment(environment_name)
            sip.set_status(SIPStatus[sip_status_label])

            sip.tag_mapping = _parse_tag_mapping(tag_mapping)
            sip.folder_mapping = json.loads(folder_mapping)
            sip.edepot_sip_id = edepot_sip_id

            dossier_table_results = conn.execute("select * from dossier").fetchall()

            sip.set_dossiers([DossierWidget(path=path) for _, path in dossier_table_results])

            sip.grid_data.data_as_df = pd.read_sql("select * from data", conn, dtype=str).fillna("")

            return (
                sip,
                json.loads(series_json)[APIResponseKey.ID.value],
                json.loads(series_json)[APIResponseKey.CONTENT.value][APIResponseKey.NAME.value],
            )

        return self._execute_with_conn(sip_db_file_name, _read)
