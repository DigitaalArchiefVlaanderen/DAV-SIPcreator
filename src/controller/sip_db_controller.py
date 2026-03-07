import json
import os
from typing import Iterable

import sqlite3 as sql

from src.utils.base_object import BaseObject
from src.utils.constants import UI_TEXT_ELEMENTS, SIP_CREATOR_VERSION
from src.utils.data_objects.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import Helper

from src.widget.components.digital.dossier_widget import DossierWidget



class SIPDBController(BaseObject):
    def __init__(self) -> None:
        super().__init__()

        # NOTE: this exists to transition old dbs to new ones
        self.old_sip_db_controller = OldSIPDBController()

    def conn(self, sip_db_file_name: str) -> sql.Connection:
        return sql.connect(
            os.path.join(
                self.application.configuration.sip_db_location,
                sip_db_file_name
            )
        )
    
    def create_sip_db(self, sip: SIP) -> None:
        if os.path.exists((db_path := os.path.join(self.application.configuration.sip_db_location, sip.db_name))):
            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_already_exists_error"]["text"].format(db_apth=db_path),
            )
            return

        Helper().wait_for_series_loaded(custom_signal=sip.series_changed_signal, warn=False)
        if sip.series is None:
            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_series_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["db_creation_when_db_has_no_series_error"]["text"],
            )
            return
        if sip.data is None:
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
                sip.series._id,
                sip.series.get_full_name(),
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

            conn.execute(
                f"""
                    CREATE TABLE data (
                        {',\n'.join(
                            f"'{column_name}' text" for column_name in sip.data.keys()
                        )}
                    )
                """
            )
            conn.executemany(
                f"""
                    INSERT INTO data ({', '.join(f"'{column_name}'" for column_name in sip.data.keys())})
                    VALUES({', '.join('?' for _ in sip.data.keys())})
                """,
                zip(*(sip.data[column_name] for column_name in sip.data.keys()))
            )

    def read_sip_db(self, sip_db_file_name: str) -> tuple[SIP, str, str]:
        """
        Reads a sip from its db.
        Note however that this does not read the data, since we only get that on demand.
        """
        with self.conn(sip_db_file_name) as conn:
            result = conn.execute("SELECT name, status, environment_name, series_id, series_name, edepot_sip_id, dossiers_list, tag_mapping, folder_mapping FROM sip;").fetchone()
            name, status, environment_name, series_id, series_name, edepot_sip_id, dossiers_list, tag_mapping, folder_mapping = result\
            
            sip = SIP()
            # NOTE: order is important here, since set_name sets db_name as well
            sip.set_name(name)
            sip.db_name = sip_db_file_name
            sip.set_status(SIPStatus[status])
            sip.environment = self.application.configuration.get_environment(environment_name)

            sip.edepot_sip_id = edepot_sip_id
            sip.set_dossiers([DossierWidget(d) for d in json.loads(dossiers_list)])
            sip.tag_mapping = json.loads(tag_mapping)
            sip.folder_mapping = json.loads(folder_mapping)

            return sip, series_id, series_name
        

    def read_sip_data(self, sip_db_file_name: str) -> dict[str, list[str]]:
        with self.conn(sip_db_file_name) as conn:
            cursor = conn.execute("select * from data")

            data_table_columns = [desc[0] for desc in cursor.description]
            data_table_results = cursor.fetchall()

            return {
                col: [row[i] for row in data_table_results]
                for i, col in enumerate(data_table_columns)
            }

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
        sip, *_ = self.old_sip_db_controller.read_sip_db(old_db_file_name)

        sip.db_name = Helper().get_new_transitioned_db_name(old_db_file_name)

        if os.path.exists(os.path.join(self.application.configuration.sip_db_location, sip.db_name)):
            # Assume we have already transitioned it, don't do it again
            return

        self.create_sip_db(sip=sip)

        return sip.db_name

    def transition_all_old_dbs(self) -> None:
        for sip_db_file_name in self.old_sip_db_controller.g_read_all_sip_db_names():
            self.transition_old_db(sip_db_file_name)

class OldSIPDBController(BaseObject):
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

            sip = SIP()
            sip.set_name(os.path.splitext(sip_db_file_name)[0])
            sip.environment = self.application.configuration.get_environment(environment_name)
            sip.set_status(SIPStatus[sip_status_label])

            sip.tag_mapping = json.loads(tag_mapping)
            sip.folder_mapping = json.loads(folder_mapping)
            sip.edepot_sip_id = edepot_sip_id


            dossier_table_results = conn.execute("select * from dossier").fetchall()

            sip.set_dossiers([
                DossierWidget(path)
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
