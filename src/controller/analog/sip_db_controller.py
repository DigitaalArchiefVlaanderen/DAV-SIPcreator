import json
import os
import sqlite3 as sql

import pandas as pd

from src.controller.base_sip_db_controller import BaseSIPDBController

from src.utils.constants import (
    PROD_ENVIRONMENT_NAME,
    TI_ENVIRONMENT_NAME,
    UNKNOWN_TRANSFORMED,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.analog.sip import AnalogSIP
from src.utils.data_objects.sip_status import SIPStatus


class AnalogSIPDBController(BaseSIPDBController):
    SIP_TYPE = AnalogSIP

    def __init__(self) -> None:
        super().__init__()

    @property
    def db_location(self) -> str:
        return self.application.configuration.analoog_location

    def create_sip_db(
        self, sip: AnalogSIP, columns: list[str], series_id: str, series_name: str, transformed: str = ""
    ) -> bool:
        db_path = os.path.join(self.db_location, sip.db_name)

        if os.path.exists(db_path):
            self._warn_db_already_exists(db_path)
            return False

        def _create(conn: sql.Connection) -> None:
            conn.execute(f"""
                CREATE TABLE {DBTableName.SIP} (
                    {DBColumnName.NAME} text,
                    {DBColumnName.STATUS} text,
                    {DBColumnName.ENVIRONMENT_NAME} text,
                    {DBColumnName.SERIES_ID} text,
                    {DBColumnName.SERIES_NAME} text,
                    {DBColumnName.EDEPOT_SIP_ID} text,
                    {DBColumnName.UPLOADED} integer default 0,
                    {DBColumnName.GRID_VALID} integer default 0
                )
            """)
            conn.execute(
                f"""
                INSERT INTO {DBTableName.SIP}
                ({DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME},
                 {DBColumnName.SERIES_ID}, {DBColumnName.SERIES_NAME},
                 {DBColumnName.EDEPOT_SIP_ID}, {DBColumnName.UPLOADED}, {DBColumnName.GRID_VALID})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    sip.name,
                    sip.status.name,
                    sip.environment.name,
                    series_id,
                    series_name,
                    sip.edepot_sip_id or "",
                    int(sip.uploaded),
                    int(sip.grid_valid),
                ),
            )

            self._create_sip_creator_table(conn, transformed)

            df = pd.DataFrame(columns=columns)
            df.loc[0] = [""] * len(columns)
            df.to_sql(DBTableName.DATA, conn, index=False, dtype="text")

        self._execute_with_conn(sip.db_name, _create)

        return True

    def read_sip_db(self, db_file_name: str) -> tuple[AnalogSIP, str, str]:
        def _read(conn: sql.Connection) -> tuple[AnalogSIP, str, str]:
            result = conn.execute(
                f"SELECT {DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME}, "
                f"{DBColumnName.SERIES_ID}, {DBColumnName.SERIES_NAME}, "
                f"{DBColumnName.EDEPOT_SIP_ID}, {DBColumnName.UPLOADED} "
                f"FROM {DBTableName.SIP};"
            ).fetchone()

            columns = [col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()]
            has_grid_valid = DBColumnName.GRID_VALID in columns

            result = conn.execute(
                f"SELECT {DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME}, "
                f"{DBColumnName.SERIES_ID}, {DBColumnName.SERIES_NAME}, "
                f"{DBColumnName.EDEPOT_SIP_ID}, {DBColumnName.UPLOADED}"
                + (f", {DBColumnName.GRID_VALID}" if has_grid_valid else "")
                + f" FROM {DBTableName.SIP};"
            ).fetchone()

            name, status, environment_name, series_id, series_name, edepot_sip_id, uploaded = result[:7]
            grid_valid = bool(result[7]) if has_grid_valid else False

            sip = AnalogSIP()
            sip.force_set_name(name)
            sip.set_status(SIPStatus[status])
            sip.environment = self.application.configuration.get_environment(environment_name)
            sip.saved_series_name = series_name
            sip.uploaded = bool(uploaded)
            sip.set_grid_valid(grid_valid)

            if edepot_sip_id:
                sip.edepot_sip_id = edepot_sip_id

            return sip, series_id, series_name

        return self._execute_with_conn(db_file_name, _read)

    def read_data(self, db_file_name: str) -> pd.DataFrame:
        return self._execute_with_conn(
            db_file_name,
            lambda conn: pd.read_sql(f"SELECT * FROM {DBTableName.DATA}", conn, dtype=str).fillna(""),
        )

    def save_data(self, sip: AnalogSIP, df: pd.DataFrame) -> None:
        self._execute_with_conn(
            sip.db_name,
            lambda conn: df.to_sql(DBTableName.DATA, conn, if_exists="replace", index=False, dtype="text"),
        )

    def persist_sip(self, sip: AnalogSIP) -> None:
        if not self.db_exists(sip.db_name):
            return

        def _persist(conn: sql.Connection) -> None:
            series_name = sip.series.get_full_name() if sip.series else (sip.saved_series_name or "")
            columns = [col_name for _, col_name, *_ in conn.execute("PRAGMA table_info(sip);").fetchall()]

            if DBColumnName.GRID_VALID in columns:
                conn.execute(
                    f"UPDATE {DBTableName.SIP} SET {DBColumnName.STATUS} = ?, "
                    f"{DBColumnName.SERIES_NAME} = ?, {DBColumnName.EDEPOT_SIP_ID} = ?, "
                    f"{DBColumnName.UPLOADED} = ?, {DBColumnName.GRID_VALID} = ?",
                    (sip.status.name, series_name, sip.edepot_sip_id or "", int(sip.uploaded), int(sip.grid_valid)),
                )
            else:
                conn.execute(
                    f"UPDATE {DBTableName.SIP} SET {DBColumnName.STATUS} = ?, "
                    f"{DBColumnName.SERIES_NAME} = ?, {DBColumnName.EDEPOT_SIP_ID} = ?, "
                    f"{DBColumnName.UPLOADED} = ?",
                    (sip.status.name, series_name, sip.edepot_sip_id or "", int(sip.uploaded)),
                )

            self._update_sip_creator_version(conn)

        self._execute_with_conn(sip.db_name, _persist)

    def _validate_db(self, db_file_name: str) -> bool:
        def _validate(conn: sql.Connection) -> bool | str:
            tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            if "extra" in tables:
                return "needs_transition"

            return (
                DBTableName.SIP in tables
                and DBTableName.DATA in tables
                and DBTableName.SIP_CREATOR in tables
            )

        result = self._execute_with_conn(db_file_name, _validate)

        if result == "needs_transition":
            return self._transition_old_analog_db(db_file_name)

        return result

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

        location = self.db_location
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
