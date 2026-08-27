"""
JumpIndicator: Vektorisierte Grid-Level Touches, Proximity-Bounces und Breakouts.
Pfad: algos/jump_indicator.py
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from algos.base_indicator import BaseIndicator
from algos.signal_events import IndicatorResult, SignalEvent


class JumpIndicator(BaseIndicator):
    """Vektorisierter Indikator für statische Preis-Grids und Proximity-Zonen."""

    name: str = "JumpIndicator"

    def __init__(
        self,
        grid_interval: float = 0.50,
        proximity_buffer: float = 0.20,
        point_size: float = 0.001,
    ) -> None:
        super().__init__(
            grid_interval=grid_interval,
            proximity_buffer=proximity_buffer,
            point_size=point_size,
        )
        self.name: str = "JumpIndicator"
        self.grid_interval: float = float(grid_interval)
        self.proximity_buffer: float = float(proximity_buffer)
        self.point_size: float = float(point_size)

    def compute(
        self,
        df: pd.DataFrame,
        symbol: str = "SILVER",
        timeframe: str = "M1",
    ) -> IndicatorResult:
        """Berechnet vektorisiert maximal 2 Signale je Kerze: Touches/Bounces und Breakouts."""
        if df.empty or len(df) < 2:
            return IndicatorResult(
                symbol=symbol,
                timeframe=timeframe,
                indicator_name=self.name,
                params=dict(self.params),
                df=df,
                events=[],
                plot_meta={},
            )

        df_out: pd.DataFrame = df.copy()
        grid: float = self.grid_interval
        prox: float = self.proximity_buffer

        times: np.ndarray = df_out["time"].values
        opens: np.ndarray = df_out["open"].values.astype(np.float64)
        highs: np.ndarray = df_out["high"].values.astype(np.float64)
        lows: np.ndarray = df_out["low"].values.astype(np.float64)
        closes: np.ndarray = df_out["close"].values.astype(np.float64)

        # Vektorisierte Level-Grenzbereiche ermitteln (inkl. Proximity-Zone)
        min_lvls: np.ndarray = np.floor((lows - prox) / grid) * grid
        max_lvls: np.ndarray = np.ceil((highs + prox) / grid) * grid

        events: List[SignalEvent] = []

        for i in range(len(df_out)):
            o_val: float = float(opens[i])
            h_val: float = float(highs[i])
            l_val: float = float(lows[i])
            c_val: float = float(closes[i])
            t_val = pd.Timestamp(times[i])

            i_min_lvl: float = float(min_lvls[i])
            i_max_lvl: float = float(max_lvls[i])
            levels: np.ndarray = np.arange(i_min_lvl, i_max_lvl + grid * 0.5, grid)

            bar_events: List[SignalEvent] = []

            for lvl in levels:
                lvl_val: float = round(float(lvl), 4)

                # 1. Durchstoßen / Breakout
                if o_val < lvl_val < c_val:
                    bar_events.append(
                        SignalEvent(
                            time=t_val,
                            signal_type="BREAK_UP",
                            direction=1,
                            price=lvl_val,
                            strength=1.0,
                            meta={
                                "level_price": lvl_val,
                                "event_kind": "breakout",
                                "source": "jump",
                            },
                        )
                    )
                elif o_val > lvl_val > c_val:
                    bar_events.append(
                        SignalEvent(
                            time=t_val,
                            signal_type="BREAK_DOWN",
                            direction=-1,
                            price=lvl_val,
                            strength=1.0,
                            meta={
                                "level_price": lvl_val,
                                "event_kind": "breakout",
                                "source": "jump",
                            },
                        )
                    )

                # 2. Touch oder Proximity-Bounce (Support: Test von oben)
                elif (lvl_val - prox) <= l_val <= (lvl_val + prox) and o_val >= lvl_val and c_val >= lvl_val:
                    dist: float = round(abs(l_val - lvl_val), 4)
                    bar_events.append(
                        SignalEvent(
                            time=t_val,
                            signal_type="circle_yellow",
                            direction=1,
                            price=lvl_val,
                            strength=0.5,
                            meta={
                                "level_price": lvl_val,
                                "event_kind": "touch" if dist == 0.0 else "proximity_bounce",
                                "is_proximity": dist > 0.0,
                                "distance": dist,
                                "source": "jump",
                            },
                        )
                    )

                # 3. Touch oder Proximity-Bounce (Resistance: Test von unten)
                elif (lvl_val - prox) <= h_val <= (lvl_val + prox) and o_val <= lvl_val and c_val <= lvl_val:
                    dist: float = round(abs(h_val - lvl_val), 4)
                    bar_events.append(
                        SignalEvent(
                            time=t_val,
                            signal_type="circle_fuchsia",
                            direction=-1,
                            price=lvl_val,
                            strength=0.5,
                            meta={
                                "level_price": lvl_val,
                                "event_kind": "touch" if dist == 0.0 else "proximity_bounce",
                                "is_proximity": dist > 0.0,
                                "distance": dist,
                                "source": "jump",
                            },
                        )
                    )

            if len(bar_events) > 2:
                bar_events = bar_events[:2]

            events.extend(bar_events)

        return IndicatorResult(
            symbol=symbol,
            timeframe=timeframe,
            indicator_name=self.name,
            params=dict(self.params),
            df=df_out,
            events=events,
            plot_meta={},
        )