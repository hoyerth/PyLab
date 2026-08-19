# algos/grid_indicator.py
"""
Grid & Proximity Indicator Plugin (Ultra-High-Performance Vectorized Edition)
Pfad: algos/grid_indicator.py
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

# =============================================================================
# 1. DEFAULT-PARAMETER
# =============================================================================
DEFAULT_GRID_PARAMS: Dict[str, Any] = {
    "enable_master": True,
    "step_size": 0.50,
    "steps_around": 4,
    "custom_levels": [],
    "visit_pct": 0.05,
    "use_time_filter": True,
    "time_window_mins": 5,
    "show_lines": True,
    "show_circles": True,
    "max_circles": 150,  # Deckelung für blitzschnelles LWC-Rendering
    "grid_line_width": 1,
    "custom_line_width": 1,
    "line_color": "rgba(41, 121, 255, 0.85)",

    # Legacy Fallbacks
    "prox_level1": 0.0,
    "prox_level2": 0.0,
    "prox_level3": 0.0,
    "prox_level4": 0.0,
    "prox_level5": 0.0,
    "prox_level6": 0.0,
}


def f_round_to_custom_step(price: float, step: float) -> float:
    if step <= 0:
        return price
    inv_step = 1.0 / step
    return round(price * inv_step) / inv_step


def f_strip_trailing_zeros(val: float) -> str:
    s = f"{val:.6f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


# =============================================================================
# 2. INDIKATOR KLASSE
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

        def _get_param(new_k: str, old_k: str, default: Any) -> Any:
            if new_k in p:
                return p[new_k]
            if old_k in p:
                return p[old_k]
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
        max_circles = int(p.get("max_circles", 150))

        grid_line_width = int(p.get("grid_line_width", 1))
        custom_line_width = int(p.get("custom_line_width", 1))
        line_color = str(p.get("line_color", "rgba(41, 121, 255, 0.85)"))

        # 1. Custom Levels & Grid-Raster aufbauen
        custom_levels = list(p.get("custom_levels", []))
        for i in range(1, 7):
            v = float(p.get(f"prox_level{i}", 0.0))
            if v > 0.0 and v not in custom_levels:
                custom_levels.append(v)
        valid_custom_levels = [float(lvl) for lvl in custom_levels if float(lvl) > 0.0]

        last_close = float(df["close"].iloc[-1])
        center_price = f_round_to_custom_step(last_close, step_size)

        grid_set = {round(center_price + (i * step_size), 6) for i in range(-steps_around, steps_around + 1)}
        grid_set.update([round(c, 6) for c in valid_custom_levels])
        sorted_levels = sorted(list(grid_set), reverse=True)

        # 2. Vektorisierte Zeitfenster-Maske (:00 & :30 Fenster)
        times = df["time"].values
        dt_index = pd.DatetimeIndex(df["time"])
        minutes = dt_index.minute.values

        m_mod30 = minutes % 30
        in_window_mask = (m_mod30 <= time_window_mins) | (m_mod30 >= (30 - time_window_mins))
        in_time_window_now = bool(in_window_mask[-1]) if use_time_filter else True

        # 3. Vektorisierte Proximity- & Piercing-Berechnung
        hit_circles: List[Dict[str, Any]] = []
        active_hits: List[str] = []
        n_bars = len(df)

        if show_circles and show_lines and len(sorted_levels) > 0:
            highs = df["high"].to_numpy()
            lows = df["low"].to_numpy()

            raw_hits: List[tuple] = []  # (index, time, price, color)

            for lvl in sorted_levels:
                visit_min = lvl * (1.0 - visit_pct / 100.0)
                visit_max = lvl * (1.0 + visit_pct / 100.0)

                # NumPy Vektormasken
                touch_high = (highs >= visit_min) & (highs <= visit_max)
                touch_low = (lows >= visit_min) & (lows <= visit_max)
                pierce = (lows <= lvl) & (highs >= lvl)

                hits_mask = touch_high | touch_low | pierce
                hit_indices = np.flatnonzero(hits_mask)

                if len(hit_indices) == 0:
                    continue

                for idx in hit_indices:
                    t_val = times[idx]
                    in_win = in_window_mask[idx]
                    is_yellow = (not use_time_filter) or in_win
                    c_color = "#FFEB3B" if is_yellow else "#E91E63"

                    raw_hits.append((idx, t_val, lvl, c_color))

                    if idx == n_bars - 1:
                        active_hits.append(f_strip_trailing_zeros(lvl))

            # Chronologisch nach Bar-Index sortieren & deckeln
            if raw_hits:
                raw_hits.sort(key=lambda x: x[0])
                if len(raw_hits) > max_circles:
                    raw_hits = raw_hits[-max_circles:]

                hit_circles = [
                    {"time": item[1], "price": item[2], "color": item[3]}
                    for item in raw_hits
                ]

        # 4. Lines Payload
        lines_payload = []
        if show_lines:
            for lvl in sorted_levels:
                is_custom = any(abs(lvl - c_lvl) < 1e-4 for c_lvl in valid_custom_levels)
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
                "in_time_window": in_time_window_now,
                "active_hits": active_hits,
            },
        }