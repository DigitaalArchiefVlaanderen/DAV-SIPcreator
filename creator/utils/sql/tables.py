from enum import Enum


class Tables(Enum):
    DOSSIER = "dossier"
    SIP = "SIP"
    SIP_DOSSIER_LINK = "SIP_dossier_link"


create_dossier_table = f"""
CREATE TABLE IF NOT EXISTS {Tables.DOSSIER.value} (
    path text PRIMARY KEY,
    disabled int DEFAULT false
)
"""
read_all_dossier = f"""SELECT * FROM {Tables.DOSSIER.value};"""
find_dossier = f"""
SELECT *
FROM {Tables.DOSSIER.value}
WHERE path=?
"""
insert_dossier = f"""
INSERT INTO {Tables.DOSSIER.value}(path)
VALUES(?)
"""
disable_dossier = f"""
UPDATE {Tables.DOSSIER.value}
SET disabled=true
WHERE path=?
"""
enable_dossier = f"""
UPDATE {Tables.DOSSIER.value}
SET disabled=true
WHERE path=?
"""

create_sip_dossier_link_table = f"""
CREATE TABLE IF NOT EXISTS {Tables.SIP_DOSSIER_LINK.value} (
    sip_id text NOT NULL,
    dossier_id text NOT NULL
)
"""
insert_sip_dossier_link = f"""
INSERT INTO {Tables.SIP_DOSSIER_LINK.value}(sip_id, dossier_id)
VALUES(?,?)
"""
get_dossiers_by_sip_id = f"""
SELECT *
FROM {Tables.DOSSIER.value} as d
WHERE d.path IN (
    SELECT dossier_id
    FROM {Tables.SIP_DOSSIER_LINK.value}
    WHERE sip_id=?
)
"""

create_sip_table = f"""
CREATE TABLE IF NOT EXISTS {Tables.SIP.value} (
    id text PRIMARY KEY,
    environment_name text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    series_id text NOT NULL,
    series_name text NOT NULL,
    metadata_file_path text NOT NULL,
    mapping_dict text NOT NULL
)
"""
read_all_sip = f"""
SELECT * FROM {Tables.SIP.value}
"""
get_sip_count = f"""
SELECT count(*) FROM {Tables.SIP.value}
"""
insert_sip = f"""
INSERT INTO {Tables.SIP.value}(id, environment_name, name, status, series_id, series_name, metadata_file_path, mapping_dict)
VALUES(?,?,?,?,?,?,?,?)
"""
update_sip = f"""
UPDATE {Tables.SIP.value}
SET environment_name=?,
    name=?,
    status=?,
    series_id=?,
    series_name=?,
    metadata_file_path=?,
    mapping_dict=?
WHERE id=?
"""
