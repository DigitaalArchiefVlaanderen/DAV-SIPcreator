"""Version-based DB migration for analog SIP databases."""

from __future__ import annotations

import json
import sqlite3 as sql
from collections.abc import Callable

import pandas as pd

from src.controller.db_versioning_common import run_db_migrations as _run_db_migrations

from src.utils.constants import (
    MIGRATION_ID_COLUMN,
    PROD_ENVIRONMENT_NAME,
    SIP_CREATOR_VERSION,
    UNKNOWN_TRANSFORMED,
    APIResponseKey,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.sip_status import SIPStatus


class SeriesNotFoundError(Exception):
    """Raised when an old analog DB's series cannot be found in any environment."""

    def __init__(self, series_id: str, series_name: str) -> None:
        self.series_id = series_id
        self.series_name = series_name
        super().__init__(f"Series not found: id={series_id!r}, name={series_name!r}")


def migrate_analog_to_3_0(
    conn: sql.Connection,
    *,
    environment_resolver: Callable[[str, str], str | None] | None = None,
) -> None:
    """Migrate a pre-3.0 analog database to the 3.0 schema **in-place**.

    Pre-3.0 databases have:
    - A ``data`` table with ``_id`` INTEGER PRIMARY KEY + dynamic columns
    - An ``extra`` table with ``series_json``, ``edepot_id``,
      ``data_changed_since_last_upload``

    After migration:
    - ``extra`` table removed
    - ``sip`` table created with flattened fields
    - ``sip_creator`` table created
    - ``data`` table has ``_id`` column removed

    Raises:
        SeriesNotFoundError: If an environment_resolver is provided but cannot
            find the series in any environment.
    """
    # 1. Read extra table
    extra = conn.execute("SELECT * FROM extra").fetchone()
    if extra is None:
        return

    series_json_str, edepot_id, data_changed = extra

    # 2. Parse series_json (handles both API response format and simplified format)
    series_dict = json.loads(series_json_str)
    series_id = series_dict.get(APIResponseKey.ID, series_dict.get(MIGRATION_ID_COLUMN, ""))
    content = series_dict.get(APIResponseKey.CONTENT, {})
    series_name = content.get(APIResponseKey.NAME, "") if isinstance(content, dict) else ""
    if not series_name:
        series_name = series_dict.get(DBColumnName.NAME, "")

    # 3. Resolve environment (must happen before any data modification)
    environment_name = PROD_ENVIRONMENT_NAME
    if environment_resolver is not None:
        resolved = environment_resolver(series_id, series_name)
        if resolved is None:
            raise SeriesNotFoundError(series_id, series_name)
        environment_name = resolved

    # 4. Infer status
    if edepot_id and not data_changed:
        status = SIPStatus.ACCEPTED
    elif edepot_id:
        status = SIPStatus.SIP_CREATED
    else:
        status = SIPStatus.IN_PROGRESS

    uploaded = bool(edepot_id)

    # 5. Remove _id column from data table
    df = pd.read_sql(f"SELECT * FROM {DBTableName.DATA}", conn).fillna("").astype(str)
    if MIGRATION_ID_COLUMN in df.columns:
        df = df.drop(columns=[MIGRATION_ID_COLUMN])
    conn.execute(f"DROP TABLE {DBTableName.DATA}")
    df.to_sql(DBTableName.DATA, conn, index=False, dtype="text")

    # 6. Drop extra table
    conn.execute("DROP TABLE extra")

    # 7. Create sip table
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
        f"INSERT INTO {DBTableName.SIP} "
        f"({DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME}, "
        f"{DBColumnName.SERIES_ID}, {DBColumnName.SERIES_NAME}, {DBColumnName.EDEPOT_SIP_ID}, "
        f"{DBColumnName.UPLOADED}, {DBColumnName.GRID_VALID}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("", status.name, environment_name, series_id, series_name, edepot_id or "", int(uploaded), 0),
    )

    # 8. Create sip_creator table
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
        (SIP_CREATOR_VERSION, UNKNOWN_TRANSFORMED, SIP_CREATOR_VERSION),
    )


# ---------------------------------------------------------------------------
# Migration registry & runner
# ---------------------------------------------------------------------------

SCHEMA_MIGRATIONS: dict[str, Callable[[sql.Connection], None]] = {
    "3.0": migrate_analog_to_3_0,
}


def run_db_migrations(
    conn: sql.Connection,
    db_path: str,
    *,
    environment_resolver: Callable[[str, str], str | None] | None = None,
) -> None:
    """Run all pending migrations for an analog SIP DB."""
    bound = {
        version: (lambda c, fn=fn: fn(c, environment_resolver=environment_resolver))
        for version, fn in SCHEMA_MIGRATIONS.items()
    }
    _run_db_migrations(conn, db_path, bound)
