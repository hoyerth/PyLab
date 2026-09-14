# -*- coding: utf-8 -*-
"""READ-ONLY Sichtpruefung MAI/JUN/JUL -- V021-BASELINE, je Monat EIN PNG.

Auftrag (Anwender, 14.09.2026, H20.52 Paragraph 9 / Beschluss F3)
-----------------------------------------------------------------
Sichtpruefung der SAUBEREN V021-Baseline (35 / 28 / 21 Trades) -- NICHT des
V020-Tripels (58 / 56 / 68). Der Tripel-Pfad ist der in H20.48/H20.49
demaskierte Stand; er wurde in K4 nur zur Rueckverfolgung der Regression
reproduziert und wuerde als Marktbild erneut verfaelschen.

Darstellung (bindende Konventionen)
-----------------------------------
* Kerzen je Bar, X-Achse = BAR-ZEIT OHNE OFFSET (BKZ, Kanon K1/K4).
* Handlungsrelevante Kanten: NUR die Kids, die tatsaechlich getradet wurden,
  PLUS die jeweilige GEGENKANTE (dort sitzt ``tp2`` -- die arretierte
  Extremum-Zielwahl, H20.52 Paragraph 1).
* Trade-Kreise IMMER farbig gefuellt (``mfc=col``), LONG gruen / SHORT rot,
  gesetzt am ``entry_bar`` mit dem kausalen Preis ``entry``.
* Gestrichelte SL-TP2-Range je Trade; Label ``K<kid> <entry>`` + ``R``.
* ENDE-Exits (Fensterrand-Glattstellung, ``close[-1]``) magenta umringt --
  sie sind KEINE Marktereignisse, werden aber als realisierter R gebucht.
* KEIN Equity-/cumR-Panel (Anwender-Vorgabe 14.09.2026, H20.52 Paragraph 8).
  Die cumR-Kennzahlen bleiben als ZAHLEN im Statistikblock.
* Statistik mittig, Legende oben links, Titel ``... (Bars 0..n-1)``.
* Statistikblock traegt die Konzentrationszeile (F6/F18) und die
  diagnostischen Spalten ``crvExt`` / ``crvNae`` / ``ordN`` (F12).

Diagnostik (KEINE Handelswirkung, H20.52 Paragraph 11)
------------------------------------------------------
Je Trade werden ``dist_extremum_usd``, ``dist_naechste_usd``, ``crv_extremum``,
``crv_naechste`` und ``ordnung_naechste_poc_erfuellt`` ausgewiesen. Die
Auswahl der NAEECHSTEN Gegenkante ist gespiegelt zu ``_gegenkante_extern``
(Befund B), aber auf den ZULAESSIGKEITS-HALBRAUM der Engine beschraenkt
(Befund D: ``kein_raum``, Basis-Repo Z. 2677-2692). Sie wird aus
``_chk_mai_juli_gegenkante.py`` importiert (F16: keine
Funktionsverdopplung). Referenz-Bar ist der SIGNAL-Bar ``t.bar``
(Praezisierung K1), NICHT der Entry-Bar.

Der Halbraum ist zwingend: ohne ihn waehlt der reine Spiegel mitunter eine
Kante diesseits der getradeten Basis -- ein Niveau, das der Motor nie als
Ziel zulaesst. Mit Halbraum reproduziert die Diagnostik F3
(``_chk_u3_spec_beleg.py``) exakt: ordN 8/35, 4/28, 9/21 und crvNae-Median
1.36 / 2.50 / 1.80.

ADDITIV -- Motoren/Adapter/Handoff bleiben byte-identisch (SHA-Guard).

Aufruf:
    .venv\\Scripts\\python.exe test\\_render_mai_jun_jul.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Literal, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
V021_PFAD = ROOT / "test" / "tmp_kanten_engine_v021_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
EXT_REND_PFAD = ROOT / "test" / "tmp_png_ext_sichttest_v2.py"
GK_PFAD = ROOT / "test" / "_chk_mai_juli_gegenkante.py"

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
V021_SHA_SOLL = (
    "cda9e5b189ed4137198795e1547cec00436dffe64222434bb6ec4c448e598e89")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

# --- Sichtpruefungsstand (Beschluss F3) -------------------------------------
# "BASELINE" = V021-Defaults, ``ist_legacy`` True -> Delegation an
# ``B._se_trades`` (tmp_kanten_engine_v021_replay.py Zeile 545/546),
# bit-identisch per Konstruktion. "TRIPEL" ist BEWUSST NICHT implementiert.
STAND: Literal["BASELINE"] = "BASELINE"

MONATE: Tuple[Tuple[str, str, str, str], ...] = (
    ("MAI", "2026-05-01", "2026-06-01", "2026-05-29"),
    ("JUN", "2026-06-01", "2026-07-01", "2026-06-30"),
    ("JUL", "2026-07-01", "2026-08-01", "2026-07-31"),
)
# Sollwerte der V021-BASELINE. Doppelt belegt: H20.51 Paragraph 1
# (Legacy-Spalte) und _chk_u3_schwanz_last_out.txt. Kein Hardcoding-Ersatz --
# der Lauf MUSS sie reproduzieren, sonst Abbruch (fail-loud).
SOLL: Dict[str, Tuple[int, float]] = {
    "MAI": (35, 38.318126), "JUN": (28, -11.421155), "JUL": (21, -4.325355)}

C_UP, C_DN = "#3d8f6d", "#c05656"
C_LONG, C_SHORT = "#2ca02c", "#d62728"
C_KANTE = "#7f7f7f"
C_GEG = "#a0522d"          # Gegenkante (Traeger von tp2 = Extremum)
C_ENDE = "#d500f9"         # ENDE-Exit (Fensterrand-Glattstellung)
C_TRAEGER = "#b8860b"      # Traeger-Trade (groesster Einzeltrade), F20
C_TOUCH_OBEN, C_TOUCH_UNTEN = "#8b0000", "#004d00"

OUT_PROTOKOLL = ROOT / "test" / "render_mai_jun_jul_baseline_out.txt"


@dataclass(frozen=True, slots=True)
class DiagnostischeZielKennzahlen:
    """Diagnostische Ziel-/Erreichbarkeitsmetriken je Trade (keine Wirkung).

    Datenvertrag H20.52 Paragraph 11 (F10). Die Kennzahlen dienen
    ausschliesslich der Beobachtung der Gegenliquiditaet (F5); ``tp2`` bleibt
    das Extremum.

    Kausalitaet: ``naechste_kante_preis`` ist ``gegen.basis_bei(t.bar)`` --
    die kausale Basis am SIGNAL-Bar, NIE die statische Provenienz
    ``gegen.basis`` (K1).

    Fehlende Gegenkante: ``naechste_kante_preis``, ``dist_naechste_usd`` und
    ``crv_naechste`` sind dann ``float("nan")``, niemals 0.0.
    """

    kid: int
    signal_bar: int
    entry_bar: int
    entry_preis: float
    extremum_preis: float
    naechste_kante_preis: float
    dist_extremum_usd: float
    dist_naechste_usd: float
    crv_extremum: float
    crv_naechste: float
    ordnung_naechste_poc_erfuellt: bool
    ziel_klasse: ClassVar[Literal["EXTREMUM"]] = "EXTREMUM"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _assert_shas() -> None:
    for p, soll in ((BASELINE_PFAD, BASELINE_SHA_SOLL),
                    (V020_PFAD, V020_SHA_SOLL),
                    (V021_PFAD, V021_SHA_SOLL),
                    (ADAPTER_PFAD, ADAPTER_SHA_SOLL)):
        ist = _sha(p)
        assert ist == soll, (
            f"Fremdstand {p.name}: {ist[:16]}... != {soll[:16]}...")


class _StdoutStub:
    """fd-freier stdout-Ersatz (Module haengen beim Import stdout um)."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _lade(name: str, p: Path) -> Any:
    real = sys.stdout
    try:
        sys.stdout = _StdoutStub()  # type: ignore[assignment]
        spec = importlib.util.spec_from_loader(name, loader=None)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        mod.__file__ = str(p)
        sys.modules[name] = mod
        exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"),
             mod.__dict__)
    finally:
        sys.stdout = real
    return mod


def _lade_fenster_lokal(B: Any, start: str, ende: str) -> Any:
    """Fenster laden. 'LAB' lebt nur waehrend des Ladevorgangs (read-only)."""
    B.FENSTER["LAB"] = (start, ende)
    try:
        return B._lade_fenster("LAB")
    finally:
        del B.FENSTER["LAB"]


def _monat_scan(B: Any, V: Any, start: str, ende: str
                ) -> Tuple[Dict[str, Any], List[Any], int, Any]:
    """Scan + V021-BASELINE-Trades eines Monats (Vollauf, ``box_end_bar = n``).

    Befund A (H20.52 Paragraph 9): ``B`` MUSS die Modulinstanz von
    ``V._engine()`` sein. Eine zweite Instanz (etwa ueber ``run_lab._load``)
    haette ein EIGENES ``FENSTER``-Dict und ein eigenes ``_lade_fenster`` --
    jeder Patch liefe ins Leere und ``_se_scan('LAB', ...)`` scheiterte mit
    ``KeyError``.

    Args:
        B: Die Modulinstanz ``V._engine()`` (Baseline, read-only).
        V: Die V021-Kapsel.
        start: BKZ-Startdatum (inklusiv).
        ende: BKZ-Enddatum (exklusiv).

    Returns:
        ``(scan, trades, n, dataframe)`` -- ``trades`` stammen aus dem
        Default-Vertrag (``ist_legacy`` True -> Delegation an
        ``B._se_trades``, Zeile 545/546) und sind damit bit-identisch.
    """
    d = _lade_fenster_lokal(B, start, ende)
    n = int(len(d))
    original = B._lade_fenster
    B._lade_fenster = (lambda _f, _d=d: _d.copy())  # type: ignore
    try:
        scan = B._se_scan("LAB", B.StraightEdgeHarnessKonfiguration())
    finally:
        B._lade_fenster = original  # type: ignore
    scan = copy.deepcopy(scan)
    scan["box_end_bar"] = int(n)
    tr = V._lauf(scan, V.V021KantenKonfiguration(), box_end=n)
    tr = sorted(list(tr), key=lambda x: int(x.entry_bar))
    return scan, tr, n, d


def _diagnostik(G: Any, alle: Sequence[Any], t: Any
                ) -> DiagnostischeZielKennzahlen:
    """Diagnostische Zielkennzahlen eines Trades (keine Handelswirkung).

    Args:
        G: Modul ``_chk_mai_juli_gegenkante`` (Pool + Naechste + Ordnung).
        alle: ``scan['edges'] + scan['seeds']``.
        t: ``_SESetup``.

    Returns:
        Der Datenvertrag ``DiagnostischeZielKennzahlen``.
    """
    kk = int(t.bar)
    richtung = str(t.richtung)
    entry = float(t.entry)
    risiko = abs(float(t.sl) - entry)
    extrem = float(t.tp2)
    nae, _pool = G._naechste_kante_extern(alle, kk, richtung, float(t.basis))
    if nae is None:
        nae_preis = float("nan")
        dist_nae = float("nan")
        crv_nae = float("nan")
        ordnung = False
    else:
        nae_preis = float(nae.basis_bei(kk))
        dist_nae = abs(nae_preis - entry)
        crv_nae = (dist_nae / risiko) if risiko > 0.0 else float("nan")
        ordnung = bool(G.ordnung_poc_erfuellt(t, nae_preis))
    dist_ext = abs(extrem - entry)
    return DiagnostischeZielKennzahlen(
        kid=int(t.kid),
        signal_bar=kk,
        entry_bar=int(t.entry_bar),
        entry_preis=entry,
        extremum_preis=extrem,
        naechste_kante_preis=nae_preis,
        dist_extremum_usd=dist_ext,
        dist_naechste_usd=dist_nae,
        crv_extremum=(dist_ext / risiko) if risiko > 0.0 else float("nan"),
        crv_naechste=crv_nae,
        ordnung_naechste_poc_erfuellt=ordnung,
    )


def _traeger_marker(ax: Any, trades: Sequence[Any]) -> Any:
    """Traeger-Trade (groesster Einzeltrade) optisch hervorheben (F20).

    H20.52 Paragraph 3: Das Ergebnis der Monate haengt an EINEM weiten Treffer.
    Der Traeger darf nicht in einer Textzeile verschwinden -- er muss im
    Kerzenchart sofort ins Auge stechen: farbiger Ring (mfc=col, wie alle
    Trades), zusaetzlicher Kragen und Label mit Entry, R und Laufweg.

    Args:
        ax: Kurs-Panel.
        trades: Setups des Monats.

    Returns:
        Der markierte ``_SESetup`` (groesster ``r``).
    """
    tr_opt = max(trades, key=lambda t: float(t.r))
    x = int(tr_opt.entry_bar)
    col = C_SHORT if str(tr_opt.richtung) == "SHORT" else C_LONG
    ax.plot(x, float(tr_opt.entry), "o", ms=9.5, color=col, mec="#1a1a1a",
            mew=0.9, mfc=col, zorder=15)
    ax.plot(x, float(tr_opt.entry), "o", ms=26.0, mfc="none", mec=C_TRAEGER,
            mew=2.6, zorder=16)
    ax.annotate(
        f"TRAEGER K{int(tr_opt.kid)} {float(tr_opt.r):+.2f}R\n"
        f"entry {float(tr_opt.entry):.4f} -> tp2 {float(tr_opt.tp2):.4f}\n"
        f"Laufweg {abs(float(tr_opt.tp2) - float(tr_opt.entry)):.4f} USD "
        f"(SL {float(tr_opt.sl):.4f})",
        (x, float(tr_opt.entry)), textcoords="offset points", xytext=(0, -78),
        ha="center", va="top", fontsize=11.0, color="#000000", weight="bold",
        zorder=17,
        bbox=dict(boxstyle="round,pad=0.35", fc="#fff8e1", ec=C_TRAEGER,
                  lw=2.2, alpha=0.97),
        arrowprops=dict(arrowstyle="-", color=C_TRAEGER, lw=1.8))
    return tr_opt


def _marker_trades(ax: Any, trades: Sequence[Any]) -> None:
    """Kreise (mfc=col) am entry_bar, SL-TP2-Range, Label, ENDE-Ring.

    Lesbarkeit: LONG wird UNTER, SHORT UEBER dem Kreis beschriftet (die
    Richtung zeigt ins Kursinnere) und zusaetzlich zweistufig gestaffelt,
    damit dicht aufeinanderfolgende Signale nicht kollidieren.
    """
    for i, t in enumerate(trades):
        x = int(t.entry_bar)
        short = str(t.richtung) == "SHORT"
        col = C_SHORT if short else C_LONG
        ax.plot([x, x], [float(t.sl), float(t.tp2)], color=col, lw=1.1,
                alpha=0.45, ls=":", zorder=6)
        ax.plot(x, float(t.entry), "o", ms=9.5, color=col, mec="#1a1a1a",
                mew=0.9, mfc=col, zorder=12)
        if str(t.grund1) == "ENDE" or str(t.grund2) == "ENDE":
            ax.plot(x, float(t.entry), "o", ms=16.0, mfc="none", mec=C_ENDE,
                    mew=1.7, zorder=13)
        stag = 26 * (i % 2)
        dy = (-18 - stag) if short else (18 + stag)
        ax.annotate(f"K{t.kid} {float(t.entry):.4f}\n{float(t.r):+.2f}R "
                    f"sig {int(t.bar)}", (x, float(t.entry)),
                    textcoords="offset points", xytext=(0, dy), ha="center",
                    va="top" if short else "bottom", fontsize=7.0,
                    color=col, zorder=11,
                    bbox=dict(boxstyle="round,pad=0.16", fc="white",
                              alpha=0.88, ec=col, lw=0.6))


def _fmt(v: float, w: int = 6, p: int = 2) -> str:
    """NaN-feste Formatierung (Diagnostik kann nan tragen)."""
    if v != v:
        return f"{'n/a':>{w}s}"
    return f"{v:>{w}.{p}f}"


def _agg(werte: List[float]) -> Tuple[str, str, str]:
    """(min, median, max) als Text; leere Liste -> ('n/a', 'n/a', 'n/a').

    Notwendig, weil ``crv_naechste`` ``nan`` sein darf: ``min()``/``median()``
    ueber eine leere Liste wuerde werfen statt zu berichten.
    """
    if not werte:
        return "n/a", "n/a", "n/a"
    return (_fmt(min(werte)), _fmt(float(np.median(werte))), _fmt(max(werte)))


def _statblock(lab: str, start: str, endtag: str, n: int, trades: List[Any],
               dzk: List[DiagnostischeZielKennzahlen]) -> List[str]:
    """Statistikblock: Kennzahlen, Diagnostik, Konzentration (F6/F18)."""
    rs = [float(t.r) for t in trades]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    summe = float(sum(rs))
    pf = (sum(pos) / abs(sum(neg))) if neg else float("inf")
    risiko = [abs(float(t.sl) - float(t.entry)) for t in trades]
    bester = max(trades, key=lambda t: float(t.r))
    n_sl1 = sum(1 for t in trades if str(t.grund1) == "SL")
    n_sl2 = sum(1 for t in trades if str(t.grund2) == "SL")
    n_tp1 = sum(1 for t in trades if str(t.grund1) == "TP1")
    n_tp2 = sum(1 for t in trades if str(t.grund2) == "TP2")
    n_ende1 = sum(1 for t in trades if str(t.grund1) == "ENDE")
    n_ende2 = sum(1 for t in trades if str(t.grund2) == "ENDE")
    crv_e = [d.crv_extremum for d in dzk if d.crv_extremum == d.crv_extremum]
    crv_n = [d.crv_naechste for d in dzk if d.crv_naechste == d.crv_naechste]
    n_na = sum(1 for d in dzk if d.naechste_kante_preis != d.naechste_kante_preis)
    n_ord = sum(1 for d in dzk if d.ordnung_naechste_poc_erfuellt)
    e_min, e_med, e_max = _agg(crv_e)
    n_min, n_med, n_max = _agg(crv_n)
    tp2_w = sorted({round(float(t.tp2), 4) for t in trades})

    zeilen: List[str] = [
        f"{lab}  {start} .. {endtag} (BKZ, ohne Offset)   |   "
        f"Bars 0..{n - 1}   |   Vollauf box_end_bar = n   |   "
        f"STAND {STAND} (F3): V021-Defaults, ist_legacy=True, "
        f"Delegation an B._se_trades",
        f"Trades {len(trades)}   |   SumR {summe:+.6f} R   |   "
        f"Win-Rate {100.0 * len(pos) / len(rs):.2f} % ({len(pos)}/{len(neg)})"
        f"   |   Profit-Faktor {pf:.4f}",
        f"Risiko |sl-entry| USD:  min {min(risiko):.4f}   median "
        f"{float(np.median(risiko)):.4f}   max {max(risiko):.4f}   |   "
        f"TP2 distinct: {len(tp2_w)} "
        f"({', '.join(f'{v:.4f}' for v in tp2_w)})",
        f"Exits  1. Haelfte: TP1 {n_tp1} / SL {n_sl1} / ENDE {n_ende1}   |   "
        f"2. Haelfte: TP2 {n_tp2} / SL {n_sl2} / ENDE {n_ende2}   |   "
        f"magenta Ringe = ENDE-Glattstellung am Fensterrand "
        f"({sum(1 for t in trades if 'ENDE' in (str(t.grund1), str(t.grund2)))} "
        f"Trades betroffen)",
        f"KONZENTRATION: bester Trade K{int(bester.kid)} "
        f"({float(bester.r):+.6f} R, Risiko "
        f"{abs(float(bester.sl) - float(bester.entry)):.4f} USD) = "
        f"{100.0 * float(bester.r) / summe:.1f} % des SumR   ->   "
        f"SumR OHNE diesen Trade {summe - float(bester.r):+.6f} R",
        "",
        f"DIAGNOSTIK (F5, keine Handelswirkung): crvExt = "
        f"dist(entry,Extremum)/Risiko | crvNae = "
        f"dist(entry,NAECHSTE Kante)/Risiko (K1: Signal-Bar) | ordN = "
        f"sl<entry<poc<naechste bzw. gespiegelt | beide Ziele im "
        f"ZULAESSIGKEITS-HALBRAUM der Engine (kein_raum: LONG gegen_basis > "
        f"basis, SHORT < basis)",
        f"  crvExt : min {e_min} median {e_med} max {e_max}   "
        f"(n={len(crv_e)})",
        f"  crvNae : min {n_min} median {n_med} max {n_max}   "
        f"(n={len(crv_n)})",
        f"  ordN erfuellt: {n_ord} von {len(dzk)}   |   Gegenkanten-Pool leer "
        f"(nan): {n_na}   |   crvNae < 1.0: "
        f"{sum(1 for v in crv_n if v < 1.0)}   |   < 1.5: "
        f"{sum(1 for v in crv_n if v < 1.5)}",
        "",
        f"{'#':>3} {'Bar':>5} {'Kante':>6} {'Richt':>5} {'entry':>8} "
        f"{'SL':>8} {'Risiko':>7} {'poc':>8} {'tp2':>8} {'R':>10} "
        f"{'crvExt':>7} {'crvNae':>7} {'ordN':>5}",
    ]
    for i, t in enumerate(trades, 1):
        d = dzk[i - 1]
        zeilen.append(
            f"{i:>3} {int(t.bar):>5} {'K' + str(int(t.kid)):>6} "
            f"{str(t.richtung):>5} {float(t.entry):>8.4f} {float(t.sl):>8.4f} "
            f"{abs(float(t.sl) - float(t.entry)):>7.4f} {float(t.poc):>8.4f} "
            f"{float(t.tp2):>8.4f} {float(t.r):>+10.4f} "
            f"{_fmt(d.crv_extremum)} {_fmt(d.crv_naechste)} "
            f"{'JA' if d.ordnung_naechste_poc_erfuellt else 'nein':>5}")
    zeilen.append("")
    zeilen.append(
        f"DATEI-SHA256: {hashlib.sha256(BASELINE_PFAD.read_bytes()).hexdigest()[:16]}..."
        f"   (Basis/V020/V021/Adapter byte-identisch arretiert)")
    return zeilen


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    _assert_shas()
    # --- Befund A: EINE Modulinstanz, die dieselbe ist wie in der Kapsel ---
    V = importlib.import_module("tmp_kanten_engine_v021_replay")
    B = V._engine()
    G = _lade("gk_render", GK_PFAD)
    ext = _lade("ext_render", EXT_REND_PFAD)
    cfg = B.StraightEdgeHarnessKonfiguration()
    assert V.V021KantenKonfiguration().ist_legacy, (
        "Default-Vertrag ist nicht legacy -- Stand 'BASELINE' nicht gegeben.")

    z: List[str] = []
    z.append("SICHTPRUEFUNG MAI / JUN / JUL -- V021-BASELINE (F3), je Monat"
             " ein PNG, KEINE Equity-Grafik (H20.52 Paragraph 8)")
    z.append("Zeitbasis: BKZ = time AT TIME ZONE 'UTC' (Kanon K1/K4), keine")
    z.append("           Zeitzonen-Projektion, X-Achse = Bar-Zeit ohne Offset.")
    z.append(f"STAND {STAND} | touch_band_pct {cfg.touch_band_pct:.2f} | "
             f"sl_buffer_usd {cfg.sl_buffer_usd:.2f} | "
             f"tp1_anteil_pct {cfg.tp1_anteil_pct:.0f}")
    z.append("")

    for lab, start, ende, endtag in MONATE:
        scan, trades, n, d = _monat_scan(B, V, start, ende)
        ts = d["ts"].to_numpy().astype("datetime64[ns]")
        idx = np.arange(n)
        op = d["open"].to_numpy(dtype=float)
        hi = d["high"].to_numpy(dtype=float)
        lo = d["low"].to_numpy(dtype=float)
        cl = d["close"].to_numpy(dtype=float)
        wall = int(cfg.wall_live_bars)

        soll_n, soll_r = SOLL[lab]
        ist_r = round(float(sum(float(t.r) for t in trades)), 6)
        assert (len(trades), ist_r) == (soll_n, round(soll_r, 6)), (
            f"{lab}: Soll ({soll_n}, {soll_r}) != Ist ({len(trades)}, {ist_r})")

        alle = list(scan["edges"]) + list(scan["seeds"])
        dzk = [_diagnostik(G, alle, t) for t in trades]
        # Befund D, Regressionsbremse: das EXTREMUM (tp2) liegt per
        # Konstruktion im Zulaessigkeits-Halbraum der Engine; die Diagnostik
        # darf keinen Trade ausweisen, den der Vertrag verworfen haette.
        for t in trades:
            _b, _tp2 = float(t.basis), float(t.tp2)
            if str(t.richtung) == "SHORT":
                assert _tp2 < _b, (lab, int(t.kid), _b, _tp2)
            else:
                assert _tp2 > _b, (lab, int(t.kid), _b, _tp2)
        kids_trade = {int(t.kid) for t in trades}
        kids_geg: set = set()
        n_ident = 0
        for t in trades:
            geg, _pool = G._gegenkante_extern(alle, int(t.bar),
                                              str(t.richtung))
            # Regressionsbremse (portiert aus
            # `_chk_mai_juli_gegenkante.main()`): die nachgerechnete
            # EXTREMUM-Auswahl MUSS den arretierten `tp2` bit-identisch
            # treffen -- und es MUSS ueberhaupt eine Gegenkante geben (der
            # Motor verwirft Trades ohne Gegner als ``kein_gegner``).
            assert geg is not None, f"{lab}: kein Gegner fuer K{int(t.kid)}"
            _gbb = float(geg.basis_bei(int(t.bar)))
            assert abs(_gbb - float(t.tp2)) < 1e-9, (
                lab, int(t.kid), _gbb, float(t.tp2))
            n_ident += 1
            kids_geg.add(int(geg.kid))
        kanten = [e for e in alle if int(e.kid) in kids_trade]
        kanten_geg = [e for e in alle
                      if int(e.kid) in kids_geg and int(e.kid) not in kids_trade]

        y0, y1 = float(lo.min()), float(hi.max())

        fig = plt.figure(figsize=(34, 20))
        # KEINE Equity-Grafik: zwei Panels (Kurs + Statistik), height_ratios
        # ohne das ehemalige axc-cumR-Panel.
        gs = fig.add_gridspec(2, 1, height_ratios=[4.3, 0.85], hspace=0.09)
        ax = fig.add_subplot(gs[0])
        axs = fig.add_subplot(gs[1])

        ext._zeichne_kerzen(ax, 0, n - 1, idx, op, hi, lo, cl, breite=0.62)
        if kanten_geg:
            ext._zeichne_kanten(ax, kanten_geg, n, wall, mit_historie=False,
                                lw=1.8)
        ext._zeichne_kanten(ax, kanten, n, wall, mit_historie=False, lw=1.2)
        ext._zeichne_touches(ax, kanten + kanten_geg, ms=5.0)
        _marker_trades(ax, trades)
        traeger = _traeger_marker(ax, trades)   # F20: Traeger nicht verstecken
        ax.set_xlim(-8, n + 8)
        _pad = (y1 - y0) * 0.07
        ax.set_ylim(y0 - _pad, y1 + _pad)
        ax.grid(alpha=0.20)
        ticks = np.linspace(0, n - 1, 16).astype(int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in ticks],
                           fontsize=9)
        ax.set_title(
            f"SICHTPRUEFUNG {lab} -- {start}..{endtag} | V021-BASELINE (F3) | "
            f"Kerzen + handlungsrelevante Kanten + Gegenkanten (tp2 = "
            f"Extremum) + Trades (Bars 0..{n - 1}) | {len(trades)} Trades / "
            f"{ist_r:+.4f} R", fontsize=15)
        ax.legend(handles=[
            Line2D([0], [0], marker="o", color="w", mfc=C_LONG, ms=10,
                   label="LONG (entry, mfc=col)"),
            Line2D([0], [0], marker="o", color="w", mfc=C_SHORT, ms=10,
                   label="SHORT (entry, mfc=col)"),
            Line2D([0], [0], marker="o", color="w", mfc="none", mec=C_ENDE,
                   ms=12, mew=1.7, label="ENDE-Exit (Fensterrand)"),
            Line2D([0], [0], color=C_KANTE, lw=1.2, label="Kante (getradet)"),
            Line2D([0], [0], color=C_GEG, lw=1.8,
                   label="GEGENKANTE (Extremum, Traeger von tp2)"),
            Line2D([0], [0], marker="^", color="w", mfc=C_TOUCH_OBEN, ms=8,
                   label="Touch OBEN"),
            Line2D([0], [0], marker="v", color="w", mfc=C_TOUCH_UNTEN, ms=8,
                   label="Touch UNTEN"),
            Line2D([0], [0], color=C_LONG, ls=":", lw=1.4,
                   label="SL-TP2-Range"),
            Line2D([0], [0], marker="o", color="w", mfc="none",
                   mec=C_TRAEGER, ms=14, mew=2.6,
                   label="TRAEGER (groesster Einzeltrade, F20)"),
        ], loc="upper left", fontsize=10.5, framealpha=0.92)

        zeilen = _statblock(lab, start, endtag, n, trades, dzk)
        axs.axis("off")
        axs.text(0.5, 0.98, "\n".join(zeilen), fontsize=9.0, va="top",
                 ha="center", family="monospace", transform=axs.transAxes,
                 bbox=dict(boxstyle="round,pad=0.5", fc="#f7f7f7",
                           ec="#888888", lw=0.8))

        out = ROOT / "test" / f"render_{lab.lower()}_baseline.png"
        fig.subplots_adjust(left=0.032, right=0.997, top=0.945, bottom=0.022)
        fig.savefig(out, dpi=200)
        plt.close(fig)

        z.append(f"===== {lab} ({start} .. {ende} exkl.) | n={n} | "
                 f"edges={len(scan['edges'])} seeds={len(scan['seeds'])} "
                 f"| STAND {STAND} =====")
        z.extend("  " + s for s in zeilen)
        z.append(f"  PNG: {out}")
        z.append(f"  Identitaet EXTREMUM: {n_ident}/{len(trades)} Trades mit "
                 f"basis_bei(t.bar) == tp2 (Toleranz 1e-9)  OK")
        z.append(f"  Gegenkanten-Kids: "
                 f"{', '.join('K' + str(k) for k in sorted(kids_geg))}")
        z.append(f"  getradete Kids  : "
                 f"{', '.join('K' + str(k) for k in sorted(kids_trade))}")
        z.append(f"  cumR-Endstand (nur Zahl, keine Grafik): {ist_r:+.6f} R")
        z.append(f"  TRAEGER (F20, optisch markiert): K{int(traeger.kid)}@"
                 f"{int(traeger.entry_bar)} {float(traeger.r):+.6f} R"
                 f"  [{100.0 * float(traeger.r) / ist_r:+.1f} % des SumR]")
        z.append("")
        for x in zeilen:
            print(x)
        print(f"PNG: {out}\n")

    OUT_PROTOKOLL.write_text("\n".join(z) + "\n", encoding="utf-8",
                             newline="\n")
    print(f"TXT: {OUT_PROTOKOLL}")


if __name__ == "__main__":
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        OUT_PROTOKOLL.write_text(
            f"ABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}", encoding="utf-8")
    print(f"\nFehler={_fehler}")
