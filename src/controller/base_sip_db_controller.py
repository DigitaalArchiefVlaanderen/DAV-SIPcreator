import os
import sqlite3 as sql
from collections.abc import Iterator

from src.utils.base_object import BaseObject
from src.utils.constants import DB_FILE_EXTENSION, SIP_CREATOR_VERSION, UI_TEXT_ELEMENTS, DBColumnName, DBTableName
from src.utils.data_objects.sip import SIP


class BaseSIPDBController(BaseObject):
    """
    Base class for SIP database controllers.

    Subclasses must set SIP_TYPE and implement db_location.
    """

    SIP_TYPE: type[SIP]

    def __init__(self) -> None:
        super().__init__()

    @property
    def db_location(self) -> str:
        raise NotImplementedError

    def conn(self, db_file_name: str) -> sql.Connection:
        return sql.connect(os.path.join(self.db_location, db_file_name))

    def _execute_with_conn(self, db_file_name: str, func):
        conn = self.conn(db_file_name)

        try:
            result = func(conn)
            conn.commit()

            return result
        except Exception:
            conn.rollback()

            raise
        finally:
            conn.close()

    def db_exists(self, db_file_name: str) -> bool:
        return os.path.exists(os.path.join(self.db_location, db_file_name))

    def _can_connect(self, db_file_name: str) -> bool:
        if not self.db_exists(db_file_name):
            return False

        if not db_file_name.endswith(DB_FILE_EXTENSION):
            return False

        try:
            conn = self.conn(db_file_name)
            conn.close()
        except Exception:
            return False

        return True

    def persist_all_sips(self) -> None:
        sips_by_env = self.application.sips.get(self.SIP_TYPE, {})

        for sips in sips_by_env.values():
            for sip in sips:
                self.persist_sip(sip)

    def persist_sip(self, sip: SIP) -> None:
        raise NotImplementedError

    def get_db_version_info(self, db_file_name: str) -> tuple[str, str] | None:
        def _read(conn: sql.Connection) -> tuple[str, str] | None:
            db_tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            if DBTableName.SIP_CREATOR not in db_tables:
                return None

            columns = [
                col_name
                for _, col_name, *_ in conn.execute(f"PRAGMA table_info({DBTableName.SIP_CREATOR});").fetchall()
            ]

            row = conn.execute(f"SELECT * FROM {DBTableName.SIP_CREATOR}").fetchone()

            if row is None:
                return None

            version = row[0] if DBColumnName.VERSION in columns else ""
            transformed = row[columns.index(DBColumnName.TRANSFORMED)] if DBColumnName.TRANSFORMED in columns else ""

            return version, transformed

        try:
            return self._execute_with_conn(db_file_name, _read)
        except Exception:
            return None

    def _create_sip_creator_table(self, conn: sql.Connection, transformed: str = "") -> None:
        conn.execute(f"""
            CREATE TABLE {DBTableName.SIP_CREATOR} (
                {DBColumnName.VERSION} text,
                {DBColumnName.TRANSFORMED} text,
                {DBColumnName.LAST_OPENED} text
            )
        """)
        conn.execute(
            f"INSERT INTO {DBTableName.SIP_CREATOR} "
            f"({DBColumnName.VERSION}, {DBColumnName.TRANSFORMED}, {DBColumnName.LAST_OPENED}) "
            f"VALUES (?, ?, ?)",
            (SIP_CREATOR_VERSION, transformed, SIP_CREATOR_VERSION),
        )

    def _update_sip_creator_version(self, conn: sql.Connection) -> None:
        conn.execute(
            f"UPDATE {DBTableName.SIP_CREATOR} SET {DBColumnName.LAST_OPENED} = ?",
            (SIP_CREATOR_VERSION,),
        )

    def _warn_invalid_db(self, db_file_name: str) -> None:
        self.application.notify_user_signal.emit(
            UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["title"],
            UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["text"].format(
                db_path=os.path.join(self.db_location, db_file_name)
            ),
        )

    def is_valid_db(self, db_file_name: str) -> bool:
        if not self._can_connect(db_file_name):
            return False

        result = self._validate_db(db_file_name)

        if not result:
            self._warn_invalid_db(db_file_name)

        return result

    def _validate_db(self, db_file_name: str) -> bool:
        raise NotImplementedError

    def read_sip_db(self, db_file_name: str):
        raise NotImplementedError

    def g_read_all_sip_dbs(self) -> Iterator:
        if not os.path.exists(self.db_location):
            return

        for file in os.listdir(self.db_location):
            if file.startswith("old_") or ".original" in file:
                continue

            if not self.is_valid_db(file):
                continue

            yield self.read_sip_db(file)

    def _warn_db_already_exists(self, db_path: str) -> None:
        self.application.notify_user_signal.emit(
            UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["title"],
            UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["text"].format(db_path=db_path),
        )
