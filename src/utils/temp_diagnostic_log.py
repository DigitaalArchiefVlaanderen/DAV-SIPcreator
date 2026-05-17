"""TEMPORARY diagnostic logger — remove after the v3.0.0.7 edepot/HTTPError diagnosis is done.

Writes a single log file (truncated on every app start) that captures full tracebacks
for any `error_handler` invocation plus per-series URL info from the migration e-depot
dialog. The user runs this build, reproduces the issue, and sends back the log file.

Not part of the long-term codebase — delete the module and its call sites once the
investigation is complete.
"""

from __future__ import annotations

import datetime as _dt
import os
import threading
import traceback as _tb

_LOG_FILE_NAME = "sipcreator_debug.log"
_lock = threading.Lock()
_log_path: str | None = None


def init(root_path: str) -> None:
    global _log_path

    if not root_path:
        _log_path = None
        return

    try:
        os.makedirs(root_path, exist_ok=True)
        _log_path = os.path.join(root_path, _LOG_FILE_NAME)

        with open(_log_path, "w", encoding="utf-8") as f:
            f.write(f"=== SIP Creator diagnostic log — {_dt.datetime.now().isoformat(timespec='seconds')} ===\n")
    except OSError:
        _log_path = None


def get_log_path() -> str | None:
    return _log_path


def log(message: str, *, exc: BaseException | None = None) -> None:
    if _log_path is None:
        return

    timestamp = _dt.datetime.now().isoformat(timespec="milliseconds")
    lines = [f"[{timestamp}] {message}"]

    if exc is not None:
        lines.append("".join(_tb.format_exception(type(exc), exc, exc.__traceback__)).rstrip())

    try:
        with _lock, open(_log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass
