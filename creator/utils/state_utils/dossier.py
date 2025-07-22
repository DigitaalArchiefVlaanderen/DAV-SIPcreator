from dataclasses import dataclass

import os


@dataclass(eq=False)
class Dossier:
    path: str
    disabled: bool = False

    @property
    def dossier_label(self) -> str:
        return os.path.basename(self.path)

    def __eq__(self, other: "Dossier") -> bool:
        if not isinstance(other, Dossier):
            return False

        if self.path == other.path:
            return True
