"""
SETUP C - MONATS-KONSOLIDAT (scripts/setup_c_konsolidat.py)
===========================================================
Fasst mehrere Setup-C-Laeufe (beliebige Zeitraeume, die zuvor mit
``scripts.setup_c_profil`` erzeugt wurden) zu einer Monats-/Zeitraum-Tabelle
zusammen und zusaetzlich zu einem Gesamtaggregat je (Modus, Zeit-Horizont).

Datenquelle sind AUSSCHLIESSLICH die maschinenlesbaren Trade-Bloecke des
Kerns - es wird nichts neu simuliert und nichts geschrieben (ausser dem
optionalen ``--csv``):

  BASE  ``setup_c_trades_<LABEL>.tsv``               (F4 intrabar + Zeit-Exit)
        Horizonte 48 / 96 (via ``--horizonte=``).
  TR    ``setup_c_ab_trailing_trades_<LABEL>.tsv``   (EMA-Slope-Trailing,
        Variante B, §5.2). Horizont ist die Crash-Sicherung
        (``notfall_horizont_bars``, Default 300) und wird aus der Datei
        gelesen - kein Hardcoding.

Kennzahlen je (Modus, Label, Horizont):
  sum R    Summe r_f4 (RECHTS_ZENSIERT strikt isoliert = nicht gewertet, E2)
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
    python -m scripts.setup_c_konsolidat --modus=base
    python -m scripts.setup_c_konsolidat --labels=MAI26 --modus=tr --csv=x.csv

Optionen:
    --labels=LABEL[,LABEL...]  Explizite Reihenfolge. Default: alle
                               vorhandenen BASE-TSVs, sortiert, ohne die
                               Alias-Referenzanker AUG/S1/S2 (§2.14).
    --modus=alle|base|tr       Auszuweisende Varianten (Default alle).
    --horizonte=48,96          Horizonte der BASE-Variante (Default 48,96).
                               Fuer TR wird der Datei-Horizont verwendet.
    --dir=Pfad                 Reportordner (Default reports/setup_c).
    --csv=Pfad                 Optionaler CSV-Export der Tabelle (das
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

_TSV_BASE: str = "setup_c_trades_"
_TSV_TR: str = "setup_c_ab_trailing_trades_"

# Modus-Kennungen (Reihenfolge = Tabellenreihenfolge je Label)
MODI: Tuple[str, ...] = ("BASE", "TR")

__all__ = [
    "finde_labels",
    "zeitraum_aus_chart_txt",
    "kennzahlen",
    "main",
    "MODI",
]


def finde_labels(report_dir: Path, modus: str = "BASE") -> List[str]:
    """Alle konsolidierbaren Lauf-Labels eines Reportordners.

    Args:
        report_dir: Ordner mit ``setup_c_trades_<LABEL>.tsv`` bzw.
            ``setup_c_ab_trailing_trades_<LABEL>.tsv``.
        modus: ``BASE`` oder ``TR`` - bestimmt das Dateipraefix.

    Returns:
        Sortierte Labels ohne die Alias-Referenzanker (AUG/S1/S2).
    """
    praefix: str = _TSV_BASE if modus == "BASE" else _TSV_TR
    labels: List[str] = []
    for p in sorted(report_dir.glob(f"{praefix}*.tsv")):
        label: str = p.name[len(praefix) : -len(".tsv")]
        if label not in _ALIAS_LABELS:
            labels.append(label)
    return labels


def tsv_pfad(report_dir: Path, label: str, modus: str) -> Path:
    """Pfad des Trade-Blocks einer Variante.

    Args:
        report_dir: Reportordner.
        label: Lauf-Label.
        modus: ``BASE`` oder ``TR``.

    Returns:
        Pfad der TSV-Datei.
    """
    praefix: str = _TSV_BASE if modus == "BASE" else _TSV_TR
    return report_dir / f"{praefix}{label}.tsv"


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
    """Kennzahlen eines (Label, Modus, Horizont)-Laufs in Exit-Reihenfolge.

    Args:
        trades: Trade-DataFrame eines Labels (TSV-Inhalt).
        horizont: Zeit-Horizont (Bars); BASE 48/96, TR = Crash-Sicherung.

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


def reihe(
    trades: pd.DataFrame, horizont: int
) -> np.ndarray:
    """Gewertete r_f4 eines Laufs in Exit-Reihenfolge (Aggregat-Basis).

    Args:
        trades: Trade-DataFrame eines Labels.
        horizont: Zeit-Horizont (Bars).

    Returns:
        float64-Array der gewerteten r_f4 (RECHTS_ZENSIERT isoliert, E2).
    """
    dh: pd.DataFrame = trades[
        (trades["horizont"] == horizont)
        & (trades["exit_grund"] != "RECHTS_ZENSIERT")
    ].sort_values("exit_idx")
    r: np.ndarray = dh["r_f4"].to_numpy(dtype=float)
    return r[np.isfinite(r)]


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
    """CLI-Einstieg: Monatstabelle + Gesamtaggregat je (Modus, Horizont).

    Args:
        argv: Argumentliste (Default: ``sys.argv[1:]``).

    Returns:
        Exit-Code 0 bei Erfolg, 1 bei fehlenden TSV-Dateien.
    """
    ap = argparse.ArgumentParser(
        description="Setup-C Monats-Konsolidat aus den Trade-TSVs (rein lesend)."
    )
    ap.add_argument("--labels", default=None, help="Komma-Liste (Default: alle)")
    ap.add_argument("--modus", default="alle", choices=("alle", "base", "tr"),
                    help="BASE, TR oder alle (Default)")
    ap.add_argument("--horizonte", default="48,96", help="z. B. 48,96 (nur BASE)")
    ap.add_argument("--dir", default=str(_DEFAULT_DIR), help="Reportordner")
    ap.add_argument("--csv", default=None, help="Optionaler CSV-Export")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))

    report_dir: Path = Path(ns.dir)
    horizonte_base: List[int] = [
        int(x) for x in str(ns.horizonte).split(",") if x.strip()
    ]
    modi: Tuple[str, ...] = (
        MODI if ns.modus == "alle"
        else (("BASE",) if ns.modus == "base" else ("TR",))
    )
    labels: List[str] = (
        [x.strip() for x in str(ns.labels).split(",") if x.strip()]
        if ns.labels
        else finde_labels(report_dir, modus="BASE")
    )
    if not labels:
        print(f"FEHLER: keine {_TSV_BASE}*.tsv in {report_dir}")
        return 1

    # --- Varianten einlesen (fehlende Variante = uebersprungen, mit Hinweis)
    vorhanden: Dict[str, pd.DataFrame] = {}
    for modus in modi:
        for lb in labels:
            p: Path = tsv_pfad(report_dir, lb, modus)
            if p.is_file():
                vorhanden[f"{modus}|{lb}"] = pd.read_csv(
                    p, sep="\t", comment="#"
                )
            else:
                print(f"HINWEIS: {modus} fehlt fuer {lb}: {p.name}")

    kopf: str = (
        "{:<5} {:<8} {:<25} {:>3} {:>3} {:>4} {:>5} {:>9} {:>8} {:>7} {:>8} {:>6}"
    )
    print("=" * 112)
    print("SETUP C RAW-CLUSTER A | KONSOLIDAT (BASE = F4 intrabar + Zeit-Exit, "
          "TR = EMA-Slope-Trailing Variante B)")
    print("=" * 112)
    print(kopf.format("Modus", "Label", "Zeitraum (BKZ)", "N", "n", "gew", "zens",
                      "sum R", "WR", "PF", "MDD", "HD"))
    zeilen_csv: List[Dict[str, object]] = []
    per_key: Dict[Tuple[str, int], List[np.ndarray]] = {}
    for lb in labels:
        zr: str = zeitraum_aus_chart_txt(report_dir, lb)
        for modus in modi:
            df: Optional[pd.DataFrame] = vorhanden.get(f"{modus}|{lb}")
            if df is None:
                continue
            horizont_liste: List[int] = (
                horizonte_base
                if modus == "BASE"
                else sorted(int(h) for h in df["horizont"].unique())
            )
            for h in horizont_liste:
                k: Dict[str, float] = kennzahlen(df, h)
                r: np.ndarray = reihe(df, h)
                per_key.setdefault((modus, h), []).append(r)
                print(kopf.format(
                    modus, lb, zr, str(h), _fmt(k["n"], ".0f"),
                    _fmt(k["n"] - k["n_zensiert"], ".0f"),
                    _fmt(k["n_zensiert"], ".0f"),
                    f"{k['sum_r']:+.2f}",
                    f"{k['wr']:.1f}%" if np.isfinite(k["wr"]) else "-",
                    _fmt(k["pf"]),
                    f"{k['mdd']:+.2f}" if np.isfinite(k["mdd"]) else "-",
                    _fmt(k["hd"], ".0f"),
                ))
                zeilen_csv.append(
                    {"modus": modus, "label": lb, "zeitraum": zr, "horizont": h, **k}
                )
        print("-" * 112)

    print()
    print("GESAMT je (Modus, Horizont) - alle Labels, fortlaufend in Exit-Reihenfolge:")
    for modus in modi:
        for h in sorted({hk for (mk, hk) in per_key if mk == modus}):
            r = np.concatenate(per_key[(modus, h)])
            if len(r) == 0:
                print(f"  {modus} N{h}: (keine gewerteten Trades)")
                continue
            pos: float = float(r[r > 0.0].sum())
            neg: float = float(-r[r < 0.0].sum())
            cum: np.ndarray = np.cumsum(r)
            mdd: float = float((cum - np.maximum.accumulate(cum)).min())
            print(
                f"  {modus} N{h:<3}: n={len(r):>2}  sum={r.sum():+8.2f}R  "
                f"mean={r.mean():+.2f}R  WR={np.mean(r > 0.0) * 100.0:5.1f}%  "
                f"PF={pos / neg:5.2f}  MDD={mdd:+.2f}R  "
                f"best={r.max():+7.2f}R  worst={r.min():+.2f}R"
            )
    print("=" * 112)

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
