# backtest_lab/naming.py
"""Namensschema Option A: kurzer Backtest-Name.

Signal-Run-Namen sind bereits lang (z. B.
`MAINDICATOR_ehma_p04_s06_a2_SILVER_M30_20260821_1608`, 52 Zeichen).
Der Backtest-Run-Name bleibt deshalb kurz und kompakt:

    BT_{sp}{spread}_{sl}{sl}_{tp}{tp}_{sz}{size}_{JJJJMMTT_HHMM}

Beispiel: `BT_sp005_sl2_tp4_sz1_20260821_2030`

Der volle Signal-Name wird NICHT hier gespeichert, sondern per JOIN ueber
`signal_run_id` aus `analytics_data` geholt (siehe Umsetzungsdokument §5).
"""
from datetime import datetime
from typing import Optional


def _fmt_pct(pct: Optional[float]) -> str:
    """Kompakte Prozentdarstellung (Ganzzahl ohne Dezimalpunkt).

    Args:
        pct: Prozentwert (z. B. 2.0). None -> "x" (kein SL/TP).

    Returns:
        Formatierter String (z. B. "2", "2.5", "x").
    """
    if pct is None:
        return "x"
    return f"{pct:g}"


def build_backtest_run_name(
    spread_pct: float,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    position_size_pct: float,
    timestamp: Optional[datetime] = None,
    free_tag: str = "",
    leverage: float = 1000.0,
) -> str:
    """Erzeugt den kurzen Backtest-Run-Namen (Namensschema Option A).

    Args:
        spread_pct: Spread in Prozent (0.05 -> "005").
        stop_loss_pct: SL in Prozent (None -> "x").
        take_profit_pct: TP in Prozent (None -> "x").
        position_size_pct: Positionsgroesse in Prozent.
        timestamp: Zeitstempel fuer den Namens-Anhang (Default: jetzt).
        free_tag: Optionaler individueller Textanhang (wie Signal Lab).
        leverage: CFD-Hebel (Default 1000). Wird als `_lev{hebel}` in den
            Namen aufgenommen, damit sich Runs auch per Name unterscheiden
            (identische Order-Parameter, nur anderer Hebel -> eigener Name).

    Returns:
        Name im Format
        `BT_sp{spread}_{sl}{sl}_{tp}{tp}_{sz}{size}_lev{leverage}_{JJJJMMTT_HHMM}`.

    Example:
        >>> build_backtest_run_name(0.05, 2.0, 4.0, 1.0,
        ...                         datetime(2026, 8, 21, 20, 30))
        'BT_sp005_sl2_tp4_sz1_lev1000_20260821_2030'
    """
    ts = timestamp or datetime.now()
    # round-half-up statt round() (Banker's Rounding): 0.5 bps -> sp001,
    # nicht sp000. spread_pct*100 = Basis-Punkte (1% = 100 bps).
    sp = int(spread_pct * 100 + 0.5)
    name = (
        f"BT_sp{sp:03d}"
        f"_sl{_fmt_pct(stop_loss_pct)}"
        f"_tp{_fmt_pct(take_profit_pct)}"
        f"_sz{_fmt_pct(position_size_pct)}"
        f"_lev{_fmt_pct(leverage)}"
        f"_{ts.strftime('%Y%m%d_%H%M')}"
    )
    if free_tag:
        tag = str(free_tag).strip().replace(" ", "_")
        name = f"{name}_{tag}"
    return name
