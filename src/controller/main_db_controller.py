import sqlite3 as sql

from src.utils.base_object import BaseObject
from src.utils.constants import MAIN_DB_LOCATION


class MainDBController(BaseObject):
    TABLES = dict(
        dossier="dossier"
    )
    
    def __init__(self):
        super().__init__()

        self.create_dossier_table()

    @property
    def conn(self) -> sql.Connection:
        return sql.connect(MAIN_DB_LOCATION)

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
        self._execute_with_conn(lambda conn: conn.execute(
            f"""
                CREATE TABLE IF NOT EXISTS {self.TABLES["dossier"]} (
                    path text PRIMARY KEY
                )
            """
        ))

    def write_dossier_paths(self, paths: list[str]) -> None:
        self._execute_with_conn(lambda conn: conn.executemany(
            f"""
                INSERT INTO {self.TABLES["dossier"]}(path)
                VALUES(?)
            """,
            [(p,) for p in paths]
        ))

    def read_dossier_paths(self) -> list[str]:
        def _read(conn: sql.Connection) -> list[str]:
            result = conn.execute(f'SELECT * FROM {self.TABLES["dossier"]};').fetchall()

            return [r for r, *_ in result]

        return self._execute_with_conn(_read)

    def delete_dossier_paths(self, paths: list[str]) -> None:
        self._execute_with_conn(lambda conn: conn.executemany(
            f"""
                DELETE FROM {self.TABLES["dossier"]}
                WHERE path = ?
            """,
            [(p,) for p in paths]
        ))
