# algos/ma_indicator.py
"""
Moving Average Indikator (TEMA, EMA, SMA, WMA) mit Steigungssegmentierung.
Pfad: algos/ma_indicator.py
"""

from typing import List, Tuple
import numpy as np
import pandas as pd

DEFAULT_BULL_COLOR = "#089981"  # Grün
DEFAULT_BEAR_COLOR = "#F23645"  # Rot
DEFAULT_LINE_WIDTH = 2


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
    ):
        self.ma_type = ma_type.upper()
        self.period = max(1, int(period))
        self.smoothing = max(1, int(smoothing))
        self.alpha_factor = float(alpha_factor)
        self.bull_color = bull_color
        self.bear_color = bear_color
        self.line_width = line_width

    def _calc_ema(self, series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    def _calc_tema(self, series: pd.Series, span: int) -> pd.Series:
        ema1 = self._calc_ema(series, span)
        ema2 = self._calc_ema(ema1, span)
        ema3 = self._calc_ema(ema2, span)
        return 3 * ema1 - 3 * ema2 + ema3

    def apply(self, df: pd.DataFrame, generate_signals: bool = True) -> pd.DataFrame:
        """Berechnet den MA und optional Kauf-/Verkaufssignale voll vektorisiert."""
        if df.empty or "close" not in df.columns:
            return df

        col_name = f"ma_{self.ma_type.lower()}_{self.period}"
        close = df["close"]

        if self.ma_type == "TEMA":
            raw_ma = self._calc_tema(close, self.period)
        elif self.ma_type == "EMA":
            raw_ma = self._calc_ema(close, self.period)
        else:
            raw_ma = close.rolling(window=self.period, min_periods=1).mean()

        if self.smoothing > 1:
            raw_ma = self._calc_ema(raw_ma, self.smoothing)

        df[col_name] = raw_ma

        # Steigung für Farbwechsel (1 = Bullish / Steigend, -1 = Bearish / Fallend)
        diff = df[col_name].diff().fillna(0)
        df[f"{col_name}_bull"] = diff >= 0
        df[f"{col_name}_bear"] = diff < 0

        # Signale (Richtungswechsel der Steigung)
        if generate_signals:
            direction = np.where(diff > 0, 1, np.where(diff < 0, -1, 0))
            dir_series = pd.Series(direction, index=df.index)
            # Signal nur bei Wechsel
            signal = np.zeros(len(df), dtype=int)
            prev_dir = dir_series.shift(1).fillna(0)

            signal[(dir_series == 1) & (prev_dir == -1)] = 1  # Kaufsignal (Drehung nach oben)
            signal[(dir_series == -1) & (prev_dir == 1)] = -1  # Verkaufsignal (Drehung nach unten)
            df["signal"] = signal

        return df

    def get_segments(self, df: pd.DataFrame, ma_col: str) -> List[Tuple[pd.DataFrame, str]]:
        """Teilt die MA-Linie in farbige Segmente (Garantierte O(N) Terminierung)."""
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
                # Segment abschließen
                seg_df = df_valid.iloc[start_idx:i + 1]
                color = self.bull_color if is_bull[start_idx] else self.bear_color
                segments.append((seg_df, color))
                start_idx = i

        # Letztes Segment anhängen
        if start_idx < n - 1:
            seg_df = df_valid.iloc[start_idx:n]
            color = self.bull_color if is_bull[start_idx] else self.bear_color
            segments.append((seg_df, color))

        return segments