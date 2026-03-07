from typing import Iterable

from src.widget.base_widget import ComponentWidget


class CentralWidget(ComponentWidget):
    def load_items(self) -> Iterable[None]:
        ...
    ...
