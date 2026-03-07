import json
import os
from typing import Iterable

import pandas as pd
import sqlite3 as sql

from src.utils.base_object import BaseObject
from src.utils.constants import UI_TEXT_ELEMENTS, SIP_CREATOR_VERSION
from src.utils.data_objects.sip import SIP
from src.utils.data_objects.digital.sip import SIP as DigitalSIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import Helper

from src.widget.components.digital.dossier_widget import DossierWidget



class DigitalSIPDBController(BaseObject):
    def __init__(self) -> None:
        super().__init__()

        # NOTE: this exists to transition old dbs to new ones
        self.old_sip_db_controller = OldDigitalSIPDBController()

    def conn(self, sip_db_file_name: str) -> sql.Connection:
        return sql.connect(
            os.path.join(
                self.application.configuration.sip_db_location,
                sip_db_file_name
            )
        )

    def create_sip_db(self, sip: SIP, series_id: str = None, series_name: str = None) -> None:
        if os.path.exists((db_path := os.path.join(self.application.configuration.sip_db_location, sip.db_name))):
            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["text"].format(db_apth=db_path),
            )
            return

        if series_id is None or series_name is None:
            Helper().wait_for_series_loaded(custom_signal=sip.series_changed_signal, warn=False)
            if sip.series is None:
                self.application.thread_error_signal.emit(
                    UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_series_error"]["title"],
                    UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_series_error"]["text"],
                )
                return
            series_id = sip.series._id
            series_name = sip.series.get_full_name()

        if not sip.grid_data.has_data:
            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_data_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_data_error"]["text"],
            )
            return

        with self.conn(sip.db_name) as conn:
            conn.execute(f"""
                CREATE TABLE sip (
                    name text,
                    status text,
                    environment_name text,
                    series_id text,
                    series_name text,
                    edepot_sip_id text,
                    dossiers_list text,
                    tag_mapping text,
                    folder_mapping text
                )
            """)
            conn.execute(f"""
                INSERT INTO sip (name, status, environment_name, series_id, series_name, edepot_sip_id, dossiers_list, tag_mapping, folder_mapping)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sip.name,
                sip.status.name,
                sip.environment.name,
                series_id,
                series_name,
                sip.edepot_sip_id or "",
                json.dumps([d.path for d in sip.dossiers]),
                json.dumps(sip.tag_mapping),
                json.dumps(sip.folder_mapping)
            ))

            conn.execute(
                f"""
                    CREATE TABLE sip_creator (
                        version text
                    )
                """
            )
            conn.execute(
                "INSERT INTO sip_creator (version) VALUES (?)",
                (SIP_CREATOR_VERSION,)
            )

            sip.grid_data.data_as_df.to_sql("data", conn, index=False, dtype="text")

    def read_sip_db(self, sip_db_file_name: str) -> tuple[SIP, str, str]:
        """
        Reads a sip from its db.
        Note however that this does not read the data, since we only get that on demand.
        """
        with self.conn(sip_db_file_name) as conn:
            result = conn.execute("SELECT name, status, environment_name, series_id, series_name, edepot_sip_id, dossiers_list, tag_mapping, folder_mapping FROM sip;").fetchone()
            name, status, environment_name, series_id, series_name, edepot_sip_id, dossiers_list, tag_mapping, folder_mapping = result\

            sip = DigitalSIP()
            sip.set_name(name)
            if sip_db_file_name.startswith("new_"):
                sip.mark_as_transitioned()
            sip.set_status(SIPStatus[status])
            sip.environment = self.application.configuration.get_environment(environment_name)

            sip.edepot_sip_id = edepot_sip_id
            sip.set_dossiers([DossierWidget(path=d) for d in json.loads(dossiers_list)])
            sip.tag_mapping = json.loads(tag_mapping)
            sip.folder_mapping = json.loads(folder_mapping)

            return sip, series_id, series_name


    def read_sip_data(self, sip_db_file_name: str) -> pd.DataFrame:
        with self.conn(sip_db_file_name) as conn:
            return pd.read_sql("select * from data", conn, dtype=str).fillna("")

    def g_read_all_sip_dbs(self) -> Iterable[tuple[SIP, str, str]]:
        """
        Tries to transition any old dbs first,
        then generates all the sip dbs that are for the correct environment
        """
        if self.old_sip_db_controller.old_dbs_exist():
            self.transition_all_old_dbs()

        for file in os.listdir(self.application.configuration.sip_db_location):
            is_valid = self.is_valid_db(file)

            # NOTE: this means it's an old db that is already transitioned
            # The user simply left the old db file in place, but we are going to ignore it
            # The amount of code that needs to be written for user error is getting to me :)
            if is_valid is None:
                continue

            if not is_valid:
                self.application.thread_error_signal.emit(
                    UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["title"],
                    UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["text"].format(
                        db_path=os.path.join(self.application.configuration.old_sip_db_location, file)
                    )
                )
                continue

            yield self.read_sip_db(file)

    # Helpers
    def db_exists(self, sip_db_file_name: str) -> bool:
        return os.path.exists(os.path.join(self.application.configuration.sip_db_location, sip_db_file_name))

    def is_valid_db(self, sip_db_file_name: str) -> bool|None:
        if not self.db_exists(sip_db_file_name=sip_db_file_name):
            return False

        if not sip_db_file_name.endswith(".db"):
            return False

        try:
            conn = self.conn(sip_db_file_name)
            conn.close()
        except:
            return False

        with self.conn(sip_db_file_name) as conn:
            # Get all table names
            db_tables = [r for r, *_ in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

            if "SIP" in db_tables and self.old_sip_db_controller.is_valid_db(sip_db_file_name):
                # NOTE: it really shouldn't be here, but I won't be able to stop users from doing it anyway
                new_sip_db_file_name, *_ = self.transition_old_db(sip_db_file_name)

                return self.is_valid_db(new_sip_db_file_name)

            if not "data" in db_tables:
                return False
            if not "sip" in db_tables:
                return False


            columns = {
                column_name: data_type.lower()
                for _, column_name, data_type, *_ in
                conn.execute(f"PRAGMA table_info(sip);").fetchall()
            }

            expected_columns = {
                "status": "text",
                "environment_name": "text",
                "series_name": "text",
                "edepot_sip_id": "text",
                "dossiers_list": "text",
                "tag_mapping": "text",
                "folder_mapping": "text"
            }

            for column, data_type in expected_columns.items():
                # NOTE: missing column
                if column not in columns:
                    return False

                # NOTE: bad data_type
                if data_type != columns[column]:
                    return False

        return True

    def transition_old_db(self, old_db_file_name: str) -> tuple[str]|None:
        sip, series_id, series_name = self.old_sip_db_controller.read_sip_db(old_db_file_name)

        sip.mark_as_transitioned()

        if os.path.exists(os.path.join(self.application.configuration.sip_db_location, sip.db_name)):
            return

        self.create_sip_db(sip=sip, series_id=series_id, series_name=series_name)

        return sip.db_name

    def transition_all_old_dbs(self) -> None:
        for sip_db_file_name in self.old_sip_db_controller.g_read_all_sip_db_names():
            self.transition_old_db(sip_db_file_name)

class OldDigitalSIPDBController(BaseObject):
    # NOTE: "data" table is not mentioned here
    TABLES = {
        "SIP": {
            "environment": "TEXT",
            "status": "TEXT",
            "series_json": "TEXT",
            "metadata_file_path": "TEXT",
            "tag_mapping": "TEXT",
            "folder_mapping": "TEXT",
            "edepot_sip_id": "TEXT",
        },
        "dossier": {
            "name": "TEXT",
            "path": "TEXT",
        }
    }

    def conn(self, sip_db_file_name: str) -> sql.Connection:
        return sql.connect(
            os.path.join(
                self.application.configuration.old_sip_db_location,
                sip_db_file_name
            )
        )

    def old_dbs_exist(self) -> bool:
        return os.path.exists(self.application.configuration.old_sip_db_location) and os.path.isdir(self.application.configuration.old_sip_db_location)

    def is_valid_db(self, sip_db_file_name: str) -> bool:
        if not os.path.exists(os.path.join(self.application.configuration.old_sip_db_location, sip_db_file_name)):
            return False

        if not sip_db_file_name.endswith(".db"):
            return False

        try:
            conn = self.conn(sip_db_file_name)
            conn.close()
        except:
            return False

        with self.conn(sip_db_file_name) as conn:
            # Get all table names
            db_tables = (r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())

            if not "data" in db_tables:
                return False

            for table in db_tables:
                # NOTE: no extra tables allowed
                if table not in self.TABLES:
                    # NOTE: we will not consider the 'data'-table since it is too variable
                    if table == "data":
                        continue

                    return False


                columns = {column_name: data_type for column_name, data_type, *_ in conn.execute(f"PRAGMA table_info({table});").fetchall()}

                for column, data_type in self.TABLES[table].items():
                    # NOTE: missing column
                    if column not in columns:
                        return False

                    # NOTE: bad data_type
                    if data_type != columns[column].upper():
                        return False

        return True

    def read_sip_db(self, sip_db_file_name: str) -> tuple[SIP, str, str]:
        with self.conn(sip_db_file_name) as conn:
            sip_table_results = conn.execute("select * from SIP").fetchone()

            environment_name, sip_status_label, series_json, _, tag_mapping, folder_mapping, edepot_sip_id = sip_table_results

            sip = DigitalSIP()
            sip.set_name(os.path.splitext(sip_db_file_name)[0])
            sip.environment = self.application.configuration.get_environment(environment_name)
            sip.set_status(SIPStatus[sip_status_label])

            sip.tag_mapping = json.loads(tag_mapping)
            sip.folder_mapping = json.loads(folder_mapping)
            sip.edepot_sip_id = edepot_sip_id


            dossier_table_results = conn.execute("select * from dossier").fetchall()

            sip.set_dossiers([
                DossierWidget(path=path)
                for _, path in dossier_table_results
            ])


            cursor = conn.execute("select * from data")

            data_table_columns = [desc[0] for desc in cursor.description]
            data_table_results = cursor.fetchall()

            data = {
                col: [row[i] for row in data_table_results]
                for i, col in enumerate(data_table_columns)
            }

            sip.data = data

            return sip, json.loads(series_json)["Id"], json.loads(series_json)["Content"]["Name"]

    def g_read_all_sip_db_names(self) -> Iterable[str]:
        """
        Generates all the old sip dbs
        """
        for file in os.listdir(self.application.configuration.old_sip_db_location):
            if not self.is_valid_db(file):
                self.application.thread_error_signal.emit(
                    UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["title"],
                    UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["text"].format(
                        db_path=os.path.join(self.application.configuration.old_sip_db_location, file)
                    )
                )
                continue

            yield file
