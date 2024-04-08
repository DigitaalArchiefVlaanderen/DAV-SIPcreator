from dataclasses import dataclass

import os


@dataclass
class Dossier:
    path: str
    disabled: bool = False

    @property
    def dossier_label(self) -> str:
        return os.path.basename(self.path)
