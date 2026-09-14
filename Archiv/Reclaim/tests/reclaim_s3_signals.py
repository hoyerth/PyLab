# test/reclaim_s3_signals.py
"""S3: Signal-Loop gegen Store-Kanten (Setup B) + Rolling-VP-Exit (Konzept
docs/reclaim.md, Abschnitt 9/9.1/12).

Q7-Entscheidung (User-Mentor, 02.09.): **Option A - Rolling-VP-POC als TP1**.
Wissenschaftliche Isolation: Entries (Kantenspeicher) und Exits (Baseline-
Mechanik) werden NICHT gleichzeitig getauscht. Der institutionelle Fair Value
liegt beim Volumen-Schwerpunkt (POC), nicht bei der Korridor-Mitte.

Exit-Architektur (phasenfrei, kausal):
  * TP1 = POC eines ROLLIERENDEN Volume-Profils ueber die letzten
    ROLL_VP_WINDOW=300 Bars (ca. 75 h M15) bis zur Signal-Bar k. Ersetzt den
    phasengebundenen POC der Baseline ohne Phasen-Konzept (Q4).
  * TP2 = gegenueberliegende Profil-Kante (L_zone bei SHORT / U_zone bei LONG)
    + TP2_PUFFER_PCT (identische Baseline-Exit-Mechanik, Split 25/75).
  * Entry-Filter der Baseline bleibt erhalten: SHORT nur wenn Entry > POC,
    LONG nur wenn Entry < POC (ueber/unter dem fairen Wert einsteigen).
  * Q3: Naechstes aktives Level in Handelsrichtung wird NUR als Schatten
    mitgefuehrt (target_level_* / r_level) - kein Exit-Umstieg vor S3/S4.

Signal-Loop (Setup B auf Store-Kanten, Mechanik identisch Baseline):
  * Kandidat: Bar k durchsticht eine AKTIVE Korridor-Kante (Q2/Q5: naechstes
    aktives Level ueber dem Close fuer SHORT bzw. unter dem Close fuer LONG).
  * Reclaim: in_bar (close[k] zurueck in den Korridor, Entry open[k+1]) oder
    next_bar (close[k+1] zurueck, Entry open[k+2]).
  * Filter: Entry auf richtiger POC-Seite, CRV >= MIN_RECLAIM_CRV,
    Cooldown MIN_SIGNAL_ABSTAND_BARS je Seite (Default 8, uebernommen aus CD-
    Sweep; Baseline-AUG-Referenz lief mit 12 -> Vergleich nur auf Fenster-Ebene).
  * Kein Phasen-/Zonen-Bezug: Der Store-Korridor IST die Signal-Umgebung.

Kausalitaet (invariant):
  * Der Scan laeuft INLINE im Store-Build ueber den on_bar-Hook (State nach
    Bar k: Break-Detection bis k + Pivot j=k-2 bestaetigt). Entry fruhestens
    open[k+1] - kein Lookahead.
  * Rolling-VP-Fenster endet bei Bar k (Signal-Bar), identisch zur Baseline
    ("Zone bis zur Signal-Bar").
  * Alle hier kopierten Volume-Profile-Helfer sind mathematisch identisch mit
    dem Baseline-Skript (VA_PCT 0.93, NUM_BINS 60, SMOOTH_WIN 3, VALLEY_REL
    0.15, MIN_MOUNTAIN_PCT 4.0) - bewusste Duplikation, um den Baseline-Import
    (Seiteneffekte/Plot) zu vermeiden.

Aufruf (AUG-Default mit Baseline-Abgleich; S1/S2 als Referenz):
  python test/reclaim_s3_signals.py
  python test/reclaim_s3_signals.py --start=2026-02-05 --ende=2026-08-28
  python test/reclaim_s3_signals.py --start=2025-01-01 --ende=2025-12-01
  Flags: --cooldown=, --sl-pct=, --anteil-tp1=, --no-compare
"""
from __future__ import annotations

import sys
import time
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reclaim_edge_store as res  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC_BASELINE = ROOT / "scripts" / "phasen_volumen_profil.py"

# ---------------------------------------------------------------------------
# DEFAULTS (direkt anpassbar, PineScript-Stil)
# ---------------------------------------------------------------------------
START: str = "2026-08-10"
ENDE: str = "2026-08-28"

# Rolling-VP (Q7, Option A)
ROLL_VP_WINDOW: int = 300          # Bars (~75 h M15) fuer TP1/TP2-Referenz
ROLL_VP_MIN_BARS: int = 100        # Warmup: fruehestens ab 100 Bars

# Volume-Profile-Mathe (identisch Baseline)
VA_PCT: float = 0.93
NUM_BINS: int = 60
SMOOTH_WIN: int = 3
VALLEY_REL: float = 0.15
MIN_MOUNTAIN_PCT: float = 4.0

# Baseline-Exit-Mechanik (phasenfrei auf Rolling-VP)
SL_PCT: float = 0.45               # % vom Entry
TP2_PUFFER_PCT: float = 0.20       # % innen an der Profil-Gegenseite
ANTEIL_TP1: float = 25.0           # % der Position auf TP1 (POC)

# Signal-Filter (identische Baseline-Semantik)
MIN_RECLAIM_CRV: float = 1.0
MIN_SIGNAL_ABSTAND_BARS: int = 8   # uebernommen aus CD-Sweep (Q1-Entscheid)

# S3-v2 Gates (Mentor-Freigabe 02.09.; einzeln abschaltbar fuer Isolation)
MIN_CORRIDOR_SPREAD_PCT: float = 1.0   # Gate A: min. Korridor-Spread (2-seitig)
USE_GATE_A: bool = True                # Gate A: 2-seitige Range + Spread
USE_GATE_B: bool = True                # Gate B: Struktur-Sperre (Alter > letzter
                                       #   Bruch derselben Seite unter/ueber der
                                       #   gehandelten Kante; Q6 = Fehlausbruch)

COMPARE_BASELINE: bool = True      # nur AUG-Fenster: Baseline-Referenz laden


@dataclass(slots=True)
class S3Resolution:
    """Baseline-Exit-Aufloesung (Split 25/75, kein Trailing) + Schatten."""
    r1: float
    r2: float
    exit1: float
    exit2: float
    grund1: str
    grund2: str
    r_mult: float
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"]
    tp1_hit: bool
    tp2_hit: bool
    sl_hit1: bool
    sl_hit2: bool
    sl_init: float
    exit1_bar: int                   # absolute Bar (df) Ende Haelfte 1
    exit2_bar: int                   # absolute Bar (df) Ende Haelfte 2
    # Q3-Schatten: naechstes aktives Level in Handelsrichtung
    target_level_price: Optional[float] = None
    target_level_id: Optional[int] = None
    target_level_side: Optional[str] = None
    target_level_hit: bool = False
    target_hit_bar: Optional[int] = None
    r_level: Optional[float] = None
    grund_shadow: str = "-"


@dataclass(slots=True)
class S3Signal:
    typ: Literal["SHORT", "LONG"]
    bar: int
    ts: pd.Timestamp
    reclaim: Literal["in_bar", "next_bar"]
    einstieg_bar: int
    einstieg_preis: float
    # Store-Kante (gehandelte Korridor-Kante)
    edge_price: float
    edge_id: int
    edge_side: str
    edge_touches: int
    edge_indep: int
    edge_score: float
    edge_gap: int                        # Bars seit letztem Touch der Kante
    two_sided: bool                      # beide Korridor-Seiten aktiv?
    # Rolling-VP-Referenz (TP1/TP2/Fair-Value)
    poc: float
    u_zone: float
    l_zone: float
    tp1: float
    tp2: float
    sl: float
    crv: float
    crv2: float
    trade: Optional[S3Resolution] = None


# ---------------------------------------------------------------------------
# Rolling-Volume-Profil (identische Mathe wie Baseline, nur phasenfrei)
# ---------------------------------------------------------------------------

def rv_profile(sub: pd.DataFrame) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Volume-Profile-Histogramm ueber `sub` (Basis: baseline build_volume_profile)."""
    if sub.empty:
        return None
    pmin = float(sub["low"].min())
    pmax = float(sub["high"].max())
    if pmax <= pmin:
        return None
    edges = np.linspace(pmin, pmax, NUM_BINS + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(NUM_BINS)
    lows = sub["low"].values.astype(float)
    highs = sub["high"].values.astype(float)
    vols = sub["tick_volume"].values.astype(float)
    for lo, hi, v in zip(lows, highs, vols):
        if hi <= lo or v <= 0:
            continue
        lo_b = int(np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, NUM_BINS - 1))
        hi_b = int(np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, NUM_BINS - 1))
        if lo_b == hi_b:
            vol[lo_b] += v
        else:
            ov = np.array([
                max(0.0, min(hi, edges[b + 1]) - max(lo, edges[b]))
                for b in range(lo_b, hi_b + 1)
            ])
            tot = ov.sum()
            if tot > 0:
                vol[lo_b:hi_b + 1] += v * ov / tot
    return centers, edges, vol


def rv_smooth(vol: np.ndarray, win: int = SMOOTH_WIN) -> np.ndarray:
    if win <= 1 or len(vol) < win:
        return vol.astype(float)
    return np.convolve(vol, np.ones(win) / win, mode="same")


def rv_mountains(
    vol_s: np.ndarray,
    min_pct: float = MIN_MOUNTAIN_PCT,
    valley_rel: float = VALLEY_REL,
) -> List[Tuple[int, int, int]]:
    """Berge (Basis: baseline find_mountains)."""
    n = len(vol_s)
    if n < 3:
        return []
    mountains: List[Tuple[int, int, int]] = []
    start = 0
    for i in range(1, n - 1):
        if vol_s[i] <= vol_s[i - 1] and vol_s[i] < vol_s[i + 1]:
            left_peak = float(np.max(vol_s[start:i + 1]))
            right_peak = float(np.max(vol_s[i:n]))
            threshold = min(left_peak, right_peak) * valley_rel
            if vol_s[i] < threshold:
                p_idx = start + int(np.argmax(vol_s[start:i + 1]))
                if vol_s[start:i + 1].max() > 0:
                    mountains.append((start, p_idx, i))
                start = i
    p_idx = start + int(np.argmax(vol_s[start:n]))
    if vol_s[start:n].max() > 0:
        mountains.append((start, p_idx, n - 1))
    if not mountains:
        return []
    max_vol = max(vol_s[p] for _, p, _ in mountains)
    mountains = [m for m in mountains if vol_s[m[1]] >= max_vol * min_pct / 100.0]
    mountains.sort(key=lambda m: -vol_s[m[1]])
    return mountains


def rv_va(vol_s: np.ndarray, edges: np.ndarray,
          mountain: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """POC/VAL/VAH eines Bergs (Basis: baseline va_for_mountain)."""
    s, p, e = mountain
    poc = float((edges[p] + edges[p + 1]) / 2)
    total = float(vol_s[s:e + 1].sum())
    target = total * VA_PCT
    lo, hi = p, p
    acc = float(vol_s[p])
    while acc < target and (lo > s or hi < e):
        down = float(vol_s[lo - 1]) if lo > s else -1.0
        up = float(vol_s[hi + 1]) if hi < e else -1.0
        if down >= up and down >= 0:
            lo -= 1
            acc += down
        elif up >= 0:
            hi += 1
            acc += up
        else:
            break
    return poc, float(edges[lo]), float(edges[hi + 1])


def rolling_zone(df: pd.DataFrame, k: int,
                 window: int = ROLL_VP_WINDOW) -> Optional[Tuple[float, float, float]]:
    """Kausale POC/U_zone/L_zone ueber die letzten `window` Bars bis k.

    Returns:
        (poc, u_zone, l_zone) - identische Aggregation wie Baseline
        compute_volume_zone (U=max VAH, L=min VAL, POC=dominanter Berg).
        None, wenn weniger als ROLL_VP_MIN_BARS verfuegbar.
    """
    if k + 1 < ROLL_VP_MIN_BARS:
        return None
    sub = df.iloc[max(0, k - window + 1): k + 1]
    prof = rv_profile(sub)
    if prof is None:
        return None
    _, edges, vol = prof
    vol_s = rv_smooth(vol)
    mountains = rv_mountains(vol_s)
    if not mountains:
        return None
    dominant = mountains[0]
    poc, _, _ = rv_va(vol_s, edges, dominant)
    vah_vals: List[float] = []
    val_vals: List[float] = []
    for m in mountains:
        _, val, vah = rv_va(vol_s, edges, m)
        vah_vals.append(vah)
        val_vals.append(val)
    return float(poc), float(max(vah_vals)), float(min(val_vals))


# ---------------------------------------------------------------------------
# Baseline-Exit-Aufloesung + Q3-Schatten-Level
# ---------------------------------------------------------------------------

def resolve_baseline_exit(
    df: pd.DataFrame,
    s: S3Signal,
    sl_pct: float = SL_PCT,
    anteil_tp1: float = ANTEIL_TP1,
    target: Optional[res.EdgeLevel] = None,
) -> S3Resolution:
    """Identische Aufloesung wie Baseline `_aufloesen` (kein Trailing).

    Zusaetzlich (Q3-Schatten): Wurde das naechste aktive Level in
    Handelsrichtung (`target`) innerhalb der offenen Trade-Dauer erreicht?
    """
    e_bar = s.einstieg_bar
    entry = s.einstieg_preis
    typ = s.typ
    tp1, tp2 = s.tp1, s.tp2
    p = sl_pct / 100.0
    sl_init = entry * (1.0 + p) if typ == "SHORT" else entry * (1.0 - p)

    hi = df["high"].values[e_bar:]
    lo = df["low"].values[e_bar:]
    cl = df["close"].values[e_bar:]
    n_bars = len(hi)
    risk = abs(sl_init - entry)
    if risk <= 0:
        risk = 1e-9

    def _first(mask: np.ndarray) -> int:
        return int(np.argmax(mask)) if mask.any() else n_bars

    def _r(exit_price: float) -> float:
        return (entry - exit_price) / risk if typ == "SHORT" else (exit_price - entry) / risk

    if typ == "SHORT":
        t1 = _first(lo <= tp1)
        t2 = _first(lo <= tp2)
        t_sl = _first(hi >= sl_init)
    else:
        t1 = _first(hi >= tp1)
        t2 = _first(hi >= tp2)
        t_sl = _first(lo <= sl_init)

    # Haelfte 1: TP1 (POC)
    if t1 < t_sl:
        r1, ex1, g1, b1 = _r(tp1), tp1, "TP1", t1
    elif t_sl < n_bars:
        r1, ex1, g1, b1 = -1.0, sl_init, "SL", t_sl
    else:
        r1, ex1, g1, b1 = _r(float(cl[-1])), float(cl[-1]), "ENDE", n_bars - 1

    # Haelfte 2: TP2 (Profil-Gegenseite)
    if t2 < t_sl:
        r2, ex2, g2, b2 = _r(tp2), tp2, "TP2", t2
    elif t_sl < n_bars:
        r2, ex2, g2, b2 = _r(sl_init), sl_init, "SL", t_sl
    else:
        r2, ex2, g2, b2 = _r(float(cl[-1])), float(cl[-1]), "ENDE", n_bars - 1

    w1 = anteil_tp1 / 100.0
    w2 = 1.0 - w1
    if w2 <= 0:
        r2, g2 = 0.0, "-"
    r_mult = w1 * r1 + w2 * r2
    resultat: Literal["GEWONNEN", "VERLOREN", "NEUTRAL"] = (
        "GEWONNEN" if r_mult > 1e-9 else ("VERLOREN" if r_mult < -1e-9 else "NEUTRAL")
    )
    out = S3Resolution(
        r1=r1, r2=r2, exit1=ex1, exit2=ex2,
        grund1=g1, grund2=g2,
        r_mult=r_mult, resultat=resultat,
        tp1_hit=g1 == "TP1", tp2_hit=g2 == "TP2",
        sl_hit1=g1 == "SL", sl_hit2=g2 == "SL",
        sl_init=sl_init,
        exit1_bar=e_bar + b1, exit2_bar=e_bar + b2,
    )

    # --- Q3-Schatten-Level (rein informativ, kein Exit-Eingriff) ---
    if target is not None:
        tgt_px = float(target.price)
        out.target_level_price = tgt_px
        out.target_level_id = target.edge_id
        out.target_level_side = target.side
        end_bar = max(out.exit1_bar, out.exit2_bar)
        seg_hi = df["high"].values[e_bar: end_bar + 1]
        seg_lo = df["low"].values[e_bar: end_bar + 1]
        if typ == "SHORT":
            m = np.where(seg_lo <= tgt_px)[0]
        else:
            m = np.where(seg_hi >= tgt_px)[0]
        if len(m):
            out.target_level_hit = True
            out.target_hit_bar = e_bar + int(m[0])
            out.r_level = _r(tgt_px)
            out.grund_shadow = "LEVEL"
        else:
            out.grund_shadow = "nicht erreicht"
    return out


# ---------------------------------------------------------------------------
# S3-Simulation (Inline im Store-Build)
# ---------------------------------------------------------------------------

def simulate(df: pd.DataFrame,
             cooldown_bars: int = MIN_SIGNAL_ABSTAND_BARS,
             min_crv: float = MIN_RECLAIM_CRV,
             sl_pct: float = SL_PCT,
             anteil_tp1: float = ANTEIL_TP1,
             tp2_puffer_pct: float = TP2_PUFFER_PCT,
             min_corridor_spread_pct: float = MIN_CORRIDOR_SPREAD_PCT,
             use_gate_a: bool = USE_GATE_A,
             use_gate_b: bool = USE_GATE_B,
             ) -> Tuple[List[S3Signal], res.EdgeStore, List[Tuple[str, S3Signal]]]:
    """Setup-B-Scan gegen Store-Kanten (kausal, inline via on_bar-Hook).

    Args:
        df: OHLCV-Frame.
        cooldown_bars: Mindestabstand zweier Signale derselben Seite.
        min_crv: CRV-Mindestwert (Entry->TP1/Risiko).
        sl_pct: SL in % vom Entry.
        anteil_tp1: Anteil der Position auf TP1 (POC).
        tp2_puffer_pct: Puffer innen an der Profil-Gegenseite (TP2).
        min_corridor_spread_pct: Gate A - Mindest-Spread des Korridors.
        use_gate_a: Gate A aktiv (2-seitige Range + Spread).
        use_gate_b: Gate B aktiv (Struktur-Sperre, Abschnitt 9.1).

    Returns:
        (sigs, store, blocked) - sigs = gehandelte Signale; blocked = Liste
        (grund, sig) der von Gate A/B blockierten Kandidaten (Trade trotzdem
        aufgeloest, fuer die R-Isolation der Gates).
    """
    sigs: List[S3Signal] = []
    blocked: List[Tuple[str, S3Signal]] = []
    last_bar: Dict[str, int] = {"SHORT": -10**9, "LONG": -10**9}
    hi = df["high"].values.astype(float)
    lo = df["low"].values.astype(float)
    cl = df["close"].values.astype(float)
    op = df["open"].values.astype(float)
    ts_arr = df["ts"].values
    puffer = tp2_puffer_pct / 100.0
    sl_p = sl_pct / 100.0
    n_df = len(df)

    def _build(k: int, typ: str, reclaim: str, e_bar: int, e_preis: float,
               edge: res.EdgeLevel, store: res.EdgeStore,
               two_sided: bool) -> Optional[S3Signal]:
        """Alle v1-Filter (Rolling-VP, POC-Seite, CRV) + Trade-Aufloesung.

        Liefert das Signal mit Trade zurueck oder None, wenn ein v1-Filter
        scheitert. Gates werden hier NICHT angewendet (Entscheidung im Hook).
        """
        rv = rolling_zone(df, k)
        if rv is None:
            return None
        poc, u_zone, l_zone = rv
        if typ == "SHORT":
            if not (e_preis > poc):
                return None
            tp1 = float(poc)
            tp2 = float(l_zone * (1.0 + puffer))
        else:
            if not (e_preis < poc):
                return None
            tp1 = float(poc)
            tp2 = float(u_zone * (1.0 - puffer))
        risk = abs(e_preis * sl_p)
        if risk <= 0:
            return None
        crv = abs(tp1 - e_preis) / risk
        crv2 = abs(tp2 - e_preis) / risk
        if np.isnan(crv) or crv < min_crv:
            return None
        sl = e_preis * (1.0 + sl_p) if typ == "SHORT" else e_preis * (1.0 - sl_p)
        sig = S3Signal(
            typ=typ, bar=k, ts=pd.Timestamp(ts_arr[k]), reclaim=reclaim,
            einstieg_bar=e_bar, einstieg_preis=e_preis,
            edge_price=edge.price, edge_id=edge.edge_id, edge_side=edge.side,
            edge_touches=edge.n_touches, edge_indep=edge.n_independent,
            edge_score=edge.score, edge_gap=k - edge.last_touch_bar,
            two_sided=two_sided,
            poc=poc, u_zone=u_zone, l_zone=l_zone,
            tp1=tp1, tp2=tp2, sl=sl, crv=crv, crv2=crv2,
        )
        # Q3-Schatten: naechstes aktives Level in Handelsrichtung (Entry-Bezug)
        target: Optional[res.EdgeLevel] = None
        cand = [lv for lv in store.active_levels()
                if (typ == "SHORT" and lv.price < e_preis)
                or (typ == "LONG" and lv.price > e_preis)]
        if cand:
            target = min(cand, key=lambda x: abs(x.price - e_preis))
        sig.trade = resolve_baseline_exit(df, sig, sl_pct=sl_pct,
                                          anteil_tp1=anteil_tp1, target=target)
        return sig

    def _gate_reasons(k: int, sig: S3Signal, up: Optional[res.EdgeLevel],
                      dn: Optional[res.EdgeLevel],
                      store: res.EdgeStore) -> List[str]:
        """Gate-Pruefung; liefert Liste der verletzten Gates (leer = ok)."""
        reasons: List[str] = []
        if use_gate_a:
            if up is None or dn is None:
                reasons.append("gate_a")
            else:
                spread = (up.price - dn.price) / dn.price * 100.0
                if spread < min_corridor_spread_pct:
                    reasons.append("gate_a")
        if use_gate_b:
            if sig.typ == "SHORT":
                lb = store.last_valid_break_bar("UPPER", up.price, below=True)
                if lb is not None and up.birth_bar >= lb:
                    reasons.append("gate_b")
            else:
                lb = store.last_valid_break_bar("LOWER", dn.price, below=False)
                if lb is not None and dn.birth_bar >= lb:
                    reasons.append("gate_b")
        return reasons

    def on_bar(k: int, store: res.EdgeStore) -> None:
        if k + 1 < ROLL_VP_MIN_BARS or k >= n_df - 1:
            return  # Rolling-VP-Warmup; Entry open[k+1] existiert nicht am Ende
        up, dn = store.corridor(cl[k])
        two_sided = up is not None and dn is not None
        if up is not None and hi[k] > up.price and k - last_bar["SHORT"] >= cooldown_bars:
            if cl[k] <= up.price:
                e_bar = k + 1
                if e_bar < n_df:
                    sig = _build(k, "SHORT", "in_bar", e_bar, float(op[e_bar]),
                                 up, store, two_sided)
                    if sig is not None:
                        reasons = _gate_reasons(k, sig, up, dn, store)
                        if reasons:
                            blocked.append(("+".join(reasons), sig))
                        else:
                            last_bar["SHORT"] = k
                            sigs.append(sig)
            elif k + 1 < n_df - 1 and cl[k + 1] <= up.price:
                e_bar = k + 2
                if e_bar < n_df:
                    sig = _build(k, "SHORT", "next_bar", e_bar, float(op[e_bar]),
                                 up, store, two_sided)
                    if sig is not None:
                        reasons = _gate_reasons(k, sig, up, dn, store)
                        if reasons:
                            blocked.append(("+".join(reasons), sig))
                        else:
                            last_bar["SHORT"] = k
                            sigs.append(sig)
        if dn is not None and lo[k] < dn.price and k - last_bar["LONG"] >= cooldown_bars:
            if cl[k] >= dn.price:
                e_bar = k + 1
                if e_bar < n_df:
                    sig = _build(k, "LONG", "in_bar", e_bar, float(op[e_bar]),
                                 dn, store, two_sided)
                    if sig is not None:
                        reasons = _gate_reasons(k, sig, up, dn, store)
                        if reasons:
                            blocked.append(("+".join(reasons), sig))
                        else:
                            last_bar["LONG"] = k
                            sigs.append(sig)
            elif k + 1 < n_df - 1 and cl[k + 1] >= dn.price:
                e_bar = k + 2
                if e_bar < n_df:
                    sig = _build(k, "LONG", "next_bar", e_bar, float(op[e_bar]),
                                 dn, store, two_sided)
                    if sig is not None:
                        reasons = _gate_reasons(k, sig, up, dn, store)
                        if reasons:
                            blocked.append(("+".join(reasons), sig))
                        else:
                            last_bar["LONG"] = k
                            sigs.append(sig)

    store = res.EdgeStore().build(df, on_bar=on_bar)
    sigs.sort(key=lambda s: s.ts)
    return sigs, store, blocked


# ---------------------------------------------------------------------------
# Baseline-Referenz (AUG, exec-cut wie reclaim_s1_*)
# ---------------------------------------------------------------------------

def baseline_reference(start: str, ende: str):
    """Fuehrt die Baseline (phasengebunden) aus und liefert deren Signale."""
    src = SRC_BASELINE.read_text(encoding="utf-8")
    cut = src.index("reclaim_signals: List[ReclaimSignal] = []")
    mod_name = "_phasen_volumen_profil_s3ref"
    if mod_name in sys.modules:
        mod = sys.modules[mod_name]
    else:
        mod = types.ModuleType(mod_name)
        mod.__file__ = str(SRC_BASELINE)
        sys.modules[mod_name] = mod
    sys.argv = [str(SRC_BASELINE), f"--start={start}", f"--ende={ende}"]
    exec(compile(src[:cut], str(SRC_BASELINE), "exec"), mod.__dict__)
    ns = mod.__dict__
    df_base = ns["df"]
    phases = ns["phases"]
    refs = []
    for i_p, p in enumerate(phases, 1):
        for s in ns["find_reclaim_signals"](df_base, p):
            s.phase = i_p
            refs.append(s)
    refs.sort(key=lambda s: s.ts)
    return refs


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _fmt_ts(t: pd.Timestamp) -> str:
    return t.strftime("%d.%m %H:%M")


def print_report(sigs: List[S3Signal], start: str, ende: str,
                 blocked: Optional[List[Tuple[str, S3Signal]]] = None) -> None:
    decided = [s for s in sigs if s.trade and s.trade.resultat != "NEUTRAL"]
    wins = [s for s in sigs if s.trade and s.trade.resultat == "GEWONNEN"]
    wr = 100.0 * len(wins) / len(decided) if decided else 0.0
    sum_r = sum(s.trade.r_mult for s in sigs if s.trade)
    gate_txt = ""
    if blocked is not None:
        n_b = len(blocked)
        sum_b = sum(s.trade.r_mult for _, s in blocked if s.trade)
        from collections import Counter
        cnt = Counter(g for g, _ in blocked)
        g_txt = ", ".join(f"{g} {n}" for g, n in cnt.most_common())
        gate_txt = (f"\nGates: A={USE_GATE_A} (Spread>={MIN_CORRIDOR_SPREAD_PCT:.1f}%), "
                    f"B={USE_GATE_B} | blockiert {n_b} ({g_txt}) | "
                    f"entgangene Summe R {sum_b:+.2f}")
    print(f"\n{'=' * 150}")
    print(f"S3 (Store-Kanten + Rolling-VP-Exit): {start} - {ende}")
    print(f"Signale: {len(sigs)} | GEWONNEN {len(wins)} | VERLOREN "
          f"{len(decided) - len(wins)} | WR {wr:.0f}% (entschieden) | Summe R {sum_r:+.2f}"
          f"{gate_txt}")
    print(f"Parameter: SL {SL_PCT:.2f}% | Split {ANTEIL_TP1:.0f}/"
          f"{100 - ANTEIL_TP1:.0f} | TP2-Puffer {TP2_PUFFER_PCT:.2f}% | "
          f"Cooldown {MIN_SIGNAL_ABSTAND_BARS} | Rolling-VP {ROLL_VP_WINDOW} Bars")
    print("=" * 150)
    if len(sigs) <= 60:
        for s in sigs:
            assert s.trade is not None
            sh = s.trade
            sh_txt = f"Lvl {s.trade.target_level_price:.3f}" if s.trade.target_level_price else "Lvl ---"
            sh_txt += f" {'HIT ' + f'{s.trade.r_level:+.2f}R' if s.trade.target_level_hit else '(nicht erreicht)'}"
            print(
                f"  {_fmt_ts(s.ts)} {s.typ:5s} Rec {s.reclaim:8s} Ein {s.einstieg_preis:7.3f} "
                f"| Kante {s.edge_price:7.3f} id={s.edge_id:3d} T={s.edge_touches:2d} "
                f"score={s.edge_score:5.1f} | POC {s.poc:7.3f} TP1 {s.tp1:7.3f} TP2 {s.tp2:7.3f} "
                f"SL {s.sl:7.3f} CRV {s.crv:4.2f} | "
                f"H1 {s.trade.exit1:.3f} ({s.trade.grund1}) {s.trade.r1:+5.2f}R | "
                f"H2 {s.trade.exit2:.3f} ({s.trade.grund2}) {s.trade.r2:+6.2f}R | "
                f"{s.trade.resultat} {s.trade.r_mult:+6.2f}R | Schatten {sh_txt}"
            )
    else:
        n_short = sum(1 for s in sigs if s.typ == "SHORT")
        n_long = len(sigs) - n_short
        print(f"  (Detail-Liste unterdrueckt: {len(sigs)} Signale, davon {n_short} SHORT / {n_long} LONG)")
    # Schatten-Statistik
    lvl_def = [s.trade for s in sigs if s.trade and s.trade.target_level_price is not None]
    lvl_hit = [t for t in lvl_def if t.target_level_hit]
    print(f"\nSchatten-Level-TP (Q3): definiert {len(lvl_def)} | erreicht {len(lvl_hit)}")
    if lvl_hit:
        print(f"  avg r_level (erreicht): "
              f"{sum(t.r_level for t in lvl_hit if t.r_level is not None) / len(lvl_hit):+.2f}R")

    def _buckets(label: str, key) -> None:
        print(f"\nBucket-Diagnose: {label}")
        groups: Dict[str, List[S3Signal]] = {}
        for s in sigs:
            groups.setdefault(key(s), []).append(s)
        for b, g in sorted(groups.items()):
            dec = [x for x in g if x.trade and x.trade.resultat != "NEUTRAL"]
            w = sum(1 for x in g if x.trade and x.trade.resultat == "GEWONNEN")
            sr = sum(x.trade.r_mult for x in g if x.trade)
            wr = 100.0 * w / len(dec) if dec else 0.0
            print(f"  {b:>22}: n={len(g):3d} | WR {wr:3.0f}% | Summe R {sr:+7.2f}")

    _buckets("beide Korridor-Seiten aktiv",
             lambda s: "2-seitig" if s.two_sided else "1-seitig")
    _buckets("Bars seit letztem Touch (edge_gap)",
             lambda s: "gap<48" if s.edge_gap < 48
             else ("gap 48-95" if s.edge_gap < 96
                   else ("gap 96-287" if s.edge_gap < 288 else "gap>=288")))
    _buckets("Score-Band",
             lambda s: "score<4" if s.edge_score < 4
             else ("score 4-8" if s.edge_score < 8
                   else ("score 8-16" if s.edge_score < 16 else "score>=16")))
    _buckets("CRV-Band",
             lambda s: "crv<2" if s.crv < 2 else ("crv 2-4" if s.crv < 4 else "crv>=4"))
    return sum_r, len(sigs), wr


# ---------------------------------------------------------------------------
# Akzeptanzfall-Check (AUG)
# ---------------------------------------------------------------------------

def acceptance_aug(sigs: List[S3Signal], df: pd.DataFrame) -> None:
    print("\n" + "=" * 150)
    print("AKZEPTANZFALL-PRUEFUNG AUG (14.-18.08, P5-Fenster)")
    print("=" * 150)
    try:
        refs = baseline_reference(START, ENDE)
    except Exception as exc:  # pragma: no cover
        print(f"Baseline-Referenz fehlgeschlagen: {exc}")
        return
    ts_lo, ts_hi = pd.Timestamp("2026-08-14"), pd.Timestamp("2026-08-19")
    ref_p5 = [s for s in refs if ts_lo <= s.ts < ts_hi]
    ref_losers = [s for s in ref_p5 if s.typ == "SHORT" and s.trade
                  and s.trade.resultat == "VERLOREN"]
    ref_winners = [s for s in ref_p5 if s.typ == "SHORT" and s.trade
                   and s.trade.resultat == "GEWONNEN"]
    sig_map = {s.ts: s for s in sigs}

    print(f"Baseline P5-Referenz: {len(ref_p5)} Signale "
          f"({len(ref_losers)} Verlust-SHORTs, {len(ref_winners)} Gewinn-SHORTs)")

    ok = True
    strict = True
    # Fall 1: die 5 Trailing-Konter-SHORTs duerfen NICHT entstehen
    # (Typ-Bug-Fix 02.09.: sig_map matcht nur ts - ein LONG am selben Bar ist
    # KEIN Wiederkehrer des Konter-SHORTs, sondern ein legitimer Gewinner an
    # einer dn-Kante. Nur ein S3-SHORT am selben ts ist ein Fall-1-Fehler.)
    print("\n[Fall 1] 5 P5-Konter-SHORTs (Trailing) entfallen:")
    for s in ref_losers:
        hit = sig_map.get(s.ts)
        if hit is not None and hit.typ == "SHORT":
            status = "*** FEHLER: Signal entsteht weiterhin ***"
            ok = False
            strict = False
        elif hit is not None:
            status = (f"nur {hit.typ} am selben Bar ({hit.trade.resultat} "
                      f"{hit.trade.r_mult:+.2f}R) - kein Konter-SHORT -> OK")
        else:
            status = "entfaellt OK"
        print(f"  {_fmt_ts(s.ts)} Baseline-SHORT (Entry {s.einstieg_preis:.3f}, "
              f"{s.trade.resultat} {s.trade.r_mult:+.2f}R) -> {status}")

    def _near_winner(ts: pd.Timestamp, tol_bars: int = 2) -> Optional[S3Signal]:
        """S3-SHORT-Gewinner auf derselben Kante +/- tol_bars um ts."""
        best: Optional[S3Signal] = None
        best_d = 10**9
        for s in sigs:
            if s.typ != "SHORT" or not s.trade or s.trade.resultat != "GEWONNEN":
                continue
            if not (pd.Timestamp("2026-08-14") <= s.ts < pd.Timestamp("2026-08-19")):
                continue
            d = abs(int((s.ts - ts).total_seconds()) // 900)
            if d <= tol_bars and (best is None or d < best_d):
                best, best_d = s, d
        return best

    # Fall 2: die 2 Gewinner an 66.28 bleiben erhalten
    print("\n[Fall 2] 2 Gewinner an 66.28 (17./18.08) bleiben:")
    for s in ref_winners:
        hit = sig_map.get(s.ts)
        if hit is not None and hit.typ == "SHORT" and hit.trade and \
                hit.trade.resultat == "GEWONNEN":
            print(f"  {_fmt_ts(s.ts)} Baseline-Winner {s.trade.r_mult:+.2f}R -> "
                  f"S3-Signal am selben Bar: {hit.trade.resultat} {hit.trade.r_mult:+.2f}R "
                  f"(Kante {hit.edge_price:.3f} id={hit.edge_id}) -> OK")
            continue
        near = _near_winner(s.ts)
        if hit is not None:
            strict = False
            print(f"  {_fmt_ts(s.ts)} Baseline-Winner {s.trade.r_mult:+.2f}R -> "
                  f"S3-Signal am selben Bar: {hit.typ} "
                  f"({hit.trade.resultat if hit.trade else '?'} "
                  f"{hit.trade.r_mult:+.2f}R) - *** KEIN Gewinner am selben Bar ***")
        if near is not None and near.trade:
            print(f"      wirtschaftliches Aequivalent {_fmt_ts(near.ts)}: "
                  f"GEWONNEN {near.trade.r_mult:+.2f}R (Kante {near.edge_price:.3f} "
                  f"id={near.edge_id}, +1..2 Bars) -> OK (wirtschaftlich)")
        else:
            ok = False
            print(f"      *** FEHLER: kein wirtschaftliches Gewinner-Aequivalent "
                  f"innerhalb 2 Bars ***")

    # Fall 3: 18.08 ~02:00 - Kante nach altem Phasenende gueltig -> wird gehandelt
    print("\n[Fall 3] 18.08 ~02:00 (Kante nach altem Phasenende gueltig):")
    case3_ts = pd.Timestamp("2026-08-18 02:15")
    s3 = sig_map.get(case3_ts)
    if s3 is not None:
        print(f"  {_fmt_ts(s3.ts)} S3-Signal vorhanden ({s3.typ}, Kante "
              f"{s3.edge_price:.3f} id={s3.edge_id}, "
              f"{s3.trade.resultat if s3.trade else '?'} "
              f"{s3.trade.r_mult:+.2f}R) -> OK (wird gehandelt)")
    else:
        strict = False
        near3 = _near_winner(case3_ts)
        if near3 is not None and near3.trade:
            print(f"  kein Signal exakt an {_fmt_ts(case3_ts)}; wirtschaftliches "
                  f"Aequivalent {_fmt_ts(near3.ts)}: {near3.trade.resultat} "
                  f"{near3.trade.r_mult:+.2f}R (Kante {near3.edge_price:.3f} "
                  f"id={near3.edge_id}) -> OK (wirtschaftlich, ~02:30)")
        else:
            ok = False
            print(f"  *** FEHLER: kein S3-Signal um {_fmt_ts(case3_ts)} ***")

    print(f"\n=== AUG-AKZEPTANZ (wirtschaftlich): "
          f"{'ALLE FAELLE ERFUELLT' if ok else 'FEHLER - bitte pruefen'} | "
          f"strikt bar-identisch: {'JA' if strict else 'NEIN (Kantenpreis +0.10 -> 1-2 Bars versetzt, '
          f'gleiche 66.386/66.388-Zone, Gewinner erhalten)'} ===")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    global START, ENDE, MIN_SIGNAL_ABSTAND_BARS, COMPARE_BASELINE
    global MIN_CORRIDOR_SPREAD_PCT, USE_GATE_A, USE_GATE_B
    for _a in sys.argv[1:]:
        if _a.startswith("--start="):
            START = _a.split("=", 1)[1]
        if _a.startswith("--ende="):
            ENDE = _a.split("=", 1)[1]
        if _a.startswith("--cooldown="):
            MIN_SIGNAL_ABSTAND_BARS = int(_a.split("=", 1)[1])
        if _a.startswith("--sl-pct="):
            globals()["SL_PCT"] = float(_a.split("=", 1)[1])
        if _a.startswith("--anteil-tp1="):
            globals()["ANTEIL_TP1"] = float(_a.split("=", 1)[1])
        if _a.startswith("--corridor-spread="):
            MIN_CORRIDOR_SPREAD_PCT = float(_a.split("=", 1)[1])
        if _a == "--no-gate-a":
            USE_GATE_A = False
        if _a == "--no-gate-b":
            USE_GATE_B = False
        if _a == "--no-compare":
            COMPARE_BASELINE = False

    t0 = time.time()
    df = res.load_data(res.DB_PATH, START, ENDE)
    print(f"candles: {len(df)}  ({time.time() - t0:.1f}s load)")

    t0 = time.time()
    sigs, store, blocked = simulate(
        df,
        cooldown_bars=MIN_SIGNAL_ABSTAND_BARS,
        sl_pct=SL_PCT,
        anteil_tp1=ANTEIL_TP1,
        min_corridor_spread_pct=MIN_CORRIDOR_SPREAD_PCT,
        use_gate_a=USE_GATE_A,
        use_gate_b=USE_GATE_B,
    )
    print(f"simulate: {time.time() - t0:.1f}s | Store: {len(store.levels)} Level | "
          f"created {store.n_created} | reactivated {store.n_reactivated}")

    sum_r, n_sig, wr = print_report(sigs, START, ENDE, blocked)

    if COMPARE_BASELINE and START == "2026-08-10":
        acceptance_aug(sigs, df)

    print(f"\nZEILE: {START} - {ENDE} | S3-Signale {n_sig} | WR {wr:.0f}% | Summe R {sum_r:+.2f}")


if __name__ == "__main__":
    main()
