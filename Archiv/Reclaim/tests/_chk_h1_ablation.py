# -*- coding: utf-8 -*-
"""READ-ONLY H1-Ablation (6 Laeufe): S2-Pool / S2-Blocker / S3 / S4 isoliert.

Zweck
-----
V020 erzeugt in H1 14 Trades / +27.327383 R statt der Baseline 8 / +38.919584 R
(Delta -11.592201 R; H20.40). Verursacher sind die drei generell gewordenen
Kernpraedikate:
  S2  A_SB          : ``existiert_nativ`` (aktiv ODER realer Durchstich) --
                      wirkt DOPPELT (Kandidaten-Pool UND Blocker-Pool; H20.41)
  S3  A_M6L         : dormante Linien sperren nicht (``lebt_kausal``-Skip)
  S4  endogener Rand: ``Marktrand`` + ``im_aeusseren_quartil``

Verfahren
---------
Parametrisierte Gate-Rekonstruktion (identische Logik wie das bewiesene
``_chk_k45_trace.py``: Rekonstruktion == echter Motor, Fail-Loud-Assert),
erweitert um vier unabhaengige Schalter. KEIN Monkeypatch, KEINE Mutation
des arretierten V020-Motors. Jeder Lauf erhaelt eine eigene ``deepcopy``.

Matrix (H20.41 Abschnitt 9)
---------------------------
  Lauf    S2-Pool S2-Blocker S3-Blocker S4-Quartil  Zweck
  H1-0    AN      AN         AN         endogen     Status quo (14/+27.327383)
  H1-B    AUS     AUS        AN         endogen     S2 total aus
  H1-BP   AUS     AN         AN         endogen     isoliert Pool-Verdraengung
  H1-M    AN      AN         AUS        endogen     isoliert A_M6L
  H1-Q    AN      AN         AN         global      Null-Eichpunkt S4
  H1-V0   AUS     AUS        AUS        global      Baseline (8/+38.919584)

Fail-Loud-Anker (Zero-Trust)
----------------------------
1. H1-Reinheit: ``adapter.angewandte_basis(k, kid, basis_bei(k)) ==
   basis_bei(k)`` fuer ALLE Kanten und alle ``k <= 643`` -- beweist, dass im
   H1-Fenster kein Adapter-Override wirkt (sonst Abbruch).
2. Rekonstruktion H1-0 == echter ``_se_trades_v020``-Lauf (Vollsignatur).
3. Rekonstruktion H1-V0 == echter ``_se_trades``-Lauf (Vollsignatur).
4. H1-0-Totale == 14 / +27.327383 R; H1-V0-Totale == 8 / +38.919584 R.
5. Zaehler-Anker (am Ende, nach der Ausgabe): ``blocker``,
   ``quartil_blockiert``, ``frisch_blockiert``, ``zyklus_blockiert`` der
   H1-0-Rekonstruktion == Werte des echten Motors.

Reichweite: ``box_end_bar = 647``. Begruendung: H1 = ``entry_bar < 644``
<=> ``bar <= 642``; der Loop ``range(2, box_end-3)`` erreicht mit 647
exakt k=643. Der Scan bleibt der native ``_se_scan`` (box_end=644); nur das
Trade-Loop-Ende wird gesetzt (kausal identisch zum Vollauf).

Read-only-Garantie: SHA-Guards (Baseline/V020/Adapter); DB nur read_only
(``_lade_fenster``); einzige Schreiboperation ist
``test/_chk_h1_ablation_out.txt``.

Verifikation: ``python -m py_compile`` + genau eine Ausfuehrung.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
PROTOKOLL = ROOT / "test" / "_chk_h1_ablation_out.txt"

V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

FENSTER = "AUG"
BOX_END = 647                 # H1-Deckung (kausal identisch zum Vollauf)
H1_GRENZE = 644               # box_end_nativ der Baseline
K_MAX_H1 = 643                # k-Obergrenze des H1-Reinheits-Checks
ANCHOR_H1_0 = (14, 27.327383)
ANCHOR_H1_V0 = (8, 38.919584)
R_TOL = 1e-9
ZAEHLER_ANKER = ("blocker", "quartil_blockiert", "frisch_blockiert",
                 "zyklus_blockiert")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
    return mod


# --------------------------------------------------------------- Schalter
@dataclass(frozen=True, slots=True)
class Schalter:
    """Vier unabhaengige Ablations-Schalter."""

    label: str
    s2_pool: bool          # A_SB im Kandidaten-Pool (existiert_nativ)
    s2_blocker: bool       # A_SB im Blocker-Pool
    s3_blocker: bool       # A_M6L: dormante Linien sperren nicht
    s4_endogen: bool       # endogener Marktrand statt globalem Quartil


MATRIX: Tuple[Schalter, ...] = (
    Schalter("H1-0", True, True, True, True),
    Schalter("H1-B", False, False, True, True),
    Schalter("H1-BP", False, True, True, True),
    Schalter("H1-M", True, True, False, True),
    Schalter("H1-Q", True, True, True, False),
    Schalter("H1-V0", False, False, False, False),
)


# ------------------------------------------------------------------ Quartil
class _V0Quartil:
    """Baseline ``_im_aussenquartil`` (Z. 2483-2490), global ab Bar 0."""

    def __init__(self, hi: np.ndarray, lo: np.ndarray, cfg: Any) -> None:
        self.hi, self.lo, self.cfg = hi, lo, cfg

    def __call__(self, k: int, px: float,
                 richtung: str) -> Tuple[bool, str, bool]:
        ex_hi = float(np.max(self.hi[:k + 1]))
        ex_lo = float(np.min(self.lo[:k + 1]))
        spanne = ex_hi - ex_lo
        if spanne <= 0.0:
            return True, "degeneriert", True
        dist = ((ex_hi - px) if richtung == "SHORT"
                else (px - ex_lo)) / spanne * 100.0
        info = (f"global ex_hi={ex_hi:.3f} ex_lo={ex_lo:.3f} "
                f"spanne={spanne:.3f} dist={dist:.3f}%")
        return dist <= self.cfg.quartil_distanz_pct, info, False


class _V020Quartil:
    """Endogener Marktrand (S4) aus lebenden Kanten."""

    def __init__(self, eng: Any, edges: List[Any], kidx: Dict[int, Any],
                 kcfg: Any) -> None:
        self.eng, self.edges, self.kidx, self.kcfg = eng, edges, kidx, kcfg

    def __call__(self, k: int, px: float,
                 richtung: str) -> Tuple[bool, str, bool]:
        refs = self.eng._referenzen(self.edges, k)
        rand = self.eng._marktrand(
            [refs[int(e.kid)] for e in self.edges], k, self.kidx)
        if rand is None:
            return True, "rand=undefiniert (permissiv)", True
        spanne = rand.decke - rand.boden
        if spanne <= 0.0:
            return True, f"rand degeneriert ({rand.quelle})", True
        dist = ((rand.decke - px) if richtung == "SHORT"
                else (px - rand.boden)) / spanne * 100.0
        info = (f"endogen decke={rand.decke:.3f} boden={rand.boden:.3f} "
                f"spanne={spanne:.3f} quelle={rand.quelle} dist={dist:.3f}%")
        return dist <= self.kcfg.quartil_distanz_pct, info, False


QuartilFn = Callable[[int, float, str], Tuple[bool, str, bool]]


# -------------------------------------------------------------- Rekonstruktion
def _rekonstruiere(sw: Schalter, B: Any, cfg: Any, v020: Any,
                   quartil: QuartilFn, scan: Dict[str, Any],
                   box_end: int) -> Tuple[List[Any], Dict[str, int]]:
    """Baut die ``_se_trades``-Gate-Kette read-only nach (k=2..box_end-3).

    Args:
        sw: Schalterkombination dieses Laufs.
        B: Baseline-Modul.
        cfg: ``StraightEdgeHarnessKonfiguration``.
        v020: V020-Modul (``existiert_nativ``, ``V3_TP_MINDIST_PCT``).
        quartil: injizierte Quartilpruefung (global oder endogen).
        scan: Scan-Dict (eigene deepcopy).
        box_end: Trade-Loop-Ende.

    Returns:
        ``(setups, stats)`` -- Setups im H1-Fenster (entry_bar < H1_GRENZE)
        und die Gate-Zaehler des Laufs.
    """
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    alle: List[Any] = list(scan["edges"]) + list(scan["seeds"])
    seite_edges: Dict[str, List[Any]] = {
        "OBEN": [e for e in alle if e.seite == "OBEN"],
        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}
    tp_mindist = float(v020.V3_TP_MINDIST_PCT)
    kcfg = v020.V020KantenKonfiguration()

    setups: List[Any] = []
    stats: Dict[str, int] = {
        "blocker": 0, "quartil_blockiert": 0, "quartil_undefiniert": 0,
        "frisch_blockiert": 0, "zyklus_blockiert": 0, "kein_gegner": 0,
        "kein_raum": 0, "f3": 0, "concurrency_blockiert": 0}
    poc_start = 0
    letzter_trade: Dict[int, Any] = {}
    getradete: set = set()

    def _lebt_wicks(e: Any, kk: int) -> bool:
        bars = [b for b, _ in e.wicks if b <= kk]
        return bool(bars) and max(bars) >= kk - cfg.wall_live_bars

    def _exist_pool(e: Any, kk: int, sweep: float) -> bool:
        if not sw.s2_pool:
            return bool(e.ist_aktiv_bei(kk)) and e.erster_pivot_bar + 2 <= kk + 1
        return v020.existiert_nativ(
            v020.kantenreferenz_aus(e, kk, None), kk, kcfg, sweep)

    def _exist_blocker(e: Any, kk: int, sweep: float) -> bool:
        if not sw.s2_blocker:
            return bool(e.ist_aktiv_bei(kk)) and e.erster_pivot_bar + 2 <= kk + 1
        return v020.existiert_nativ(
            v020.kantenreferenz_aus(e, kk, None), kk, kcfg, sweep)

    def _etabliert(e: Any, kk: int) -> bool:
        return kk - e.erster_pivot_bar >= cfg.min_wall_alter_bars

    def _kandidat(richtung: str, kk: int, sweep: float) -> Optional[Any]:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"

        def _dist(e: Any) -> float:
            b = float(e.basis_bei(kk))
            return ((sweep - b) if richtung == "SHORT"
                    else (b - sweep)) / b * 100.0

        pool: List[Any] = []
        for e in seite_edges[seite]:
            if not _exist_pool(e, kk, sweep):
                continue
            if not ((e.ist_prim_anker and kk >= e.promoviert_ab_bar)
                    or e.touch_conf(kk) >= 2):
                continue
            if not _etabliert(e, kk):
                if _dist(e) > cfg.touch_band_pct:
                    stats["frisch_blockiert"] += 1
                continue
            pool.append(e)
        for e in seite_edges[seite]:
            if (e in pool or e.ist_prim_anker
                    or not _exist_pool(e, kk, sweep)):
                continue
            if e.touch_conf(kk) >= 2 or not _etabliert(e, kk):
                continue
            dd = _dist(e)
            if (cfg.sweep_mindestdurchstich_pct
                    < dd <= cfg.max_sweep_ueberdehnung_pct):
                pool.append(e)
        if not pool:
            return None
        pool.sort(key=lambda e: float(e.basis_bei(kk)),
                  reverse=(seite == "OBEN"))
        for pos, e in enumerate(pool):
            dist = _dist(e)
            if dist < 0.0:
                if _lebt_wicks(e, kk):
                    return None
                continue
            if dist > cfg.max_sweep_ueberdehnung_pct:
                return None
            if dist <= cfg.sweep_mindestdurchstich_pct:
                continue
            if pos == 0:
                return e
            if e.touch_conf(kk) < cfg.min_touches_handelbar:
                continue
            return e
        return None

    def _blockiert(richtung: str, kk: int, kd: Any,
                   sweep: float) -> Optional[Any]:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"
        basis_k = float(kd.basis_bei(kk))
        aussen: Optional[Any] = None
        for e in seite_edges[seite]:
            if e is kd or not _exist_blocker(e, kk, sweep):
                continue
            if sw.s3_blocker and not _lebt_wicks(e, kk):
                continue                       # A_M6L: dormante sperrt nicht
            b = float(e.basis_bei(kk))
            if seite == "OBEN":
                if b <= sweep:
                    continue
                if aussen is None or b > float(aussen.basis_bei(kk)):
                    aussen = e
            else:
                if b >= sweep:
                    continue
                if aussen is None or b < float(aussen.basis_bei(kk)):
                    aussen = e
        if aussen is None:
            return None
        b = float(aussen.basis_bei(kk))
        dist = ((b - basis_k) if seite == "OBEN"
                else (basis_k - b)) / basis_k * 100.0
        return aussen if 0.0 < dist <= cfg.max_seed_distanz_pct else None

    def _gegen(richtung: str, kk: int) -> Optional[Any]:
        gegenseite = "UNTEN" if richtung == "SHORT" else "OBEN"
        pool = [e for e in seite_edges[gegenseite]
                if e.erster_pivot_bar + 2 <= kk + 1
                and ((e.ist_prim_anker and kk >= e.promoviert_ab_bar)
                     or e.touch_conf(kk) >= 2)]
        if not pool:
            return None
        if gegenseite == "OBEN":
            return max(pool, key=lambda e: float(e.basis_bei(kk)))
        return min(pool, key=lambda e: float(e.basis_bei(kk)))

    for k in range(2, box_end - 3):
        for richtung in ("SHORT", "LONG"):
            sweep = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            kd = _kandidat(richtung, k, sweep)
            if kd is None:
                continue
            blk = _blockiert(richtung, k, kd, sweep)
            if blk is not None:
                stats["blocker"] += 1
                continue
            pas, _info, undef = quartil(k, sweep, richtung)
            if undef:
                stats["quartil_undefiniert"] += 1
            if not pas:
                stats["quartil_blockiert"] += 1
                continue
            seite = "OBEN" if richtung == "SHORT" else "UNTEN"
            basis = float(kd.basis_bei(k))
            stufe_n, stufe_name = B._reclaim_stufe(
                seite, k, basis, hi, lo, cl, cfg)
            if stufe_n == 0:
                continue
            entry_bar = k + stufe_n
            reclaim_bar = entry_bar - 1
            if k <= kd.letzter_sweep_bar:
                stats["f3"] += 1
                continue
            if richtung == "SHORT":
                cluster = float(np.max(hi[k:reclaim_bar + 1]))
                sl = cluster + cfg.sl_buffer_usd
            else:
                cluster = float(np.min(lo[k:reclaim_bar + 1]))
                sl = cluster - cfg.sl_buffer_usd
            _vor = letzter_trade.get(kd.kid)
            if (_vor is not None
                    and entry_bar - _vor.entry_bar < cfg.retest_zyklus_bars):
                stats["zyklus_blockiert"] += 1
                continue
            geg = _gegen(richtung, k)
            if geg is None:
                stats["kein_gegner"] += 1
                continue
            gegen_basis = float(geg.basis_bei(k))
            if richtung == "SHORT":
                if not (gegen_basis < basis) or (
                        abs(basis - gegen_basis) / basis * 100.0 < tp_mindist):
                    stats["kein_raum"] += 1
                    continue
                unter, ober = gegen_basis, basis
            else:
                if not (gegen_basis > basis) or (
                        abs(gegen_basis - basis) / basis * 100.0 < tp_mindist):
                    stats["kein_raum"] += 1
                    continue
                unter, ober = basis, gegen_basis
            poc = B.berechne_kausalen_histogramm_poc(
                d, poc_start, k, unter, ober, cfg.num_bins)
            if not (unter < poc < ober):
                stats["kein_raum"] += 1
                continue
            entry = float(op[entry_bar])
            tp2 = gegen_basis
            ok = ((sl > entry > poc > tp2) if richtung == "SHORT"
                  else (sl < entry < poc < tp2))
            if not ok:
                stats["kein_raum"] += 1
                continue
            risk = abs(sl - entry)
            if risk <= 0:
                stats["kein_raum"] += 1
                continue
            trade = B._c_loese_trade(hi, lo, cl, entry_bar, entry, richtung,
                                     sl, poc, tp2, cfg.tp1_anteil_pct)
            if cfg.max_gleichzeitig_je_richtung > 0:
                offen = B._konkurrenz_aktiv(
                    setups, richtung, entry_bar,
                    trade.exit1_bar, trade.exit2_bar)
                if offen > cfg.max_gleichzeitig_je_richtung:
                    stats["concurrency_blockiert"] += 1
                    continue
            if entry_bar in getradete:
                continue
            getradete.add(entry_bar)
            kd.letzter_signal_bar = k
            kd.letzter_sweep_bar = k
            if richtung == "SHORT":
                kd.cluster_hoch = max(kd.cluster_hoch, cluster)
            else:
                kd.cluster_tief = (cluster if kd.cluster_tief <= 0.0
                                   else min(kd.cluster_tief, cluster))
            setup = B._SESetup(
                bar=k, richtung=richtung, kid=kd.kid, basis=basis,
                sweep=sweep, trigger_close=float(cl[k]),
                touch_n=kd.touch_conf(k), poc=float(poc), tp2=float(tp2),
                sl=sl, entry=entry, r=trade.r_mult, resultat=trade.resultat,
                stufe=stufe_name or "STUFE_1_IN_BAR", reclaim_bar=reclaim_bar,
                entry_bar=entry_bar, ist_prim_anker=kd.ist_prim_anker,
                grund1=trade.grund1, exit1_bar=trade.exit1_bar,
                exit2_bar=trade.exit2_bar, grund2=trade.grund2,
                r1=trade.r1, r2=trade.r2)
            letzter_trade[kd.kid] = setup
            setups.append(setup)

    h1 = [s for s in setups if int(s.entry_bar) < H1_GRENZE]
    return h1, stats


# ------------------------------------------------------------------ Vergleich
def _key(x: Any) -> Tuple[int, int, str]:
    return (int(x.bar), int(x.kid), str(x.richtung))


def _karte(ss: List[Any]) -> Dict[Tuple[int, int, str], Any]:
    return {_key(x): x for x in ss}


def _sig_karte(ss: List[Any]) -> Dict[Tuple[int, int, str], Tuple[Any, ...]]:
    return {_key(x): (int(x.bar), int(x.kid), str(x.richtung), float(x.r),
                      int(x.entry_bar), float(x.sl), float(x.tp2),
                      int(x.exit2_bar))
            for x in ss}


def _diff(ref: List[Any], akt: List[Any]
          ) -> Tuple[List[Any], List[Any], List[Tuple[Any, Any, float]]]:
    """Drei Kategorien: nur-ref, nur-akt, gemeinsam mit |dR| > R_TOL."""
    kr, ka = _karte(ref), _karte(akt)
    nur_ref = [kr[kk] for kk in kr if kk not in ka]
    nur_akt = [ka[kk] for kk in ka if kk not in kr]
    gem: List[Tuple[Any, Any, float]] = []
    for kk in kr:
        if kk in ka:
            dr = float(ka[kk].r) - float(kr[kk].r)
            if abs(dr) > R_TOL:
                gem.append((kr[kk], ka[kk], dr))
    gem.sort(key=lambda t: -abs(t[2]))
    return nur_ref, nur_akt, gem


def _report_diff(titel: str, ref: List[Any], akt: List[Any]) -> None:
    nr, na, gem = _diff(ref, akt)
    print(f"  {titel}: nur-REF {len(nr)} ({sum(x.r for x in nr):+.6f} R) | "
          f"nur-AKT {len(na)} ({sum(x.r for x in na):+.6f} R) | "
          f"gemeinsam-dR {len(gem)} ({sum(g[2] for g in gem):+.6f} R)")
    for x in sorted(nr, key=lambda y: (y.bar, y.kid)):
        print(f"      nur-REF bar={x.bar} K{x.kid} {x.richtung:5s} "
              f"entry={x.entry_bar} r={x.r:+.6f}")
    for x in sorted(na, key=lambda y: (y.bar, y.kid)):
        print(f"      nur-AKT bar={x.bar} K{x.kid} {x.richtung:5s} "
              f"entry={x.entry_bar} r={x.r:+.6f}")
    for a, b, dr in gem:
        print(f"      dR={dr:+.6f} bar={a.bar} K{a.kid} {a.richtung:5s} "
              f"sl {a.sl:.4f}->{b.sl:.4f} entry {a.entry:.4f}->{b.entry:.4f} "
              f"tp2 {a.tp2:.4f}->{b.tp2:.4f} exit2 {a.exit2_bar}->{b.exit2_bar}")


class _Tee:
    """Spiegelt die Ausgabe auf Terminal und Protokolldatei."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.buf: List[str] = []

    def write(self, s: str) -> int:
        self.buf.append(s)
        return self._real.write(s)

    def flush(self) -> None:
        self._real.flush()


def main() -> None:
    assert _sha(BASELINE_PFAD) == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(V020_PFAD) == V020_SHA_SOLL, "V020-Fremdstand"
    assert _sha(ADAPTER_PFAD) == ADAPTER_SHA_SOLL, "Adapter-Fremdstand"
    print("SHA-Guards OK: Baseline 53f28e1b / V020 e79c5c29 / "
          "Adapter 770eda2c")

    v020 = _load("v020_h1_abl", V020_PFAD)
    B = v020.baseline()
    from backtest_lab.phasen_regime_adapter import (  # noqa: E402
        ADAPTER_V019_KAUSAL)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = v020.V020KantenKonfiguration()
    scan0 = B._se_scan(FENSTER, cfg)
    print(f"FENSTER {FENSTER} n={scan0['n']} "
          f"box_end_nativ={scan0['box_end_bar']} | Ablation box_end={BOX_END}"
          f" | H1-Grenze entry_bar<{H1_GRENZE}")

    hi = scan0["d"]["high"].to_numpy(dtype=float)
    lo = scan0["d"]["low"].to_numpy(dtype=float)
    edges0 = list(scan0["edges"])
    kindex0 = {int(e.kid): e for e in edges0}

    # --- Anker 1: H1-Reinheit (kein Adapter-Override im H1-Fenster) -------
    verletzungen = []
    for e in list(scan0["edges"]) + list(scan0["seeds"]):
        for k in range(2, K_MAX_H1 + 1):
            b = float(e.basis_bei(k))
            w = float(ADAPTER_V019_KAUSAL.angewandte_basis(k, int(e.kid), b))
            if abs(w - b) > 1e-12:
                verletzungen.append((int(e.kid), k, b, w))
                break
    assert not verletzungen, f"H1-Reinheit verletzt: {verletzungen[:5]}"
    print(f"Anker H1-Reinheit OK: kein Adapter-Override fuer k<= {K_MAX_H1} "
          f"({len(scan0['edges'])} edges + {len(scan0['seeds'])} seeds "
          f"geprueft)")

    # --- Echte Motoren als Fail-Loud-Referenz (je eigene deepcopy) --------
    sc_e0 = copy.deepcopy(scan0)
    sc_e0["box_end_bar"] = BOX_END
    echt_v0 = [s for s in B._se_trades(sc_e0, cfg)[0]
               if int(s.entry_bar) < H1_GRENZE]

    sc_ev = copy.deepcopy(scan0)
    sc_ev["box_end_bar"] = BOX_END
    eng = v020.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    _ev_setups, echt_stats = eng._se_trades_v020(sc_ev, cfg)
    echt_v020 = [s for s in _ev_setups if int(s.entry_bar) < H1_GRENZE]

    # --- Injektion der Quartilpruefungen (explizit, kein Methodenkopplung) -
    q_global: QuartilFn = _V0Quartil(hi, lo, cfg)
    q_endogen: QuartilFn = _V020Quartil(eng, edges0, kindex0, kcfg)

    # --- 6 Ablations-Laeufe ----------------------------------------------
    ergebnisse: Dict[str, List[Any]] = {}
    stats_map: Dict[str, Dict[str, int]] = {}
    for sw in MATRIX:
        sc = copy.deepcopy(scan0)
        sc["box_end_bar"] = BOX_END
        q = q_endogen if sw.s4_endogen else q_global
        setups, st = _rekonstruiere(sw, B, cfg, v020, q, sc, BOX_END)
        ergebnisse[sw.label] = setups
        stats_map[sw.label] = st

    # --- Anker 2-4 (Fail-Loud, vor der Interpretation) --------------------
    assert _sig_karte(ergebnisse["H1-0"]) == _sig_karte(echt_v020), (
        "H1-0-Rekonstruktion != echter V020-Motor")
    assert _sig_karte(ergebnisse["H1-V0"]) == _sig_karte(echt_v0), (
        "H1-V0-Rekonstruktion != echter Baseline-Motor")
    n0 = len(ergebnisse["H1-0"])
    r0 = sum(x.r for x in ergebnisse["H1-0"])
    nv = len(ergebnisse["H1-V0"])
    rv = sum(x.r for x in ergebnisse["H1-V0"])
    assert (n0, round(r0, 6)) == ANCHOR_H1_0, (n0, round(r0, 6))
    assert (nv, round(rv, 6)) == ANCHOR_H1_V0, (nv, round(rv, 6))
    print(f"Anker H1-0 OK: {n0} / {r0:+.6f} == {ANCHOR_H1_0} "
          f"(== echter V020-Motor)")
    print(f"Anker H1-V0 OK: {nv} / {rv:+.6f} == {ANCHOR_H1_V0} "
          f"(== echter Baseline-Motor)\n")

    # --- Lauf-Tabelle -----------------------------------------------------
    print("===== LAUF-MATRIX =====")
    print(f"  {'Lauf':6s} {'Pool':>4s} {'Blk':>4s} {'S3':>4s} {'S4':>8s} "
          f"{'Trades':>7s} {'R':>13s}")
    for sw in MATRIX:
        ss = ergebnisse[sw.label]
        print(f"  {sw.label:6s} "
              f"{'AN' if sw.s2_pool else 'AUS':>4s} "
              f"{'AN' if sw.s2_blocker else 'AUS':>4s} "
              f"{'AN' if sw.s3_blocker else 'AUS':>4s} "
              f"{'endogen' if sw.s4_endogen else 'global':>8s} "
              f"{len(ss):7d} {sum(x.r for x in ss):+13.6f}")

    # --- Zaehler je Lauf --------------------------------------------------
    print("\n===== ZAEHLER JE LAUF =====")
    keys = ("blocker", "quartil_blockiert", "quartil_undefiniert",
            "frisch_blockiert", "zyklus_blockiert", "concurrency_blockiert",
            "kein_gegner", "kein_raum", "f3")
    kopf = "  " + f"{'Lauf':6s}" + "".join(f"{k[:11]:>13s}" for k in keys)
    print(kopf)
    for sw in MATRIX:
        st = stats_map[sw.label]
        print("  " + f"{sw.label:6s}"
              + "".join(f"{st[k]:13d}" for k in keys))
    print("  " + f"{'ECHTER':6s}"
          + "".join(f"{int(echt_stats.get(k, 0)):13d}" for k in keys)
          + "   <- V020-Motor (Referenz)")

    # --- Trade-Listen je Lauf ---------------------------------------------
    for sw in MATRIX:
        print(f"\n===== {sw.label}: Trades "
              f"(S2-Pool={'AN' if sw.s2_pool else 'AUS'} "
              f"S2-Blocker={'AN' if sw.s2_blocker else 'AUS'} "
              f"S3={'AN' if sw.s3_blocker else 'AUS'} "
              f"S4={'endogen' if sw.s4_endogen else 'global'}) =====")
        for x in sorted(ergebnisse[sw.label], key=lambda y: (y.bar, y.kid)):
            print(f"  bar={x.bar:4d} entry={x.entry_bar:4d} K{x.kid:<3d} "
                  f"{x.richtung:5s} stufe={x.stufe:15s} r={x.r:+10.6f} "
                  f"sl={x.sl:.4f} tp2={x.tp2:.4f}")

    # --- Attribution: primaer gegen H1-0 ---------------------------------
    print("\n===== ATTRIBUTION (primaer: gegen H1-0 / "
          "sekundaer: gegen H1-V0) =====")
    for sw in MATRIX:
        if sw.label == "H1-0":
            continue
        print(f"\n--- {sw.label} vs. H1-0 ---")
        _report_diff("H1-0 -> " + sw.label, ergebnisse["H1-0"],
                     ergebnisse[sw.label])
    for sw in MATRIX:
        if sw.label == "H1-V0":
            continue
        print(f"\n--- {sw.label} vs. H1-V0 ---")
        _report_diff("H1-V0 -> " + sw.label, ergebnisse["H1-V0"],
                     ergebnisse[sw.label])

    # --- Kurzschluss-Hinweis (informativ, H20.41 Abschnitt 11 / Frage 4) --
    b_ok = (len(ergebnisse["H1-B"]) == ANCHOR_H1_V0[0]
            and abs(sum(x.r for x in ergebnisse["H1-B"])
                    - ANCHOR_H1_V0[1]) < 1e-6)
    print("\n===== KURZSCHLUSS-HINWEIS (informativ) =====")
    if b_ok:
        print("  H1-B == H1-V0 -> S3 (A_M6L) UND S4 (endogener Rand) sind in "
              "H1 inert;")
        print("  die H1-Regression stammt vollstaendig aus S2 (A_SB).")
        print("  -> S2-Neuspezifikation (H20.41 Abschnitt 7) kann direkt "
              "folgen.")
    else:
        print(f"  H1-B = {len(ergebnisse['H1-B'])} / "
              f"{sum(x.r for x in ergebnisse['H1-B']):+.6f} R != H1-V0 "
              f"{ANCHOR_H1_V0}. S3/S4 sind in H1 NICHT vollstaendig inert;")
        print("  die Matrix liefert die Zuordnung je Schalter (siehe oben).")

    # --- Gesamtbilanz -----------------------------------------------------
    print("\n===== GESAMTBILANZ =====")
    for sw in MATRIX:
        ss = ergebnisse[sw.label]
        print(f"  {sw.label:6s} {len(ss):3d} Trades / "
              f"{sum(x.r for x in ss):+12.6f} R")

    # --- Anker 5: Zaehler-Anker (am Ende, damit die Ausgabe erhalten bleibt)
    print("\n===== ANKER 5: ZAEHLER-VERIFIKATION (H1-0 vs. echter Motor) "
          "=====")
    st0 = stats_map["H1-0"]
    for k in ZAEHLER_ANKER:
        print(f"  {k:22s} Reko={int(st0[k]):6d}  Echt="
              f"{int(echt_stats.get(k, 0)):6d}")
    for k in ZAEHLER_ANKER:
        assert int(st0[k]) == int(echt_stats.get(k, 0)), (
            f"Zaehler-Anker verletzt bei '{k}': "
            f"{int(st0[k])} != {int(echt_stats.get(k, 0))}")
    print("  Zaehler-Anker OK (4 Schluessel)")


if __name__ == "__main__":
    _real = sys.stdout
    _tee = _Tee(_real)
    sys.stdout = _tee  # type: ignore[assignment]
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        traceback.print_exc()
        print(f"ABBRUCH: {type(exc).__name__}: {exc}")
    finally:
        sys.stdout = _real
        PROTOKOLL.write_text("".join(_tee.buf), encoding="utf-8")
        print(f"\nProtokoll -> {PROTOKOLL}  ({PROTOKOLL.stat().st_size:,} B)"
              f"  Fehler={_fehler}")
