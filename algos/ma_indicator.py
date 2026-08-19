# algos/ma_indicator.py
"""
MA Indicator Plugin (Ultra-High-Performance Vectorized Edition)
Pfad: algos/ma_indicator.py
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

# =============================================================================
# 1. FARBEN & DEFAULT-KONFIGURATION
# =============================================================================
DEFAULT_BULL_COLOR = "#00E676"  # Leuchtendes Grün
DEFAULT_BEAR_COLOR = "#FF5252"  # Leuchtendes Rot
DEFAULT_LINE_WIDTH = 2

# =============================================================================
# 2. VEKTORISIERTE MATHEMATIK-KERNE
# =============================================================================
def calc_sma(s: pd.Series, period: int) -> pd.Series:
    return s.rolling(window=period, min_periods=1).mean()


def calc_ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(span=period, adjust=False, min_periods=1).mean()


def calc_rma(s: pd.Series, period: int) -> pd.Series:
    alpha = 1.0 / float(period) if period > 0 else 1.0
    return s.ewm(alpha=alpha, adjust=False, min_periods=1).mean()


def calc_wma(s: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1)
    w_sum = weights.sum()
    return s.rolling(window=period, min_periods=period).apply(
        lambda x: np.dot(x, weights) / w_sum, raw=True
    ).bfill()


def calc_dema(s: pd.Series, period: int) -> pd.Series:
    ema1 = calc_ema(s, period)
    ema2 = calc_ema(ema1, period)
    return (2.0 * ema1) - ema2


def calc_tema(s: pd.Series, period: int) -> pd.Series:
    ema1 = calc_ema(s, period)
    ema2 = calc_ema(ema1, period)
    ema3 = calc_ema(ema2, period)
    return (3.0 * (ema1 - ema2)) + ema3


def calc_hma(s: pd.Series, period: int) -> pd.Series:
    half_len = max(1, int(period / 2))
    sqrt_len = max(1, int(np.sqrt(period)))
    wma_half = calc_wma(s, half_len)
    wma_full = calc_wma(s, period)
    diff = 2.0 * wma_half - wma_full
    return calc_wma(diff, sqrt_len)


def calc_alma(s: pd.Series, period: int, offset: float = 0.85, sigma: float = 6.0) -> pd.Series:
    m = np.floor(offset * (period - 1))
    s_sq = 2.0 * (sigma ** 2)
    weights = np.exp(-((np.arange(period) - m) ** 2) / s_sq)
    w_sum = weights.sum()
    weights /= w_sum
    return s.rolling(window=period, min_periods=period).apply(
        lambda x: np.dot(x, weights), raw=True
    ).bfill()


# =============================================================================
# 3. INDIKATOR KLASSE
# =============================================================================
class MAIndicator:
    def __init__(
        self,
        ma_type: str = "TEMA",
        period: int = 17,
        smoothing: int = 5,
        alpha_factor: float = 3.0,
        bull_color: str = DEFAULT_BULL_COLOR,
        bear_color: str = DEFAULT_BEAR_COLOR,
        line_width: int = DEFAULT_LINE_WIDTH,
    ) -> None:
        self.ma_type = ma_type.upper()
        self.period = int(period)
        self.smoothing = int(smoothing)
        self.alpha_factor = float(alpha_factor)
        self.bull_color = bull_color
        self.bear_color = bear_color
        self.line_width = line_width

    def _calc_raw_ma(self, s: pd.Series, ma_type: str, period: int) -> pd.Series:
        t = ma_type.upper()
        if t == "SMA":
            return calc_sma(s, period)
        elif t == "EMA":
            return calc_ema(s, period)
        elif t == "WMA":
            return calc_wma(s, period)
        elif t == "DEMA":
            return calc_dema(s, period)
        elif t == "TEMA":
            return calc_tema(s, period)
        elif t == "HMA":
            return calc_hma(s, period)
        elif t == "RMA":
            return calc_rma(s, period)
        elif t == "ALMA":
            return calc_alma(s, period)
        else:
            return calc_ema(s, period)

    def apply(self, df: pd.DataFrame, generate_signals: bool = True) -> pd.DataFrame:
        if df.empty:
            return df

        col_name = f"ma_{self.ma_type.lower()}_{self.period}"
        close = df["close"]

        # 1. Basis MA berechnen
        raw_ma = self._calc_raw_ma(close, self.ma_type, self.period)

        # 2. Glättung
        if self.smoothing > 1:
            final_ma = calc_ema(raw_ma, self.smoothing)
        else:
            final_ma = raw_ma

        df[col_name] = final_ma.values

        # 3. Vektorisierte Steigung & Farbmasken
        diff = final_ma.diff().fillna(0.0).values
        is_bull = diff >= 0.0

        df[f"{col_name}_bull"] = is_bull
        df[f"{col_name}_bear"] = ~is_bull

        # 4. Signale vektoriell berechnen (Farbwechsel)
        if generate_signals:
            shift_bull = np.roll(is_bull, 1)
            shift_bull[0] = is_bull[0]

            buy_mask = is_bull & (~shift_bull)
            sell_mask = (~is_bull) & shift_bull

            signals = np.zeros(len(df), dtype=int)
            signals[buy_mask] = 1
            signals[sell_mask] = -1
            df["signal"] = signals

        return df

    def get_segments(self, df: pd.DataFrame, col_name: str) -> List[Tuple[pd.DataFrame, str]]:
        """
        Vektorisierte Segmentzerlegung in Mikrosekunden (für LWC-Line-Segments).
        """
        if col_name not in df.columns or len(df) < 2:
            return []

        values = df[col_name].to_numpy()
        times = df["time"].to_numpy()
        
        diff = np.diff(values)
        is_bull = np.empty(len(values), dtype=bool)
        is_bull[0] = diff[0] >= 0 if len(diff) > 0 else True
        is_bull[1:] = diff >= 0

        # Finde Farbwechsel-Indizes
        change_indices = np.flatnonzero(is_bull[1:] != is_bull[:-1]) + 1
        splits = np.split(np.arange(len(df)), change_indices)

        segments = []
        for i, idx_arr in enumerate(splits):
            if len(idx_arr) == 0:
                continue
            # Überlappung um 1 Punkt für lückenlosen Linienzug
            start_idx = idx_arr[0]
            if start_idx > 0 and i > 0:
                start_idx -= 1
            end_idx = idx_arr[-1] + 1
            
            sub_times = times[start_idx:end_idx]
            sub_vals = values[start_idx:end_idx]
            color = self.bull_color if is_bull[idx_arr[0]] else self.bear_color
            
            segments.append((
                pd.DataFrame({"time": sub_times, col_name: sub_vals}),
                color
            ))

        return segments