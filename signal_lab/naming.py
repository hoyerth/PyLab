# signal_lab/naming.py
"""Run-Namensschema: sprechende, sortierbare Namen + technischer Hash."""
import hashlib
import json
from datetime import datetime
from typing import Any, Dict


def param_short(indicator_name: str, params: Dict[str, Any]) -> str:
    """Kompakte Parameter-Kurzform je Indikator (MA: p06_s10_a3.0)."""
    ind = indicator_name.lower()
    if "ma" in ind:
        p = params.get("period", "?")
        s = params.get("smoothing", "?")
        a = params.get("alpha_factor", "?")
        mt = str(params.get("ma_type", "")).lower()
        return f"{mt}_p{p:02d}_s{s:02d}_a{a}"
    # Generischer Fallback: alphabetisch sortierte key-value Kette
    parts = []
    for k in sorted(params.keys()):
        parts.append(f"{k}{params[k]}")
    return "_".join(parts) or "default"


def build_run_name(
    indicator_name: str,
    params: Dict[str, Any],
    symbol: str,
    timeframe: str,
    timestamp: datetime = None,
    free_tag: str = "",
) -> str:
    """Erzeugt den sprechenden Run-Namen.

    Format: {INDIKATOR}_{PARAM-KURZ}_{SYMBOL}_{TF}_{JJJJMMTT}_{HHMM}
    Optionaler freier Tag wird angehängt.
    """
    ts = timestamp or datetime.now()
    base = (
        f"{indicator_name.upper()}_{param_short(indicator_name, params)}"
        f"_{symbol}_{timeframe}"
        f"_{ts.strftime('%Y%m%d')}_{ts.strftime('%H%M')}"
    )
    if free_tag:
        tag = str(free_tag).strip().replace(" ", "_")
        base = f"{base}_{tag}"
    return base


def build_run_id(indicator_name: str, params: Dict[str, Any], symbol: str, timeframe: str) -> str:
    """Technischer Hash – identisch zu DuckDBSignalService._generate_run_id."""
    key = f"{indicator_name}_{symbol}_{timeframe}_{json.dumps(params, sort_keys=True)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
