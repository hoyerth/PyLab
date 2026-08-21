"""
1:1 Pine Script kompatibler Moving Average Indikator (TH Pivot v478).
Pfad: algos/ma_indicator.py
"""

from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

from algos.base_indicator import BaseIndicator
from algos.signal_events import IndicatorResult, extract_events_numpy

DEFAULT_BULL_COLOR = "#089981"  # Grün
DEFAULT_BEAR_COLOR = "#F23645"  # Rot
DEFAULT_LINE_WIDTH = 4


def _pine_ema(series: np.ndarray, length: int) -> np.ndarray:
    """Berechnet ta.ema exakt wie in TradingView."""
    n = len(series)
    out = np.full(n, np.nan, dtype=np.float64)
    if n == 0 or length <= 0:
        return out

    alpha = 2.0 / (length + 1.0)
    valid_idx = np.where(~np.isnan(series))[0]
    if len(valid_idx) == 0:
        return out

    first_i = valid_idx[0]
    out[first_i] = series[first_i]

    for i in range(first_i + 1, n):
        val = series[i]
        out[i] = out[i - 1] if np.isnan(val) else alpha * val + (1.0 - alpha) * out[i - 1]

    return out


def _pine_hma_ema(src: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    n = len(src)
    if n == 0:
        return np.full(0, np.nan, dtype=np.float64)

    length = max(1, length)
    smoothing = max(1, smoothing)

    alpha_calc = alpha_factor / (length + 1.0)
    alpha_calc = min(1.0, max(0.0, alpha_calc))

    ema_src = _pine_ema(src, smoothing)
    sm_alpha = 2.0 / (smoothing + 1.0)

    hma_sum = np.full(n, np.nan, dtype=np.float64)
    ema_hma_sum = np.full(n, np.nan, dtype=np.float64)

    valid_idx = np.where(~np.isnan(ema_src))[0]
    if len(valid_idx) == 0:
        return hma_sum

    first_i = valid_idx[0]
    hma_sum[first_i] = src[first_i]
    ema_hma_sum[first_i] = src[first_i]

    for i in range(first_i + 1, n):
        cur_src_ema = ema_src[i] if not np.isnan(ema_src[i]) else src[i]
        prev_sum = hma_sum[i - 1]
        ema_hma_sum[i] = sm_alpha * prev_sum + (1.0 - sm_alpha) * ema_hma_sum[i - 1]
        prev_sum_ema = ema_hma_sum[i]
        hma_sum[i] = alpha_calc * cur_src_ema + (1.0 - alpha_calc) * prev_sum_ema

    return hma_sum


def _pine_hma_dema(src: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    e1 = _pine_hma_ema(src, length, smoothing, alpha_factor)
    e2 = _pine_hma_ema(e1, length, smoothing, alpha_factor)
    return 2.0 * e1 - e2


def _pine_hma_tema(src: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    e1 = _pine_hma_ema(src, length, smoothing, alpha_factor)
    e2 = _pine_hma_ema(e1, length, smoothing, alpha_factor)
    e3 = _pine_hma_ema(e2, length, smoothing, alpha_factor)
    return 3.0 * (e1 - e2) + e3


def _pine_hma_ehma(src: np.ndarray, length: int, smoothing: int, alpha_factor: float) -> np.ndarray:
    half_len = max(1, int(length / 2))
    sqrt_len = max(1, int(np.sqrt(length / 2)))
    inner = 2.0 * _pine_hma_ema(src, half_len, smoothing, alpha_factor) - _pine_hma_ema(src, length, smoothing, alpha_factor)
    return _pine_hma_ema(inner, sqrt_len, smoothing, alpha_factor)


class MAIndicator(BaseIndicator):
    def __init__(
            self,
            ma_type: str = "TEMA",
            period: int = 17,
            smoothing: int = 5,
            alpha_factor: float = 3.0,
            bull_color: str = DEFAULT_BULL_COLOR,
            bear_color: str = DEFAULT_BEAR_COLOR,
            line_width: int = DEFAULT_LINE_WIDTH,
    ):
        super().__init__(
            ma_type=ma_type.upper(),
            period=max(1, int(period)),
            smoothing=max(1, int(smoothing)),
            alpha_factor=float(alpha_factor),
            bull_color=bull_color,
            bear_color=bear_color,
            line_width=line_width
        )
        self.ma_type = self.params["ma_type"]
        self.period = self.params["period"]
        self.smoothing = self.params["smoothing"]
        self.alpha_factor = self.params["alpha_factor"]
        self.bull_color = self.params["bull_color"]
        self.bear_color = self.params["bear_color"]
        self.line_width = self.params["line_width"]

    def apply(self, df: pd.DataFrame, generate_signals: bool = True) -> pd.DataFrame:
        """Berechnet den MA exakt wie hma_ma() aus Pine Script (Legacy & Core)."""
        if df.empty or "close" not in df.columns:
            return df

        closes = df["close"].to_numpy(dtype=np.float64)
        col_name = f"ma_{self.ma_type.lower()}_{self.period}"

        if self.ma_type == "TEMA":
            ma_vals = _pine_hma_tema(closes, self.period, self.smoothing, self.alpha_factor)
        elif self.ma_type == "EHMA":
            ma_vals = _pine_hma_ehma(closes, self.period, self.smoothing, self.alpha_factor)
        elif self.ma_type == "DEMA":
            ma_vals = _pine_hma_dema(closes, self.period, self.smoothing, self.alpha_factor)
        elif self.ma_type == "EMA":
            ma_vals = _pine_hma_ema(closes, self.period, self.smoothing, self.alpha_factor)
        elif self.ma_type == "SMA":
            ma_vals = pd.Series(closes).rolling(self.period, min_periods=1).mean().values
        else:
            ma_vals = _pine_hma_tema(closes, self.period, self.smoothing, self.alpha_factor)

        df[col_name] = ma_vals

        diff = np.diff(ma_vals, prepend=np.nan)
        df[f"{col_name}_bull"] = diff >= 0
        df[f"{col_name}_bear"] = diff < 0

        if generate_signals:
            direction = np.where(diff > 0, 1, np.where(diff < 0, -1, 0))
            dir_series = pd.Series(direction, index=df.index)
            signal = np.zeros(len(df), dtype=int)
            prev_dir = dir_series.shift(1).fillna(0)

            signal[(dir_series == 1) & (prev_dir == -1)] = 1
            signal[(dir_series == -1) & (prev_dir == 1)] = -1
            df["signal"] = signal

        return df

    def compute(self, df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> IndicatorResult:
        """Standardisierte Vektor-Ausgabe für RAM-Chart & Analytics-DB."""
        df_calc = self.apply(df.copy(), generate_signals=True)
        col_name = f"ma_{self.ma_type.lower()}_{self.period}"

        times = df_calc["time"].to_numpy()
        prices = df_calc["close"].to_numpy()
        signals = df_calc["signal"].to_numpy() if "signal" in df_calc.columns else np.zeros(len(df_calc))

        events = extract_events_numpy(
            times=times,
            signals=signals,
            prices=prices,
            signal_type="swing_change",
            strength=1.0,
            meta_dict={"ma_col": col_name}
        )

        plot_meta = {
            "type": "ma",
            "col_name": col_name,
            "bull_color": self.bull_color,
            "bear_color": self.bear_color,
            "line_width": self.line_width,
        }

        return IndicatorResult(
            symbol=symbol,
            timeframe=timeframe,
            indicator_name="MAIndicator",
            params=self.params,
            df=df_calc,
            events=events,
            plot_meta=plot_meta
        )

    def get_segments(self, df: pd.DataFrame, ma_col: str) -> List[Tuple[pd.DataFrame, str]]:
        if ma_col not in df.columns or len(df) < 2:
            return []

        vals = df[ma_col].values
        valid_mask = ~np.isnan(vals)
        if not np.any(valid_mask):
            return []

        df_valid = df[valid_mask].copy()
        if len(df_valid) < 2:
            return []

        diffs = np.diff(df_valid[ma_col].values)
        is_bull = np.concatenate([[diffs[0] >= 0], diffs >= 0])

        segments = []
        start_idx = 0
        n = len(df_valid)

        for i in range(1, n):
            if is_bull[i] != is_bull[i - 1]:
                seg_df = df_valid.iloc[start_idx: i + 1]
                color = self.bull_color if is_bull[start_idx] else self.bear_color
                segments.append((seg_df, color))
                start_idx = i

        if start_idx < n - 1:
            seg_df = df_valid.iloc[start_idx:n]
            color = self.bull_color if is_bull[start_idx] else self.bear_color
            segments.append((seg_df, color))

        return segments