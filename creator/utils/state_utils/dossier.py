from dataclasses import dataclass

import os


@dataclass
class Dossier:
    path: str

    @property
    def dossier_label(self) -> str:
        return os.path.basename(self.path)
