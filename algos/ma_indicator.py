"""
algos/ma_indicator.py - Vektorisierter Moving Average Indikator mit segmentierten Up/Down-Farben.
"""

from __future__ import annotations
from typing import Literal, Optional, List, Tuple
import numpy as np
import pandas as pd

# ===========================================================================
# 0. ZENTRALE DEFAULTS & KONSTANTEN
# ===========================================================================
DEFAULT_MA_TYPE: MAType = "EHMA"
DEFAULT_PERIOD: int = 4
DEFAULT_SMOOTHING: int = 10
DEFAULT_ALPHA_FACTOR: float = 2.0
DEFAULT_BULL_COLOR: str = "#089981"  # TradingView Grün
DEFAULT_BEAR_COLOR: str = "#F23645"  # TradingView Rot
DEFAULT_LINE_WIDTH: int = 2

MAType = Literal[
    "SMA", "EMA", "WMA", "DEMA", "TEMA", "HMA",
    "EHMA", "ZLEMA", "RMA", "KAMA", "ALMA", "VWMA"
]

MA_TYPES: tuple = (
    "SMA", "EMA", "WMA", "DEMA", "TEMA", "HMA",
    "EHMA", "ZLEMA", "RMA", "KAMA", "ALMA", "VWMA"
)

_PINEPIVOT_TYPES: frozenset = frozenset({"HMA", "EMA", "DEMA", "TEMA", "EHMA"})
_KAMA_FAST_ALPHA: float = 2.0 / (2.0 + 1.0)
_KAMA_SLOW_ALPHA: float = 2.0 / (30.0 + 1.0)
_ALMA_OFFSET: float = 0.85


# ===========================================================================
# 1. VEKTORISIERTE KERN-ROUTINEN (NumPy / Pandas ewm)
# ===========================================================================

def _sma_values(values: np.ndarray, period: int) -> np.ndarray:
    if period <= 1:
        return values.astype(float, copy=True)
    if len(values) < period:
        return np.full(len(values), np.nan, dtype=float)
    window = np.ones(period, dtype=float)
    conv = np.convolve(values, window, mode="valid") / float(period)
    result = np.full(len(values), np.nan, dtype=float)
    result[period - 1:] = conv
    return result


def _wma_values(values: np.ndarray, period: int) -> np.ndarray:
    if period <= 1:
        return values.astype(float, copy=True)
    if len(values) < period:
        return np.full(len(values), np.nan, dtype=float)
    weights = np.arange(period, 0, -1, dtype=float)
    conv = np.convolve(values, weights, mode="valid") / weights.sum()
    result = np.full(len(values), np.nan, dtype=float)
    result[period - 1:] = conv
    return result


def _ema_alpha_values(values: np.ndarray, alpha: float) -> np.ndarray:
    return np.array(
        pd.Series(values).ewm(alpha=alpha, adjust=False).mean().to_numpy(),
        dtype=float, copy=True
    )


def _ema_span_values(values: np.ndarray, period: int) -> np.ndarray:
    return np.array(
        pd.Series(values).ewm(span=period, adjust=False).mean().to_numpy(),
        dtype=float, copy=True
    )


def _rma_values(values: np.ndarray, period: int) -> np.ndarray:
    if period <= 1:
        return values.astype(float, copy=True)
    return np.array(
        pd.Series(values).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy(),
        dtype=float, copy=True
    )


def _hma_values(values: np.ndarray, period: int) -> np.ndarray:
    if period <= 1:
        return values.astype(float, copy=True)
    if len(values) < period:
        return np.full(len(values), np.nan, dtype=float)
    half = max(period // 2, 1)
    sqrt_period = max(int(round(np.sqrt(period))), 1)
    inner = 2.0 * _wma_values(values, half) - _wma_values(values, period)
    return _wma_values(inner, sqrt_period)


def _hma_ema_values(values: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    n = len(values)
    if n == 0:
        return values.astype(float, copy=True)
    alpha = float(alpha_factor) / (length + 1)
    smoothing = max(int(smoothing), 1)
    if smoothing <= 1:
        return _ema_alpha_values(values, alpha)
    beta = 2.0 / (smoothing + 1.0)
    gamma = beta * alpha
    e_src = _ema_span_values(values, smoothing)
    v = np.array(
        pd.Series(e_src).ewm(alpha=gamma, adjust=False).mean().to_numpy(),
        dtype=float, copy=True
    )
    if np.isfinite(e_src[0]):
        v = v + (beta - 1.0) * float(e_src[0]) * np.power(1.0 - gamma, np.arange(n))
    result = np.empty(n, dtype=float)
    result[0] = float(values[0]) if np.isfinite(values[0]) else float(e_src[0])
    result[1:] = alpha * e_src[1:] + (1.0 - alpha) * v[:-1]
    return result


def _hma_dema_values(values: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    e1 = _hma_ema_values(values, length, smoothing, alpha_factor)
    e2 = _hma_ema_values(e1, length, smoothing, alpha_factor)
    return 2.0 * e1 - e2


def _hma_tema_values(values: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    e1 = _hma_ema_values(values, length, smoothing, alpha_factor)
    e2 = _hma_ema_values(e1, length, smoothing, alpha_factor)
    e3 = _hma_ema_values(e2, length, smoothing, alpha_factor)
    return 3.0 * (e1 - e2) + e3


def _hma_ehma_values(values: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    half = max(int(length / 2), 1)
    sqrt_half = max(int(np.sqrt(length / 2.0)), 1)
    inner = (2.0 * _hma_ema_values(values, half, smoothing, alpha_factor)
             - _hma_ema_values(values, length, smoothing, alpha_factor))
    return _hma_ema_values(inner, sqrt_half, smoothing, alpha_factor)


def _zlema_values(values: np.ndarray, period: int) -> np.ndarray:
    if period <= 1:
        return values.astype(float, copy=True)
    lag = max(int((period - 1) / 2), 1)
    shifted = np.empty_like(values, dtype=float)
    shifted[:lag] = np.nan
    shifted[lag:] = values[:-lag]
    xt = values + (values - shifted)
    result = _ema_span_values(xt, period)
    result[: max(period - 1, 0)] = np.nan
    return result


def _kama_values(values: np.ndarray, period: int) -> np.ndarray:
    length = max(int(period), 1)
    n = len(values)
    result = np.full(n, np.nan, dtype=float)
    if n <= length:
        return result
    diff = np.abs(np.diff(values))
    vol = np.convolve(diff, np.ones(length, dtype=float), mode="valid")
    change = np.abs(values[length:] - values[:-length])
    er = np.divide(change, vol, out=np.zeros_like(change, dtype=float), where=vol > 0.0)
    sc = np.square(er * (_KAMA_FAST_ALPHA - _KAMA_SLOW_ALPHA) + _KAMA_SLOW_ALPHA)
    m = n - length
    kama = np.empty(m, dtype=float)
    prev = float(values[length])
    kama[0] = prev
    for i in range(1, m):
        val = float(values[length + i])
        prev = prev + sc[i] * (val - prev)
        kama[i] = prev
    result[length:] = kama
    return result


def _alma_values(values: np.ndarray, period: int) -> np.ndarray:
    if period <= 1:
        return values.astype(float, copy=True)
    if len(values) < period:
        return np.full(len(values), np.nan, dtype=float)
    offset = (period - 1) * _ALMA_OFFSET
    sigma = period / 6.0
    m = np.arange(period, dtype=float) - offset
    weights = np.exp(-(m * m) / (2.0 * sigma * sigma))
    weights = weights / weights.sum()
    conv = np.convolve(values, weights[::-1], mode="valid")
    result = np.full(len(values), np.nan, dtype=float)
    result[period - 1:] = conv
    return result


def _vwma_values(values: np.ndarray, volume: np.ndarray, period: int) -> np.ndarray:
    if period <= 1:
        return values.astype(float, copy=True)
    if len(values) < period:
        return np.full(len(values), np.nan, dtype=float)
    vol = np.where(np.isnan(volume), 0.0, volume)
    pv = values * vol
    pv_sum = np.convolve(pv, np.ones(period, dtype=float), mode="valid")
    vol_sum = np.convolve(vol, np.ones(period, dtype=float), mode="valid")
    sma_tail = _sma_values(values, period)[period - 1:]
    valid = vol_sum > 0.0
    wv = np.full(len(vol_sum), np.nan, dtype=float)
    wv[valid] = pv_sum[valid] / vol_sum[valid]
    wv[~valid] = sma_tail[~valid]
    result = np.full(len(values), np.nan, dtype=float)
    result[period - 1:] = wv
    return result


# ===========================================================================
# 2. INDIKATOR-KLASSE
# ===========================================================================

class MAIndicator:
    def __init__(
        self,
        ma_type: MAType = DEFAULT_MA_TYPE,
        period: int = DEFAULT_PERIOD,
        smoothing: int = DEFAULT_SMOOTHING,
        alpha_factor: float = DEFAULT_ALPHA_FACTOR,
        bull_color: str = DEFAULT_BULL_COLOR,
        bear_color: str = DEFAULT_BEAR_COLOR,
        line_width: int = DEFAULT_LINE_WIDTH,
    ):
        self.ma_type = str(ma_type).upper()
        self.period = int(period)
        self.smoothing = int(smoothing)
        self.alpha_factor = float(alpha_factor)
        self.bull_color = str(bull_color)
        self.bear_color = str(bear_color)
        self.line_width = int(line_width)

    def calculate(self, source: pd.Series, volume: Optional[pd.Series] = None) -> pd.Series:
        src = pd.to_numeric(source, errors="coerce")
        values = src.to_numpy(dtype=float, na_value=np.nan)
        n = len(values)
        if n == 0:
            return pd.Series(index=src.index, dtype=float)

        key = self.ma_type
        if key == "SMA":
            res = _sma_values(values, self.period)
        elif key == "EMA":
            res = _hma_ema_values(values, self.period, self.smoothing, self.alpha_factor)
        elif key == "WMA":
            res = _wma_values(values, self.period)
        elif key == "DEMA":
            res = _hma_dema_values(values, self.period, self.smoothing, self.alpha_factor)
        elif key == "TEMA":
            res = _hma_tema_values(values, self.period, self.smoothing, self.alpha_factor)
        elif key == "HMA":
            res = _hma_values(values, self.period)
        elif key == "EHMA":
            res = _hma_ehma_values(values, self.period, self.smoothing, self.alpha_factor)
        elif key == "ZLEMA":
            res = _zlema_values(values, self.period)
        elif key == "RMA":
            res = _rma_values(values, self.period)
        elif key == "KAMA":
            res = _kama_values(values, self.period)
        elif key == "ALMA":
            res = _alma_values(values, self.period)
        elif key == "VWMA":
            vol = volume.to_numpy(dtype=float, na_value=np.nan) if volume is not None else None
            res = _vwma_values(values, vol, self.period) if vol is not None else _sma_values(values, self.period)
        else:
            raise ValueError(f"Unbekannter MA-Typ '{key}'. Gültig: {MA_TYPES}")

        if key not in _PINEPIVOT_TYPES and self.smoothing > 1:
            ema_first = _ema_span_values(res, self.smoothing)
            alpha_calc = self.alpha_factor / (self.period + 1.0)
            res = _ema_alpha_values(ema_first, alpha_calc)

        return pd.Series(res, index=src.index, dtype=float)

    def get_segments(self, df: pd.DataFrame, ma_col: str) -> List[Tuple[pd.DataFrame, str]]:
        segments = []
        series = df[["time", ma_col]].dropna(subset=[ma_col]).reset_index(drop=True)
        n = len(series)
        if n < 2:
            return segments

        diff = series[ma_col].diff()
        is_up = diff >= 0
        is_up.iloc[0] = is_up.iloc[1] if n > 1 else True

        start_idx = 0
        current_state = bool(is_up.iloc[1])

        for i in range(2, n):
            state = bool(is_up.iloc[i])
            if state != current_state:
                # Altes Segment endet exakt am Wendepunkt (i - 1)
                seg_df = series.iloc[start_idx:i]
                color = self.bull_color if current_state else self.bear_color
                segments.append((seg_df, color))

                # Neues Segment startet am Wendepunkt (i - 1), damit die Verbindungslinie zur Bar i direkt die neue Farbe hat
                start_idx = i - 1
                current_state = state

        # Letztes Segment bis zum Ende anhängen
        seg_df = series.iloc[start_idx:]
        color = self.bull_color if current_state else self.bear_color
        segments.append((seg_df, color))
        return segments

    def apply(self, df: pd.DataFrame, generate_signals: bool = False) -> pd.DataFrame:
        out = df.copy()
        vol = out["volume"] if "volume" in out.columns else None

        # 1. MA berechnen
        col_name = f"ma_{self.ma_type.lower()}_{self.period}"
        ma_series = self.calculate(out["close"], volume=vol)
        out[col_name] = ma_series

        # 2. Signale: Exakt am Richtungswechsel der Steigung
        if generate_signals:
            diff = ma_series.diff()
            prev_diff = diff.shift(1)
            buy_cond = (diff >= 0) & (prev_diff < 0)
            sell_cond = (diff <= 0) & (prev_diff > 0)
            out["signal"] = np.select([buy_cond, sell_cond], [1, -1], default=0)
        elif "signal" in out.columns:
            out = out.drop(columns=["signal"])

        return out