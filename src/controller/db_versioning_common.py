"""Shared utilities for version-based DB migrations.

Each SIP type (digital, analog, migration) has its own versioning module
with type-specific migration functions. This module provides the common
infrastructure: version detection, backup, and the migration runner.
"""

from __future__ import annotations

import os
import shutil
import sqlite3 as sql
from collections.abc import Callable

from natsort import natsorted

from src.utils.constants import (
    DB_SCHEMA_CHANGE_VERSIONS,
    SIP_CREATOR_VERSION,
    DBColumnName,
    DBTableName,
)


def extract_major_minor(version: str) -> str:
    """Return ``'major.minor'`` from a full version string."""
    parts = version.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return version


def is_version_older(version_a: str, version_b: str) -> bool:
    """Return ``True`` if *version_a* is strictly older than *version_b*."""
    sorted_versions = natsorted([version_a, version_b])
    return sorted_versions[0] == version_a and version_a != version_b


def detect_schema_version(conn: sql.Connection) -> str | None:
    """Detect the DB's schema version.

    Returns ``None`` for pre-3.0 databases (no ``sip_creator`` table),
    or the major.minor version string otherwise.
    """
    tables = [name for name, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

    if DBTableName.SIP_CREATOR not in tables:
        return None

    row = conn.execute(f"SELECT {DBColumnName.VERSION} FROM {DBTableName.SIP_CREATOR}").fetchone()

    if row is None or not row[0]:
        return None

    return extract_major_minor(row[0])


def backup_original(db_path: str) -> None:
    """Create a one-time backup of the DB before any migration.

    The backup is named ``<db_path>.original`` and is only created if
    it does not already exist, so repeated opens never overwrite the
    original.
    """
    backup_path = db_path + ".original"

    if os.path.exists(backup_path):
        return

    shutil.copy2(db_path, backup_path)

    for suffix in ("-journal", "-wal", "-shm"):
        src = db_path + suffix
        if os.path.exists(src):
            shutil.copy2(src, backup_path + suffix)


def run_db_migrations(
    conn: sql.Connection,
    db_path: str,
    schema_migrations: dict[str, Callable[[sql.Connection], None]],
) -> None:
    """Detect the DB schema version and apply all needed migrations.

    *schema_migrations* maps target schema versions to migration functions.
    A one-time ``.original`` backup is created before the first migration.
    """
    db_version = detect_schema_version(conn)

    migrations_to_run: list[Callable[[sql.Connection], None]] = []

    for schema_version in DB_SCHEMA_CHANGE_VERSIONS:
        if db_version is None or is_version_older(db_version, schema_version):
            migration_fn = schema_migrations.get(schema_version)
            if migration_fn:
                migrations_to_run.append(migration_fn)

    if not migrations_to_run:
        return

    backup_created = False
    backup_path = db_path + ".original"

    if not os.path.exists(backup_path):
        backup_original(db_path)
        backup_created = True

    try:
        for migration_fn in migrations_to_run:
            migration_fn(conn)
    except Exception:
        # Remove the backup if we just created it and the migration failed
        if backup_created and os.path.exists(backup_path):
            os.remove(backup_path)

            for suffix in ("-journal", "-wal", "-shm"):
                bak = backup_path + suffix
                if os.path.exists(bak):
                    os.remove(bak)

        raise

    # Update version to current
    conn.execute(
        f"UPDATE {DBTableName.SIP_CREATOR} SET {DBColumnName.VERSION} = ?, {DBColumnName.LAST_OPENED} = ?",
        (SIP_CREATOR_VERSION, SIP_CREATOR_VERSION),
    )
