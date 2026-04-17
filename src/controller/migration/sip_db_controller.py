import os
import sqlite3 as sql

import pandas as pd

from src.controller.base_sip_db_controller import BaseSIPDBController
from src.controller.migration.db_versioning import run_db_migrations

from src.utils.constants import (
    UI_TEXT_ELEMENTS,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus


class MigrationSIPDBController(BaseSIPDBController):
    SIP_TYPE = MigrationSIP

    def __init__(self) -> None:
        super().__init__()

    @property
    def db_location(self) -> str:
        return self.application.configuration.overdrachtslijsten_location

    def create_sip_db(self, sip: MigrationSIP, transformed: str = "") -> None:
        db_path = os.path.join(self.db_location, sip.db_name)

        if os.path.exists(db_path):
            self._warn_db_already_exists(db_path)
            return

        if not sip.main_grid_data.has_data:
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
                    {DBColumnName.GRID_VALID} integer default 0
                )
            """)
            conn.execute(
                f"""
                INSERT INTO {DBTableName.SIP}
                ({DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME},
                 {DBColumnName.GRID_VALID})
                VALUES (?, ?, ?, ?)
            """,
                (
                    sip.name,
                    sip.status.name,
                    sip.environment.name,
                    int(sip.grid_valid),
                ),
            )

            self._create_sip_creator_table(conn, transformed)

            sip.main_grid_data.data_as_df.to_sql(DBTableName.OVERDRACHTSLIJST, conn, index=False, dtype="text")

            conn.execute(f"""
                CREATE TABLE {DBTableName.TABLES} (
                    {DBColumnName.TABLE_NAME} text,
                    "{DBColumnName.URI_SERIEREGISTER}" text,
                    {DBColumnName.EDEPOT_ID} text,
                    {DBColumnName.STATUS} text default '{SIPStatus.IN_PROGRESS.name}',
                    UNIQUE({DBColumnName.TABLE_NAME})
                )
            """)

        self._execute_with_conn(sip.db_name, _create)

    def read_sip_db(self, sip_db_file_name: str) -> MigrationSIP:
        def _read(conn: sql.Connection) -> MigrationSIP:
            columns = [col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()]
            has_grid_valid = DBColumnName.GRID_VALID in columns

            result = conn.execute(
                f"SELECT {DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME}"
                + (f", {DBColumnName.GRID_VALID}" if has_grid_valid else "")
                + f" FROM {DBTableName.SIP};"
            ).fetchone()

            name, status, environment_name = result[:3]
            grid_valid = bool(result[3]) if has_grid_valid else False

            sip = MigrationSIP()
            sip.force_set_name(name)
            sip.set_status(SIPStatus[status])
            sip.environment = self.application.configuration.get_environment(environment_name)
            sip.set_grid_valid(grid_valid)

            return sip

        return self._execute_with_conn(sip_db_file_name, _read)

    def read_main_data(self, sip_db_file_name: str) -> pd.DataFrame:
        return self._execute_with_conn(
            sip_db_file_name,
            lambda conn: pd.read_sql(f"SELECT * FROM {DBTableName.OVERDRACHTSLIJST}", conn, dtype=str).fillna(""),
        )

    def read_tables(self, sip_db_file_name: str) -> list[tuple[str, str, str, str]]:
        return self._execute_with_conn(
            sip_db_file_name,
            lambda conn: conn.execute(
                f'SELECT {DBColumnName.TABLE_NAME}, "{DBColumnName.URI_SERIEREGISTER}", '
                f"{DBColumnName.EDEPOT_ID}, {DBColumnName.STATUS} "
                f"FROM {DBTableName.TABLES}"
            ).fetchall(),
        )

    def read_series_data(self, sip_db_file_name: str, table_name: str) -> pd.DataFrame:
        return self._execute_with_conn(
            sip_db_file_name, lambda conn: pd.read_sql(f"SELECT * FROM [{table_name}]", conn, dtype=str).fillna("")
        )

    def create_series_table(self, sip: MigrationSIP, uri_serieregister: str, table_name: str, df: pd.DataFrame) -> None:
        def _create(conn: sql.Connection) -> None:
            conn.execute(
                f"INSERT INTO {DBTableName.TABLES} ({DBColumnName.TABLE_NAME}, "
                f'"{DBColumnName.URI_SERIEREGISTER}", {DBColumnName.EDEPOT_ID}, '
                f"{DBColumnName.STATUS}) VALUES (?, ?, ?, ?)",
                (table_name, uri_serieregister, "", SIPStatus.IN_PROGRESS.name),
            )

            df.to_sql(table_name, conn, index=False, dtype="text")

        self._execute_with_conn(sip.db_name, _create)

    def update_series_status(self, sip: MigrationSIP, table_name: str, status: SIPStatus, edepot_id: str = "") -> None:
        def _update(conn: sql.Connection) -> None:
            conn.execute(
                f"UPDATE {DBTableName.TABLES} SET {DBColumnName.STATUS} = ?, "
                f"{DBColumnName.EDEPOT_ID} = ? WHERE {DBColumnName.TABLE_NAME} = ?",
                (status.name, edepot_id, table_name),
            )

        self._execute_with_conn(sip.db_name, _update)

    def read_series_statuses(self, sip_db_file_name: str) -> dict[str, tuple[str, str]]:
        def _read(conn: sql.Connection) -> dict[str, tuple[str, str]]:
            rows = conn.execute(
                f"SELECT {DBColumnName.TABLE_NAME}, {DBColumnName.STATUS}, "
                f"{DBColumnName.EDEPOT_ID} FROM {DBTableName.TABLES}"
            ).fetchall()

            return {name: (status, edepot_id) for name, status, edepot_id in rows}

        return self._execute_with_conn(sip_db_file_name, _read)

    def save_series_data(self, sip: MigrationSIP, table_name: str, df: pd.DataFrame) -> None:
        self._execute_with_conn(
            sip.db_name, lambda conn: df.to_sql(table_name, conn, if_exists="replace", index=False, dtype="text")
        )

    def delete_series_table(self, sip: MigrationSIP, table_name: str) -> None:
        def _delete(conn: sql.Connection) -> None:
            conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
            conn.execute(
                f"DELETE FROM {DBTableName.TABLES} WHERE {DBColumnName.TABLE_NAME} = ?",
                (table_name,),
            )

        self._execute_with_conn(sip.db_name, _delete)

    def save_main_data(self, sip: MigrationSIP, df: pd.DataFrame) -> None:
        self._execute_with_conn(
            sip.db_name,
            lambda conn: df.to_sql(DBTableName.OVERDRACHTSLIJST, conn, if_exists="replace", index=False, dtype="text"),
        )

    def add_columns_to_series_table(
        self, sip: MigrationSIP, table_name: str, columns: list[str], after_column: str
    ) -> None:
        def _add_columns(conn: sql.Connection) -> None:
            df = pd.read_sql(f"SELECT * FROM [{table_name}]", conn, dtype=str).fillna("")

            col_loc = df.columns.get_loc(after_column)

            for i, col in enumerate(columns):
                df.insert(col_loc + 1 + i, col, "")

            conn.execute(f"DROP TABLE [{table_name}]")

            df.to_sql(table_name, conn, index=False, dtype="text")

        self._execute_with_conn(sip.db_name, _add_columns)

    def persist_sip(self, sip: MigrationSIP) -> None:
        if not self.db_exists(sip.db_name):
            return

        def _persist(conn: sql.Connection) -> None:
            columns = [col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()]

            if DBColumnName.GRID_VALID in columns:
                conn.execute(
                    f"UPDATE {DBTableName.SIP} SET {DBColumnName.STATUS} = ?, {DBColumnName.GRID_VALID} = ?",
                    (sip.status.name, int(sip.grid_valid)),
                )
            else:
                conn.execute(
                    f"UPDATE {DBTableName.SIP} SET {DBColumnName.STATUS} = ?",
                    (sip.status.name,),
                )

            self._update_sip_creator_version(conn)

            for series_name, series_status in sip.series_statuses.items():
                edepot_id = sip.series_edepot_ids.get(series_name, "")
                conn.execute(
                    f"UPDATE {DBTableName.TABLES} SET {DBColumnName.STATUS} = ?, "
                    f"{DBColumnName.EDEPOT_ID} = ? WHERE {DBColumnName.TABLE_NAME} = ?",
                    (series_status.name, edepot_id, series_name),
                )

        self._execute_with_conn(sip.db_name, _persist)

    def _validate_db(self, sip_db_file_name: str) -> bool:
        def _validate(conn: sql.Connection) -> bool:
            db_path = os.path.join(self.db_location, sip_db_file_name)

            # Run version-based migrations (handles pre-3.0 → 3.0 and future upgrades)
            run_db_migrations(conn, db_path)

            # Ensure the SIP name is set (migration creates it empty)
            name_row = conn.execute("SELECT name FROM sip").fetchone()
            if name_row and not name_row[0]:
                sip_name = os.path.splitext(sip_db_file_name)[0]
                conn.execute("UPDATE sip SET name = ?", (sip_name,))

            # Verify the DB has the expected current-format tables
            db_tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            has_current_format = (
                DBTableName.SIP in db_tables
                and DBTableName.OVERDRACHTSLIJST in db_tables
                and DBTableName.TABLES in db_tables
            )

            if not has_current_format:
                return False

            columns = {
                column_name: data_type.lower()
                for _, column_name, data_type, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()
            }

            expected_columns = {
                "name": "text",
                "status": "text",
                "environment_name": "text",
            }

            for column, data_type in expected_columns.items():
                if column not in columns:
                    return False

                if data_type != columns[column]:
                    return False

            return True

        return self._execute_with_conn(sip_db_file_name, _validate)
