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
  Δ N48    Differenz der Summe gegen die BASE-Referenz desselben Labels
           (Default ``--ref=48``); zeigt direkt, ob TR/N96 den N48-Ertrag
           schlaegt oder kostet
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
    python -m scripts.setup_c_konsolidat --trades            (Einzeltrade-Reihe)
    python -m scripts.setup_c_konsolidat --labels=MAI26 --modus=tr --csv=x.csv
    python -m scripts.setup_c_konsolidat --symbol=Brent      (nur _BRENT-Labels)

Optionen:
    --labels=LABEL[,LABEL...]  Explizite Reihenfolge. Default: alle
                               vorhandenen BASE-TSVs, sortiert, ohne die
                               Alias-Referenzanker AUG/S1/S2 (§2.14).
                               Bei expliziter Angabe werden die Labels
                               unveraendert verwendet (--symbol filtert nur
                               die automatische Ermittlung).
    --symbol=SYM               Nur Labels DIESES Instruments (Suffix ueber
                               ``setup_c_profil.symbol_suffix``, z. B.
                               ``Brent`` -> ``_BRENT``). Verhindert, dass
                               Brent- und Silber-Laeufe in EIN Gesamtaggregat
                               gemischt werden. Default: kein Filter.
    --modus=alle|base|tr       Auszuweisende Varianten (Default alle).
    --horizonte=48,96          Horizonte der BASE-Variante (Default 48,96).
                               Fuer TR wird der Datei-Horizont verwendet.
    --ref=48                   Referenz-Horizont der Spalte Δ N48.
    --trades                   Zusaetzlich je Lauf die Einzeltrade-Reihe
                               r_f4 in Exit-Reihenfolge ausgeben.
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

# Direktaufruf (``python scripts/setup_c_konsolidat.py``) legt nur ``scripts/``
# auf den Modulpfad -> der Namespace-Import ``scripts.*`` scheitert. Der Guard
# stellt die Projekt-Wurzel voran und macht BEIDE Aufrufarten gueltig; beim
# ``-m``-Aufruf ist ``__package__`` gesetzt und der Guard ist inaktiv.
if __package__ in (None, ""):
    _projekt_root: Path = Path(__file__).resolve().parent.parent
    if str(_projekt_root) not in sys.path:
        sys.path.insert(0, str(_projekt_root))

# SSoT der Label-/Instrumenten-Namensraumbildung (identisch zum Profil-Kern).
from scripts.setup_c_profil import symbol_suffix

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


def finde_labels(
    report_dir: Path, modus: str = "BASE", symbol: Optional[str] = None
) -> List[str]:
    """Alle konsolidierbaren Lauf-Labels eines Reportordners.

    Args:
        report_dir: Ordner mit ``setup_c_trades_<LABEL>.tsv`` bzw.
            ``setup_c_ab_trailing_trades_<LABEL>.tsv``.
        modus: ``BASE`` oder ``TR`` - bestimmt das Dateipraefix.
        symbol: Optionaler Instrumenten-Filter. ``None`` = kein Filter;
            andernfalls bleiben nur Labels mit dem Suffix
            ``symbol_suffix(symbol)`` uebrig (z. B. ``Brent`` -> ``_BRENT``),
            damit verschiedene Instrumente nicht in EIN Gesamtaggregat
            gemischt werden.

    Returns:
        Sortierte Labels ohne die Alias-Referenzanker (AUG/S1/S2).
    """
    praefix: str = _TSV_BASE if modus == "BASE" else _TSV_TR
    suffix: str = symbol_suffix(symbol) if symbol else ""
    labels: List[str] = []
    for p in sorted(report_dir.glob(f"{praefix}*.tsv")):
        label: str = p.name[len(praefix) : -len(".tsv")]
        if label in _ALIAS_LABELS:
            continue
        if suffix:
            if not label.endswith(suffix):
                continue
            if label[: -len(suffix)] in _ALIAS_LABELS:
                continue
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


def trade_reihe(
    trades: pd.DataFrame, horizont: int
) -> List[Tuple[str, float, str, int]]:
    """Einzeltrades eines Laufs in Exit-Reihenfolge (Nachweis-Reihe).

    Args:
        trades: Trade-DataFrame eines Labels.
        horizont: Zeit-Horizont (Bars).

    Returns:
        Liste ``(entry_ts, r_f4, exit_grund, haltezeit_bars)`` je gewertetem
        Trade, chronologisch nach ``exit_idx`` (RECHTS_ZENSIERT isoliert).
    """
    dh: pd.DataFrame = trades[
        (trades["horizont"] == horizont)
        & (trades["exit_grund"] != "RECHTS_ZENSIERT")
    ].sort_values("exit_idx")
    out: List[Tuple[str, float, str, int]] = []
    for _, row in dh.iterrows():
        r: float = float(row["r_f4"])
        if not np.isfinite(r):
            continue
        out.append(
            (
                str(row["entry_ts"])[:16],
                r,
                str(row["exit_grund"]),
                int(row["haltezeit_bars"]),
            )
        )
    return out


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
    ap.add_argument("--symbol", default=None,
                    help="Nur Labels dieses Instruments (z. B. Brent -> _BRENT)")
    ap.add_argument("--modus", default="alle", choices=("alle", "base", "tr"),
                    help="BASE, TR oder alle (Default)")
    ap.add_argument("--horizonte", default="48,96", help="z. B. 48,96 (nur BASE)")
    ap.add_argument("--ref", type=int, default=48,
                    help="Referenz-Horizont der Spalte dN (Default 48)")
    ap.add_argument("--trades", action="store_true",
                    help="Einzeltrade-Reihe r_f4 ausgeben")
    ap.add_argument("--dir", default=str(_DEFAULT_DIR), help="Reportordner")
    ap.add_argument("--csv", default=None, help="Optionaler CSV-Export")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))

    report_dir: Path = Path(ns.dir)
    horizont_ref: int = int(ns.ref)
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
        else finde_labels(report_dir, modus="BASE", symbol=ns.symbol)
    )
    if not labels:
        sym_hinweis: str = (
            f" (Symbol-Filter: --symbol={ns.symbol})" if ns.symbol else ""
        )
        print(f"FEHLER: keine {_TSV_BASE}*.tsv in {report_dir}{sym_hinweis}")
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

    # --- Referenzsummen je Label (BASE @ --ref) fuer die Spalte dN ----------
    ref_summe: Dict[str, float] = {}
    for lb in labels:
        df_ref: Optional[pd.DataFrame] = vorhanden.get(f"BASE|{lb}")
        if df_ref is not None:
            ref_summe[lb] = float(kennzahlen(df_ref, horizont_ref)["sum_r"])

    kopf: str = (
        "{:<5} {:<8} {:<24} {:>3} {:>3} {:>5} {:>5} {:>9} {:>9} {:>8} {:>7} "
        "{:>8} {:>6}"
    )
    print("=" * 112)
    print("SETUP C RAW (live-kausal) | KONSOLIDAT (BASE = F4 intrabar + "
          "Zeit-Exit, TR = EMA-Slope-Trailing Variante B)")
    if ns.symbol:
        print(f"Instrumenten-Filter: --symbol={ns.symbol} "
              f"(Label-Suffix '{symbol_suffix(ns.symbol)}')")
    print("=" * 112)
    print(kopf.format("Modus", "Label", "Zeitraum (BKZ)", "N", "n", "gew", "zens",
                      "sum R", f"dN{horizont_ref}", "WR", "PF", "MDD", "HD"))
    zeilen_csv: List[Dict[str, object]] = []
    per_key: Dict[Tuple[str, int], List[np.ndarray]] = {}
    reihen: List[Tuple[str, str, int, float, List[Tuple[str, float, str, int]]]] = []
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
                # dN nur fuer Nicht-Referenz-Zeilen (Ref selbst = "-")
                ist_ref: bool = modus == "BASE" and h == horizont_ref
                d_ref: float = float("nan")
                if not ist_ref and lb in ref_summe:
                    d_ref = k["sum_r"] - ref_summe[lb]
                print(kopf.format(
                    modus, lb, zr, str(h),
                    _fmt(k["n_kandidaten"], ".0f"),
                    _fmt(k["n"], ".0f"),
                    _fmt(k["n_zensiert"], ".0f"),
                    f"{k['sum_r']:+.2f}",
                    "-" if ist_ref else f"{d_ref:+.2f}",
                    f"{k['wr']:.1f}%" if np.isfinite(k["wr"]) else "-",
                    _fmt(k["pf"]),
                    f"{k['mdd']:+.2f}" if np.isfinite(k["mdd"]) else "-",
                    _fmt(k["hd"], ".0f"),
                ))
                zeilen_csv.append(
                    {"modus": modus, "label": lb, "zeitraum": zr, "horizont": h,
                     "delta_ref": d_ref, **k}
                )
                if ns.trades:
                    reihen.append((modus, lb, h, k["sum_r"], trade_reihe(df, h)))
        print("-" * 121)

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

    # --- Einzeltrade-Reihe (--trades): Nachweis der Aggregat-Zahlen ----------
    if ns.trades:
        print()
        print("EINZELTRADES je (Modus, Label, Horizont) - Exit-Reihenfolge "
              "(gewertet, RECHTS_ZENSIERT isoliert):")
        for modus, lb, h, s, tr in reihen:
            print(f"  {modus} {lb} N{h:<3} n={len(tr):>2}  sum={s:+.2f}R")
            for entry_ts, r, grund, hd in tr:
                print(f"      {entry_ts}  {r:+7.2f}R  {grund:<14} {hd:>3} Bars")
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
