"""
algos/chart_plugins.py - Dünne, gestrichelte Tagestrenner ohne Skalen-Verzerrung.
"""

from typing import Optional
import numpy as np
import pandas as pd


def add_day_separators(
    chart,
    df: pd.DataFrame,
    color: str = "rgba(41, 98, 255, 0.40)",
    width: int = 1,
    style: str = "dashed",
    visible_bars: Optional[int] = 350,
):
    """
    Erkennt Tageswechsel (00:00) und Wochenend-Gaps (>12h)
    und zeichnet vertikale Trennlinien, ohne die Y-Achse zu stauchen.
    """
    if len(df) < 2:
        return

    # 1. Nur den sichtbaren Bereich betrachten (verhindert historische Extremwerte)
    work_df = df.iloc[-visible_bars:] if visible_bars and len(df) > visible_bars else df

    times = work_df["time"]
    day_diff = times.dt.date != times.dt.date.shift(1)
    time_gap = (times - times.shift(1)) > pd.Timedelta(hours=12)
    sep_mask = (day_diff | time_gap) & (work_df.index != work_df.index[0])

    separator_indices = work_df.index[sep_mask].tolist()
    if not separator_indices:
        return

    # Preisgrenzen nur aus dem aktuell sichtbaren Fenster holen
    min_price = float(work_df["low"].min())
    max_price = float(work_df["high"].max())

    # Vertikale Liniensegmente zeichnen
    for idx in separator_indices:
        t = work_df.loc[idx, "time"]

        line = chart.create_line(
            color=color,
            width=width,
            style=style,
            price_line=False,
            price_label=False,
        )

        seg_data = pd.DataFrame(
            {
                "time": [t, t],
                "value": [min_price, max_price],
            }
        )
        line.set(seg_data)


# Alias
inject_day_separators = add_day_separators