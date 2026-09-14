"""
SETUP C - ATTRIBUTION DER NICHT-KAUSALEN CLUSTER-A-SELEKTION
===========================================================
Beantwortet die Frage: **Wie viel des RAW-A-Ertrags stammt aus der
1-Bar-Vorauswahl ``vorlauf_bars <= cluster_a_max_vorlauf`` (Default 1)?**

Hintergrund (Kausalitaets-Befund)
---------------------------------
Der Trigger selbst ist kausal: ``_erfasse_raw`` feuert am ersten Bar mit
``high >= kante`` (bzw. ``low <= kante``) UND ``tick_volume >= 1.5 *
SMA20(tick_volume).shift(1)``; der Einstieg liegt am Open des Folge-Bars.

Die **Selektion** dagegen ist es nicht: ``vorlauf_bars = brk_idx - trigger_idx``
mit ``brk_idx = j`` setzt die 2-Close-Bestaetigung voraus, die erst mit
``close[j+1]`` abgeschlossen ist:

    vorlauf = 0  -> Trigger = j    -> Entry = Open(j+1)   (close[j+1] unbekannt)
    vorlauf = 1  -> Trigger = j-1  -> Entry = Open(j)     (close[j] UND
                                                           close[j+1] unbekannt)

Der Cluster-A-Filter ist damit eine **Vorauswahl mit Zukunftswissen**.

Kausale Vergleichsmassstaebe
----------------------------
  * ``alle RAW``  = erster Volumen-Durchstoss je (Phase, Richtung) ohne
    Bruchfilter. Da ``_erfasse_raw`` je (Phase, Richtung) genau EIN Signal
    liefert, ist das die vollstaendige kausale Grundgesamtheit (Cluster A
    disjunkt vereinigt mit Cluster B).
  * ``CONFIRMED`` = Arm 2 des Kerns, Entry erst ``open[brk_idx+2]``. Zu diesem
    Zeitpunkt sind ``close[j]`` UND ``close[j+1]`` bekannt -> **vollstaendig
    kausal**. Das ist der faire, handelbare Bruch-Trade zum schlechteren Preis.
  * ``RETEST``    = Arm 3 (Pullback an die gebrochene Kante, F6/F7/F8).

Gegenstand (rein lesend; schreibt nur die eigene TXT unter ``test/``):
  1) Verteilung ``vorlauf_bars`` je Fenster.
  2) Kennzahlen je ``vorlauf_bars``-Wert (N48 / N96 / TR300).
  3) Attribution Cluster A (<= 1) vs. Cluster B (> 1) vs. gesamt.
  4) Schwellen-Sweep ``cluster_a_max_vorlauf`` {0,1,2,3,5,999} bitgenau ueber
     ``setup_c_profil._kern_lauefe`` (Produktionspfad) inkl. Konsistenz-Check
     gegen die Partitionierung (Sweep k=1 == Partition vorlauf<=1).
  5) Toptreiber der Cluster-A-Summe (N96).
  6) Kausale Vergleichsarme (alle RAW / CONFIRMED / RETEST) je Modus.

Aufruf (Projekt-Root):
    python test/setup_c/tmp_setup_c_vorlauf_attribution.py
    python test/setup_c/tmp_setup_c_vorlauf_attribution.py --mit-referenz

Hinweis: ``TrendConfig`` ist ``frozen``; die Schwellen-Variation laeuft ueber
``dataclasses.replace`` (keine Mutation des Produktions-Defaults).
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

if __package__ in (None, ""):
    _projekt_root: Path = Path(__file__).resolve().parents[2]
    if str(_projekt_root) not in sys.path:
        sys.path.insert(0, str(_projekt_root))

from scripts.market_segmentation import (  # noqa: E402
    SegmentConfig,
    SegmentResult,
    load_data,
    segmentiere_markt,
)
from scripts.setup_c_profil import (  # noqa: E402
    AggBlock,
    EMASlopeTrailingConfig,
    KernelTrade,
    SetupCSignal,
    TrendConfig,
    _agg_block,
    _erfasse_signale,
    _kern_lauefe,
    _simuliere_kern,
    _simuliere_kern_ema_trailing,
    berechne_ema_slope_vektoren,
)

# ---------------------------------------------------------------------------
# Fenster (freie Monatszeitraeume, konform zur BKZ-Datenkonvention)
# ---------------------------------------------------------------------------

MONATE: Dict[str, Tuple[str, str]] = {
    "MAI26": ("2026-05-01", "2026-06-01"),
    "JUN26": ("2026-06-01", "2026-07-01"),
    "JUL26": ("2026-07-01", "2026-08-01"),
    "AUG26": ("2026-08-01", "2026-09-01"),
}

REFERENZ: Dict[str, Tuple[str, str]] = {
    "AUG": ("2026-08-10", "2026-08-28"),
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}

HORIZONTE: Tuple[int, ...] = (48, 96)
NOTFALL_TR: int = 300
MODI: Tuple[str, ...] = ("N48", "N96", f"TR{NOTFALL_TR}")

# Sweep der Cluster-A-Schwelle (999 = "alle RAW", entspricht unendlich)
SCHWELLEN: Tuple[int, ...] = (0, 1, 2, 3, 5, 999)

_AUSGABE: Path = (
    Path(__file__).resolve().parent / "tmp_setup_c_vorlauf_attribution.txt"
)


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def mdd_r(trades: Sequence[KernelTrade]) -> float:
    """Maximaler Rueckgang der R-Kumulation in Exit-Reihenfolge.

    Args:
        trades: KernelTrades (intern auf ``exit_idx`` sortiert).

    Returns:
        MDD in R (negativ oder 0.0; ``0.0`` wenn keine gewerteten Trades).
    """
    r: np.ndarray = np.array(
        [
            float(t.r_f4)
            for t in sorted(trades, key=lambda x: x.exit_idx)
            if t.exit_grund != "RECHTS_ZENSIERT" and np.isfinite(float(t.r_f4))
        ],
        dtype=float,
    )
    if len(r) == 0:
        return 0.0
    cum: np.ndarray = np.cumsum(r)
    return float((cum - np.maximum.accumulate(cum)).min())


def gueltige_signale(
    signale: Sequence[SetupCSignal], arm: str
) -> List[SetupCSignal]:
    """Gueltige SIGNAL-Population eines Arms (Popup-Standard der Produktion).

    Args:
        signale: Alle erfassten Signale eines Fensters.
        arm: ``"RAW"``, ``"CONFIRMED"`` oder ``"RETEST"``.

    Returns:
        Signale mit ``status == "SIGNAL"``, ``entry_idx >= 0`` und
        endlichem ``sl_usd > 0`` (RAW zusaetzlich mit gesetztem
        ``vorlauf_bars``).
    """
    out: List[SetupCSignal] = [
        s
        for s in signale
        if s.arm == arm
        and s.status == "SIGNAL"
        and s.entry_idx >= 0
        and np.isfinite(s.sl_usd)
        and s.sl_usd > 0.0
    ]
    if arm == "RAW":
        out = [s for s in out if s.vorlauf_bars is not None]
    return out


def simuliere_alle(
    df,
    kandidaten: Sequence[SetupCSignal],
    cfg: TrendConfig,
) -> Dict[str, List[KernelTrade]]:
    """Simuliert alle uebergebenen Kandidaten je Modus.

    Da das Simulationsergebnis nicht von der Cluster-Schwelle abhaengt, wird
    einmal je Modus ueber die volle Grundgesamtheit simuliert; die Attribution
    ist anschliessend eine Partitionierung derselben Trade-Objekte.

    Args:
        df: OHLCV-DataFrame.
        kandidaten: Signale (jede Population, z. B. RAW oder CONFIRMED).
        cfg: TrendConfig (Produktions-Defaults).

    Returns:
        Dict ``modus -> Liste KernelTrade`` (Modi ``N48``, ``N96``, ``TR300``).
    """
    cfg_plain: TrendConfig = replace(cfg, ema_trailing=EMASlopeTrailingConfig())
    out: Dict[str, List[KernelTrade]] = {}
    for h in HORIZONTE:
        out[f"N{h}"] = [_simuliere_kern(df, s, cfg_plain, h) for s in kandidaten]
    tc: EMASlopeTrailingConfig = EMASlopeTrailingConfig(aktiviert=True)
    ema_arr, slope_arr = berechne_ema_slope_vektoren(df, tc.ema_periode)
    out[f"TR{NOTFALL_TR}"] = [
        _simuliere_kern_ema_trailing(df, s, cfg, ema_arr, slope_arr, tc)
        for s in kandidaten
    ]
    return out


def sortiere_nach_signal(
    trades: Sequence[KernelTrade], kandidaten: Sequence[SetupCSignal]
) -> List[KernelTrade]:
    """Bringt Trades in die Reihenfolge der Signal-Liste (Attributions-Join).

    Args:
        trades: Trades einer Simulation (gleiche Laenge wie ``kandidaten``).
        kandidaten: Zugehoerige Signale.

    Returns:
        Trades in der Reihenfolge der Kandidaten.
    """
    index: Dict[Tuple[int, str, int], KernelTrade] = {
        (int(t.phase), str(t.dir), int(t.entry_idx)): t for t in trades
    }
    return [
        index[(int(s.phase), str(s.dir), int(s.entry_idx))] for s in kandidaten
    ]


def zeile_metrik(trades: Sequence[KernelTrade]) -> str:
    """Kompakte Metrikzeile fuer eine Trade-Teilmenge.

    Args:
        trades: KernelTrades (Teilmenge).

    Returns:
        Formatierter String mit n, zensiert, sum/mean R, WR, PF, MDD.
    """
    agg: AggBlock = _agg_block(list(trades))
    if agg.n_gewertet == 0:
        return f"n={agg.n_aktiv:>2} (keine gewerteten Trades)"
    return (
        f"n={agg.n_aktiv:>2} zens={agg.n_zensiert:>2} gew={agg.n_gewertet:>2}  "
        f"sum={agg.sum_r_f4:+8.2f}R  mean={agg.mean_r_f4:+5.2f}R  "
        f"WR={agg.wr:5.1f}%  PF={agg.pf:5.2f}  MDD={mdd_r(trades):+6.2f}R"
    )


def partitioniere(
    ergebnisse: Sequence[Dict[str, object]], modus: str, schluessel: str
) -> List[KernelTrade]:
    """Sammelt Trades einer sign-aligned Partition ueber alle Fenster.

    Args:
        ergebnisse: Ergebnis-Dicts je Fenster (Felder ``sim_<schluessel>``,
            ``kandidaten_<schluessel>``, ``maske_<schluessel>``).
        modus: ``N48`` | ``N96`` | ``TR300``.
        schluessel: ``'r'`` (RAW) | ``'c'`` (CONFIRMED) | ``'t'`` (RETEST).

    Returns:
        Verkettete KernelTrades der maskierten Teilmenge.
    """
    out: List[KernelTrade] = []
    for e in ergebnisse:
        sim = e[f"sim_{schluessel}"]  # type: ignore[index]
        kands = e[f"kandidaten_{schluessel}"]  # type: ignore[index]
        maske = e[f"maske_{schluessel}"]  # type: ignore[index]
        geordnet = sortiere_nach_signal(sim[modus], kands)  # type: ignore[index]
        out.extend([t for t, m in zip(geordnet, maske) if bool(m)])  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------------------
# Auswertung
# ---------------------------------------------------------------------------


def block_fenster(
    zeilen: List[str], ergebnisse: Sequence[Dict[str, object]]
) -> None:
    """Abschnitte 1 und 2: Verteilung + Kennzahlen je vorlauf-Wert.

    Args:
        zeilen: Ausgabepuffer.
        ergebnisse: Ergebnis-Dicts je Fenster.
    """
    for e in ergebnisse:
        label: str = str(e["label"])
        start, ende = e["spanne"]  # type: ignore[misc]
        kandidaten = e["kandidaten_r"]
        vorlauf = e["vorlauf"]
        sim = e["sim_r"]
        zeilen.append("")
        zeilen.append(f"--- FENSTER {label} ({start} .. {ende}, ende-exklusiv) ---")
        zeilen.append(
            f"  Segmente: {len(e['sr'].phases)} | RAW-Kandidaten: "  # type: ignore[union-attr]
            f"{len(kandidaten)} | davon Cluster A: "  # type: ignore[arg-type]
            f"{int((np.asarray(vorlauf) <= 1).sum())}"
        )
        counter: Dict[int, int] = {}
        for v in np.asarray(vorlauf):
            counter[int(v)] = counter.get(int(v), 0) + 1
        teile: List[str] = [
            f"v={k}:{counter[k]}" for k in sorted(counter) if k <= 5
        ]
        gt5: int = sum(c for k, c in counter.items() if k > 5)
        if gt5:
            teile.append(f"v>5:{gt5}")
        zeilen.append(
            "  1) Verteilung vorlauf_bars: "
            + (" | ".join(teile) if teile else "(keine)")
        )
        zeilen.append("  2) Kennzahlen je vorlauf_bars-Wert:")
        for modus in MODI:
            geordnet = sortiere_nach_signal(sim[modus], kandidaten)
            for v in sorted(counter):
                grp = [
                    t
                    for t, vv in zip(geordnet, np.asarray(vorlauf))
                    if int(vv) == v
                ]
                zeilen.append(f"      {modus:>5}  vorlauf={v:<3} {zeile_metrik(grp)}")


def block_attribution(
    zeilen: List[str], ergebnisse: Sequence[Dict[str, object]]
) -> None:
    """Abschnitt 3: Cluster A (<=1) vs. Cluster B (>1) vs. gesamt.

    Args:
        zeilen: Ausgabepuffer.
        ergebnisse: Ergebnis-Dicts je Fenster.
    """
    zeilen.append("")
    zeilen.append("=" * 104)
    zeilen.append(
        "3) ATTRIBUTION: Cluster A (vorlauf <= 1, NICHT kausal) vs. "
        "Cluster B (> 1) vs. gesamt"
    )
    zeilen.append("=" * 104)
    zeilen.append(
        "   'gesamt' = alle RAW = kausal handelbar (erster Volumen-Durchstoss "
        "je Phase+Richtung)."
    )
    zeilen.append(
        "   'A' setzt Bruchwissen voraus, das zum Einstiegszeitpunkt nicht existiert."
    )
    zeilen.append("")
    zeilen.append(
        f"{'Modus':>6} {'Menge':<11} {'n':>4} {'zens':>5} {'sum R':>10} "
        f"{'WR':>7} {'PF':>7} {'MDD':>9}  Anteil an gesamt"
    )
    for modus in MODI:
        zeilen.append("-" * 104)
        trades_je: Dict[str, List[KernelTrade]] = {
            "A (<=1)": partitioniere_vorlauf(ergebnisse, modus, 1, 0),
            "B (>1)": partitioniere_vorlauf(ergebnisse, modus, 10**9, 2),
            "gesamt": [
                t
                for e in ergebnisse
                for t in e["sim_r"][modus]  # type: ignore[index]
            ],
        }
        gruppen: Dict[str, AggBlock] = {
            name: _agg_block(trades) for name, trades in trades_je.items()
        }
        basis: float = gruppen["gesamt"].sum_r_f4
        for name in ("A (<=1)", "B (>1)", "gesamt"):
            agg: AggBlock = gruppen[name]
            anteil: str = (
                f"{100.0 * agg.sum_r_f4 / basis:6.1f}%"
                if basis != 0.0
                else "   n/a"
            )
            zeilen.append(
                f"{modus:>6} {name:<11} {agg.n_aktiv:>4} {agg.n_zensiert:>5} "
                f"{agg.sum_r_f4:>+10.2f} "
                f"{(f'{agg.wr:.1f}%' if agg.n_gewertet else '-'):>7} "
                f"{(f'{agg.pf:.2f}' if agg.n_gewertet else '-'):>7} "
                f"{mdd_r(trades_je[name]):>+9.2f}  {anteil}"
            )
        delta: float = gruppen["A (<=1)"].sum_r_f4 - basis
        pct: str = (
            f"{100.0 * delta / abs(basis):+.1f}%"
            if basis != 0.0
            else "n/a"
        )
        zeilen.append(
            f"{modus:>6} {'DELTA A-ges':<11} {'':>4} {'':>5} {delta:>+10.2f}"
            f"{'':>24}  ({pct}; negativ = A kleiner als der kausale Pool)"
        )
    zeilen.append("-" * 104)


def partitioniere_vorlauf(
    ergebnisse: Sequence[Dict[str, object]], modus: str, vmax: int, vmin: int = 0
) -> List[KernelTrade]:
    """RAW-Trades mit ``vmin <= vorlauf_bars <= vmax`` ueber alle Fenster.

    Args:
        ergebnisse: Ergebnis-Dicts je Fenster.
        modus: ``N48`` | ``N96`` | ``TR300``.
        vmax: Obere Vorlauf-Schwelle (inklusive).
        vmin: Untere Vorlauf-Schwelle (inklusive, Default 0).

    Returns:
        Verkettete KernelTrades.
    """
    out: List[KernelTrade] = []
    for e in ergebnisse:
        sim = e["sim_r"]  # type: ignore[index]
        kands = e["kandidaten_r"]  # type: ignore[index]
        vorlauf = np.asarray(e["vorlauf"])
        geordnet = sortiere_nach_signal(sim[modus], kands)  # type: ignore[index]
        out.extend(
            [
                t
                for t, v in zip(geordnet, vorlauf)  # type: ignore[arg-type]
                if vmin <= int(v) <= vmax
            ]
        )
    return out


def block_sweep(
    zeilen: List[str], ergebnisse: Sequence[Dict[str, object]], cfg: TrendConfig
) -> None:
    """Abschnitt 4: Schwellen-Sweep ueber den Produktionspfad ``_kern_lauefe``.

    Args:
        zeilen: Ausgabepuffer.
        ergebnisse: Ergebnis-Dicts je Fenster.
        cfg: TrendConfig (Produktions-Defaults).
    """
    zeilen.append("")
    zeilen.append("=" * 104)
    zeilen.append(
        "4) SCHWELLEN-SWEEP cluster_a_max_vorlauf "
        "(bitgenau ueber setup_c_profil._kern_lauefe)"
    )
    zeilen.append("=" * 104)
    zeilen.append("   k=999 entspricht 'alle RAW' (= kausale Grundgesamtheit).")
    zeilen.append("")
    for modus in MODI:
        trailing: bool = modus.startswith("TR")
        h: int = NOTFALL_TR if trailing else int(modus[1:])
        zeilen.append(f"  {modus}:")
        for k in SCHWELLEN:
            cfg_k: TrendConfig = replace(
                cfg,
                cluster_a_max_vorlauf=k,
                ema_trailing=EMASlopeTrailingConfig(
                    aktiviert=trailing, notfall_horizont_bars=NOTFALL_TR
                ),
            )
            trades_k: List[KernelTrade] = []
            for e in ergebnisse:
                lauf, _ = _kern_lauefe(
                    e["df"], e["signale"], cfg_k, h  # type: ignore[arg-type]
                )
                trades_k.extend(lauf)
            zeilen.append(f"    k<={k:<4} {zeile_metrik(trades_k)}")
        # Konsistenz: Sweep k=1 == Partitionierung vorlauf <= 1
        part: List[KernelTrade] = partitioniere_vorlauf(ergebnisse, modus, 1)
        a1: AggBlock = _agg_block(part)
        lauf1: List[KernelTrade] = []
        cfg1: TrendConfig = replace(
            cfg,
            cluster_a_max_vorlauf=1,
            ema_trailing=EMASlopeTrailingConfig(
                aktiviert=trailing, notfall_horizont_bars=NOTFALL_TR
            ),
        )
        for e in ergebnisse:
            lauf, _ = _kern_lauefe(
                e["df"], e["signale"], cfg1, h  # type: ignore[arg-type]
            )
            lauf1.extend(lauf)
        ok: bool = abs(_agg_block(lauf1).sum_r_f4 - a1.sum_r_f4) < 1e-9
        zeilen.append(
            f"    [Check] Partition vorlauf<=1 == k<=1: "
            f"{'OK' if ok else 'ABWEICHUNG'}  "
            f"(Partition {a1.sum_r_f4:+.2f}R | Sweep {_agg_block(lauf1).sum_r_f4:+.2f}R)"
        )


def block_treiber(
    zeilen: List[str], ergebnisse: Sequence[Dict[str, object]]
) -> None:
    """Abschnitt 5: Toptreiber der Cluster-A-Summe (N96).

    Args:
        zeilen: Ausgabepuffer.
        ergebnisse: Ergebnis-Dicts je Fenster.
    """
    zeilen.append("")
    zeilen.append("=" * 104)
    zeilen.append("5) TOP-TREIBER der Cluster-A-Summe (N96, sortiert nach |r|)")
    zeilen.append("=" * 104)
    treiber: List[Tuple[str, int, str, int, float, str]] = []
    for e in ergebnisse:
        geordnet = sortiere_nach_signal(e["sim_r"]["N96"], e["kandidaten_r"])
        for t, v in zip(geordnet, np.asarray(e["vorlauf"])):
            if int(v) > 1 or t.exit_grund == "RECHTS_ZENSIERT":
                continue
            treiber.append(
                (
                    str(e["label"]),
                    int(v),
                    str(t.dir),
                    int(t.entry_idx),
                    float(t.r_f4),
                    str(t.exit_grund),
                )
            )
    treiber.sort(key=lambda x: -abs(x[4]))
    for lb, v, d, ei, r, g in treiber[:12]:
        zeilen.append(
            f"  {lb}  vorlauf={v}  {d:<4}  entry_idx={ei:<5}  {r:+7.2f}R  {g}"
        )
    if not treiber:
        zeilen.append("  (keine gewerteten Cluster-A-Trades)")


def block_status(
    zeilen: List[str], ergebnisse: Sequence[Dict[str, object]]
) -> None:
    """Abschnitt 7: Status-Zensus der RAW-Signale (kausaler Rest-Zweifel).

    Phasen, in denen bis zum ``brk_idx`` KEIN Volumen-Durchstoss auftrat, haben
    kein RAW-Signal. In einer Live-Sicht waere das Phasenende unbekannt: der
    Scan liefe weiter und koennte dort spaeter doch noch feuern. Der Anteil
    dieser Faelle quantifiziert die verbleibende Unsicherheit der
    "alle RAW"-Referenz (die Phasenkonstruktion selbst ist bruchdefiniert).

    Args:
        zeilen: Ausgabepuffer.
        ergebnisse: Ergebnis-Dicts je Fenster.
    """
    zeilen.append("")
    zeilen.append("=" * 104)
    zeilen.append("7) STATUS-ZENSUS RAW (alle erfassten Signale, nicht nur gueltige)")
    zeilen.append("=" * 104)
    zeilen.append(
        "   KEIN_DURCHSTOSS/KEIN_VOLUMEN = bis brk_idx kein Volumen-Durchstoss; "
        "live waere das"
    )
    zeilen.append(
        "   Phasenende unbekannt (Scan liefe weiter) -> Rest-Unsicherheit der "
        "'alle RAW'-Referenz."
    )
    gesamt: Dict[str, int] = {}
    for e in ergebnisse:
        c: Dict[str, int] = {}
        for s in e["signale"]:  # type: ignore[union-attr]
            if getattr(s, "arm", None) != "RAW":
                continue
            st: str = str(s.status)
            c[st] = c.get(st, 0) + 1
            gesamt[st] = gesamt.get(st, 0) + 1
        teile: List[str] = [f"{k}={v}" for k, v in sorted(c.items())]
        zeilen.append(
            f"  {e['label']}: " + (" | ".join(teile) if teile else "(keine)")
        )
    zeilen.append("")
    zeilen.append(
        "  GESAMT: " + " | ".join(f"{k}={v}" for k, v in sorted(gesamt.items()))
    )
    tot: int = sum(gesamt.values())
    if tot:
        ohne: int = tot - gesamt.get("SIGNAL", 0)
        zeilen.append(
            f"  -> {ohne} von {tot} (Phase, Richtung)-Faellen ohne handelbares "
            f"RAW-Signal ({100.0 * ohne / tot:.1f}%)"
        )
    else:
        zeilen.append("  (keine)")


def block_kausal(
    zeilen: List[str], ergebnisse: Sequence[Dict[str, object]]
) -> None:
    """Abschnitt 6: kausale Vergleichsarme (alle RAW / CONFIRMED / RETEST).

    Args:
        zeilen: Ausgabepuffer.
        ergebnisse: Ergebnis-Dicts je Fenster.
    """
    zeilen.append("")
    zeilen.append("=" * 104)
    zeilen.append(
        "6) KAUSALE VERGLEICHSARME (vollstaendig handelbar, kein Zukunftswissen)"
    )
    zeilen.append("=" * 104)
    zeilen.append(
        "   'alle RAW'  : erster Volumen-Durchstoss je (Phase, Richtung), "
        "Entry Open(trigger+1)"
    )
    zeilen.append(
        "   'CONFIRMED' : Entry erst Open(brk_idx+2) - close[j] UND close[j+1] "
        "bereits bekannt"
    )
    zeilen.append(
        "   'RETEST'    : Pullback an die gebrochene Kante (F6/F7/F8), "
        "Entry Open(trigger+1)"
    )
    zeilen.append("")
    zeilen.append(
        f"{'Modus':>6} {'Variante':<24} {'n':>4} {'sum R':>10} {'WR':>7} "
        f"{'PF':>7} {'MDD':>9}"
    )
    for modus in MODI:
        zeilen.append("-" * 104)
        gruppen: List[Tuple[str, List[KernelTrade]]] = [
            ("alle RAW (kausal)", partitioniere_vorlauf(ergebnisse, modus, 10**9)),
            ("RAW-A (nicht kausal)", partitioniere_vorlauf(ergebnisse, modus, 1)),
            ("CONFIRMED (kausal)", partitioniere(ergebnisse, modus, "c")),
            ("RETEST", partitioniere(ergebnisse, modus, "t")),
        ]
        for name, trades in gruppen:
            agg: AggBlock = _agg_block(trades)
            zeilen.append(
                f"{modus:>6} {name:<24} {agg.n_aktiv:>4} "
                f"{agg.sum_r_f4:>+10.2f} "
                f"{(f'{agg.wr:.1f}%' if agg.n_gewertet else '-'):>7} "
                f"{(f'{agg.pf:.2f}' if agg.n_gewertet else '-'):>7} "
                f"{mdd_r(trades):>+9.2f}"
            )
    zeilen.append("-" * 104)


def block_fazit(
    zeilen: List[str], ergebnisse: Sequence[Dict[str, object]]
) -> None:
    """Abschnitt 7: automatisch abgeleitetes Fazit aus den Messwerten.

    Args:
        zeilen: Ausgabepuffer.
        ergebnisse: Ergebnis-Dicts je Fenster.
    """
    zeilen.append("")
    zeilen.append("=" * 104)
    zeilen.append("8) FAZIT (automatisch aus den Messwerten abgeleitet)")
    zeilen.append("=" * 104)
    for modus in MODI:
        a: AggBlock = _agg_block(partitioniere_vorlauf(ergebnisse, modus, 1))
        alle: List[KernelTrade] = [
            t for e in ergebnisse for t in e["sim_r"][modus]  # type: ignore[index]
        ]
        g: AggBlock = _agg_block(alle)
        v1: List[KernelTrade] = []
        for e in ergebnisse:
            geordnet = sortiere_nach_signal(e["sim_r"][modus], e["kandidaten_r"])
            v1.extend(
                [
                    t
                    for t, v in zip(geordnet, np.asarray(e["vorlauf"]))
                    if int(v) == 1
                ]
            )
        a1: AggBlock = _agg_block(v1)
        konz: float = (
            100.0 * a1.sum_r_f4 / a.sum_r_f4 if a.sum_r_f4 != 0.0 else float("nan")
        )
        anteil: float = (
            100.0 * a.sum_r_f4 / g.sum_r_f4 if g.sum_r_f4 != 0.0 else float("nan")
        )
        zeilen.append(f"  {modus}:")
        zeilen.append(
            f"    Cluster A sum={a.sum_r_f4:+.2f}R ({a.n_gewertet} Trades) | "
            f"alle RAW sum={g.sum_r_f4:+.2f}R ({g.n_gewertet} Trades) | "
            f"A-Anteil {anteil:.1f}%"
        )
        zeilen.append(
            f"    davon vorlauf=1: {a1.sum_r_f4:+.2f}R ({a1.n_gewertet} Trades) "
            f"= {konz:.1f}% der Cluster-A-Summe"
        )
        zeilen.append(
            f"    Risikokennzahlen: A PF={a.pf:.2f} MDD={mdd_r(partitioniere_vorlauf(ergebnisse, modus, 1)):+.2f}R "
            f"| alle RAW PF={g.pf:.2f} MDD={mdd_r(alle):+.2f}R"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI-Einstieg der Attribution.

    Args:
        argv: Argumentliste (Default: ``sys.argv[1:]``).

    Returns:
        Exit-Code 0.
    """
    args: List[str] = list(sys.argv[1:] if argv is None else argv)
    mit_referenz: bool = "--mit-referenz" in args

    cfg: TrendConfig = TrendConfig()
    fenster: Dict[str, Tuple[str, str]] = dict(MONATE)
    if mit_referenz:
        fenster.update(REFERENZ)

    zeilen: List[str] = [
        "=" * 104,
        "SETUP C - ATTRIBUTION DER NICHT-KAUSALEN CLUSTER-A-SELEKTION "
        "(vorlauf_bars <= 1)",
        "=" * 104,
        "Kausal handelbar = erster Volumen-Durchstoss je (Phase, Richtung) "
        "= 'alle RAW'.",
        "Cluster A (vorlauf <= 1) nutzt die 2-Close-Bestaetigung (brk_idx), die zum",
        "Einstiegszeitpunkt (Open der Folge-Bar) noch NICHT bekannt ist.",
        f"Fenster: {', '.join(fenster)} | Horizonte: N48/N96 | Trailing: N{NOTFALL_TR}",
        f"Config: suppression={cfg.suppression_phasenlokal} | "
        f"stop_puffer={cfg.stop_puffer} | raw_vol_mult={cfg.raw_vol_mult} | "
        f"sl_pct_ref={cfg.sl_pct_ref}",
    ]

    ergebnisse: List[Dict[str, object]] = []
    for label, spanne in fenster.items():
        start, ende = spanne
        seg_cfg: SegmentConfig = replace(
            cfg.segment, db_path=cfg.db_path, start=start, ende=ende
        )
        df = load_data(seg_cfg.db_path, seg_cfg.start, seg_cfg.ende)
        sr: SegmentResult = segmentiere_markt(df, seg_cfg)
        signale: List[SetupCSignal] = _erfasse_signale(sr, cfg)
        kands_r: List[SetupCSignal] = gueltige_signale(signale, "RAW")
        kands_c: List[SetupCSignal] = gueltige_signale(signale, "CONFIRMED")
        kands_t: List[SetupCSignal] = gueltige_signale(signale, "RETEST")
        vorlauf: np.ndarray = np.array(
            [int(s.vorlauf_bars) for s in kands_r], dtype=int
        )
        ergebnisse.append(
            {
                "label": label,
                "spanne": spanne,
                "df": df,
                "sr": sr,
                "signale": signale,
                "kandidaten_r": kands_r,
                "kandidaten_c": kands_c,
                "kandidaten_t": kands_t,
                "vorlauf": vorlauf,
                "maske_c": [True] * len(kands_c),
                "maske_t": [True] * len(kands_t),
                "sim_r": simuliere_alle(df, kands_r, cfg),
                "sim_c": simuliere_alle(df, kands_c, cfg),
                "sim_t": simuliere_alle(df, kands_t, cfg),
            }
        )

    block_fenster(zeilen, ergebnisse)
    block_attribution(zeilen, ergebnisse)
    block_sweep(zeilen, ergebnisse, cfg)
    block_treiber(zeilen, ergebnisse)
    block_kausal(zeilen, ergebnisse)
    block_status(zeilen, ergebnisse)
    block_fazit(zeilen, ergebnisse)

    text: str = "\n".join(zeilen)
    print(text)
    _AUSGABE.write_text(text, encoding="utf-8")
    print(f"\nReport: {_AUSGABE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
