from enum import Enum


class Tables(Enum):
    DOSSIER = "dossier"
    SERIES = "series"
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
SET disabled=false
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
delete_dossiers_by_sip = f"""
DELETE FROM {Tables.DOSSIER.value} as d
WHERE d.path IN (
    SELECT dossier_id
    FROM {Tables.SIP_DOSSIER_LINK.value} as s
    WHERE s.sip_id=?
)
"""
delete_dossier_links_by_sip = f"""
DELETE FROM {Tables.SIP_DOSSIER_LINK.value}
WHERE sip_id=?
"""

create_series_table = f"""
CREATE TABLE IF NOT EXISTS {Tables.SERIES.value} (
    id text PRIMARY KEY,
    status text NOT NULL,
    name text NOT NULL,
    valid_from text NOT NULL,
    valid_to text NOT NULL
)
"""
get_series_by_id = f"""
SELECT *
FROM {Tables.SERIES.value}
WHERE id=?
"""
insert_series = f"""
INSERT INTO {Tables.SERIES.value}(id, status, name, valid_from, valid_to)
VALUES (?,?,?,?,?)
"""
update_series = f"""
UPDATE {Tables.SERIES.value}
SET status=?,
    name=?,
    valid_from=?,
    valid_to=?
WHERE id=?
"""
# NOTE: delete is nothing else references it
delete_series = f"""
DELETE FROM {Tables.SERIES.value} as series
WHERE id=?
  AND 1 = (
    SELECT count(*)
    FROM {Tables.SIP.value} as sip
    WHERE sip.series_id=series.id
  )
"""

create_sip_table = f"""
CREATE TABLE IF NOT EXISTS {Tables.SIP.value} (
    id text PRIMARY KEY,
    environment_name text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    series_id text NOT NULL,
    metadata_file_path text NOT NULL,
    tag_mapping_dict text NOT NULL,
    folder_mapping_list text NOT NULL
)
"""
update_sip_table = [
    # Adding a column
    f"""
    ALTER TABLE {Tables.SIP.value}
        ADD edepot_sip_id text;
    """,
    # Changing a status name
    f"""
    UPDATE {Tables.SIP.value}
    SET status='ACCEPTED'
    WHERE status='ARCHIVED';
    """,
]
read_all_sip = f"""
SELECT * FROM {Tables.SIP.value}
"""
insert_sip = f"""
INSERT INTO {Tables.SIP.value}(id, environment_name, name, status, series_id, metadata_file_path, tag_mapping_dict, folder_mapping_list, edepot_sip_id)
VALUES(?,?,?,?,?,?,?,?,?)
"""
update_sip = f"""
UPDATE {Tables.SIP.value}
SET environment_name=?,
    name=?,
    status=?,
    series_id=?,
    metadata_file_path=?,
    tag_mapping_dict=?,
    folder_mapping_list=?,
    edepot_sip_id=?
WHERE id=?
"""
delete_sip = f"DELETE FROM {Tables.SIP.value} WHERE id=?"
