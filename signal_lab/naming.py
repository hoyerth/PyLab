"""
Namens-Konventionen für Signal Lab Sweeps (§2).
Pfad: signal_lab/naming.py
"""

from typing import Any, Dict


def build_run_name(
    indicator_name: str,
    params: Dict[str, Any],
    symbol: str = "",
    timeframe: str = "",
    free_tag: str = "",
) -> str:
    """Erzeugt einen lesbaren Run-Namen nach Konvention."""
    ind = indicator_name.lower().replace("indicator", "")
    parts = [ind]

    if "jump" in ind:
        grid = params.get("grid_interval", 0.5)
        prox = params.get("proximity_buffer", 0.2)
        parts.append(f"g{grid}")
        parts.append(f"prox{prox}")
    else:
        mtype = params.get("ma_type", "EHMA").lower()
        parts.append(mtype)
        if "period" in params:
            parts.append(f"p{params['period']}")
        if "smoothing" in params:
            parts.append(f"s{params['smoothing']}")
        if "alpha_factor" in params:
            parts.append(f"a{params['alpha_factor']}")

    if symbol and timeframe:
        parts.append(f"{symbol}_{timeframe}")
    elif symbol:
        parts.append(symbol)
    elif timeframe:
        parts.append(timeframe)

    if free_tag:
        parts.append(free_tag.strip())

    return "_".join(str(p) for p in parts if p)