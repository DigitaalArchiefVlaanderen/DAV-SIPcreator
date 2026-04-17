"""Version-based DB migration for migration (overdrachtslijst) databases."""

from __future__ import annotations

import sqlite3 as sql
from collections.abc import Callable

import pandas as pd

from src.controller.db_versioning_common import run_db_migrations as _run_db_migrations

from src.utils.constants import (
    MIGRATION_ID_COLUMN,
    SIP_CREATOR_VERSION,
    UNKNOWN_TRANSFORMED,
    DBColumnName,
    DBTableName,
)
from src.utils.data_objects.sip_status import SIPStatus

# ---------------------------------------------------------------------------
# Migration: pre-3.0 → 3.0
# ---------------------------------------------------------------------------


def _infer_environment_name(conn: sql.Connection) -> str:
    """Infer the environment name from URIs stored in the ``tables`` table."""
    from src.utils.constants import PROD_ENVIRONMENT_NAME, TI_ENVIRONMENT_NAME

    uris = conn.execute(
        'SELECT "URI Serieregister" FROM tables WHERE "URI Serieregister" IS NOT NULL AND "URI Serieregister" != ""'
    ).fetchall()

    for uri, *_ in uris:
        if "-ti." in uri:
            return TI_ENVIRONMENT_NAME

    if uris:
        return PROD_ENVIRONMENT_NAME

    return PROD_ENVIRONMENT_NAME


def _find_overdrachtslijst_table(conn: sql.Connection) -> str | None:
    """Find the Overdrachtslijst table name (case-insensitive)."""
    all_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()

    for (name,) in all_tables:
        if name.lower() == "overdrachtslijst":
            return name

    return None


def migrate_to_3_0(conn: sql.Connection) -> None:
    """Migrate a pre-3.0 migration database to the 3.0 schema **in-place**.

    Pre-3.0 databases have:
    - An ``Overdrachtslijst`` table with an ``id`` column
    - Series tables with ``id`` and ``main_id`` columns
    - A ``tables`` table listing all tables (including Overdrachtslijst)
    - No ``sip`` or ``sip_creator`` tables

    After migration:
    - ``Overdrachtslijst`` has ``_id`` instead of ``id``
    - Series tables keep ``main_id`` (FK to ``_id``), ``id`` is dropped
    - ``tables`` no longer lists the Overdrachtslijst
    - ``tables`` has a ``status`` column
    - ``sip`` and ``sip_creator`` tables are created
    - Location column suffixes are normalized
    """
    # 1. Find and standardize the Overdrachtslijst table
    main_table = _find_overdrachtslijst_table(conn)
    if main_table and main_table != DBTableName.OVERDRACHTSLIJST:
        conn.execute(f"ALTER TABLE [{main_table}] RENAME TO [{DBTableName.OVERDRACHTSLIJST}]")
        main_table = DBTableName.OVERDRACHTSLIJST

    # 2. Rename id → _id in Overdrachtslijst
    if main_table:
        main_df = pd.read_sql(f"SELECT * FROM [{DBTableName.OVERDRACHTSLIJST}]", conn, dtype=str).fillna("")

        if "id" in main_df.columns:
            main_df = main_df.rename(columns={"id": MIGRATION_ID_COLUMN})
        elif MIGRATION_ID_COLUMN not in main_df.columns:
            main_df.insert(0, MIGRATION_ID_COLUMN, [str(i) for i in range(len(main_df))])

        conn.execute(f"DROP TABLE [{DBTableName.OVERDRACHTSLIJST}]")
        main_df.to_sql(DBTableName.OVERDRACHTSLIJST, conn, index=False, dtype="text")

    # 3. Remove Overdrachtslijst entry from tables, and collect series entries
    tables_columns = {
        col_name for _, col_name, *_ in conn.execute(f"PRAGMA table_info({DBTableName.TABLES});").fetchall()
    }

    series_table_names: list[str] = []
    rows = conn.execute(f"SELECT {DBColumnName.TABLE_NAME} FROM {DBTableName.TABLES}").fetchall()

    for (table_name,) in rows:
        clean = table_name.strip('"')
        if clean.lower() == "overdrachtslijst":
            conn.execute(
                f"DELETE FROM {DBTableName.TABLES} WHERE {DBColumnName.TABLE_NAME} = ?",
                (table_name,),
            )
        else:
            # Strip surrounding quotes from table_name values (old format stored them quoted)
            if clean != table_name:
                conn.execute(
                    f"UPDATE {DBTableName.TABLES} SET {DBColumnName.TABLE_NAME} = ? WHERE {DBColumnName.TABLE_NAME} = ?",
                    (clean, table_name),
                )
            series_table_names.append(clean)

    # 4. Ensure tables.status column exists (absorbs _migrate_tables_uploaded_to_status)
    if "uploaded" in tables_columns and "status" not in tables_columns:
        conn.execute(f"ALTER TABLE {DBTableName.TABLES} ADD COLUMN status text default '{SIPStatus.IN_PROGRESS.name}'")
        conn.execute(f"""
            UPDATE {DBTableName.TABLES} SET status = CASE
                WHEN uploaded = 1 THEN '{SIPStatus.UPLOADED.name}'
                ELSE '{SIPStatus.IN_PROGRESS.name}'
            END
        """)
    elif "status" not in tables_columns:
        conn.execute(f"ALTER TABLE {DBTableName.TABLES} ADD COLUMN status text default '{SIPStatus.IN_PROGRESS.name}'")

    # 5. For each series table: drop id, keep main_id
    for series_name in series_table_names:
        try:
            series_df = pd.read_sql(f"SELECT * FROM [{series_name}]", conn, dtype=str).fillna("")
        except Exception:
            continue

        changed = False
        if "id" in series_df.columns:
            series_df = series_df.drop(columns=["id"])
            changed = True

        if changed:
            conn.execute(f"DROP TABLE [{series_name}]")
            series_df.to_sql(series_name, conn, index=False, dtype="text")

    # 6. Create sip table
    db_tables = [name for name, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

    if DBTableName.SIP not in db_tables:
        environment_name = _infer_environment_name(conn)

        conn.execute(f"""
            CREATE TABLE {DBTableName.SIP} (
                {DBColumnName.NAME} text,
                {DBColumnName.STATUS} text,
                {DBColumnName.ENVIRONMENT_NAME} text,
                {DBColumnName.GRID_VALID} integer default 0
            )
        """)
        conn.execute(
            f"INSERT INTO {DBTableName.SIP} "
            f"({DBColumnName.NAME}, {DBColumnName.STATUS}, {DBColumnName.ENVIRONMENT_NAME}, "
            f"{DBColumnName.GRID_VALID}) VALUES (?, ?, ?, ?)",
            ("", SIPStatus.IN_PROGRESS.name, environment_name, 0),
        )

    # 7. Create sip_creator table
    if DBTableName.SIP_CREATOR not in db_tables:
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

    # 8. Normalize location column suffixes (absorbs _migrate_location_column_suffixes)
    _migrate_location_column_suffixes(conn)


def _migrate_location_column_suffixes(conn: sql.Connection) -> None:
    """Rename ``_N`` suffixed location columns to trailing-space convention."""
    from src.utils.grid.checks.migration.location_group_check import LOCATION_COLUMNS

    all_tables = [name for name, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

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


# ---------------------------------------------------------------------------
# Migration registry & runner
# ---------------------------------------------------------------------------

SCHEMA_MIGRATIONS: dict[str, Callable[[sql.Connection], None]] = {
    "3.0": migrate_to_3_0,
}


def run_db_migrations(conn: sql.Connection, db_path: str) -> None:
    """Run all pending migrations for a migration (overdrachtslijst) DB."""
    _run_db_migrations(conn, db_path, SCHEMA_MIGRATIONS)
