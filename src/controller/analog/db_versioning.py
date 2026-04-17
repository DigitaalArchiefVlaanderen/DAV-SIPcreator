"""Version-based DB migration for analog SIP databases."""

from __future__ import annotations

import json
import sqlite3 as sql
from collections.abc import Callable

import pandas as pd

from src.controller.db_versioning_common import run_db_migrations as _run_db_migrations

from src.utils.constants import (
    PROD_ENVIRONMENT_NAME,
    SIP_CREATOR_VERSION,
    UNKNOWN_TRANSFORMED,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.sip_status import SIPStatus


def migrate_analog_to_3_0(
    conn: sql.Connection,
    *,
    environment_resolver: Callable[[str], str | None] | None = None,
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
    """
    # 1. Read extra table
    extra = conn.execute("SELECT * FROM extra").fetchone()
    if extra is None:
        return

    series_json_str, edepot_id, data_changed = extra

    # 2. Parse series_json
    series_dict = json.loads(series_json_str)
    series_id = series_dict.get("_id", "")
    series_name = series_dict.get("name", "")

    # 3. Resolve environment
    environment_name = PROD_ENVIRONMENT_NAME
    if environment_resolver is not None:
        resolved = environment_resolver(series_id)
        if resolved is not None:
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
    df = pd.read_sql("SELECT * FROM data", conn, dtype=str).fillna("")
    if "_id" in df.columns:
        df = df.drop(columns=["_id"])
    conn.execute("DROP TABLE data")
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
    environment_resolver: Callable[[str], str | None] | None = None,
) -> None:
    """Run all pending migrations for an analog SIP DB."""
    bound = {
        version: (lambda c, fn=fn: fn(c, environment_resolver=environment_resolver))
        for version, fn in SCHEMA_MIGRATIONS.items()
    }
    _run_db_migrations(conn, db_path, bound)
