import json
import os
import re
import sys
from enum import Enum, StrEnum

from PySide6 import QtGui

from src.utils.data_objects.sip_status import SIPStatus

SIP_CREATOR_VERSION = "3.0.0.3"


class SaveLocations(Enum):
    CONFIGURATION_FILE = "configuration.json"

    DEFAULT_BASE_SAVE_LOCATION = "SIP_Creator"

    IMPORT_TEMPLATES_FOLDER = "import_templates"
    GRID_FOLDER = "Grid"
    SIPS_FOLDER = "SIPs"
    SIP_DB_FOLDER = "SIP_dbs"

    OVERDRACHTSLIJSTEN_FOLDER = "overdrachtslijsten"

    ANALOOG_FOLDER = "analoog"


class ColumnName(Enum):
    PATH_IN_SIP = "Path in SIP"
    TYPE = "Type"
    DOSSIER_REF = "DossierRef"
    ANALOOG = "Analoog?"
    NAAM = "Naam"
    OPENINGSDATUM = "Openingsdatum"
    SLUITINGSDATUM = "Sluitingsdatum"
    ID_RIJKSREGISTERNUMMER = "ID_Rijksregisternummer"
    ID_BESCHRIJVING = "ID beschrijving"
    ID_VERPAKKING = "ID verpakking"
    ORIGINEEL_DOOSNUMMER = "Origineel Doosnummer"
    LEGACY_LOCATIE_ID = "Legacy locatie ID"
    LEGACY_RANGE = "Legacy range"
    VERPAKKINGSTYPE = "Verpakkingstype"


class OverdrachtslijstColumnName(Enum):
    BESCHRIJVING = "Beschrijving"
    BEGINDATUM = "Begindatum"
    EINDDATUM = "Einddatum"
    DOOSNR = "Doosnr"


class DBTableName(Enum):
    DATA = "data"
    SIP = "sip"
    OVERDRACHTSLIJST = "Overdrachtslijst"
    TABLES = "tables"
    SIP_CREATOR = "sip_creator"
    DOSSIER = "dossier"


class DBColumnName(Enum):
    NAME = "name"
    PATH = "path"
    STATUS = "status"
    ENVIRONMENT_NAME = "environment_name"
    EDEPOT_SIP_ID = "edepot_sip_id"
    SERIES_JSON = "series_json"
    METADATA_FILE_PATH = "metadata_file_path"
    TAG_MAPPING = "tag_mapping"
    FOLDER_MAPPING = "folder_mapping"
    OVERDRACHTSLIJST_NAME = "overdrachtslijst_name"
    TABLE_NAME = "table_name"
    URI_SERIEREGISTER = "URI Serieregister"
    EDEPOT_ID = "edepot_id"
    UPLOADED = "uploaded"
    VERSION = "version"
    TRANSFORMED = "transformed"
    LAST_OPENED = "last_opened"
    SERIES_ID = "series_id"
    SERIES_NAME = "series_name"


class ConfigKey(Enum):
    API = "API"
    FTPS = "FTPS"
    URL = "url"
    USERNAME = "username"
    PASSWORD = "password"
    CLIENT_ID = "client_id"
    CLIENT_SECRET = "client_secret"
    PORT = "port"


class APIResponseKey(Enum):
    ID = "Id"
    CONTENT = "Content"
    STATUS = "Status"
    VALIDITY_PERIOD = "ValidityPeriod"
    NAME = "Name"
    FROM = "From"
    TO = "To"
    ORGANISATION = "Organisation"
    TYPE = "Type"


class SIPType(StrEnum):
    DIGITAAL = "digitaal"
    MIGRATIE = "migratie"
    ONROEREND_ERFGOED = "onroerend_erfgoed"
    ANALOOG = "analoog"


class RowType:
    DOSSIER = "dossier"
    STUK = "stuk"
    GEEN = "geen"


class BusinessRules:
    SIP_TITLE_MAX_LENGTH: int = 185
    MAX_ROWS_PER_SERIES: int = 9998


KLANT_ROLE = "klant"
ROLE_DEPOTMEDEWERKER = "depotmedewerker"
MIGRATION_MAIN_ID_COLUMN = "main_id"
SERIES_NAME_COLUMN = "series_name"
ANALOOG_DEFAULT_VALUE = "ja"
DB_FILE_EXTENSION = ".db"

# Configuration JSON keys
CONFIG_SECTION_MISC = "misc"
CONFIG_KEY_SIP_STORAGE = "SIP Creator opslag locatie"
CONFIG_KEY_BESTANDSCONTROLE = "Bestandscontrole lijst locatie"
CONFIG_KEY_ENVIRONMENTS = "Omgevingen"
CONFIG_KEY_ROLES = "Rollen"
CONFIG_KEY_TYPE_SIPS = "Type SIPs"

# Default environment URLs
DEFAULT_TI_API_URL = "https://digitaalarchief-ti.vlaanderen.be"
DEFAULT_TI_FTPS_URL = "ingest.digitaalarchief-ti.vlaanderen.be"
DEFAULT_PROD_API_URL = "https://digitaalarchief.vlaanderen.be"
DEFAULT_PROD_FTPS_URL = "ingest.digitaalarchief.vlaanderen.be"


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.abspath(relative_path)


def get_logo() -> QtGui.QIcon:
    return QtGui.QIcon(resource_path("logo.ico"))


with open(resource_path("src/utils/ui_text_elements.json")) as f:
    UI_TEXT_ELEMENTS = json.load(f)

CONFIGURATION_FILE_NAME = "configuration.json"
APPDATA_FALLBACK_FOLDER = "SIP_Creator"


def _can_write_to(directory: str) -> bool:
    test_file = os.path.join(directory, ".write_test")

    try:
        with open(test_file, "w") as f:
            f.write("test")

        os.remove(test_file)

        return True
    except (PermissionError, OSError):
        return False


def determine_root_path() -> str | None:
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.getcwd()

    if _can_write_to(exe_dir):
        return exe_dir

    appdata = os.environ.get("APPDATA", "")

    if not appdata:
        return None

    appdata_folder = os.path.join(appdata, APPDATA_FALLBACK_FOLDER)

    try:
        os.makedirs(appdata_folder, exist_ok=True)
    except OSError:
        return None

    if _can_write_to(appdata_folder):
        return appdata_folder

    return None


TI_ENVIRONMENT_NAME = "ti"
PROD_ENVIRONMENT_NAME = "prod"
ENVIRONMENT_NAMES = (TI_ENVIRONMENT_NAME, PROD_ENVIRONMENT_NAME)

FILE_REGEXES_TO_IGNORE = [
    r"^~.*",
    r"^.+\.te?mp$",
    r"^Thumbs\.db$",
    r"^Desktop\.ini$",
    r"^\.DS_Store$",
    r"^\._.+$",
    r"^\.Spotlight-V100$",
    r"^\.Trashes$",
    r"^\.fseventsd$",
]

MAIN_DB_NAME = "sip_creator.db"
OLD_MAIN_DB_NAME = "sqlite.db"
UNKNOWN_TRANSFORMED = "<3.0"
BASE_SIP_NAME = "SIP {number}"

CHECKABLE_SIP_STATUSES = (SIPStatus.UPLOADED, SIPStatus.PROCESSING)
POLL_INTERVAL_SECONDS = 10

# Grid checks constants
RRN_LOOSE_PATTERN = re.compile(r"^\d{11}$")
RRN_STRICT_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2}$")
