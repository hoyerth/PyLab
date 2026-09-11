# signal_lab/run_definition.py
"""Run-Definition: Parameter-Raum + Zähler für den Massentest."""
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class RunDefinition:
    """Beschreibt einen kompletten Sweep (ohne Indikator-Instanz)."""
    symbols: List[str]
    timeframes: List[str]
    param_space: List[Dict[str, Any]]   # Liste von Parameter-Diktaten (Kreuzprodukt/Stichprobe)
    date_from: Optional[str] = None      # ISO-String oder None
    date_to: Optional[str] = None
    strategy: str = "grid"               # "grid" | "random"
    sample_size: int = 50
    htf_exact_time: bool = False
    htf_small_tf: str = "M15"
    overlay_tfs: List[str] = field(default_factory=lambda: ["H1", "H4"])

    def count_runs(self) -> int:
        """Anzahl der Runs = Symbole × TFs × Parameter-Sets."""
        return len(self.symbols) * len(self.timeframes) * len(self.param_space)


def _expand_range(cfg: Dict[str, float]) -> List[float]:
    """Wandelt {min, step, max} in eine Werteliste um (np.arange inkl. max)."""
    lo = float(cfg["min"])
    step = float(cfg["step"])
    hi = float(cfg["max"])
    if step <= 0:
        return [lo]
    # np.arange(lo, hi+step*0.5, step) -> inklusive hi
    vals = np.arange(lo, hi + step * 0.5, step)
    # Runden gegen Float-Artefakte, int-kompatibel wenn ganzzahlig
    out = []
    for v in vals:
        v = round(float(v), 6)
        if float(v).is_integer():
            v = int(v)
        out.append(v)
    return out


def build_param_space(ranges: Dict[str, Dict[str, float]],
                      strategy: str = "grid",
                      sample_size: int = 50,
                      seed: int = 42) -> List[Dict[str, Any]]:
    """Erzeugt den Parameter-Raum als Kreuzprodukt (grid) oder Stichprobe.

    ranges: {"period": {"min":4,"step":2,"max":16}, "smoothing": {...}, ...}
    """
    if not ranges:
        return [{}]

    # Listen je Parameter
    lists = {k: _expand_range(v) for k, v in ranges.items()}
    keys = list(lists.keys())

    if strategy == "random":
        rng = np.random.default_rng(seed)
        n_total = int(np.prod([len(lists[k]) for k in keys]))
        n_sample = min(sample_size, n_total)
        # Indizes der Stichprobe (reproduzierbar)
        combos = list(product(*[lists[k] for k in keys]))
        idx = rng.choice(len(combos), size=n_sample, replace=False)
        return [{k: combos[i][j] for j, k in enumerate(keys)} for i in idx]

    # grid: Kreuzprodukt
    return [dict(zip(keys, vals)) for vals in product(*[lists[k] for k in keys])]


def build_run_definition(
    symbols: List[str],
    timeframes: List[str],
    ranges: Dict[str, Dict[str, float]],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    strategy: str = "grid",
    sample_size: int = 50,
    htf_exact_time: bool = False,
    htf_small_tf: str = "M15",
    overlay_tfs: Optional[List[str]] = None,
    fixed_params: Optional[Dict[str, Any]] = None,
) -> RunDefinition:
    """Baut eine RunDefinition aus UI-Werten.

    fixed_params: zusätzliche feste Parameter, die jedem Param-Set beigemischt
    werden (z. B. {"ma_type": "EHMA"}), damit Indikator-Instanz, Run-Name und
    Hash den Parameter vollständig abbilden.
    """
    param_space = build_param_space(ranges, strategy=strategy, sample_size=sample_size)
    if fixed_params:
        param_space = [{**fixed_params, **ps} for ps in param_space]
    return RunDefinition(
        symbols=list(symbols),
        timeframes=list(timeframes),
        param_space=param_space,
        date_from=date_from,
        date_to=date_to,
        strategy=strategy,
        sample_size=sample_size,
        htf_exact_time=htf_exact_time,
        htf_small_tf=htf_small_tf,
        overlay_tfs=overlay_tfs or ["H1", "H4"],
    )


# Sortier-Ordnung für Timeframes (M1 < M2 < ... < H1 < H4 < D1 < W1 < MN1)
_TF_ORDER = {
    "M1": 1, "M2": 2, "M5": 3, "M10": 4, "M15": 5, "M30": 6,
    "H1": 7, "H2": 8, "H4": 9, "H6": 10, "H12": 11, "D1": 12,
    "W1": 13, "MN1": 14,
}


def tf_sort_key(tf: str) -> int:
    """Sortier-Key für Timeframes (aufsteigend nach Dauer)."""
    return _TF_ORDER.get(str(tf).upper(), 99)


def favorite_symbols(db_path) -> List[str]:
    """Favoriten-Symbole aus app_data.broker_symbols (is_favorite=True)."""
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT symbol FROM broker_symbols WHERE is_favorite = TRUE ORDER BY symbol"
        ).fetchall()
    except Exception:
        return []
    finally:
        con.close()
    return [r[0] for r in rows]


def available_date_range(db_path):
    """Verfügbare Datumsspanne in market_data (BKZ, tz-naiv).

    Liefert (min_date, max_date) als pandas.Timestamp (Datum) oder (None, None),
    wenn keine Daten vorhanden sind. Rechenbasis ist die Broker-Kerzen-Zeit
    (BKZ = ``time AT TIME ZONE 'UTC'``, docs/ZEITBASIS_KANON.md); ein
    Offset-Parameter existiert bewusst nicht mehr.
    """
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row = con.execute(
            'SELECT MIN("time" AT TIME ZONE \'UTC\'), '
            'MAX("time" AT TIME ZONE \'UTC\') '
            'FROM ohlcv_bars WHERE "time" IS NOT NULL'
        ).fetchone()
    finally:
        con.close()
    if not row or row[0] is None or row[1] is None:
        return None, None
    import pandas as pd
    # BKZ-Kanon: die SQL projiziert bereits naive Broker-Kerzen-Zeit.
    return pd.Timestamp(row[0]), pd.Timestamp(row[1])


def available_symbols(db_path, favorite_symbols: Optional[List[str]] = None) -> List[str]:
    """Verfügbare Symbole aus market_data (Favoriten zuerst)."""
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT symbol FROM ohlcv_bars ORDER BY symbol"
        ).fetchall()
    finally:
        con.close()
    syms = [r[0] for r in rows]
    if favorite_symbols:
        favs = [s for s in favorite_symbols if s in syms]
        rest = [s for s in syms if s not in favorite_symbols]
        return favs + rest
    return syms


def available_timeframes(db_path, symbol: Optional[str] = None) -> List[str]:
    """Verfügbare TFs aus market_data (optional gefiltert auf ein Symbol)."""
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        if symbol:
            rows = con.execute(
                "SELECT DISTINCT timeframe FROM ohlcv_bars WHERE LOWER(symbol)=LOWER(?)",
                [symbol],
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT DISTINCT timeframe FROM ohlcv_bars"
            ).fetchall()
    finally:
        con.close()
    # Nach Dauer sortieren (M1 < M5 < ... < H1 < H4 < D1 < W1 < MN1)
    return sorted([r[0] for r in rows], key=tf_sort_key)
