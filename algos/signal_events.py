# algos/signal_events.py
from dataclasses import dataclass
from typing import Any, Dict, List
import json
import numpy as np
import pandas as pd

@dataclass
class SignalEvent:
    time: pd.Timestamp
    signal_type: str
    direction: int
    price: float
    strength: float
    meta: Dict[str, Any]

@dataclass
class IndicatorResult:
    symbol: str
    timeframe: str
    indicator_name: str
    params: Dict[str, Any]
    df: pd.DataFrame
    events: List[SignalEvent]
    plot_meta: Dict[str, Any]

    def to_events_frame(self) -> pd.DataFrame:
        """Vektorisierte Umwandlung in UTC-normalisierten DataFrame."""
        if not self.events:
            return pd.DataFrame(columns=[
                "time", "signal_type", "direction", "price", "strength",
                "symbol", "timeframe", "indicator_name", "meta_json"
            ])

        # UTC-Sicherheit erzwingen
        times = [pd.Timestamp(e.time).tz_localize("UTC") if pd.Timestamp(e.time).tz is None
                 else pd.Timestamp(e.time).tz_convert("UTC") for e in self.events]

        return pd.DataFrame({
            "time": times,
            "signal_type": [e.signal_type for e in self.events],
            "direction": np.array([e.direction for e in self.events], dtype=np.int8),
            "price": np.array([e.price for e in self.events], dtype=np.float64),
            "strength": np.array([e.strength for e in self.events], dtype=np.float64),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "indicator_name": self.indicator_name,
            "meta_json": [json.dumps(e.meta) for e in self.events]
        })

def extract_events_numpy(
    times: np.ndarray,
    signals: np.ndarray,
    prices: np.ndarray,
    signal_type: str,
    strength: float = 1.0,
    meta_dict: Dict[str, Any] = None
) -> List[SignalEvent]:
    """NumPy-Maskierung zur Event-Extraktion."""
    mask = signals != 0
    if not np.any(mask):
        return []

    t_hits = times[mask]
    s_hits = signals[mask].astype(int)
    p_hits = prices[mask].astype(float)
    meta = meta_dict or {}

    return [
        SignalEvent(
            time=pd.Timestamp(t),
            signal_type=signal_type,
            direction=int(s),
            price=float(p),
            strength=strength,
            meta=meta
        )
        for t, s, p in zip(t_hits, s_hits, p_hits)
    ]