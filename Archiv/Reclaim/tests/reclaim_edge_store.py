# test/reclaim_edge_store.py
"""EdgeStore - Kantenspeicher-Prototyp (S1 + S2, Konzept docs/reclaim.md).

Scope S1 (Design-Entscheidungen Q1/Q4/Q5/Q6, 02.09.2026):
  * Seeds ausschliesslich aus bestaetigten H/L-Pivots (PIVOT_LOOKBACK=2,
    Williams-Fraktal-aequivalent) - KEINE Volume-Zonen-/Phasen-Seeds (Q1).
  * Volumen ist nur Touch-Attribut: Touch-Bar-Volumen >> rollierender Median
    -> Touch-Typ "volume_cluster" (Q1, Abschnitt 6).
  * Matching raum-zeitlich: Pivot innerhalb EDGE_TOL eines bestehenden Levels
    = Touch (keine Neuanlage), sonst neues Kandidaten-Level.
  * Lebenszyklus: candidate -> active (>= MIN_EDGE_TOUCHES unabhaengige
    Touches ODER 1 High-Volume-Touch) -> sleeping (2-Close-Bruch, Abschnitt
    9.1/10.4). sleeping bleibt als Referenz in den Bins.
  * RE-AKTIVIERUNG (Q6): sleeping + bestaetigter Pivot GLEICHER Orientierung
    (kind H an UPPER / kind L an LOWER) in EDGE_TOL = Re-Validierung ->
    zurueck auf active (Historie bleibt, kein Zeitfenster).
  * Korridor (Vereinfachung Q5): naechstes aktives Level ueber dem Close
    (SHORT-Seite) / unter dem Close (LONG-Seite).
    BEKANNTE SCHWAECHE (User 02.09.): Nach einem Breakout liegt der Close
    jenseits der gebrochenen Kante (-> sleeping); bis ein neuer gegen-
    seitiger Pivot entsteht, kann die Korridor-Seite unter dem Kurs leer
    sein (None) -> Reclaims im Niemandsland unmoeglich. Wird in S3 geloest
    (Korridor = letzte ungebrochene Kante + Bruchpunkt wird Level, 9.1/10.4).

Scope S2 - Confluence-Score v1 (Architektur-Vorgaben User, 02.09.):
  * rel_volume(touch) = tick_volume / ROLLIERENDER MEDIAN der vorangegangenen
    VOL_REF_LOOKBACK Bars (shift(1)). NIEMALS Gesamtdurchschnitt (Lookahead).
  * Decay auf HANDELSZEIT = Bars (jede verarbeitete M15-Zeile = 1 Schritt),
    nicht auf Wanduhrzeit. Wochenenden/Feiertage altern keine Kante (sie
    existieren nicht als Bars im Datensatz).
  * Score INKREMENTELL: score(lev,k) = d * score(lev,k-1) + touch_contrib,
    d = exp(-1 / EDGE_HALF_LIFE_BARS). Jeder Touch addiert seinen gewichteten
    Wert; ohne frische Touches zerfaellt der Score stetig.
  * touch_contrib = W_VOLUME*rel_volume + W_TYPE[touch_type]
                    + W_COUNT (nur wenn unabhaengiger Touch, spacing).
  * w_grid / w_session bleiben reine Neben-Gewichte (0.0) - nicht vor S4 anfassen.

Der Kantenspeicher ist ein bewusster sequenzieller kausaler Prozess (wie der
Signal-Loop im Hauptskript) - Ausnahme zur Vektorisierungs-Regel.

Nur Modulebene: keine Seiteneffekte beim Import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# DEFAULTS (direkt anpassbar, PineScript-Stil)
# ---------------------------------------------------------------------------
DB_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"

PIVOT_LOOKBACK: int = 2          # n=2 => 5-Bar-Fenster (identisch Baseline)
EDGE_TOL: float = 0.15           # USD; Matching-Band (war DENSITY_BAND 0.15)
MIN_EDGE_TOUCHES: int = 2        # unabhaengige Touches fuer status=active
MIN_TOUCH_SPACING_BARS: int = 5  # Mindestabstand zweier "unabhaengiger" Touches
VOL_CLUSTER_MULT: float = 2.0    # Touch-Vol >= mult * roll. Median => volume_cluster
VOL_REF_LOOKBACK: int = 200      # Bars (~50h M15) fuer rollierenden Volumen-Median
BREAK_CLOSES: int = 2            # Closes jenseits der Kante => sleeping (9.1)

# S2: Confluence-Score v1 (Defaults; Kalibrierung in S4-Sweep, nie nur S1)
EDGE_HALF_LIFE_BARS: int = 2880  # ~30 Handelstage (96 M15-Bars/Tag), Bar-basiert
W_VOLUME: float = 1.0            # Gewicht rel_volume (roll. Median)
W_COUNT: float = 0.5             # Gewicht je unabhaengigem Touch (spacing)
TOUCH_TYPE_WEIGHTS: Dict[str, float] = {
    "pivot_test": 1.0,       # normaler Pivot-Test
    "volume_cluster": 1.5,   # institutionelle Reaktion (Abschnitt 7.2) > Test
    "counter_run": 1.2,      # Rollen-Tausch-Bestaetigung (Abschnitt 7.3)
}

SYMBOL: str = "SILVER"
TIMEFRAME: str = "M15"


@dataclass(slots=True)
class EdgeTouch:
    """A single price reaction at an EdgeLevel (causal, pivot-confirmed)."""
    bar: int
    ts: pd.Timestamp
    kind: Literal["H", "L"]
    price: float
    tick_volume: float
    rel_volume: float                     # tick_volume / rolling median
    touch_type: Literal["pivot_test", "volume_cluster", "counter_run"]
    follow_swing: float = 0.0             # post-hoc, filled in S2+ (0.0 in S1)


@dataclass(slots=True)
class EdgeLevel:
    """A horizontal memory level with touch history (Abschnitt 4/5)."""
    edge_id: int
    side: Literal["UPPER", "LOWER"]       # from seed pivot kind (H/L)
    price: float                          # volume-weighted band mean
    status: Literal["candidate", "active", "sleeping"] = "candidate"
    birth_bar: int = 0
    birth_ts: Optional[pd.Timestamp] = None
    last_touch_bar: int = -1
    last_touch_ts: Optional[pd.Timestamp] = None
    touches: List[EdgeTouch] = field(default_factory=list)
    n_touches: int = 0                    # all touches
    n_independent: int = 0                # spaced touches (activation)
    last_independent_bar: int = -10**9
    last_sleep_bar: int = -10**9          # iter des letzten 2-Close-Bruchs (S3,
                                          # Gate B: Struktur-Sperre, Abschnitt 9.1)
    score: float = 0.0                    # S2: inkrementeller Confluence-Score

    def add_touch(self, t: EdgeTouch, spacing_bars: int) -> bool:
        """Append a touch, update counters and the volume-weighted price.

        Returns:
            True if this touch counts as independent (spacing satisfied).
        """
        self.touches.append(t)
        self.n_touches += 1
        if self.birth_ts is None:
            self.birth_ts = t.ts
        self.last_touch_bar = t.bar
        self.last_touch_ts = t.ts
        independent = t.bar - self.last_independent_bar >= spacing_bars
        if independent:
            self.n_independent += 1
            self.last_independent_bar = t.bar
        w = np.asarray([x.tick_volume for x in self.touches], dtype=float)
        p = np.asarray([x.price for x in self.touches], dtype=float)
        w = np.maximum(w, 1e-9)
        self.price = float(np.average(p, weights=w))
        return independent


class EdgeStore:
    """Sequential causal store of horizontal levels (S1 prototype)."""

    def __init__(
        self,
        edge_tol: float = EDGE_TOL,
        min_edge_touches: int = MIN_EDGE_TOUCHES,
        min_touch_spacing_bars: int = MIN_TOUCH_SPACING_BARS,
        vol_cluster_mult: float = VOL_CLUSTER_MULT,
        vol_ref_lookback: int = VOL_REF_LOOKBACK,
        break_closes: int = BREAK_CLOSES,
        pivot_lookback: int = PIVOT_LOOKBACK,
        half_life_bars: int = EDGE_HALF_LIFE_BARS,
        w_volume: float = W_VOLUME,
        w_count: float = W_COUNT,
        w_type: Optional[Dict[str, float]] = None,
    ) -> None:
        self.edge_tol = float(edge_tol)
        self.min_edge_touches = int(min_edge_touches)
        self.min_spacing = int(min_touch_spacing_bars)
        self.vol_mult = float(vol_cluster_mult)
        self.vol_lookback = int(vol_ref_lookback)
        self.break_closes = int(break_closes)
        self.pivot_lookback = int(pivot_lookback)

        # S2: Confluence-Score v1
        self.half_life_bars = int(half_life_bars)
        self.w_volume = float(w_volume)
        self.w_count = float(w_count)
        self.w_type: Dict[str, float] = (
            dict(TOUCH_TYPE_WEIGHTS) if w_type is None else dict(w_type)
        )
        self._decay = (
            float(np.exp(-1.0 / self.half_life_bars))
            if self.half_life_bars > 0 else 0.0
        )

        self.levels: List[EdgeLevel] = []
        self._watch: List[EdgeLevel] = []            # candidate/active only
        self._bins: Dict[int, List[EdgeLevel]] = {}  # price buckets (incl. sleeping)
        self._next_id: int = 1

        # counters for diagnostics
        self.n_created: int = 0
        self.n_touch_events: int = 0
        self.n_activated: int = 0
        self.n_reactivated: int = 0
        self.n_sleeping: int = 0

        # causal corridor snapshots (bar -> lightweight copy), set via build()
        self.snapshots: Dict[int, Tuple[Optional[Tuple[float, int, str, int]],
                                        Optional[Tuple[float, int, str, int]]]] = {}

        # status-transition audit log: {iter, edge_id, event, price, touch_bar}
        # iter = bar at which the change is causally known (pivot j known at j+n).
        self.transitions: List[Dict[str, object]] = []

        # data references (set by build)
        self.df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------ bins
    @staticmethod
    def _bin(price: float, tol: float) -> int:
        return int(price / tol + 0.5)

    def _bin_keys(self, price: float) -> List[int]:
        k = self._bin(price, self.edge_tol)
        return [k + d for d in (-2, -1, 0, 1, 2)]

    def _index_level(self, lev: EdgeLevel) -> None:
        k = self._bin(lev.price, self.edge_tol)
        self._bins.setdefault(k, []).append(lev)

    def _reindex_level(self, lev: EdgeLevel, old_price: float) -> None:
        k_old = self._bin(old_price, self.edge_tol)
        k_new = self._bin(lev.price, self.edge_tol)
        if k_old == k_new:
            return
        bucket = self._bins.get(k_old)
        if bucket is not None and lev in bucket:
            bucket.remove(lev)
        self._bins.setdefault(k_new, []).append(lev)

    # --------------------------------------------------------------- helpers
    def _nearest_match(self, price: float) -> Optional[EdgeLevel]:
        """Nearest non-discarded level within EDGE_TOL (sleeping allowed)."""
        best: Optional[EdgeLevel] = None
        best_d: float = self.edge_tol + 1e-9
        for k in self._bin_keys(price):
            for lev in self._bins.get(k, ()):
                d = abs(lev.price - price)
                if d > best_d:
                    continue
                better_status = (
                    d == best_d
                    and lev.status in ("candidate", "active")
                    and best is not None
                    and best.status == "sleeping"
                )
                if d < best_d or better_status:
                    best, best_d = lev, d
        return best

    def _log_transition(self, iter_k: int, lev: EdgeLevel, event: str,
                        touch_bar: Optional[int] = None) -> None:
        self.transitions.append({
            "iter": iter_k, "edge_id": lev.edge_id, "event": event,
            "price": float(lev.price), "touch_bar": touch_bar,
        })

    # ------------------------------------------------------------ S2: score
    def _apply_decay(self) -> None:
        """Per-bar score decay (S2, handelszeit-basiert: 1 Zeile = 1 Schritt).

        score(lev) *= exp(-1 / EDGE_HALF_LIFE_BARS)  -- applied once per bar.
        A level loses score steadily unless fresh touches recharge it.
        """
        if self._decay == 0.0 or not self.levels:
            return
        d = self._decay
        for lev in self.levels:
            lev.score *= d

    def _touch_contrib(self, lev: EdgeLevel, ttype: str,
                       rel_vol: float, independent: bool) -> float:
        """Incremental score contribution of a single touch (S2)."""
        contrib = self.w_volume * rel_vol + self.w_type.get(ttype, 1.0)
        if independent:
            contrib += self.w_count
        return float(contrib)

    def _set_sleeping(self, lev: EdgeLevel, iter_k: int) -> None:
        if lev.status == "sleeping":
            return
        lev.status = "sleeping"
        lev.last_sleep_bar = iter_k          # S3/Gate B: Bruch-Zeitpunkt kausal
        self.n_sleeping += 1
        if lev in self._watch:
            self._watch.remove(lev)
        self._log_transition(iter_k, lev, "sleep")

    def _check_break(self, k: int) -> None:
        """Elastischer rollen-agnostischer 2-Close-Bruch (Store-Reparatur 02.09.).

        Hysterese-Band [p - tol, p + tol] mit tol = self.edge_tol (0.15 USD,
        Wiederverwendung der Matching-Toleranz - kein neuer Parameter):
        Verharren INNERHALB des Bandes bricht nie (kein Retail-Mikroskopie-
        Cent-Crossing). Erst der entscheidende 2-Close-AUSTRITT echt jenseits
        der Bandkante ist ein Bruch.

        up_break (Resistance-Bruch): Markt war nicht etabliert ueber dem Band
            (c_before <= p+tol) und schliesst 2x echt darueber (> p+tol).
        dn_break (Support-Bruch):    Markt war nicht etabliert unter dem Band
            (c_before >= p-tol) und schliesst 2x echt darunter (< p-tol).
        c_before in der Hysterese-Zone zaehlt als Naheseite (Einseiten-Gate);
        ein Zwang zu c_before echt ausserhalb erzeugt eine Deadzone (ein
        Level, das nach einem Band-Zwischenstopp nie mehr bricht).

        Symmetrie: tol wirkt in beide Richtungen richtungsneutral - auch fuer
        Rollen-Tausch-Kanten (Seed-UPPER als Support nach unten, Seed-LOWER
        als Resistance nach oben). Die Bruchrichtung folgt der Markt-Rolle,
        nicht dem Seed `lev.side` (Mentor-Freigabe 02.09.).

        Beispiel 66.386 (17.08.26): Poke +0.026 (17:45, im Band) kippt die
        Rolle nicht; Closes 66.305/66.303 (18:00/18:15) liegen oberhalb
        p-tol=66.236 -> kein dn_break -> Kante ueberlebt als aktive Resistance.
        """
        if k < 2 or not self._watch or self.df is None:
            return
        c_before = float(self.df["close"].iloc[k - 2])  # Markt VOR dem Paar
        c_prev = float(self.df["close"].iloc[k - 1])
        c_now = float(self.df["close"].iloc[k])
        tol = float(self.edge_tol)
        for lev in list(self._watch):
            p = float(lev.price)
            up_break = c_before <= p + tol and c_prev > p + tol and c_now > p + tol
            dn_break = c_before >= p - tol and c_prev < p - tol and c_now < p - tol
            if up_break or dn_break:
                self._set_sleeping(lev, k)

    # ------------------------------------------------------------------ build
    def build(self, df: pd.DataFrame,
              record_bars: Optional[set] = None,
              on_bar: Optional[Callable[[int, "EdgeStore"], None]] = None
              ) -> "EdgeStore":
        """Sequential causal construction bar by bar over `df`.

        Args:
            df: OHLCV frame (columns ts/open/high/low/close/tick_volume).
            record_bars: optional set of bar indices; for each bar the corridor
                (state after processing bar k) is snapshotted causally.
            on_bar: optional callback ``on_bar(k, store)`` invoked after bar k
                is fully processed (break detection + pivot confirmation at
                k-PIVOT_LOOKBACK). This is the exact decision state for a
                signal at bar k (entry no earlier than open k+1). S3 uses
                this hook to scan Setup-B candidates inline (no second pass,
                no lookahead). Default None keeps S1/S2 behaviour unchanged.
        """
        self.df = df
        record = record_bars or set()
        n = self.pivot_lookback
        h = df["high"].to_numpy(dtype=float)
        l = df["low"].to_numpy(dtype=float)
        v = df["tick_volume"].to_numpy(dtype=float)

        # Pivot flags (vectorized, identical to baseline find_pivots)
        hi_s = pd.Series(h)
        lo_s = pd.Series(l)
        is_hi = (
            (hi_s == hi_s.rolling(2 * n + 1, center=True, min_periods=1).max())
            & (hi_s.shift(n) < hi_s)
            & (hi_s.shift(-n) < hi_s)
        ).to_numpy().copy()
        is_lo = (
            (lo_s == lo_s.rolling(2 * n + 1, center=True, min_periods=1).min())
            & (lo_s.shift(n) > lo_s)
            & (lo_s.shift(-n) > lo_s)
        ).to_numpy().copy()
        is_hi[:n] = False
        is_hi[-n:] = False
        is_lo[:n] = False
        is_lo[-n:] = False

        # Rolling volume median (causal: shift(1), excludes current bar)
        vol_ref = (
            df["tick_volume"]
            .rolling(self.vol_lookback, min_periods=20)
            .median()
            .shift(1)
            .to_numpy(dtype=float)
        )

        for k in range(len(df)):
            # 1) S2: score decay for bar k (handelszeit-basiert: 1 Zeile = 1 Schritt)
            self._apply_decay()
            # 2) pivot confirmation FIRST: pivot bar j = k - n is the OLDER
            #    market event (touch at j, confirmed at k = j+n). Store-
            #    Reparatur 02.09. (Chronologie-Fix): der historische Touch
            #    wird VOR dem Bruch-Check der juengeren Closes k-1/k verarbeitet,
            #    damit ein vergangener Pivot nie einen zukuenftigen Bruch
            #    aushebeln kann (Q6 nur aus strikt frueheren sleeps, s.u.).
            j = k - n
            if j >= 0:
                if is_hi[j]:
                    self._add_pivot(j, "H", float(h[j]), float(v[j]),
                                    float(vol_ref[j]) if vol_ref[j] == vol_ref[j] else np.nan)
                elif is_lo[j]:
                    self._add_pivot(j, "L", float(l[j]), float(v[j]),
                                    float(vol_ref[j]) if vol_ref[j] == vol_ref[j] else np.nan)
            # 3) 2-close break detection (Reaktion auf die juengsten Closes k-1/k)
            self._check_break(k)
            # 4) causal corridor snapshot after bar k (if requested)
            if k in record:
                up, dn = self.corridor(float(df["close"].iloc[k]))
                self.snapshots[k] = (
                    (up.price, up.n_touches, up.status, up.edge_id) if up else None,
                    (dn.price, dn.n_touches, dn.status, dn.edge_id) if dn else None,
                )
            # 5) S3 hook: exact decision state after bar k (entry >= open k+1)
            if on_bar is not None:
                on_bar(k, self)
        return self

    def _add_pivot(self, j: int, kind: Literal["H", "L"], price: float,
                   volume: float, vol_ref_j: float) -> None:
        """Register a confirmed pivot as touch (existing level) or seed."""
        assert self.df is not None
        high_vol = bool(
            vol_ref_j == vol_ref_j and volume >= self.vol_mult * vol_ref_j
        )
        rel_vol = (
            float(volume / vol_ref_j)
            if vol_ref_j == vol_ref_j and vol_ref_j > 0
            else 1.0
        )
        ts_j = self.df["ts"].iloc[j]

        lev = self._nearest_match(price)
        k_known = j + self.pivot_lookback  # iteration at which this pivot is known
        if lev is None:
            # --- create new candidate (seed) ---
            side: Literal["UPPER", "LOWER"] = "UPPER" if kind == "H" else "LOWER"
            ttype: Literal["pivot_test", "volume_cluster", "counter_run"] = (
                "volume_cluster" if high_vol else "pivot_test"
            )
            touch = EdgeTouch(bar=j, ts=ts_j, kind=kind, price=price,
                              tick_volume=volume, rel_volume=rel_vol,
                              touch_type=ttype)
            lev = EdgeLevel(edge_id=self._next_id, side=side, price=price,
                            birth_bar=j, birth_ts=ts_j)
            self._next_id += 1
            independent = lev.add_touch(touch, self.min_spacing)
            lev.score += self._touch_contrib(lev, ttype, rel_vol, independent)
            self.levels.append(lev)
            self._watch.append(lev)
            self._index_level(lev)
            self.n_created += 1
            self.n_touch_events += 1
            self._log_transition(k_known, lev, "create", touch_bar=j)
            if high_vol:
                lev.status = "active"
                self.n_activated += 1
                self._log_transition(k_known, lev, "activate_highvol", touch_bar=j)
            return

        # --- matching level found: append touch ---
        same_orientation = (kind == "H" and lev.side == "UPPER") or \
                           (kind == "L" and lev.side == "LOWER")
        if lev.status == "sleeping" and same_orientation and lev.last_sleep_bar < j:
            # Q6: re-validation of a broken level (failed break / re-test from
            # the pre-break side AFTER the break bar) -> back to active, history
            # stays intact. Guard `lev.last_sleep_bar < j` (Store-Reparatur
            # 02.09.): nur ein Pivot, dessen Bar strikt NACH dem Bruch-Bar liegt,
            # kann einen Fehl-Bruch validieren - ein historischer Pre-Bruch-
            # Pivot (Zeitreise) darf einen Bruch nie ungeschehen machen.
            lev.status = "active"
            self.n_reactivated += 1
            self._watch.append(lev)
            self._log_transition(k_known, lev, "reactivate", touch_bar=j)
            ttype = "volume_cluster" if high_vol else "pivot_test"
        elif lev.status == "sleeping" and same_orientation:
            # same-orientation pivot at a sleeping level whose bar lies BEFORE
            # the break (causal lag j+2 > break_iter): the level was still
            # active at pivot bar j; the touch is real history but cannot
            # reactivate (the break stays). No counter_run bonus (same
            # orientation is not a role flip).
            ttype = "volume_cluster" if high_vol else "pivot_test"
        elif lev.status == "sleeping":
            # opposite-orientation pivot at a broken level = role-flip test
            # (old UPPER re-tested from above as support etc., Abschnitt 7.3)
            ttype = "counter_run"
        elif lev.status == "candidate":
            ttype = "volume_cluster" if high_vol else "pivot_test"
        else:  # active
            ttype = "counter_run" if not same_orientation else \
                ("volume_cluster" if high_vol else "pivot_test")
        old_price = lev.price
        touch = EdgeTouch(bar=j, ts=ts_j, kind=kind, price=price,
                          tick_volume=volume, rel_volume=rel_vol,
                          touch_type=ttype)
        independent = lev.add_touch(touch, self.min_spacing)
        lev.score += self._touch_contrib(lev, ttype, rel_vol, independent)
        self._reindex_level(lev, old_price)
        self.n_touch_events += 1
        if lev.status == "candidate":
            last = lev.touches[-1]
            if lev.n_independent >= self.min_edge_touches or last.touch_type == "volume_cluster":
                lev.status = "active"
                self.n_activated += 1
                self._log_transition(k_known, lev, "activate", touch_bar=j)

    # --------------------------------------------------------------- corridor
    def corridor(
        self, close_price: float
    ) -> Tuple[Optional[EdgeLevel], Optional[EdgeLevel]]:
        """Nearest active level above close (SHORT) / below close (LONG)."""
        up: Optional[EdgeLevel] = None
        dn: Optional[EdgeLevel] = None
        for lev in self.levels:
            if lev.status != "active":
                continue
            if lev.price > close_price:
                if up is None or lev.price < up.price:
                    up = lev
            elif lev.price < close_price:
                if dn is None or lev.price > dn.price:
                    dn = lev
        return up, dn

    def last_valid_break_bar(self, side: Literal["UPPER", "LOWER"],
                             price_ref: float, below: bool) -> Optional[int]:
        """Letzter 2-Close-Bruch (sleeping) eines Levels der Seite `side`.

        S3-v2 Gate B (Struktur-Sperre, Abschnitt 9.1): Ein SHORT-Fade an einer
        UPPER-Kante ist nur zulaessig, wenn die Kante VOR dem letzten Bruch
        einer darunterliegenden UPPER-Kante existierte (Geburt vor dem
        Bruch-Ereignis) - frische Kanten der Expansionswelle sind Treppen-
        stufen, keine historische Struktur.

        Args:
            side: Orientierung der gebrochenen Kante ("UPPER"/"LOWER").
            price_ref: Preis der gehandelten (aktiven) Kante.
            below: True -> nur Brueche UNTER price_ref (SHORT-Fall);
                   False -> nur Brueche UEBER price_ref (LONG-Fall).

        Returns:
            iter (Bar) des letzten gueltigen Bruchs oder None.

        Kausalitaet: Wird im on_bar-Hook (Live-Zustand NACH Bar k) aufgerufen.
        Per Q6 reaktivierte Level sind `active` und fallen damit automatisch
        aus der Bruch-Menge (Fehlausbruch verifiziert = kein Trend-Bruch).
        Ein erneuter Bruch spaeter ueberschreibt `last_sleep_bar`.
        """
        best: Optional[int] = None
        for lev in self.levels:
            if lev.side != side or lev.status != "sleeping":
                continue
            if below and not (lev.price < price_ref):
                continue
            if not below and not (lev.price > price_ref):
                continue
            if lev.last_sleep_bar >= 0 and \
                    (best is None or lev.last_sleep_bar > best):
                best = lev.last_sleep_bar
        return best

    # ------------------------------------------------------------- diagnostics
    def status_counts(self) -> Dict[str, int]:
        cnt: Dict[str, int] = {"candidate": 0, "active": 0, "sleeping": 0}
        for lev in self.levels:
            cnt[lev.status] += 1
        return cnt

    def active_levels(self) -> List[EdgeLevel]:
        return [lev for lev in self.levels if lev.status == "active"]

    def levels_near(self, price: float, band: float) -> List[EdgeLevel]:
        return [lev for lev in self.levels if abs(lev.price - price) <= band]


def load_data(db_path: Path, start: str, ende: str) -> pd.DataFrame:
    """Load SILVER M15 OHLCV (UTC, Berlin wall clock invariant)."""
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB-Datei nicht gefunden: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    d = con.execute(f"""
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='{SYMBOL}' AND timeframe='{TIMEFRAME}'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
    """).fetchdf()
    con.close()
    d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)
    d["idx"] = np.arange(len(d))
    return d


if __name__ == "__main__":
    print("reclaim_edge_store: Modulebene OK (kein Seiteneffekt)")
