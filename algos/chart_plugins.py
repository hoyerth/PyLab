"""
algos/chart_plugins.py - Dünne, gestrichelte Tagestrenner für Lightweight Charts.
"""

from typing import Optional
import numpy as np
import pandas as pd


def add_day_separators(
    chart,
    df: pd.DataFrame,
    color: str = "rgba(41, 98, 255, 0.45)",  # Dezentes Blau
    width: int = 1,
    style: str = "dashed",  # 'dashed', 'dotted' oder 'solid'
):
    """
    Erkennt Tageswechsel (00:00) und Wochenend-Gaps (>12h)
    und zeichnet dünne, gestrichelte vertikale Trennlinien.
    """
    if len(df) < 2:
        return

    times = df["time"]
    day_diff = times.dt.date != times.dt.date.shift(1)
    time_gap = (times - times.shift(1)) > pd.Timedelta(hours=12)
    sep_mask = (day_diff | time_gap) & (df.index != df.index[0])

    separator_indices = df.index[sep_mask].tolist()
    if not separator_indices:
        return

    # Dynamische Preisspanne für die vertikale Linie ermitteln
    min_price = float(df["low"].min())
    max_price = float(df["high"].max())

    # Für jeden Tageswechsel eine dünne, gestrichelte Vertikallinie setzen
    for idx in separator_indices:
        t = df.loc[idx, "time"]

        line = chart.create_line(
            color=color,
            width=width,
            style=style,
            price_line=False,
            price_label=False,
        )

        # Zwei Punkte auf demselben Zeitstempel spannen die Vertikale auf
        seg_data = pd.DataFrame(
            {
                "time": [t, t],
                "value": [min_price, max_price],
            }
        )
        line.set(seg_data)


# Alias für Abwärtskompatibilität
inject_day_separators = add_day_separators