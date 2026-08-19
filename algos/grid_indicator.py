# algos/grid_indicator.py
"""
Grid & Proximity Indicator Plugin
Pfad: algos/grid_indicator.py
"""

from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

# =============================================================================
# 1. DEFAULT-PARAMETER (GANZ OBEN ZUM SCHNELLEN ANPASSEN)
# =============================================================================
DEFAULT_GRID_PARAMS: Dict[str, Any] = {
    # Master Switch
    "enable_master": True,

    # Raster & Custom Levels
    "step_size": 0.50,
    "steps_around": 4,
    "custom_levels": [],  # Beliebige Liste z. B. [64.30, 63.70]

    # Proximity & Hit-Logik
    "visit_pct": 0.05,
    "use_time_filter": True,
    "time_window_mins": 5,

    # Visualisierungs-Flags & Styling
    "show_lines": True,
    "show_circles": True,
    "grid_line_width": 1,
    "custom_line_width": 1,
    "line_color": "rgba(41, 121, 255, 0.85)",

    # Legacy Einzelfelder (Abwärtskompatibilität)
    "prox_level1": 0.0,
    "prox_level2": 0.0,
    "prox_level3": 0.0,
    "prox_level4": 0.0,
    "prox_level5": 0.0,
    "prox_level6": 0.0,
}


# =============================================================================
# 2. HILFSFUNKTIONEN
# =============================================================================
def f_round_to_custom_step(price: float, step: float) -> float:
    if step <= 0:
        return price
    inv_step = 1.0 / step
    return round(price * inv_step) / inv_step


def f_strip_trailing_zeros(val: float) -> str:
    s = f"{val:.6f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def f_in_window_around(minute_val: int, center: int, span: int) -> bool:
    lower = center - span
    upper = center + span
    if lower < 0:
        return minute_val >= (60 + lower) or minute_val <= upper
    elif upper > 59:
        return minute_val >= lower or minute_val <= (upper - 60)
    else:
        return lower <= minute_val <= upper


# =============================================================================
# 3. INDIKATOR KLASSE
# =============================================================================
class GridIndicator:
    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params: Dict[str, Any] = DEFAULT_GRID_PARAMS.copy()
        if params:
            self.params.update(params)

    def calculate(self, df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        p = self.params.copy()
        if params:
            p.update(params)

        def _get_param(new_key: str, old_key: str, default: Any) -> Any:
            if new_key in p:
                return p[new_key]
            if old_key in p:
                return p[old_key]
            return default

        enable = bool(_get_param("enable_master", "prox_enableMaster", True))
        if df.empty or not enable:
            return {
                "lines": [],
                "hit_circles": [],
                "status_info": {"in_time_window": False, "active_hits": []},
            }

        step_size = float(_get_param("step_size", "prox_stepSize", 0.50))
        steps_around = int(_get_param("steps_around", "prox_stepsAround", 4))
        visit_pct = float(_get_param("visit_pct", "prox_visitPct", 0.05))
        time_window_mins = int(_get_param("time_window_mins", "prox_timeWindowMins", 5))
        use_time_filter = bool(_get_param("use_time_filter", "prox_useTimeFilter", True))

        show_lines = bool(_get_param("show_lines", "prox_showLines", True))
        show_circles = bool(_get_param("show_circles", "prox_showCircles", True))

        grid_line_width = int(p.get("grid_line_width", 1))
        custom_line_width = int(p.get("custom_line_width", 1))
        line_color = str(p.get("line_color", "rgba(41, 121, 255, 0.85)"))

        # Custom Levels zusammenführen
        custom_levels = list(p.get("custom_levels", []))
        for i in range(1, 7):
            v = float(p.get(f"prox_level{i}", 0.0))
            if v > 0.0 and v not in custom_levels:
                custom_levels.append(v)

        valid_custom_levels = [float(lvl) for lvl in custom_levels if float(lvl) > 0.0]

        last_row = df.iloc[-1]
        last_close = float(last_row["close"])

        # 1. Grid Levels bilden
        center_price = f_round_to_custom_step(last_close, step_size)
        grid_levels = set()

        for i in range(-steps_around, steps_around + 1):
            grid_levels.add(round(center_price + (i * step_size), 6))

        for c_lvl in valid_custom_levels:
            grid_levels.add(round(c_lvl, 6))

        sorted_levels = sorted(list(grid_levels), reverse=True)

        # 2. Zeitfenster-Status
        last_time = last_row["time"]
        last_minute = last_time.minute if isinstance(last_time, pd.Timestamp) else pd.to_datetime(last_time).minute
        full_win = f_in_window_around(last_minute, 0, time_window_mins)
        half_win = f_in_window_around(last_minute, 30, time_window_mins)
        in_time_window = (full_win or half_win) if use_time_filter else True

        # 3. Proximity & Hit Circles
        hit_circles = []
        active_hits = []

        if show_circles and show_lines:
            for row in df.itertuples():
                time_val = row.time
                c_high = float(row.high)
                c_low = float(row.low)

                row_m = time_val.minute if isinstance(time_val, pd.Timestamp) else pd.to_datetime(time_val).minute
                row_in_time = (
                        f_in_window_around(row_m, 0, time_window_mins) or f_in_window_around(row_m, 30,
                                                                                             time_window_mins)
                )

                if use_time_filter and not row_in_time:
                    circle_color = "#E91E63"  # Fuchsia außerhalb Fenster[cite: 1]
                else:
                    circle_color = "#FFEB3B"  # Gelb im Fenster[cite: 1]

                for lvl in sorted_levels:
                    visit_min = lvl * (1.0 - visit_pct / 100.0)
                    visit_max = lvl * (1.0 + visit_pct / 100.0)

                    touch_high = visit_min <= c_high <= visit_max
                    touch_low = visit_min <= c_low <= visit_max
                    pierce = c_low <= lvl and c_high >= lvl

                    if touch_high or touch_low or pierce:
                        hit_circles.append({
                            "time": time_val,
                            "price": lvl,
                            "color": circle_color,
                        })
                        if getattr(row, "Index") == df.index[-1]:
                            active_hits.append(f_strip_trailing_zeros(lvl))

            # Maximale Marker-Begrenzung für blitzschnelles Rendering
            if len(hit_circles) > 150:
                hit_circles = hit_circles[-150:]

        # 4. Lines Payload
        lines_payload = []
        if show_lines:
            for lvl in sorted_levels:
                is_custom = any(abs(lvl - c_lvl) < 0.0001 for c_lvl in valid_custom_levels)
                lines_payload.append({
                    "price": lvl,
                    "color": line_color,
                    "width": custom_line_width if is_custom else grid_line_width,
                    "style": "Solid",
                    "is_custom": is_custom,
                })

        return {
            "lines": lines_payload,
            "hit_circles": hit_circles,
            "status_info": {
                "in_time_window": in_time_window,
                "active_hits": active_hits,
            },
        }