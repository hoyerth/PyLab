# -*- coding: utf-8 -*-
"""test/tmp_reclaim_snapshot_replay.py -- Schritt-0-Replay-Harness (Pfad B).

Historische Replay-Validierung der Reclaim-Snapshot-Engine (Post-Phase-Sweeps
an statisch fixierten Volume-Zone-Kanten) gemaess docs/reclaim_snapshot_spez.md
(Commit dc1e2b0, §§4-6, 8-9).

Kausalitaets-Prinzip (Spez §4):
  * EIN Segmentierungslauf je Fenster (kl.segmentiere_phasen) genuegt:
    vollendete Phasen (break_dir is not None) sind invariant gegen spaetere
    Bars; 4b trimmt nur die offene End-Phase.
  * Bewusste Implementierungs-Praezisierung: Der Harness nutzt segmentiere_phasen
    direkt (nicht berechne_reclaim_signale), weil der Intra-Phase-Signal-Scan
    des Kernels fuer Post-Phase-Sweeps irrelevant ist - erspart bei S2 (~32k
    Bars) den dominanten Laufzeit-Anteil. Die Phasen-Objekte (inkl. vol_zone/
    U_zone/L_zone/POC/brk_idx) sind identisch.
  * Kanten-Kette: vollendete Phase p aktiv fuer k in [brk_idx+1, next_aktiv),
    gedeckelt auf 192 Bars (N_MAX, 2 Handelstage).

Signalregeln (Spez §5): Sweep ueber u_zone (SHORT) / unter l_zone (LONG);
in_bar = close[k] auf Reclaim-Seite -> Entry open[k+1]; next_bar =
close[k+1] auf Reclaim-Seite -> Entry open[k+2]; Gates: Entry auf POC-Seite,
crv >= 1.0, Cooldown 12 je Richtung (Reset je Kante); Bounce-Huerde entfaellt;
Bounds k+2 < len(df). Aufloesung exakt ueber kl._aufloesen (SL 0.45%,
TP1=POC, TP2=Gegenseite+Puffer, 25/75-Split, kein Nachzug/Trailing).

Aufruf:
    .venv\\Scripts\\python.exe test/tmp_reclaim_snapshot_replay.py [--fenster=AUG|S1|S2|ALLE]

Report: Konsole + Append nach test/stats_reclaim_snapshot_replay.txt.
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import reclaim_live_kernel as kl  # noqa: E402

DB_PATH: Path = ROOT / "data" / "market_data.duckdb"
REPORT_TXT: Path = ROOT / "test" / "stats_reclaim_snapshot_replay.txt"

FensterTyp = Literal["AUG", "S1", "S2"]

FENSTER: Dict[FensterTyp, Tuple[str, str]] = {
    "AUG": ("2026-08-10", "2026-08-28"),  # nur Referenz (S1 ⊃ AUG)
    "S1": ("2026-02-05", "2026-08-28"),
    "S2": ("2025-01-01", "2025-12-01"),
}

N_MAX: int = 192  # Spez §4.3: Verfall nach 2 Handelstagen (96 M15-Bars/Tag)

FensterAuswahl = Literal["AUG", "S1", "S2", "ALLE"]


@dataclass(frozen=True, slots=True)
class ReplayFensterErgebnis:
    """Aggregiertes Replay-Ergebnis eines Benchmark-Fensters (Spez §9 + Gate)."""
    fenster: FensterTyp
    anzahl_phasen: int
    anzahl_kanten: int
    signale_gesamt: int
    signale_long: int
    signale_short: int
    trades_gewertet: int           # GEWONNEN + VERLOREN
    trades_neutral: int
    winrate_pct: float
    summe_r: float
    profit_faktor: Optional[float]  # None bei 0 entschieden
    low_n_warnung: bool            # True wenn trades_gewertet < 20
    gate_bestanden: bool           # True wenn summe_r > 0 und PF >= 1.30

    # Sensitivitaet: nur Signale aus handelbaren Phasen (Spez §8.5)
    sens_signale: int = 0
    sens_summe_r: float = 0.0
    sens_profit_faktor: Optional[float] = None

    # Rohdaten fuer den Report
    signal_zeilen: List[str] = field(default_factory=list, compare=False)


@dataclass(frozen=True, slots=True)
class _ReplaySignal:
    """Internes Signal des Harness (vor Aggregation)."""
    phase_id: int
    phase_handelbar: bool
    kanten_alter_bars: int
    sig: kl.ReclaimSignal


def _lade_fenster(fenster: FensterTyp) -> pd.DataFrame:
    """OHLCV-Fenster exakt in frozen load_data-Semantik (K13/Wanduhr)."""
    start, ende = FENSTER[fenster]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    d = con.execute(f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
    """).fetchdf()
    con.close()
    return kl.normalisiere_fenster(d)


def _scanne_kante(
    d: pd.DataFrame,
    p: kl.PhaseData,
    phase_id: int,
    k_start: int,
    k_ende: int,
    out: List[_ReplaySignal],
) -> int:
    """Scannt die aktive Kante der vollendeten Phase p ueber [k_start, k_ende).

    Args:
        d: Normalisiertes Fenster (ts tz-naiv, idx = Position).
        p: Vollendete Phase (break_dir is not None) mit Zone.
        phase_id: 1-basierte Phasen-Nummer (fuer Report).
        k_start: Erste ueberwachte Bar (brk_idx + 1).
        k_ende: Exklusives Ende (naechste Aktivierung bzw. k_start + N_MAX).
        out: Sammler fuer erzeugte Signale.

    Returns:
        Anzahl erzeugter Signale.
    """
    u, l, poc = p.U_zone, p.L_zone, p.POC
    assert u is not None and l is not None and poc is not None
    hi = d["high"].values
    lo = d["low"].values
    cl = d["close"].values
    op = d["open"].values
    ts = d["ts"].values
    n = len(d)
    cooldown = kl.MIN_SIGNAL_ABSTAND_BARS
    min_crv = kl.MIN_RECLAIM_CRV
    sl_p = kl.SL_PCT / 100.0
    tp2_puffer = kl.TP2_PUFFER_PCT / 100.0
    last_short = -10**9
    last_long = -10**9
    n_sig = 0

    for k in range(k_start, k_ende):
        if hi[k] > u and k - last_short >= cooldown:
            if cl[k] <= u:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 < n and cl[k + 1] <= u:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if reclaim is not None and e_bar is not None and e_preis > poc:
                sl = e_preis * (1.0 + sl_p)
                tp1 = poc
                tp2 = l * (1.0 + tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    last_short = k
                    sig = kl.ReclaimSignal(
                        typ="SHORT", bar=int(k), ts=pd.Timestamp(ts[k]),
                        reclaim=reclaim, einstieg_bar=int(e_bar),
                        einstieg_preis=e_preis, U_laufend=float(u),
                        L_laufend=float(l), POC=float(poc), tp1=tp1, tp2=tp2,
                        sl=sl, crv=crv, crv2=crv2, bounce_nr=0, phase=phase_id,
                    )
                    sig.trade = kl._aufloesen(d, sig)
                    out.append(_ReplaySignal(
                        phase_id=phase_id, phase_handelbar=bool(p.handelbar),
                        kanten_alter_bars=int(k - p.i_ende), sig=sig,
                    ))
                    n_sig += 1

        if lo[k] < l and k - last_long >= cooldown:
            if cl[k] >= l:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 < n and cl[k + 1] >= l:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if reclaim is not None and e_bar is not None and e_preis < poc:
                sl = e_preis * (1.0 - sl_p)
                tp1 = poc
                tp2 = u * (1.0 - tp2_puffer)
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    last_long = k
                    sig = kl.ReclaimSignal(
                        typ="LONG", bar=int(k), ts=pd.Timestamp(ts[k]),
                        reclaim=reclaim, einstieg_bar=int(e_bar),
                        einstieg_preis=e_preis, U_laufend=float(u),
                        L_laufend=float(l), POC=float(poc), tp1=tp1, tp2=tp2,
                        sl=sl, crv=crv, crv2=crv2, bounce_nr=0, phase=phase_id,
                    )
                    sig.trade = kl._aufloesen(d, sig)
                    out.append(_ReplaySignal(
                        phase_id=phase_id, phase_handelbar=bool(p.handelbar),
                        kanten_alter_bars=int(k - p.i_ende), sig=sig,
                    ))
                    n_sig += 1
    return n_sig


def _stats(signale: List[_ReplaySignal]) -> Tuple[int, int, float, Optional[float]]:
    """(gewinne, verluste, summe_r, profit_faktor) ueber entschiedene Trades."""
    gew = verl = 0
    sum_pos = sum_neg = 0.0
    sum_r = 0.0
    for rs in signale:
        t = rs.sig.trade
        assert t is not None
        r = float(t.r_mult)
        sum_r += r
        if r > 1e-9:
            gew += 1
            sum_pos += r
        elif r < -1e-9:
            verl += 1
            sum_neg += abs(r)
    if gew + verl == 0:
        return gew, verl, sum_r, None
    pf: Optional[float]
    if sum_neg <= 0:
        pf = float("inf") if sum_pos > 0 else None
    else:
        pf = sum_pos / sum_neg
    return gew, verl, sum_r, pf


def _replay(fenster: FensterTyp) -> ReplayFensterErgebnis:
    d = _lade_fenster(fenster)
    phasen = kl.segmentiere_phasen(d)

    # Vollendete Phasen mit gueltiger Zone -> Kanten-Kette
    kanten: List[Tuple[kl.PhaseData, int, int, int]] = []  # (p, phase_id, k_start, k_ende)
    phase_id_all = 0
    for p in phasen:
        phase_id_all += 1
        if p.break_dir is None or p.brk_idx is None:
            continue
        if p.U_zone is None or p.L_zone is None or p.POC is None:
            continue
        kanten.append((p, phase_id_all, 0, 0))  # Fenster spaeter gefuellt
    # Scan-Fenster: [brk_idx+1, min(naechste Aktivierung, +N_MAX, len(d)))
    n = len(d)
    for i_p, (p, pid, _, _) in enumerate(kanten):
        k_start = int(p.brk_idx) + 1
        k_ende = n
        if i_p + 1 < len(kanten):
            k_ende = min(k_ende, int(kanten[i_p + 1][0].brk_idx) + 1)
        k_ende = min(k_ende, k_start + N_MAX, n)
        kanten[i_p] = (p, pid, k_start, k_ende)

    signale: List[_ReplaySignal] = []
    for p, pid, k_start, k_ende in kanten:
        _scanne_kante(d, p, pid, k_start, k_ende, signale)
    signale.sort(key=lambda rs: (rs.sig.bar, rs.sig.typ))

    n_long = sum(1 for rs in signale if rs.sig.typ == "LONG")
    n_short = len(signale) - n_long
    gew, verl, sum_r, pf = _stats(signale)
    entschieden = gew + verl
    neutral = len(signale) - entschieden
    winrate = 100.0 * gew / entschieden if entschieden else 0.0
    low_n = entschieden < 20
    gate = entschieden > 0 and sum_r > 0 and pf is not None and pf >= 1.30

    # Sensitivitaet: nur handelbare Phasen
    sens = [rs for rs in signale if rs.phase_handelbar]
    s_gew, s_verl, s_sum, s_pf = _stats(sens)
    s_ent = s_gew + s_verl

    # Signal-Report-Zeilen (fuer Konsole + Datei)
    zeilen: List[str] = []
    for rs in signale:
        s = rs.sig
        t = s.trade
        assert t is not None
        typ_txt = f"{s.typ:5s}"
        rec_txt = f"{s.reclaim:8s}"
        zeilen.append(
            f"  P{rs.phase_id:2d} {s.ts:%m-%d %H:%M} {typ_txt} {rec_txt} "
            f"alt={rs.kanten_alter_bars:3d}B Entry {s.einstieg_preis:7.3f} "
            f"SL {s.sl:7.3f} TP1 {s.tp1:7.3f} TP2 {s.tp2:7.3f} "
            f"CRV {s.crv:4.2f} | {t.resultat:8s} {t.r_mult:+6.2f}R"
        )

    return ReplayFensterErgebnis(
        fenster=fenster,
        anzahl_phasen=len(phasen),
        anzahl_kanten=len(kanten),
        signale_gesamt=len(signale),
        signale_long=n_long,
        signale_short=n_short,
        trades_gewertet=entschieden,
        trades_neutral=neutral,
        winrate_pct=winrate,
        summe_r=sum_r,
        profit_faktor=pf,
        low_n_warnung=low_n,
        gate_bestanden=gate,
        sens_signale=len(sens),
        sens_summe_r=s_sum,
        sens_profit_faktor=s_pf,
        signal_zeilen=zeilen,
    )


def _pf_txt(pf: Optional[float]) -> str:
    if pf is None:
        return "   n/a"
    if pf == float("inf"):
        return "   inf"
    return f"{pf:6.2f}"


def _report(erg: ReplayFensterErgebnis, nur_konsole: bool = False) -> None:
    start, ende = FENSTER[erg.fenster]
    lines: List[str] = []
    lines.append("")
    lines.append("=" * 100)
    lines.append(f"=== RECLAIM-SNAPSHOT-REPLAY: {erg.fenster} ({start} .. {ende}) ===")
    lines.append("=" * 100)
    lines.append(
        f"Phasen gesamt: {erg.anzahl_phasen} | vollendete Phasen mit Zone (Kanten): "
        f"{erg.anzahl_kanten}"
    )
    lines.append(
        f"Signale: {erg.signale_gesamt} (LONG {erg.signale_long} / SHORT {erg.signale_short}) "
        f"| entschieden: {erg.trades_gewertet} | NEUTRAL: {erg.trades_neutral}"
    )
    lines.append(
        f"Winrate: {erg.winrate_pct:5.1f}% (nur entschieden) | Summe R: {erg.summe_r:+8.2f} "
        f"| PF: {_pf_txt(erg.profit_faktor)}"
    )
    lines.append(
        f"Sensitivitaet (nur handelbare Phasen): {erg.sens_signale} Signale | "
        f"Summe R: {erg.sens_summe_r:+8.2f} | PF: {_pf_txt(erg.sens_profit_faktor)}"
    )
    if erg.fenster in ("S1", "S2"):
        lines.append(
            f"Gate (S1/S2: PF >= 1.30 & Summe R > 0): "
            f"{'BESTANDEN' if erg.gate_bestanden else 'NICHT BESTANDEN'}"
            + (" | Low-n-Warnung (n < 20)" if erg.low_n_warnung else "")
        )
    else:
        lines.append("Gate: (AUG nur Referenz, nicht gate-relevant)")
    lines.append("--- Signalliste ---")
    if erg.signal_zeilen:
        lines.extend(erg.signal_zeilen[:60])
        if len(erg.signal_zeilen) > 60:
            lines.append(f"  ... (+{len(erg.signal_zeilen) - 60} weitere)")
    else:
        lines.append("  (keine Signale)")
    lines.append("")

    txt = "\n".join(lines)
    print(txt)
    if not nur_konsole:
        with open(REPORT_TXT, "a", encoding="utf-8") as f:
            f.write(txt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclaim-Snapshot-Replay (Schritt 0)")
    parser.add_argument("--fenster", default="ALLE", choices=["AUG", "S1", "S2", "ALLE"])
    args = parser.parse_args()

    reihenfolge: List[FensterTyp] = ["AUG", "S1", "S2"]
    if args.fenster != "ALLE":
        reihenfolge = [args.fenster]  # type: ignore[list-item]

    for f in reihenfolge:
        erg = _replay(f)
        _report(erg)


if __name__ == "__main__":
    main()
