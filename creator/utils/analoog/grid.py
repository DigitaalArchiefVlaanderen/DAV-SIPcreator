from dataclasses import dataclass

from ..series import Series

@dataclass
class Grid:
    series: Series

    columns: list[str]

    # 2D-List
    data: list[list[str]]
