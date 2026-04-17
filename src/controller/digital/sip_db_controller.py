import json
import os
import sqlite3 as sql

import pandas as pd

from src.controller.base_sip_db_controller import BaseSIPDBController
from src.controller.digital.db_versioning import run_db_migrations

from src.utils.constants import (
    UI_TEXT_ELEMENTS,
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
                CREATE TABLE {DBTableName.SIP} (
                    {DBColumnName.NAME} text,
                    {DBColumnName.STATUS} text,
                    {DBColumnName.ENVIRONMENT_NAME} text,
                    {DBColumnName.SERIES_ID} text,
                    {DBColumnName.SERIES_NAME} text,
                    {DBColumnName.EDEPOT_SIP_ID} text,
                    {DBColumnName.DOSSIERS_LIST} text,
                    {DBColumnName.TAG_MAPPING} text,
                    {DBColumnName.FOLDER_MAPPING} text,
                    {DBColumnName.GRID_VALID} integer default 0
                )
            """)
            conn.execute(
                f"""
                INSERT INTO {DBTableName.SIP}
                ({DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME},
                 {DBColumnName.SERIES_ID}, {DBColumnName.SERIES_NAME}, {DBColumnName.EDEPOT_SIP_ID},
                 {DBColumnName.DOSSIERS_LIST}, {DBColumnName.TAG_MAPPING}, {DBColumnName.FOLDER_MAPPING},
                 {DBColumnName.GRID_VALID})
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

            sip.grid_data.data_as_df.to_sql(DBTableName.DATA, conn, index=False, dtype="text")

        self._execute_with_conn(sip.db_name, _create)

    def read_sip_db(self, sip_db_file_name: str) -> tuple[SIP, str, str]:
        """
        Reads a sip from its db.
        Note however that this does not read the data, since we only get that on demand.
        """

        def _read(conn: sql.Connection) -> tuple[SIP, str, str]:
            columns = [col_name for _, col_name, *_ in conn.execute(f"PRAGMA table_info({DBTableName.SIP});").fetchall()]
            has_grid_valid = DBColumnName.GRID_VALID in columns

            result = conn.execute(
                f"SELECT {DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME}, "
                f"{DBColumnName.SERIES_ID}, {DBColumnName.SERIES_NAME}, {DBColumnName.EDEPOT_SIP_ID}, "
                f"{DBColumnName.DOSSIERS_LIST}, {DBColumnName.TAG_MAPPING}, {DBColumnName.FOLDER_MAPPING}"
                + (f", {DBColumnName.GRID_VALID}" if has_grid_valid else "")
                + f" FROM {DBTableName.SIP};"
            ).fetchone()

            (
                name,
                status,
                environment_name,
                series_id,
                series_name,
                edepot_sip_id,
                dossiers_list,
                tag_mapping,
                folder_mapping,
            ) = result[:9]
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
            columns = [col_name for _, col_name, *_ in conn.execute(f"PRAGMA table_info({DBTableName.SIP});").fetchall()]

            if DBColumnName.GRID_VALID in columns:
                conn.execute(
                    f"UPDATE {DBTableName.SIP} SET {DBColumnName.STATUS} = ?, "
                    f"{DBColumnName.SERIES_NAME} = ?, {DBColumnName.EDEPOT_SIP_ID} = ?, "
                    f"{DBColumnName.GRID_VALID} = ?",
                    (sip.status.name, sip.series.get_full_name(), sip.edepot_sip_id or "", int(sip.grid_valid)),
                )
            else:
                conn.execute(
                    f"UPDATE {DBTableName.SIP} SET {DBColumnName.STATUS} = ?, "
                    f"{DBColumnName.SERIES_NAME} = ?, {DBColumnName.EDEPOT_SIP_ID} = ?",
                    (sip.status.name, sip.series.get_full_name(), sip.edepot_sip_id or ""),
                )

            self._update_sip_creator_version(conn)

        self._execute_with_conn(sip.db_name, _persist)

    def save_data(self, sip: SIP) -> None:
        self._execute_with_conn(
            sip.db_name,
            lambda conn: sip.grid_data.data_as_df.to_sql(
                DBTableName.DATA, conn, if_exists="replace", index=False, dtype="text"
            ),
        )

    def read_sip_data(self, sip_db_file_name: str) -> pd.DataFrame:
        return self._execute_with_conn(
            sip_db_file_name,
            lambda conn: pd.read_sql(f"SELECT * FROM {DBTableName.DATA}", conn).fillna("").astype(str),
        )

    def _validate_db(self, sip_db_file_name: str) -> bool:
        def _validate(conn: sql.Connection) -> bool:
            db_path = os.path.join(self.db_location, sip_db_file_name)
            run_db_migrations(conn, db_path)

            # Ensure the SIP name is set (migration creates it empty)
            name_row = conn.execute(f"SELECT {DBColumnName.NAME} FROM {DBTableName.SIP}").fetchone()
            if name_row and not name_row[0]:
                sip_name = os.path.splitext(sip_db_file_name)[0]
                conn.execute(f"UPDATE {DBTableName.SIP} SET {DBColumnName.NAME} = ?", (sip_name,))

            db_tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            if DBTableName.DATA not in db_tables or DBTableName.SIP not in db_tables:
                return False

            columns = {
                column_name: data_type.lower()
                for _, column_name, data_type, *_ in conn.execute(f"PRAGMA table_info({DBTableName.SIP});").fetchall()
            }

            expected_columns = {
                DBColumnName.STATUS: "text",
                DBColumnName.ENVIRONMENT_NAME: "text",
                DBColumnName.SERIES_NAME: "text",
                DBColumnName.EDEPOT_SIP_ID: "text",
                DBColumnName.DOSSIERS_LIST: "text",
                DBColumnName.TAG_MAPPING: "text",
                DBColumnName.FOLDER_MAPPING: "text",
            }

            for column, data_type in expected_columns.items():
                if column not in columns:
                    return False

                if data_type != columns[column]:
                    return False

            return True

        return self._execute_with_conn(sip_db_file_name, _validate)
