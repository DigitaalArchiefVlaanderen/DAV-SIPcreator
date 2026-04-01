import os
import sqlite3 as sql

from natsort import natsorted

from src.utils.base_object import BaseObject
from src.utils.constants import (
    MAIN_DB_NAME,
    OLD_MAIN_DB_NAME,
    SIP_CREATOR_VERSION,
    UNKNOWN_TRANSFORMED,
    DBColumnName,
    DBTableName,
)


class MainDBController(BaseObject):
    TABLES = dict(dossier=DBTableName.DOSSIER.value)

    def __init__(self):
        super().__init__()

        self._migrate_old_db_name()
        self.create_dossier_table()
        self.create_sip_creator_table()
        self.initialize_version_info()

    def _migrate_old_db_name(self) -> None:
        root_path = self.application.configuration.root_path
        old_path = os.path.join(root_path, OLD_MAIN_DB_NAME)
        new_path = os.path.join(root_path, MAIN_DB_NAME)

        if os.path.exists(old_path) and not os.path.exists(new_path):
            os.rename(old_path, new_path)

    @property
    def conn(self) -> sql.Connection:
        root_path = self.application.configuration.root_path

        return sql.connect(os.path.join(root_path, MAIN_DB_NAME))

    def _execute_with_conn(self, func):
        conn = self.conn

        try:
            result = func(conn)
            conn.commit()

            return result
        except Exception:
            conn.rollback()

            raise
        finally:
            conn.close()

    def create_dossier_table(self) -> None:
        self._execute_with_conn(
            lambda conn: conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLES["dossier"]} (
                    path text PRIMARY KEY
                )
            """
            )
        )

    def create_sip_creator_table(self) -> None:
        self._execute_with_conn(
            lambda conn: conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {DBTableName.SIP_CREATOR.value} (
                    {DBColumnName.VERSION.value} text,
                    {DBColumnName.TRANSFORMED.value} text,
                    {DBColumnName.LAST_OPENED.value} text
                )
            """
            )
        )

    def initialize_version_info(self) -> None:
        def _initialize(conn: sql.Connection) -> None:
            row = conn.execute(
                f"SELECT {DBColumnName.VERSION.value}, {DBColumnName.TRANSFORMED.value} "
                f"FROM {DBTableName.SIP_CREATOR.value}"
            ).fetchone()

            if row is None:
                conn.execute(
                    f"INSERT INTO {DBTableName.SIP_CREATOR.value} "
                    f"({DBColumnName.VERSION.value}, {DBColumnName.TRANSFORMED.value}, {DBColumnName.LAST_OPENED.value}) "
                    f"VALUES (?, ?, ?)",
                    (SIP_CREATOR_VERSION, "", SIP_CREATOR_VERSION),
                )
                return

            db_version, transformed = row

            if db_version and self._is_version_older(db_version, SIP_CREATOR_VERSION):
                if transformed in ("unknown", UNKNOWN_TRANSFORMED):
                    transformed = db_version

                conn.execute(
                    f"UPDATE {DBTableName.SIP_CREATOR.value} SET "
                    f"{DBColumnName.VERSION.value} = ?, {DBColumnName.TRANSFORMED.value} = ?, "
                    f"{DBColumnName.LAST_OPENED.value} = ?",
                    (SIP_CREATOR_VERSION, transformed, SIP_CREATOR_VERSION),
                )
            else:
                conn.execute(
                    f"UPDATE {DBTableName.SIP_CREATOR.value} SET {DBColumnName.LAST_OPENED.value} = ?",
                    (SIP_CREATOR_VERSION,),
                )

        self._execute_with_conn(_initialize)

    @staticmethod
    def _is_version_older(version_a: str, version_b: str) -> bool:
        sorted_versions = natsorted([version_a, version_b])

        return sorted_versions[0] == version_a and version_a != version_b

    def write_dossier_paths(self, paths: list[str]) -> None:
        self._execute_with_conn(
            lambda conn: conn.executemany(
                f"""
                INSERT INTO {self.TABLES["dossier"]}(path)
                VALUES(?)
            """,
                [(os.path.normpath(p),) for p in paths],
            )
        )

    def read_dossier_paths(self) -> list[str]:
        def _read(conn: sql.Connection) -> list[str]:
            result = conn.execute(f"SELECT * FROM {self.TABLES['dossier']};").fetchall()

            return [r for r, *_ in result]

        return self._execute_with_conn(_read)

    def delete_dossier_paths(self, paths: list[str]) -> None:
        self._execute_with_conn(
            lambda conn: conn.executemany(
                f"""
                DELETE FROM {self.TABLES["dossier"]}
                WHERE path = ?
            """,
                [(os.path.normpath(p),) for p in paths],
            )
        )
