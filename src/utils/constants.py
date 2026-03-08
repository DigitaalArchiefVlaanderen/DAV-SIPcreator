import os
import re
import sys
import json
from enum import Enum

from PySide6 import QtGui

from src.utils.data_objects.sip_status import SIPStatus


SIP_CREATOR_VERSION = "3.0.0.2b"

class SaveLocations(Enum):
    CONFIGURATION_FILE = "configuration.json"

    DEFAULT_BASE_SAVE_LOCATION = "SIP_Creator"

    IMPORT_TEMPLATES_FOLDER = "import_templates"
    GRID_FOLDER = "Grid"
    SIPS_FOLDER = "SIPs"
    SIP_DB_FOLDER = "sip_databases"
    OLD_SIP_DB_FOLDER = "SIP_dbs"

    OVERDRACHTSLIJSTEN_FOLDER = "overdrachtslijsten"
    
    ANALOOG_FOLDER = "analoog"

class ColumnName(Enum):
    PATH_IN_SIP = "Path in SIP"
    TYPE = "Type"
    DOSSIER_REF = "DossierRef"
    ANALOOG = "Analoog?"
    NAAM = "Naam"
    BESCHRIJVING = "Beschrijving"
    DOSSIERCODE_BRON = "Dossiercode_bron"
    STUKREFERENTIE_BRON = "Stukreferentie_Bron"
    OPENINGSDATUM = "Openingsdatum"
    SLUITINGSDATUM = "Sluitingsdatum"
    ID_BIS_RIJKSREGISTERNUMMER = "ID_BIS-rijksregisternummer"
    ID_RIJKSREGISTERNUMMER = "ID_Rijksregisternummer"
    ID_NAAM = "ID_Naam"
    KBO_NUMMER = "KBO_nummer"
    OVO_CODE = "OVO_code"
    ORGANISATIENAAM = "Organisatienaam"
    TREFWOORDEN_VRIJ = "Trefwoorden_vrij"
    OPMERKINGEN = "Opmerkingen"
    AUTEUR = "Auteur"
    TAAL = "Taal"
    ID_BESCHRIJVING = "ID Beschrijving"
    ID_VERPAKKING = "ID Verpakking"
    ORIGINEEL_DOOSNUMMER = "Origineel Doosnummer"
    LEGACY_LOCATIE_ID = "Legacy locatie ID"
    LEGACY_RANGE = "Legacy range"
    VERPAKKINGSTYPE = "Verpakkingstype"

class RowType:
    DOSSIER = "dossier"
    STUK = "stuk"
    GEEN = "geen"


class BusinessRules:
    SIP_TITLE_MAX_LENGTH: int = 185


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.abspath(relative_path)

def get_logo() -> QtGui.QIcon:
    return QtGui.QIcon(resource_path("logo.ico"))

with open(resource_path("src/utils/ui_text_elements.json"), "r") as f:
    UI_TEXT_ELEMENTS = json.load(f)

CONFIGURATION_PATH = "configuration.json"

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
    r"^\.fseventsd$"
]

MAIN_DB_LOCATION = "sqlite.db"
BASE_SIP_NAME = "SIP {number}"

CHECKABLE_SIP_STATUSES = (SIPStatus.UPLOADED, SIPStatus.PROCESSING)
POLL_INTERVAL_SECONDS = 10

# Grid checks constants
RRN_LOOSE_PATTERN = re.compile(r"^\d{11}$")
RRN_STRICT_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2}$")
