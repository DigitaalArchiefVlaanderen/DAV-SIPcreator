import os
import sqlite3 as sql

import pandas as pd

from src.controller.base_sip_db_controller import BaseSIPDBController

from src.utils.base_object import BaseObject
from src.utils.constants import (
    MIGRATION_MAIN_ID_COLUMN,
    PROD_ENVIRONMENT_NAME,
    TI_ENVIRONMENT_NAME,
    UI_TEXT_ELEMENTS,
    UNKNOWN_TRANSFORMED,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus


class MigrationSIPDBController(BaseSIPDBController):
    SIP_TYPE = MigrationSIP

    def __init__(self) -> None:
        super().__init__()

        self.old_sip_db_controller = OldMigrationSIPDBController()

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
                f'{DBColumnName.EDEPOT_ID}, {DBColumnName.STATUS} '
                f'FROM {DBTableName.TABLES}'
            ).fetchall(),
        )

    def read_series_data(self, sip_db_file_name: str, table_name: str) -> pd.DataFrame:
        return self._execute_with_conn(
            sip_db_file_name, lambda conn: pd.read_sql(f"SELECT * FROM [{table_name}]", conn, dtype=str).fillna("")
        )

    def create_series_table(self, sip: MigrationSIP, uri_serieregister: str, table_name: str, df: pd.DataFrame) -> None:
        def _create(conn: sql.Connection) -> None:
            conn.execute(
                f'INSERT INTO {DBTableName.TABLES} ({DBColumnName.TABLE_NAME}, '
                f'"{DBColumnName.URI_SERIEREGISTER}", {DBColumnName.EDEPOT_ID}, '
                f'{DBColumnName.STATUS}) VALUES (?, ?, ?, ?)',
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
            lambda conn: df.to_sql(
                DBTableName.OVERDRACHTSLIJST, conn, if_exists="replace", index=False, dtype="text"
            ),
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
                    f"UPDATE {DBTableName.SIP} SET {DBColumnName.STATUS} = ?, "
                    f"{DBColumnName.GRID_VALID} = ?",
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
        def _validate(conn: sql.Connection) -> bool | str:
            db_tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            has_old_format = DBTableName.TABLES in db_tables and self.old_sip_db_controller.is_valid_db(
                sip_db_file_name
            )
            has_current_format = (
                DBTableName.SIP in db_tables
                and DBTableName.OVERDRACHTSLIJST in db_tables
                and DBTableName.TABLES in db_tables
            )
            has_intermediate_format = DBTableName.SIP in db_tables and "main_data" in db_tables

            if has_old_format and not has_current_format:
                return "needs_transition"

            if has_intermediate_format and not has_current_format:
                return "needs_intermediate_transition"

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

            self._migrate_tables_uploaded_to_status(conn)
            self._migrate_location_column_suffixes(conn)

            return True

        result = self._execute_with_conn(sip_db_file_name, _validate)

        if result == "needs_transition":
            self.transition_old_db(sip_db_file_name)

            return self._validate_db(sip_db_file_name)

        if result == "needs_intermediate_transition":
            self.transition_intermediate_db(sip_db_file_name)

            return self._validate_db(sip_db_file_name)

        return result

    def _needs_transformation(self, sip_db_file_name: str) -> bool:
        version_info = self.get_db_version_info(sip_db_file_name)

        if version_info is None:
            return False

        version, _ = version_info

        if not version:
            return False

        try:
            major_minor = float(version.split(".")[0] + "." + version.split(".")[1])

            return major_minor < 3.0
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _migrate_tables_uploaded_to_status(conn: sql.Connection) -> None:
        tables_columns = {col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(tables);").fetchall()}

        if "uploaded" in tables_columns and "status" not in tables_columns:
            conn.execute(f"ALTER TABLE tables ADD COLUMN status text default '{SIPStatus.IN_PROGRESS.name}'")

            conn.execute(f"""
                UPDATE tables SET status = CASE
                    WHEN uploaded = 1 THEN '{SIPStatus.UPLOADED.name}'
                    ELSE '{SIPStatus.IN_PROGRESS.name}'
                END
            """)

    @staticmethod
    def _migrate_location_column_suffixes(conn: sql.Connection) -> None:
        """Rename _N suffixed location columns to trailing-space convention in all tables."""
        from src.utils.grid.checks.migration.location_group_check import LOCATION_COLUMNS

        all_tables = [
            name for name, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        ]

        for table_name in all_tables:
            table_columns = [col_name for _, col_name, *_ in conn.execute(f"PRAGMA table_info([{table_name}]);")]
            renames = {}

            for col in table_columns:
                for base in LOCATION_COLUMNS:
                    if col.startswith(f"{base}_") and col[len(base) + 1 :].isdigit():
                        suffix_num = int(col[len(base) + 1 :])
                        new_name = base + " " * suffix_num
                        renames[col] = new_name
                        break

            if renames:
                df = pd.read_sql(f"SELECT * FROM [{table_name}]", conn, dtype=str).fillna("")
                df = df.rename(columns=renames)
                conn.execute(f"DROP TABLE [{table_name}]")
                df.to_sql(table_name, conn, index=False, dtype="text")

    def transition_old_db(self, old_db_file_name: str) -> str | None:
        sip, series_entries = self.old_sip_db_controller.read_sip_db(old_db_file_name)

        location = self.db_location
        old_db_path = os.path.join(location, old_db_file_name)
        renamed_old_path = os.path.join(location, f"old_{old_db_file_name}")

        os.rename(old_db_path, renamed_old_path)

        for suffix in ("-journal", "-wal", "-shm"):
            journal_path = old_db_path + suffix

            if os.path.exists(journal_path):
                os.rename(journal_path, renamed_old_path + suffix)

        new_db_path = os.path.join(location, sip.db_name)

        if os.path.exists(new_db_path):
            return None

        self.create_sip_db(sip=sip, transformed=UNKNOWN_TRANSFORMED)

        if series_entries:
            old_conn = sql.connect(renamed_old_path)

            try:
                for table_name, uri, _ in series_entries:
                    clean_name = table_name.strip('"')

                    if clean_name == DBTableName.OVERDRACHTSLIJST:
                        continue

                    try:
                        df = pd.read_sql(f"SELECT * FROM [{clean_name}]", old_conn, dtype=str).fillna("")
                    except Exception:
                        self.application.notify_user_signal.emit(
                            UI_TEXT_ELEMENTS["migration"]["migration_series_error"]["title"],
                            UI_TEXT_ELEMENTS["migration"]["migration_series_error"]["text"].format(
                                series_name=clean_name
                            ),
                        )
                        continue

                    if "id" in df.columns:
                        df = df.drop(columns=["id"])

                    if MIGRATION_MAIN_ID_COLUMN in df.columns:
                        df = df.drop(columns=[MIGRATION_MAIN_ID_COLUMN])

                    self.create_series_table(sip=sip, uri_serieregister=uri or "", table_name=clean_name, df=df)
            finally:
                old_conn.close()

        return sip.db_name

    def transition_intermediate_db(self, sip_db_file_name: str) -> None:
        def _transition(conn: sql.Connection) -> None:
            conn.execute("ALTER TABLE main_data RENAME TO Overdrachtslijst")

            has_series_tables = "series_tables" in [
                r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            ]

            if has_series_tables:
                rows = conn.execute("SELECT series_id, series_name, table_name FROM series_tables").fetchall()

                conn.execute("DROP TABLE series_tables")

                conn.execute(f"""
                    CREATE TABLE tables (
                        table_name text,
                        "URI Serieregister" text,
                        edepot_id text,
                        status text default '{SIPStatus.IN_PROGRESS.name}',
                        UNIQUE(table_name)
                    )
                """)

                for _, series_name, table_name in rows:
                    conn.execute(
                        'INSERT INTO tables (table_name, "URI Serieregister", edepot_id, status) VALUES (?, ?, ?, ?)',
                        (series_name, "", "", SIPStatus.IN_PROGRESS.name),
                    )

                    conn.execute(f"ALTER TABLE [{table_name}] RENAME TO [{series_name}]")
            else:
                conn.execute(f"""
                    CREATE TABLE tables (
                        table_name text,
                        "URI Serieregister" text,
                        edepot_id text,
                        status text default '{SIPStatus.IN_PROGRESS.name}',
                        UNIQUE(table_name)
                    )
                """)

            sip_columns = [col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()]

            if "file_location_path" in sip_columns:
                conn.execute("ALTER TABLE sip DROP COLUMN file_location_path")

        self._execute_with_conn(sip_db_file_name, _transition)


class OldMigrationSIPDBController(BaseObject):
    def __init__(self) -> None:
        super().__init__()

    def conn(self, sip_db_file_name: str) -> sql.Connection:
        return sql.connect(os.path.join(self.application.configuration.overdrachtslijsten_location, sip_db_file_name))

    def _execute_with_conn(self, sip_db_file_name: str, func):
        conn = self.conn(sip_db_file_name)

        try:
            result = func(conn)

            return result
        finally:
            conn.close()

    def is_valid_db(self, sip_db_file_name: str) -> bool:
        def _validate(conn: sql.Connection) -> bool:
            db_tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            if DBTableName.TABLES not in db_tables:
                return False

            columns = [
                col_name
                for _, col_name, *_ in conn.execute(f"PRAGMA table_info({DBTableName.TABLES});").fetchall()
            ]

            if DBColumnName.TABLE_NAME not in columns:
                return False

            if DBColumnName.URI_SERIEREGISTER not in columns:
                return False

            return True

        try:
            return self._execute_with_conn(sip_db_file_name, _validate)
        except Exception:
            return False

    def _infer_environment_name(self, conn: sql.Connection) -> str:
        uris = conn.execute(
            'SELECT "URI Serieregister" FROM tables WHERE "URI Serieregister" IS NOT NULL AND "URI Serieregister" != ""'
        ).fetchall()

        for uri, *_ in uris:
            if "-ti." in uri:
                return TI_ENVIRONMENT_NAME

        if uris:
            return PROD_ENVIRONMENT_NAME

        return self.application.configuration.active_environment.name

    def read_sip_db(self, sip_db_file_name: str) -> tuple[MigrationSIP, list[tuple[str, str, str]]]:
        def _read(conn: sql.Connection) -> tuple[MigrationSIP, list[tuple[str, str, str]]]:
            overdrachtslijst_name = os.path.splitext(sip_db_file_name)[0]

            environment_name = self._infer_environment_name(conn)

            main_table_name = None
            all_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()

            for table_name, *_ in all_tables:
                if table_name.lower() == "overdrachtslijst":
                    main_table_name = table_name

                    break

            sip = MigrationSIP()
            sip.force_set_name(overdrachtslijst_name)
            sip.environment = self.application.configuration.get_environment(environment_name)

            if main_table_name:
                main_df = pd.read_sql(f"SELECT * FROM [{main_table_name}]", conn, dtype=str).fillna("")

                if "id" in main_df.columns:
                    main_df = main_df.drop(columns=["id"])

                sip.main_grid_data = GridData()
                sip.main_grid_data.data_as_df = main_df
                sip.grid_data = sip.main_grid_data

            series_entries = conn.execute(
                'SELECT table_name, "URI Serieregister", edepot_id FROM tables WHERE table_name != ?',
                (f'"{main_table_name}"' if main_table_name else "",),
            ).fetchall()

            return sip, series_entries

        return self._execute_with_conn(sip_db_file_name, _read)
