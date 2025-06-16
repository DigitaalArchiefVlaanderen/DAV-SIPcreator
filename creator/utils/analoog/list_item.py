from dataclasses import dataclass

from .grid import Grid

@dataclass
class ListItem:
    # Path to db
    source_path: str

    name: str
    edepot_id: str
    grid: Grid
