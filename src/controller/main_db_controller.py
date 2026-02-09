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

    def create_dossier_table(self) -> None:
        with self.conn as conn:
            conn.execute(
                f"""
                    CREATE TABLE IF NOT EXISTS {self.TABLES["dossier"]} (
                        path text PRIMARY KEY
                    )
                """
            )

    def write_dossier_paths(self, paths: list[str]) -> None:
        with self.conn as conn:
            conn.executemany(
                f"""
                    INSERT INTO {self.TABLES["dossier"]}(path)
                    VALUES(?)
                """,
                [(p,) for p in paths]
            )

    def read_dossier_paths(self) -> list[str]:
        with self.conn as conn:
            result = conn.execute(f"SELECT * FROM {self.TABLES["dossier"]};").fetchall()

            return [r for r, *_ in result]

    def delete_dossier_paths(self, paths: list[str]) -> None:
        with self.conn as conn:
            conn.executemany(
                f"""
                    DELETE FROM {self.TABLES["dossier"]}
                    WHERE path = ?
                """,
                [(p,) for p in paths]
            )
