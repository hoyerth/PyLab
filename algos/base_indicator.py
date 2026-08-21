# algos/base_indicator.py
from abc import ABC, abstractmethod
import pandas as pd
from algos.signal_events import IndicatorResult

class BaseIndicator(ABC):
    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def compute(self, df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> IndicatorResult:
        """Führt Berechnungen aus und liefert ein normalisiertes IndicatorResult."""
        pass

