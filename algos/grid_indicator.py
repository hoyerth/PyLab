# algos/grid_indicator.py
"""
Grid Indicator mit Kurs-Zentrierung, Zeitfenster-Filter und Dual-Circle-Logik (Gelb & Fuchsia).
Pfad: algos/grid_indicator.py
"""

from typing import Any, Dict, List
import numpy as np
import pandas as pd


class GridIndicator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.step_size = float(config.get("step_size", 0.50))
        self.steps_around = int(config.get("steps_around", 4))
        self.custom_levels = [float(x) for x in config.get("custom_levels", [])]
        self.visit_pct = float(config.get("visit_pct", 0.05))
        self.grid_line_width = int(config.get("grid_line_width", 1))
        self.custom_line_width = int(config.get("custom_line_width", 1))
        self.line_color = config.get("line_color", "rgba(41, 121, 255, 0.85)")
        self.circle_color = config.get("circle_color", "#FF00FF")  # Fuchsia (Proximity Touch)
        self.time_circle_color = config.get("time_circle_color", "#FFEB3B")  # Gelb (im Zeitfenster)
        self.use_time_filter = bool(config.get("use_time_filter", True))
        self.time_window_mins = int(config.get("time_window_mins", 5))
        self.show_lines = bool(config.get("show_lines", True))
        self.show_circles = bool(config.get("show_circles", True))

    def _is_in_time_window(self, dt: pd.Timestamp) -> bool:
        """Prüft, ob die Minute um :00 oder :30 innerhalb des Puffers (z. B. +-5 Min) liegt."""
        minute = dt.minute
        dist_00 = min(minute, 60 - minute)
        dist_30 = abs(minute - 30)
        return (dist_00 <= self.time_window_mins) or (dist_30 <= self.time_window_mins)

    def calculate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Berechnet Grid-Linien und Proximity-Trefferpunkte."""
        if df.empty or len(df) < 2:
            return {"lines": [], "hit_circles": []}

        current_price = float(df["close"].iloc[-1])
        # Puffer für Annäherung (Proximity): mindestens 1 Tick bzw. step_size * visit_pct
        tolerance = max(self.step_size * self.visit_pct, 0.01)

        lines = []

        # 1. Automatische Grid-Levels ausgehend vom aktuellen Kurs
        if self.show_lines and self.step_size > 0:
            base_anchor = np.round(current_price / self.step_size) * self.step_size
            k_range = np.arange(-self.steps_around, self.steps_around + 1)
            auto_levels = [base_anchor + (k * self.step_size) for k in k_range]

            for lvl in auto_levels:
                lines.append({
                    "price": float(lvl),
                    "color": self.line_color,
                    "width": self.grid_line_width,
                })

        # 2. Benutzerdefinierte Level anhängen
        if self.show_lines:
            for lvl in self.custom_levels:
                lines.append({
                    "price": float(lvl),
                    "color": self.line_color,
                    "width": self.custom_line_width,
                })

        # 3. Hit Circles mit Proximity-Erkennung
        hit_circles = []
        if self.show_circles and lines:
            prices = np.array([l["price"] for l in lines])
            highs = df["high"].values
            lows = df["low"].values
            times = df["time"].values

            # Proximity: Kerzen-High reicht bis an Level heran ODER Kerzen-Low reicht bis an Level heran ODER Kerze schneidet Level
            hits_matrix = (highs[:, None] >= (prices[None, :] - tolerance)) & \
                          (lows[:, None] <= (prices[None, :] + tolerance))

            row_indices, col_indices = np.where(hits_matrix)

            for r_idx, c_idx in zip(row_indices, col_indices):
                candle_time = pd.Timestamp(times[r_idx])

                # Zeitfenster prüfen: Gelb bei :00/:30 +- Puffer, sonst Fuchsia
                if self.use_time_filter and self._is_in_time_window(candle_time):
                    c_color = self.time_circle_color
                else:
                    c_color = self.circle_color

                hit_circles.append({
                    "time": times[r_idx],
                    "price": float(prices[c_idx]),
                    "color": c_color,
                })

        return {"lines": lines, "hit_circles": hit_circles}