from abc import ABC, abstractmethod

import pandas as pd

from .history import History
from .inventory import Inventory


class Strategy(ABC):
    def __init__(self):
        pass

    def fit(self, history: History):
        pass

    @abstractmethod
    def execute(
        self, idx, position: Inventory, history: History
    ) -> pd.Series:  # expected element type: Signal
        pass