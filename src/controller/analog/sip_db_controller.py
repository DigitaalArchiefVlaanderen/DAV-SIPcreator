import json
import os
from typing import Iterator

import pandas as pd
import sqlite3 as sql

from src.utils.base_object import BaseObject
from src.utils.constants import (
    SIP_CREATOR_VERSION, UNKNOWN_TRANSFORMED,
    DBTableName, DBColumnName, DB_FILE_EXTENSION,
    TI_ENVIRONMENT_NAME, PROD_ENVIRONMENT_NAME,
)
from src.utils.data_objects.analog.sip import AnalogSIP
from src.utils.data_objects.sip_status import SIPStatus


class AnalogSIPDBController(BaseObject):
    def __init__(self) -> None:
        super().__init__()

    def conn(self, db_file_name: str) -> sql.Connection:
        return sql.connect(
            os.path.join(
                self.application.configuration.analoog_location,
                db_file_name
            )
        )

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

    def create_sip_db(self, sip: AnalogSIP, columns: list[str], series_id: str, series_name: str, transformed: str = "") -> bool:
        db_path = os.path.join(self.application.configuration.analoog_location, sip.db_name)

        if os.path.exists(db_path):
            from src.utils.constants import UI_TEXT_ELEMENTS

            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["text"].format(db_apth=db_path),
            )

            return False

        def _create(conn: sql.Connection) -> None:
            conn.execute(f"""
                CREATE TABLE {DBTableName.SIP.value} (
                    {DBColumnName.NAME.value} text,
                    {DBColumnName.STATUS.value} text,
                    {DBColumnName.ENVIRONMENT_NAME.value} text,
                    {DBColumnName.SERIES_ID.value} text,
                    {DBColumnName.SERIES_NAME.value} text,
                    {DBColumnName.EDEPOT_SIP_ID.value} text,
                    {DBColumnName.UPLOADED.value} integer default 0
                )
            """)
            conn.execute(f"""
                INSERT INTO {DBTableName.SIP.value}
                ({DBColumnName.NAME.value}, {DBColumnName.STATUS.value}, {DBColumnName.ENVIRONMENT_NAME.value},
                 {DBColumnName.SERIES_ID.value}, {DBColumnName.SERIES_NAME.value},
                 {DBColumnName.EDEPOT_SIP_ID.value}, {DBColumnName.UPLOADED.value})
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sip.name,
                sip.status.name,
                sip.environment.name,
                series_id,
                series_name,
                sip.edepot_sip_id or "",
                int(sip.uploaded),
            ))

            conn.execute(f"""
                CREATE TABLE {DBTableName.SIP_CREATOR.value} (
                    {DBColumnName.VERSION.value} text,
                    {DBColumnName.TRANSFORMED.value} text,
                    {DBColumnName.LAST_OPENED.value} text
                )
            """)
            conn.execute(
                f"INSERT INTO {DBTableName.SIP_CREATOR.value} ({DBColumnName.VERSION.value}, {DBColumnName.TRANSFORMED.value}, {DBColumnName.LAST_OPENED.value}) VALUES (?, ?, ?)",
                (SIP_CREATOR_VERSION, transformed, SIP_CREATOR_VERSION)
            )

            df = pd.DataFrame(columns=columns)
            df.loc[0] = [""] * len(columns)
            df.to_sql(DBTableName.DATA.value, conn, index=False, dtype="text")

        self._execute_with_conn(sip.db_name, _create)

        return True

    def read_sip_db(self, db_file_name: str) -> tuple[AnalogSIP, str, str]:
        def _read(conn: sql.Connection) -> tuple[AnalogSIP, str, str]:
            result = conn.execute(
                f"SELECT {DBColumnName.NAME.value}, {DBColumnName.STATUS.value}, {DBColumnName.ENVIRONMENT_NAME.value}, "
                f"{DBColumnName.SERIES_ID.value}, {DBColumnName.SERIES_NAME.value}, "
                f"{DBColumnName.EDEPOT_SIP_ID.value}, {DBColumnName.UPLOADED.value} "
                f"FROM {DBTableName.SIP.value};"
            ).fetchone()
            name, status, environment_name, series_id, series_name, edepot_sip_id, uploaded = result

            sip = AnalogSIP()
            sip.force_set_name(name)
            sip.set_status(SIPStatus[status])
            sip.environment = self.application.configuration.get_environment(environment_name)
            sip.saved_series_name = series_name
            sip.uploaded = bool(uploaded)

            if edepot_sip_id:
                sip.edepot_sip_id = edepot_sip_id

            return sip, series_id, series_name

        return self._execute_with_conn(db_file_name, _read)

    def read_data(self, db_file_name: str) -> pd.DataFrame:
        return self._execute_with_conn(db_file_name, lambda conn:
            pd.read_sql(f"SELECT * FROM {DBTableName.DATA.value}", conn, dtype=str).fillna("")
        )

    def save_data(self, sip: AnalogSIP, df: pd.DataFrame) -> None:
        self._execute_with_conn(sip.db_name, lambda conn:
            df.to_sql(DBTableName.DATA.value, conn, if_exists="replace", index=False, dtype="text")
        )

    def persist_sip(self, sip: AnalogSIP) -> None:
        if not self.db_exists(sip.db_name):
            return

        def _persist(conn: sql.Connection) -> None:
            series_name = sip.series.get_full_name() if sip.series else (sip.saved_series_name or "")

            conn.execute(
                f"UPDATE {DBTableName.SIP.value} SET {DBColumnName.STATUS.value} = ?, "
                f"{DBColumnName.SERIES_NAME.value} = ?, {DBColumnName.EDEPOT_SIP_ID.value} = ?, "
                f"{DBColumnName.UPLOADED.value} = ?",
                (sip.status.name, series_name, sip.edepot_sip_id or "", int(sip.uploaded))
            )

            conn.execute(
                f"UPDATE {DBTableName.SIP_CREATOR.value} SET {DBColumnName.LAST_OPENED.value} = ?",
                (SIP_CREATOR_VERSION,)
            )

        self._execute_with_conn(sip.db_name, _persist)

    def persist_all_sips(self) -> None:
        sips_by_env = self.application.sips.get(AnalogSIP, {})

        for sips in sips_by_env.values():
            for sip in sips:
                self.persist_sip(sip)

    def g_read_all_sip_dbs(self) -> Iterator[tuple[AnalogSIP, str, str]]:
        location = self.application.configuration.analoog_location

        if not os.path.exists(location):
            return

        for file in os.listdir(location):
            if file.startswith("old_"):
                continue

            if not file.endswith(DB_FILE_EXTENSION):
                continue

            if not self.is_valid_db(file):
                continue

            yield self.read_sip_db(file)

    def db_exists(self, db_file_name: str) -> bool:
        return os.path.exists(
            os.path.join(self.application.configuration.analoog_location, db_file_name)
        )

    def is_valid_db(self, db_file_name: str) -> bool:
        if not self.db_exists(db_file_name):
            return False

        try:
            conn = self.conn(db_file_name)
            tables = [
                r for r, *_ in
                conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            ]
            conn.close()
        except Exception:
            return False

        if "extra" in tables:
            return self._transition_old_analog_db(db_file_name)

        return (
            DBTableName.SIP.value in tables
            and DBTableName.DATA.value in tables
            and DBTableName.SIP_CREATOR.value in tables
        )

    def _transition_old_analog_db(self, db_file_name: str) -> bool:
        try:
            conn = self.conn(db_file_name)
            series_json_str, edepot_id, data_changed = conn.execute("SELECT * FROM extra").fetchone()
            df = pd.read_sql("SELECT * FROM data", conn, dtype=str).fillna("")

            if "_id" in df.columns:
                df = df.drop(columns=["_id"])

            conn.close()
        except Exception:
            return False

        series_dict = json.loads(series_json_str)
        series_id = series_dict.get("_id", "")
        series_name = series_dict.get("name", "")

        environment_name = self._infer_environment_from_series(series_id)

        if environment_name is None:
            return False

        if edepot_id and not data_changed:
            status = SIPStatus.ACCEPTED
        elif edepot_id:
            status = SIPStatus.SIP_CREATED
        else:
            status = SIPStatus.IN_PROGRESS

        location = self.application.configuration.analoog_location
        old_path = os.path.join(location, db_file_name)
        renamed_path = os.path.join(location, f"old_{db_file_name}")
        os.rename(old_path, renamed_path)

        sip = AnalogSIP()
        sip.force_set_name(os.path.splitext(db_file_name)[0])
        sip.set_status(status)
        sip.environment = self.application.configuration.get_environment(environment_name)
        sip.uploaded = bool(edepot_id)

        if edepot_id:
            sip.edepot_sip_id = edepot_id

        columns = list(df.columns)

        self.create_sip_db(
            sip=sip,
            columns=columns,
            series_id=series_id,
            series_name=series_name,
            transformed=UNKNOWN_TRANSFORMED,
        )

        if not df.empty:
            self.save_data(sip, df)

        return True

    def _infer_environment_from_series(self, series_id: str) -> str | None:
        all_series = self.application.sneaky_series()

        for env_name in (TI_ENVIRONMENT_NAME, PROD_ENVIRONMENT_NAME):
            for series in all_series.get(env_name, []):
                if series._id == series_id:
                    return env_name

        return None
