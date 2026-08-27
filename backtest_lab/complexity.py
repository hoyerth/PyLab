# backtest_lab/complexity.py
"""Komplexitaets-/RAM-Schaetzung fuer Backtest-Sweeps (v1).

- Schwellwerte + Schaetz-Koeffizienten als JSON konfigurierbar
  (`data/backtest_complexity.json`, siehe `DEFAULT_CONFIG`).
- Schaetzung = **volles Parameter-Kreuzprodukt** (n_runs = Symbole x TFs x
  Parameter-Sets) - realistisch, nicht beliebig skalierbar (Umsetzungsdok. §5).
- Die UI zeigt die Schaetzung vor dem Lauf an und **lehnt ab**, wenn die
  Limits ueberschritten werden (GO-Button ausgrauen).
"""
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from backtest_lab.db import count_bars

COMPLEXITY_FILE: Path = (
    Path(__file__).resolve().parent.parent / "data" / "backtest_complexity.json"
)

# Verbindliche Defaults (werden per JSON ueberschrieben, wenn die Datei existiert).
DEFAULT_CONFIG: Dict[str, Any] = {
    # Harte Schwellwerte: Ueberschreitung -> Ablehnung des Laufs
    "max_ram_mb": 4096.0,
    "max_runs": 10000,
    # Weicher Schwellwert: Ueberschreitung -> Warnhinweis (kein Abbruch)
    "warn_ram_mb": 2048.0,
    # Schaetz-Koeffizienten (VBT-Arrays pro Bar und Objekt-Overhead je Run)
    "est_bytes_per_bar": 200,
    "est_overhead_mb_per_run": 5.0,
}


@dataclass(frozen=True)
class ComplexityReport:
    """Ergebnis der Komplexitaets-Schaetzung (eine Instanz pro UI-Aktualisierung).

    Attributes:
        n_runs: Volles Kreuzprodukt (Symbole x TFs x Parameter-Sets).
        bars_total: Summe aller Bars ueber alle Runs (Kreuzprodukt).
        est_ram_total_mb: Geschaetzter Gesamt-RAM bei voller Materialisierung
            (Kreuzprodukt) - Basis der Ablehnung.
        est_ram_per_run_mb: RAM fuer den groessten Einzel-Run.
        max_ram_mb / max_runs: Konfigurierte harte Limits.
        ok: True, wenn kein hartes Limit ueberschritten ist (GO freigegeben).
        reasons: Blockierende Gruende (harte Limits) - leer, wenn ok.
        warnings: Nicht-blockierende Hinweise (z. B. Warn-RAM-Schwelle).
    """

    n_runs: int
    bars_total: int
    est_ram_total_mb: float
    est_ram_per_run_mb: float
    max_ram_mb: float
    max_runs: int
    ok: bool
    reasons: Tuple[str, ...]
    warnings: Tuple[str, ...] = ()


def load_complexity_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Liest die Komplexitaets-Konfiguration (JSON), Defaults als Fallback.

    Args:
        path: Alternativer Pfad (fuer Tests). Default: `data/backtest_complexity.json`.

    Returns:
        Konfigurations-Dict (Default-Werte mit gespeicherten Werten gemergt).
    """
    cfg_path = Path(path) if path else COMPLEXITY_FILE
    if not cfg_path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update({k: v for k, v in stored.items() if k in merged})
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_complexity_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Schreibt die Komplexitaets-Konfiguration atomar (tmp + rename).

    Args:
        config: Konfigurations-Dict (aus `load_complexity_config`).
        path: Alternativer Pfad (fuer Tests). Default: `data/backtest_complexity.json`.
    """
    cfg_path = Path(path) if path else COMPLEXITY_FILE
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(cfg_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp, cfg_path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def bar_counts_for(
    symbols: list[str],
    timeframes: list[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[Tuple[str, str], int]:
    """Tatsaechliche Bar-Anzahl je (Symbol, TF) fuer die RAM-Schaetzung.

    Read-only COUNT-Queries auf market_data (schnell, keine Datenladung).
    Nur Kombinationen mit tatsaechlich vorhandenen Daten werden aufgenommen
    (leere Kombinationen scheiden aus dem Kreuzprodukt aus).

    Args:
        symbols: Symbole der Run-Auswahl.
        timeframes: Timeframes der Run-Auswahl.
        date_from / date_to: Gewaehlter Backtest-Zeitraum (naive-UTC-Filter).
        db_path: Alternativer Pfad (fuer Tests). Default: market_data.

    Returns:
        Dict {(symbol, timeframe): bars} fuer alle vorhandenen Kombinationen.
    """
    counts: Dict[Tuple[str, str], int] = {}
    for sym in symbols or []:
        for tf in timeframes or []:
            n = count_bars(sym, tf, date_from=date_from, date_to=date_to, db_path=db_path)
            if n > 0:
                counts[(sym, tf)] = n
    return counts


def estimate_complexity(
    bar_counts: Dict[Tuple[str, str], int],
    n_param_sets: int,
    config: Optional[Dict[str, Any]] = None,
) -> ComplexityReport:
    """Schätzt RAM + Run-Anzahl fuer das volle Parameter-Kreuzprodukt.

    Args:
        bar_counts: {(symbol, tf): bars} aus `bar_counts_for` (oder Testwerte).
        n_param_sets: Anzahl Order-Parameter-Sets (Kreuzprodukt der UI-Werte;
            v1: 1, da nur ein festes Set).
        config: Optional ueberschriebene Konfiguration (fuer Tests).

    Returns:
        `ComplexityReport` mit n_runs, RAM-Schaetzung und Ablehnungs-Gruenden.

    Example:
        >>> r = estimate_complexity({("SILVER", "M30"): 1000}, 1)
        >>> r.n_runs == 1 and r.ok
        True
    """
    cfg: Dict[str, Any] = {**DEFAULT_CONFIG, **(config or {})}
    combos = list(bar_counts.items())
    n_sets = max(int(n_param_sets), 1)
    n_runs = len(combos) * n_sets
    total_bars = sum(n for _, n in combos) * n_sets
    per_run_bars = max([n for _, n in combos], default=0)

    bytes_per_bar = float(cfg["est_bytes_per_bar"])
    overhead_mb = float(cfg["est_overhead_mb_per_run"])

    est_ram_per_run_mb = per_run_bars * bytes_per_bar / 1e6 + overhead_mb
    est_ram_total_mb = total_bars * bytes_per_bar / 1e6 + n_runs * overhead_mb

    max_ram_mb = float(cfg["max_ram_mb"])
    max_runs = int(cfg["max_runs"])

    reasons: list[str] = []
    warnings: list[str] = []
    if n_runs > max_runs:
        reasons.append(
            f"Run-Anzahl {n_runs} überschreitet das Limit von {max_runs}."
        )
    if est_ram_total_mb > max_ram_mb:
        reasons.append(
            f"Geschätzter RAM {est_ram_total_mb:,.0f} MB überschreitet "
            f"das Limit von {max_ram_mb:,.0f} MB."
        )
    warn_ram_mb = float(cfg["warn_ram_mb"])
    if est_ram_total_mb > warn_ram_mb:
        warnings.append(
            f"Warnung: Geschätzter RAM {est_ram_total_mb:,.0f} MB liegt über "
            f"dem Warnschwellwert von {warn_ram_mb:,.0f} MB."
        )

    return ComplexityReport(
        n_runs=n_runs,
        bars_total=total_bars,
        est_ram_total_mb=est_ram_total_mb,
        est_ram_per_run_mb=est_ram_per_run_mb,
        max_ram_mb=max_ram_mb,
        max_runs=max_runs,
        ok=not reasons,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


def go_allowed(report: Optional[ComplexityReport]) -> bool:
    """True, wenn der Lauf freigegeben ist (kein hartes Limit ueberschritten).

    Args:
        report: `ComplexityReport` aus `estimate_complexity` (None = keine
            Schaetzung moeglich -> Lauf NICHT freigeben).

    Returns:
        True nur bei `report.ok`.
    """
    return bool(report is not None and report.ok)
