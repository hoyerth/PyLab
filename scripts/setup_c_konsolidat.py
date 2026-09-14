"""
SETUP C - MONATS-KONSOLIDAT (scripts/setup_c_konsolidat.py)
===========================================================
Fasst mehrere Setup-C-Laeufe (beliebige Zeitraeume, die zuvor mit
``scripts.setup_c_profil`` erzeugt wurden) zu einer Monats-/Zeitraum-Tabelle
zusammen und zusaetzlich zu einem Gesamtaggregat je Zeit-Horizont.

Datenquelle sind AUSSCHLIESSLICH die maschinenlesbaren Trade-Bloecke
``reports/setup_c/setup_c_trades_<LABEL>.tsv`` (Kern-Export). Es wird nichts
neu simuliert und nichts geschrieben - der Lauf ist rein lesend
(``--dir=`` erlaubt einen abweichenden Reportordner).

Kennzahlen je (Label, Horizont):
  sum R    Summe r_f4 (F4-Stop intrabar bzw. Exit-Grund, RECHTS_ZENSIERT
           strikt isoliert = nicht gewertet, E2)
  WR       Winrate der gewerteten Trades
  PF       Profit-Faktor (Summe Gewinne / Summe |Verluste|)
  MDD      maximaler Rueckgang der R-Kumulation in EXIT-Reihenfolge
           (Equity-Logik; reine Statistik - es wird kein Equity-Chart
           gezeichnet)
  HD       mittlere Haltedauer in Bars (gewertet)

Reihenfolge-Invariante: Gewertet wird in Exit-Reihenfolge (``exit_idx``),
damit MDD/Serien der Chart-Statistikbox entsprechen. Die Summe ist von der
Reihenfolge unabhaengig.

Aufruf (Projekt-Root, Namespace-Package):
    python -m scripts.setup_c_konsolidat
    python -m scripts.setup_c_konsolidat --labels=MAI26,JUN26,JUL26,AUG26
    python -m scripts.setup_c_konsolidat --horizonte=48

Optionen:
    --labels=LABEL[,LABEL...]  Explizite Reihenfolge der zu konsolidierenden
                               Laeufe. Default: alle vorhandenen
                               ``setup_c_trades_*.tsv``, sortiert, ohne die
                               Alias-Referenzanker AUG/S1/S2 (§2.14).
    --horizonte=48,96          Auszuweisende Zeit-Horizonte (Default 48,96).
    --dir=Pfad                 Reportordner (Default reports/setup_c).
    --csv=Pfad                 Optionaler CSV-Export der Monatstabelle (das
                               einzige Schreiben; ohne Angabe rein lesend).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

_PROJEKT_ROOT: Path = Path(__file__).resolve().parent.parent
_DEFAULT_DIR: Path = _PROJEKT_ROOT / "reports" / "setup_c"

# Alias-Referenzanker aus setup_c_profil.FENSTER_DEFS: nicht Teil eines
# Monats-Konsolidats (eigene §2.14-Verifikationsfenster).
_ALIAS_LABELS: Tuple[str, ...] = ("AUG", "S1", "S2")

_TSV_PRAEFIX: str = "setup_c_trades_"

__all__ = ["finde_labels", "zeitraum_aus_chart_txt", "kennzahlen", "main"]


def finde_labels(report_dir: Path) -> List[str]:
    """Alle konsolidierbaren Lauf-Labels eines Reportordners.

    Args:
        report_dir: Ordner mit ``setup_c_trades_<LABEL>.tsv``.

    Returns:
        Sortierte Labels ohne die Alias-Referenzanker (AUG/S1/S2).
    """
    labels: List[str] = []
    for p in sorted(report_dir.glob(f"{_TSV_PRAEFIX}*.tsv")):
        label: str = p.name[len(_TSV_PRAEFIX) : -len(".tsv")]
        if label not in _ALIAS_LABELS:
            labels.append(label)
    return labels


def zeitraum_aus_chart_txt(report_dir: Path, label: str) -> str:
    """Liest die Zeile ``Zeitraum: a .. b`` aus dem Chart-TXT (falls da).

    Args:
        report_dir: Reportordner.
        label: Lauf-Label.

    Returns:
        Zeitraum-String oder ``"-"`` (Chart-TXT fehlt/keine Zeile).
    """
    txt: Path = report_dir / f"setup_c_chart_{label}.txt"
    if not txt.is_file():
        return "-"
    for zeile in txt.read_text(encoding="utf-8").splitlines():
        if zeile.startswith("Zeitraum: "):
            return zeile.split(": ", 1)[1].replace("  (ende-exklusiv)", "")
    return "-"


def kennzahlen(trades: pd.DataFrame, horizont: int) -> Dict[str, float]:
    """Kennzahlen eines (Label, Horizont)-Laufs in Exit-Reihenfolge.

    Args:
        trades: Trade-DataFrame eines Labels (TSV-Inhalt).
        horizont: Zeit-Horizont (Bars).

    Returns:
        Dict mit ``n``, ``n_kandidaten``, ``n_zensiert``, ``sum_r``,
        ``mean_r``, ``wr``, ``pf``, ``mdd``, ``hd``.
    """
    dh: pd.DataFrame = trades[trades["horizont"] == horizont]
    n_zensiert: int = int((dh["exit_grund"] == "RECHTS_ZENSIERT").sum())
    gew: pd.DataFrame = dh[dh["exit_grund"] != "RECHTS_ZENSIERT"].sort_values(
        "exit_idx"
    )
    r: np.ndarray = gew["r_f4"].to_numpy(dtype=float)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return {
            "n": 0.0, "n_kandidaten": float(len(dh)), "n_zensiert": float(n_zensiert),
            "sum_r": 0.0, "mean_r": float("nan"), "wr": float("nan"),
            "pf": float("nan"), "mdd": 0.0, "hd": float("nan"),
        }
    pos: float = float(r[r > 0.0].sum())
    neg: float = float(-r[r < 0.0].sum())
    cum: np.ndarray = np.cumsum(r)
    return {
        "n": float(len(r)),
        "n_kandidaten": float(len(dh)),
        "n_zensiert": float(n_zensiert),
        "sum_r": float(r.sum()),
        "mean_r": float(r.mean()),
        "wr": float(np.mean(r > 0.0) * 100.0),
        "pf": pos / neg if neg > 0.0 else float("inf"),
        "mdd": float((cum - np.maximum.accumulate(cum)).min()),
        "hd": float(gew["haltezeit_bars"].to_numpy(dtype=float).mean()),
    }


def _fmt(v: float, f: str = ".2f") -> str:
    """Formatiert Zahlen; NaN/inf -> '-'.

    Args:
        v: Wert.
        f: Format-String.

    Returns:
        Formatierter String.
    """
    if not np.isfinite(v):
        return "-"
    return f"{v:{f}}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI-Einstieg: Monatstabelle + Gesamtaggregat je Horizont.

    Args:
        argv: Argumentliste (Default: ``sys.argv[1:]``).

    Returns:
        Exit-Code 0 bei Erfolg, 1 bei fehlenden TSV-Dateien.
    """
    ap = argparse.ArgumentParser(
        description="Setup-C Monats-Konsolidat aus den Trade-TSVs (rein lesend)."
    )
    ap.add_argument("--labels", default=None, help="Komma-Liste (Default: alle)")
    ap.add_argument("--horizonte", default="48,96", help="z. B. 48,96")
    ap.add_argument("--dir", default=str(_DEFAULT_DIR), help="Reportordner")
    ap.add_argument("--csv", default=None, help="Optionaler CSV-Export")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))

    report_dir: Path = Path(ns.dir)
    horizonte: List[int] = [int(x) for x in str(ns.horizonte).split(",") if x.strip()]
    labels: List[str] = (
        [x.strip() for x in str(ns.labels).split(",") if x.strip()]
        if ns.labels
        else finde_labels(report_dir)
    )
    if not labels:
        print(f"FEHLER: keine {_TSV_PRAEFIX}*.tsv in {report_dir}")
        return 1

    daten: Dict[str, pd.DataFrame] = {}
    for lb in labels:
        p: Path = report_dir / f"{_TSV_PRAEFIX}{lb}.tsv"
        if not p.is_file():
            print(f"FEHLER: fehlt: {p}")
            return 1
        daten[lb] = pd.read_csv(p, sep="\t", comment="#")

    kopf: str = (
        "{:<8} {:<25} {:>3} {:>3} {:>4} {:>5} {:>9} {:>8} {:>7} {:>8} {:>6}"
    )
    print("=" * 104)
    print("SETUP C RAW-CLUSTER A | KONSOLIDAT (r_f4, F4-Stop intrabar + Zeit-Exit)")
    print("=" * 104)
    print(kopf.format("Label", "Zeitraum (BKZ)", "N", "n", "gew", "zens",
                      "sum R", "WR", "PF", "MDD", "HD"))
    zeilen_csv: List[Dict[str, object]] = []
    per_h: Dict[int, List[np.ndarray]] = {h: [] for h in horizonte}
    for lb in labels:
        zr: str = zeitraum_aus_chart_txt(report_dir, lb)
        for h in horizonte:
            k: Dict[str, float] = kennzahlen(daten[lb], h)
            gew: pd.DataFrame = daten[lb][
                (daten[lb]["horizont"] == h)
                & (daten[lb]["exit_grund"] != "RECHTS_ZENSIERT")
            ].sort_values("exit_idx")
            r: np.ndarray = gew["r_f4"].to_numpy(dtype=float)
            per_h[h].append(r[np.isfinite(r)])
            print(kopf.format(
                lb, zr, str(h), _fmt(k["n"], ".0f"),
                _fmt(k["n"] - k["n_zensiert"], ".0f"), _fmt(k["n_zensiert"], ".0f"),
                f"{k['sum_r']:+.2f}", f"{k['wr']:.1f}%" if np.isfinite(k["wr"]) else "-",
                _fmt(k["pf"]), f"{k['mdd']:+.2f}" if np.isfinite(k["mdd"]) else "-",
                _fmt(k["hd"], ".0f"),
            ))
            zeilen_csv.append({"label": lb, "zeitraum": zr, "horizont": h, **k})
        print("-" * 104)

    print()
    print("GESAMT je Horizont (alle Labels, fortlaufend in Exit-Reihenfolge):")
    for h in horizonte:
        r = np.concatenate(per_h[h]) if per_h[h] and len(per_h[h][0]) else None
        if r is None or len(r) == 0:
            print(f"  N{h}: (keine gewerteten Trades)")
            continue
        pos: float = float(r[r > 0.0].sum())
        neg: float = float(-r[r < 0.0].sum())
        cum: np.ndarray = np.cumsum(r)
        mdd: float = float((cum - np.maximum.accumulate(cum)).min())
        print(
            f"  N{h}: n={len(r):>2}  sum={r.sum():+8.2f}R  mean={r.mean():+.2f}R  "
            f"WR={np.mean(r > 0.0) * 100.0:5.1f}%  "
            f"PF={pos / neg:5.2f}  MDD={mdd:+.2f}R  "
            f"best={r.max():+7.2f}R  worst={r.min():+.2f}R"
        )
    print("=" * 104)

    if ns.csv:
        ziel: Path = Path(ns.csv)
        with ziel.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(zeilen_csv[0].keys()))
            w.writeheader()
            w.writerows(zeilen_csv)
        print(f"CSV: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
