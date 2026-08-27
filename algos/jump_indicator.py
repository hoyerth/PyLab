"""
JumpIndicator: Vektorisierte Grid-Level Touches, Proximity-Bounces und Breakouts.
Pfad: algos/jump_indicator.py
"""

from typing import Any, Dict, List
import numpy as np
import pandas as pd

from algos.base_indicator import BaseIndicator
from algos.signal_events import IndicatorResult, SignalEvent

# Obergrenze (Bar, Level)-Paare pro Verarbeitungsblock. Schuetzt den RAM bei
# extrem kleinen Grids / grossen Datensätzen (z. B. M1-BTCUSD mit grid=0.1):
# die Vektorisierung materialisiert alle Level-Paare eines Blocks; der Block
# wird anhand der Paar-Anzahl begrenzt, NICHT anhand der Bar-Anzahl.
_MAX_PAIRS_PER_BLOCK: int = 5_000_000


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
        """Berechnet voll vektorisiert maximal 2 Signale je Kerze.

        Events:
          - `BREAK_UP` / `BREAK_DOWN`: Open unter/über Level, Close ober-/unterhalb
            (Durchbruch) - Richtung +1 / -1, Stärke 1.0.
          - `circle_yellow` / `circle_fuchsia`: Touch (exakt) oder Proximity-Bounce
            innerhalb `proximity_buffer` - Support (Test von oben) bzw. Resistance
            (Test von unten), Stärke 0.5.

        Pro Bar werden maximal 2 Events behalten (Sortierung: Level aufsteigend,
        Breakouts vor Touches) - identisch zur Referenz-Logik.
        """
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

        grid: float = float(self.grid_interval)
        prox: float = float(self.proximity_buffer)

        opens = df["open"].to_numpy(dtype=np.float64)
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        closes = df["close"].to_numpy(dtype=np.float64)
        times = df["time"].to_numpy()

        # Vektorisierte Level-Zuordnung je Bar (inkl. Proximity-Zone)
        lo_int = np.floor((lows - prox) / grid).astype(np.int64)
        hi_int = np.ceil((highs + prox) / grid).astype(np.int64)
        n_levels = np.maximum(hi_int - lo_int + 1, 0)

        if int(n_levels.sum()) == 0:
            return IndicatorResult(
                symbol=symbol,
                timeframe=timeframe,
                indicator_name=self.name,
                params=dict(self.params),
                df=df.copy(),
                events=[],
                plot_meta={},
            )

        events: List[SignalEvent] = []

        # Blockbildung über (Bar, Level)-Paar-Summe (RAM-Schutz)
        block_starts: List[int] = []
        block_ends: List[int] = []
        start = 0
        while start < len(df):
            end = start
            acc = 0
            while end < len(df) and acc < _MAX_PAIRS_PER_BLOCK:
                acc += int(n_levels[end])
                end += 1
            block_starts.append(start)
            block_ends.append(end)
            start = end

        for b_start, b_end in zip(block_starts, block_ends):
            events.extend(self._compute_block(
                times=times,
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                lo_int=lo_int,
                n_levels=n_levels,
                grid=grid,
                prox=prox,
                b_start=b_start,
                b_end=b_end,
            ))

        return IndicatorResult(
            symbol=symbol,
            timeframe=timeframe,
            indicator_name=self.name,
            params=dict(self.params),
            df=df.copy(),
            events=events,
            plot_meta={},
        )

    @staticmethod
    def _compute_block(
        times: np.ndarray,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        lo_int: np.ndarray,
        n_levels: np.ndarray,
        grid: float,
        prox: float,
        b_start: int,
        b_end: int,
    ) -> List[SignalEvent]:
        """Verarbeitet einen Bar-Block [b_start, b_end) voll vektorisiert."""
        n_block = b_end - b_start
        n_lv = n_levels[b_start:b_end]
        total = int(n_lv.sum())
        if total == 0:
            return []

        bar_local = np.repeat(np.arange(n_block, dtype=np.int64), n_lv)
        offsets = np.arange(total, dtype=np.int64) - np.repeat(
            np.cumsum(n_lv) - n_lv, n_lv
        )
        lvl = np.round((lo_int[b_start:b_end][bar_local] + offsets).astype(np.float64) * grid, 4)

        o = opens[b_start:b_end][bar_local]
        h = highs[b_start:b_end][bar_local]
        l = lows[b_start:b_end][bar_local]
        c = closes[b_start:b_end][bar_local]

        # 1) Breakouts (Durchbruch durch ein Level)
        mask_break_up = (o < lvl) & (lvl < c)
        mask_break_down = (o > lvl) & (lvl > c)
        mask_break = mask_break_up | mask_break_down

        # 2) Touch / Proximity-Bounce (Support: Test von oben)
        mask_touch_sup = (
            ((lvl - prox) <= l) & (l <= (lvl + prox))
            & (o >= lvl) & (c >= lvl) & ~mask_break
        )
        # 3) Touch / Proximity-Bounce (Resistance: Test von unten)
        mask_touch_res = (
            ((lvl - prox) <= h) & (h <= (lvl + prox))
            & (o <= lvl) & (c <= lvl) & ~mask_break & ~mask_touch_sup
        )

        ev_bar: List[np.ndarray] = []
        ev_lvl: List[np.ndarray] = []
        ev_type: List[np.ndarray] = []
        ev_dir: List[np.ndarray] = []
        ev_kind: List[np.ndarray] = []
        ev_dist: List[np.ndarray] = []

        def _collect(
            mask: np.ndarray,
            etype: str,
            edir: int,
            kind: int,
            dist: np.ndarray,
        ) -> None:
            if not mask.any():
                return
            n = int(mask.sum())
            ev_bar.append(bar_local[mask])
            ev_lvl.append(lvl[mask])
            ev_type.append(np.full(n, etype, dtype=object))
            ev_dir.append(np.full(n, edir, dtype=np.int8))
            ev_kind.append(np.full(n, kind, dtype=np.int8))
            ev_dist.append(dist[mask])

        _collect(mask_break_up, "BREAK_UP", 1, 0, np.zeros_like(lvl))
        _collect(mask_break_down, "BREAK_DOWN", -1, 0, np.zeros_like(lvl))
        _collect(mask_touch_sup, "circle_yellow", 1, 1, np.round(np.abs(l - lvl), 4))
        _collect(mask_touch_res, "circle_fuchsia", -1, 1, np.round(np.abs(h - lvl), 4))

        if not ev_bar:
            return []

        bar_arr = np.concatenate(ev_bar)
        lvl_arr = np.concatenate(ev_lvl)
        type_arr = np.concatenate(ev_type)
        dir_arr = np.concatenate(ev_dir)
        kind_arr = np.concatenate(ev_kind)
        dist_arr = np.concatenate(ev_dist)

        # Sortierung je Bar: Level aufsteigend, Breakout (kind 0) vor Touch (kind 1)
        order = np.lexsort((kind_arr, lvl_arr, bar_arr))
        bar_sorted = bar_arr[order]

        # Maximal 2 Events je Bar behalten
        is_new_bar = np.concatenate([[True], bar_sorted[1:] != bar_sorted[:-1]])
        starts = np.flatnonzero(is_new_bar)
        positions = np.arange(len(bar_sorted)) - np.repeat(
            starts, np.diff(np.append(starts, len(bar_sorted)))
        )
        sel = order[positions < 2]

        out: List[SignalEvent] = []
        for bi, lv, ty, dr, kind, dist in zip(
            bar_arr[sel],
            lvl_arr[sel],
            type_arr[sel],
            dir_arr[sel],
            kind_arr[sel],
            dist_arr[sel],
        ):
            t_val = pd.Timestamp(times[b_start + int(bi)])
            if int(kind) == 0:
                out.append(
                    SignalEvent(
                        time=t_val,
                        signal_type=str(ty),
                        direction=int(dr),
                        price=float(lv),
                        strength=1.0,
                        meta={
                            "level_price": float(lv),
                            "event_kind": "breakout",
                            "source": "jump",
                        },
                    )
                )
            else:
                d = float(dist)
                out.append(
                    SignalEvent(
                        time=t_val,
                        signal_type=str(ty),
                        direction=int(dr),
                        price=float(lv),
                        strength=0.5,
                        meta={
                            "level_price": float(lv),
                            "event_kind": "touch" if d == 0.0 else "proximity_bounce",
                            "is_proximity": d > 0.0,
                            "distance": d,
                            "source": "jump",
                        },
                    )
                )
        return out
