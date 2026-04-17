"""Version-based DB migration for digital SIP databases."""

from __future__ import annotations

import json
import os
import sqlite3 as sql
from collections.abc import Callable

import pandas as pd

from src.controller.db_versioning_common import run_db_migrations as _run_db_migrations

from src.utils.constants import (
    SIP_CREATOR_VERSION,
    UNKNOWN_TRANSFORMED,
    APIResponseKey,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.sip_status import SIPStatus


def migrate_digital_to_3_0(conn: sql.Connection) -> None:
    """Migrate a pre-3.0 digital database to the 3.0 schema **in-place**.

    Pre-3.0 databases have:
    - An uppercase ``SIP`` table with ``environment``, ``status``,
      ``series_json``, ``metadata_file_path``, ``tag_mapping``,
      ``folder_mapping``, ``edepot_sip_id``
    - A ``dossier`` table with ``name`` and ``path`` columns
    - A ``data`` table with dynamic columns

    After migration:
    - Lowercase ``sip`` table with flattened fields
    - ``dossier`` table removed (paths stored as JSON in ``sip.dossiers_list``)
    - ``sip_creator`` table created
    - ``data`` table untouched
    """
    # 1. Read old SIP table
    old_sip = conn.execute(
        "SELECT environment, status, series_json, metadata_file_path, "
        "tag_mapping, folder_mapping, edepot_sip_id FROM SIP"
    ).fetchone()

    if old_sip is None:
        return

    environment, status, series_json_str, _, tag_mapping, folder_mapping, edepot_sip_id = old_sip

    # 2. Parse series_json
    series_dict = json.loads(series_json_str)
    series_id = series_dict.get(APIResponseKey.ID, "")
    series_name = ""
    content = series_dict.get(APIResponseKey.CONTENT)
    if isinstance(content, dict):
        series_name = content.get(APIResponseKey.NAME, "")

    # 3. Read dossier paths
    dossier_rows = conn.execute("SELECT path FROM dossier").fetchall()
    dossiers_list = json.dumps([path for path, *_ in dossier_rows])

    # 4. Derive SIP name from DB path (not available here, will be set on open)
    sip_name = ""

    # 5. Drop old tables
    conn.execute("DROP TABLE IF EXISTS SIP")
    conn.execute("DROP TABLE IF EXISTS dossier")

    # 6. Create new sip table
    conn.execute(f"""
        CREATE TABLE {DBTableName.SIP} (
            {DBColumnName.NAME} text,
            {DBColumnName.STATUS} text,
            {DBColumnName.ENVIRONMENT_NAME} text,
            {DBColumnName.SERIES_ID} text,
            {DBColumnName.SERIES_NAME} text,
            {DBColumnName.EDEPOT_SIP_ID} text,
            {DBColumnName.DOSSIERS_LIST} text,
            {DBColumnName.TAG_MAPPING} text,
            {DBColumnName.FOLDER_MAPPING} text,
            {DBColumnName.GRID_VALID} integer default 0
        )
    """)
    conn.execute(
        f"INSERT INTO {DBTableName.SIP} "
        f"({DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME}, "
        f"{DBColumnName.SERIES_ID}, {DBColumnName.SERIES_NAME}, {DBColumnName.EDEPOT_SIP_ID}, "
        f"{DBColumnName.DOSSIERS_LIST}, {DBColumnName.TAG_MAPPING}, {DBColumnName.FOLDER_MAPPING}, "
        f"{DBColumnName.GRID_VALID}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            sip_name,
            status,
            environment,
            series_id,
            series_name,
            edepot_sip_id or "",
            dossiers_list,
            tag_mapping,
            folder_mapping,
            0,
        ),
    )

    # 7. Create sip_creator table
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

    # 8. data table is left untouched


# ---------------------------------------------------------------------------
# Migration registry & runner
# ---------------------------------------------------------------------------

SCHEMA_MIGRATIONS: dict[str, Callable[[sql.Connection], None]] = {
    "3.0": migrate_digital_to_3_0,
}


def run_db_migrations(conn: sql.Connection, db_path: str) -> None:
    """Run all pending migrations for a digital SIP DB."""
    _run_db_migrations(conn, db_path, SCHEMA_MIGRATIONS)
