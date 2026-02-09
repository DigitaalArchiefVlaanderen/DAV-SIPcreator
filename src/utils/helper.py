"""
Some basic helper functions that have no place anywhere else
"""
import os
import re
import time
from typing import Any

from PySide6 import QtCore

from src.utils.constants import FILE_REGEXES_TO_IGNORE


def get_attr_deep(widget: object, attr: str) -> Any:
    if "." not in attr:
        return getattr(widget, attr)
    
    current_value = widget

    for step in attr.split('.'):
        current_value = getattr(current_value, step)

    return current_value

def count_files_from_dirs(directories: str) -> int:
    amount_of_files = 0

    for directory in directories:
        for root, _, files in os.walk(directory):
            amount_of_files += len([
                file for file in files
                if os.path.getsize(os.path.join(root, file)) != 0
                and not any(re.match(reg, file) is not None for reg in FILE_REGEXES_TO_IGNORE)
            ])
            
    return amount_of_files
