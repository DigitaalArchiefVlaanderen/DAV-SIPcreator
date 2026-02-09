"""
Base class for a worker user
"""
from src.utils.base_object import BaseObject


class WorkerUser(BaseObject):
    def run(self) -> None:
        raise NotImplementedError
