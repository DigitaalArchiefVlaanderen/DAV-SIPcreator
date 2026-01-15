import os
import sys
import json

from PySide6 import QtGui


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
