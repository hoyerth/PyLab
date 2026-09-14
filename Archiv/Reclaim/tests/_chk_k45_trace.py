# -*- coding: utf-8 -*-
"""READ-ONLY K45-Gate-Rekonstruktion (Bar 676..684): V0 vs. V020-A.

Zweck
-----
K45 (LONG) erzielt in V0 +6.480880 R, in V020 (A/A2/B identisch)
-1.000000 R. Da K45 keinen Adapter-Override besitzt und Modus A mit
``wertedomaene=None`` laeuft, sind D1, Wertedomaene, Hook 1/2/3 als
Primaersursache logisch ausgeschlossen. Die Divergenz kann nur aus den
drei generell gewordenen Kernpraedikaten stammen:
  S2  A_SB          : ``existiert_nativ`` (aktiv ODER realer Durchstich)
  S3  A_M6L         : dormante Linien sperren nicht (``lebt_kausal``)
  S4  endogener Rand: ``Marktrand`` + ``im_aeusseren_quartil``

Verfahren (wie autorisiert: KEIN Monkeypatch)
--------------------------------------------
Reine Gate-Rekonstruktion. Ein gemeinsamer Loop wird mit austauschbaren
Primitiven betrieben (V0 vs. V020); jede Entscheidung (Pool, Blocker,
Quartil, Reclaim-Stufe, Zielkette) wird je Bar tabellarisch protokolliert.
Der Loop laeuft ZUR STATE-TREUE ueber den GESAMTEN Bereich k=2..K_BIS;
protokolliert werden nur die Zeilen k=676..684. Ein Gleichheits-Assert
stellt sicher, dass die rekonstruierten Setups EXAKT den echten
Engine-Setups entsprechen (sonst Fail-Loud-Abbruch).

Read-only-Garantie
------------------
* SHA-Guards auf Baseline und V020 (Fremdstand -> Abbruch).
* Jeder echte Engine-Lauf erhaelt eine eigene ``copy.deepcopy(scan)``.
* Die DB wird ausschliesslich read_only geoeffnet (``_lade_fenster``).
* Einzige Schreiboperation: die eigene Protokolldatei
  ``test/_chk_k45_trace_out.txt``. Kein PNG, keine DB-Mutation.

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
PROTOKOLL = ROOT / "test" / "_chk_k45_trace_out.txt"

V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")

FENSTER = "AUG"
ZIEL_KID = 45
K_VON, K_BIS = 676, 684
BOX_END_TRACE = K_BIS + 4          # range(2, box_end-3) erreicht K_BIS


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
    return mod


# ------------------------------------------------------------------ Zeilen
@dataclass(slots=True)
class Zeile:
    """Eine Gate-Zeile je (Bar, Richtung)."""

    k: int
    richtung: str
    sweep: float
    kd: Optional[int] = None
    kd_basis: float = float("nan")
    pool_groesse: int = 0
    pool_kids: str = ""
    blocker: Optional[int] = None
    blocker_basis: float = float("nan")
    quartil_pass: bool = False
    quartil_info: str = ""
    stufe_n: int = 0
    stufe_name: str = ""
    f3: bool = False
    zyklus: bool = False
    geg: Optional[int] = None
    gegen_basis: float = float("nan")
    tp2: float = float("nan")
    poc: float = float("nan")
    sl: float = float("nan")
    entry: float = float("nan")
    risk: float = float("nan")
    r: float = float("nan")
    grund1: str = ""
    grund2: str = ""
    exit1_bar: int = -1
    exit2_bar: int = -1
    r1: float = float("nan")
    r2: float = float("nan")
    # Zielkante K45 -- Einzelzustand je Bar
    t_existiert: bool = False
    t_etabliert: bool = False
    t_basis: float = float("nan")
    t_dist: float = float("nan")
    t_touch: int = 0
    t_aktiv: bool = False
    t_lebt: bool = False
    t_pool_pre: bool = False
    t_pool_idx: int = -1


@dataclass(slots=True)
class RekonPrimitive:
    """Austauschbare Kernpraedikate (V0 vs. V020)."""

    name: str
    basis: Callable[[Any, int], float]
    existiert: Callable[[Any, int, float], bool]
    etabliert: Callable[[Any, int], bool]
    blocker_lebt_gate: bool
    quartil: Callable[[int, float, str], Tuple[bool, str]]


class _V0Quartil:
    """Exakte Baseline-Nachbildung ``_im_aussenquartil`` (Z. 2483-2490)."""

    def __init__(self, hi: np.ndarray, lo: np.ndarray, cfg: Any) -> None:
        self.hi, self.lo, self.cfg = hi, lo, cfg

    def __call__(self, k: int, px: float, richtung: str) -> Tuple[bool, str]:
        ex_hi = float(np.max(self.hi[:k + 1]))
        ex_lo = float(np.min(self.lo[:k + 1]))
        spanne = ex_hi - ex_lo
        if spanne <= 0.0:
            return True, "degeneriert"
        dist = ((ex_hi - px) if richtung == "SHORT"
                else (px - ex_lo)) / spanne * 100.0
        return (dist <= self.cfg.quartil_distanz_pct,
                f"ex_hi={ex_hi:.3f} ex_lo={ex_lo:.3f} spanne={spanne:.3f} "
                f"dist={dist:.3f}% / {self.cfg.quartil_distanz_pct:.1f}%")


class _V020Quartil:
    """Endogener Rand (S4): Marktrand aus lebenden Kanten."""

    def __init__(self, eng: Any, edges: List[Any], kidx: Dict[int, Any],
                 kcfg: Any) -> None:
        self.eng, self.edges, self.kidx = eng, edges, kidx
        self.kcfg = kcfg

    def __call__(self, k: int, px: float, richtung: str) -> Tuple[bool, str]:
        refs = self.eng._referenzen(self.edges, k)
        rand = self.eng._marktrand(
            [refs[int(e.kid)] for e in self.edges], k, self.kidx)
        if rand is None:
            return True, "rand=undefiniert (permissiv)"
        spanne = rand.decke - rand.boden
        if spanne <= 0.0:
            return True, f"rand degeneriert ({rand.quelle})"
        dist = ((rand.decke - px) if richtung == "SHORT"
                else (px - rand.boden)) / spanne * 100.0
        return (dist <= self.kcfg.quartil_distanz_pct,
                f"decke={rand.decke:.3f} boden={rand.boden:.3f} "
                f"spanne={spanne:.3f} quelle={rand.quelle} "
                f"dist={dist:.3f}% / {self.kcfg.quartil_distanz_pct:.1f}%")


def _rekonstruiere(prim: RekonPrimitive, B: Any, cfg: Any,
                   v020: Any, scan: Dict[str, Any]
                   ) -> Tuple[List[Any], List[Zeile]]:
    """Baut die Gate-Kette von ``_se_trades`` read-only nach (k=2..K_BIS).

    Der Loop laeuft vollstaendig (State-Treue: ``letzter_trade``,
    ``getradete``); protokolliert werden nur Zeilen im Fenster.

    Args:
        prim: Kernpraedikate der zu rekonstruierenden Spur.
        B: Baseline-Modul (``_reclaim_stufe``, ``_c_loese_trade``,
            ``berechne_kausalen_histogramm_poc``, ``_SESetup``).
        cfg: ``StraightEdgeHarnessKonfiguration``.
        v020: V020-Modul (Konstanten ``V3_TP_MINDIST_PCT``).
        scan: Scan-Dict (als eigene deepcopy uebergeben).

    Returns:
        ``(setups, zeilen)`` -- alle Setups bis K_BIS und die Fenster-Zeilen.
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
    ziel = next((e for e in alle if int(e.kid) == ZIEL_KID), None)
    if ziel is None:
        raise RuntimeError(f"Zielkante K{ZIEL_KID} nicht im Scan")
    tp_mindist = float(v020.V3_TP_MINDIST_PCT)

    setups: List[Any] = []
    zeilen: List[Zeile] = []
    poc_start = 0                       # R1-Residualanker (Baseline-Konvention)
    letzter_trade: Dict[int, Any] = {}
    getradete: set = set()

    def _lebt_wicks(e: Any, kk: int) -> bool:
        bars = [b for b, _ in e.wicks if b <= kk]
        return bool(bars) and max(bars) >= kk - cfg.wall_live_bars

    def _kandidat(richtung: str, kk: int, sweep: float,
                  info: Dict[str, Any]) -> Optional[Any]:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"

        def _dist(e: Any) -> float:
            b = prim.basis(e, kk)
            if richtung == "SHORT":
                return (sweep - b) / b * 100.0
            return (b - sweep) / b * 100.0

        pool: List[Any] = []
        for e in seite_edges[seite]:
            if not prim.existiert(e, kk, sweep):
                continue
            if not ((e.ist_prim_anker and kk >= e.promoviert_ab_bar)
                    or e.touch_conf(kk) >= 2):
                continue
            if not prim.etabliert(e, kk):
                if _dist(e) > cfg.touch_band_pct:
                    info["frisch"] = info.get("frisch", 0) + 1
                continue
            pool.append(e)
        # Q9b: Seeds zaehlen nur bei tatsaechlichem Durchstich.
        for e in seite_edges[seite]:
            if (e in pool or e.ist_prim_anker
                    or not prim.existiert(e, kk, sweep)):
                continue
            if e.touch_conf(kk) >= 2 or not prim.etabliert(e, kk):
                continue
            dd = _dist(e)
            if (cfg.sweep_mindestdurchstich_pct
                    < dd <= cfg.max_sweep_ueberdehnung_pct):
                pool.append(e)
        info["pool"] = [int(e.kid) for e in pool]
        if not pool:
            return None
        pool.sort(key=lambda e: prim.basis(e, kk), reverse=(seite == "OBEN"))
        info["pool_sortiert"] = [int(e.kid) for e in pool]
        for pos, e in enumerate(pool):
            dist = _dist(e)
            if dist < 0.0:
                if _lebt_wicks(e, kk):
                    info["grund"] = f"lebende Wand K{e.kid} nicht erreicht"
                    return None
                continue
            if dist > cfg.max_sweep_ueberdehnung_pct:
                info["grund"] = f"ueberdehnt K{e.kid} dist={dist:.4f}%"
                return None
            if dist <= cfg.sweep_mindestdurchstich_pct:
                continue
            if pos == 0:
                info["pos"] = 0
                return e
            if e.touch_conf(kk) < cfg.min_touches_handelbar:
                continue
            info["pos"] = pos
            return e
        info["grund"] = "Pool erschoepft"
        return None

    def _blockiert(richtung: str, kk: int, kd: Any,
                   sweep: float) -> Optional[Any]:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"
        basis_k = prim.basis(kd, kk)
        aussen: Optional[Any] = None
        for e in seite_edges[seite]:
            if e is kd or not prim.existiert(e, kk, sweep):
                continue
            if prim.blocker_lebt_gate and not _lebt_wicks(e, kk):
                continue
            b = prim.basis(e, kk)
            if seite == "OBEN":
                if b <= sweep:
                    continue
                if aussen is None or b > prim.basis(aussen, kk):
                    aussen = e
            else:
                if b >= sweep:
                    continue
                if aussen is None or b < prim.basis(aussen, kk):
                    aussen = e
        if aussen is None:
            return None
        b = prim.basis(aussen, kk)
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
            return max(pool, key=lambda e: prim.basis(e, kk))
        return min(pool, key=lambda e: prim.basis(e, kk))

    def _schritt(k: int, richtung: str, z: Zeile) -> None:
        """Ein (Bar, Richtung)-Schritt; mutiert z und ggf. den State."""
        sweep = float(hi[k]) if richtung == "SHORT" else float(lo[k])
        z.sweep = sweep
        z.t_basis = prim.basis(ziel, k)
        z.t_existiert = prim.existiert(ziel, k, sweep)
        z.t_etabliert = prim.etabliert(ziel, k)
        z.t_touch = int(ziel.touch_conf(k))
        z.t_aktiv = bool(ziel.ist_aktiv_bei(k))
        z.t_lebt = _lebt_wicks(ziel, k)
        if richtung == "SHORT":
            z.t_dist = (sweep - z.t_basis) / z.t_basis * 100.0
        else:
            z.t_dist = (z.t_basis - sweep) / z.t_basis * 100.0

        info: Dict[str, Any] = {}
        kd = _kandidat(richtung, k, sweep, info)
        z.pool_groesse = len(info.get("pool", []))
        z.pool_kids = ",".join(f"K{i}" for i in info.get("pool", []))
        z.t_pool_pre = ZIEL_KID in info.get("pool", [])
        sortiert = info.get("pool_sortiert", [])
        z.t_pool_idx = sortiert.index(ZIEL_KID) if ZIEL_KID in sortiert else -1
        if kd is None:
            z.quartil_info = info.get("grund", "kein Kandidat")
            return
        z.kd = int(kd.kid)
        z.kd_basis = prim.basis(kd, k)
        blk = _blockiert(richtung, k, kd, sweep)
        if blk is not None:
            z.blocker = int(blk.kid)
            z.blocker_basis = prim.basis(blk, k)
            return
        pas, qinfo = prim.quartil(k, sweep, richtung)
        z.quartil_pass = pas
        z.quartil_info = qinfo
        if not pas:
            return
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"
        basis = prim.basis(kd, k)
        stufe_n, stufe_name = B._reclaim_stufe(seite, k, basis, hi, lo, cl, cfg)
        z.stufe_n = int(stufe_n)
        z.stufe_name = stufe_name or ""
        if stufe_n == 0:
            return
        entry_bar = k + stufe_n
        reclaim_bar = entry_bar - 1
        if k <= kd.letzter_sweep_bar:
            z.f3 = True
            return
        if richtung == "SHORT":
            cluster = float(np.max(hi[k:reclaim_bar + 1]))
            sl = cluster + cfg.sl_buffer_usd
        else:
            cluster = float(np.min(lo[k:reclaim_bar + 1]))
            sl = cluster - cfg.sl_buffer_usd
        _vor = letzter_trade.get(kd.kid)
        if (_vor is not None
                and entry_bar - _vor.entry_bar < cfg.retest_zyklus_bars):
            z.zyklus = True
            return
        geg = _gegen(richtung, k)
        if geg is None:
            z.quartil_info = f"{z.quartil_info} | kein Gegner"
            return
        z.geg = int(geg.kid)
        gegen_basis = prim.basis(geg, k)
        z.gegen_basis = gegen_basis
        if richtung == "SHORT":
            if not (gegen_basis < basis):
                z.quartil_info = f"{z.quartil_info} | kein Raum (tp2>=basis)"
                return
            if abs(basis - gegen_basis) / basis * 100.0 < tp_mindist:
                z.quartil_info = f"{z.quartil_info} | kein Raum (mindist)"
                return
            unter, ober = gegen_basis, basis
        else:
            if not (gegen_basis > basis):
                z.quartil_info = f"{z.quartil_info} | kein Raum (tp2<=basis)"
                return
            if abs(gegen_basis - basis) / basis * 100.0 < tp_mindist:
                z.quartil_info = f"{z.quartil_info} | kein Raum (mindist)"
                return
            unter, ober = basis, gegen_basis
        poc = B.berechne_kausalen_histogramm_poc(
            d, poc_start, k, unter, ober, cfg.num_bins)
        if not (unter < poc < ober):
            z.quartil_info = f"{z.quartil_info} | poc ausserhalb"
            return
        entry = float(op[entry_bar])
        tp2 = gegen_basis
        ok = ((sl > entry > poc > tp2) if richtung == "SHORT"
              else (sl < entry < poc < tp2))
        if not ok:
            z.quartil_info = f"{z.quartil_info} | Ordnung verletzt"
            return
        risk = abs(sl - entry)
        if risk <= 0:
            z.quartil_info = f"{z.quartil_info} | risk<=0"
            return
        trade = B._c_loese_trade(hi, lo, cl, entry_bar, entry, richtung,
                                 sl, poc, tp2, cfg.tp1_anteil_pct)
        z.tp2, z.poc, z.sl = float(tp2), float(poc), float(sl)
        z.entry, z.risk, z.r = entry, risk, float(trade.r_mult)
        z.grund1, z.grund2 = trade.grund1, trade.grund2
        z.exit1_bar, z.exit2_bar = int(trade.exit1_bar), int(trade.exit2_bar)
        z.r1, z.r2 = float(trade.r1), float(trade.r2)
        if cfg.max_gleichzeitig_je_richtung > 0:
            offen = B._konkurrenz_aktiv(
                setups, richtung, entry_bar,
                trade.exit1_bar, trade.exit2_bar)
            if offen > cfg.max_gleichzeitig_je_richtung:
                z.quartil_info = f"{z.quartil_info} | concurrency"
                return
        if entry_bar in getradete:
            z.quartil_info = f"{z.quartil_info} | dedup entry_bar"
            return
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
            touch_n=kd.touch_conf(k), poc=float(poc), tp2=float(tp2), sl=sl,
            entry=entry, r=trade.r_mult, resultat=trade.resultat,
            stufe=stufe_name or "STUFE_1_IN_BAR", reclaim_bar=reclaim_bar,
            entry_bar=entry_bar, ist_prim_anker=kd.ist_prim_anker,
            grund1=trade.grund1, exit1_bar=trade.exit1_bar,
            exit2_bar=trade.exit2_bar, grund2=trade.grund2,
            r1=trade.r1, r2=trade.r2)
        letzter_trade[kd.kid] = setup
        setups.append(setup)

    for k in range(2, BOX_END_TRACE):
        for richtung in ("SHORT", "LONG"):
            z = Zeile(k=k, richtung=richtung, sweep=0.0)
            _schritt(k, richtung, z)
            if K_VON <= k <= K_BIS:
                zeilen.append(z)
    return setups, zeilen


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


def _sig(ss: List[Any]) -> List[Tuple[int, int, str, float]]:
    return sorted((int(x.bar), int(x.kid), str(x.richtung), float(x.r))
                  for x in ss if int(x.bar) <= K_BIS)


def main() -> None:
    assert _sha(BASELINE_PFAD) == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(V020_PFAD) == V020_SHA_SOLL, "V020-Fremdstand"
    print("SHA-Guards OK: Baseline 53f28e1b / V020 e79c5c29")

    v020 = _load("v020_k45_trace", V020_PFAD)
    B = v020.baseline()
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = v020.V020KantenKonfiguration()
    scan0 = B._se_scan(FENSTER, cfg)
    n = int(scan0["n"])
    print(f"FENSTER {FENSTER} n={n} box_end_nativ={scan0['box_end_bar']} "
          f"edges={len(scan0['edges'])} seeds={len(scan0['seeds'])} "
          f"V3_TP_MINDIST_PCT={float(v020.V3_TP_MINDIST_PCT)}")
    print(f"Zielkante K{ZIEL_KID} (LONG-Fade) | Fenster k={K_VON}..{K_BIS} | "
          f"Trace-box_end={BOX_END_TRACE}\n")

    hi = scan0["d"]["high"].to_numpy(dtype=float)
    lo = scan0["d"]["low"].to_numpy(dtype=float)

    # --- Echte Laeufe (je eigene deepcopy) --------------------------------
    sc_v0 = copy.deepcopy(scan0)
    sc_v0["box_end_bar"] = BOX_END_TRACE
    setups_v0, _ = B._se_trades(sc_v0, cfg)

    sc_v2 = copy.deepcopy(scan0)
    sc_v2["box_end_bar"] = BOX_END_TRACE
    eng = v020.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    setups_v2, _st = eng._se_trades_v020(sc_v2, cfg)

    # --- Rekonstruktion V0 (globales Quartil) -----------------------------
    sc_r0 = copy.deepcopy(scan0)
    sc_r0["box_end_bar"] = BOX_END_TRACE
    p0 = RekonPrimitive(
        name="V0",
        basis=lambda e, k: float(e.basis_bei(k)),
        existiert=lambda e, k, px: (bool(e.ist_aktiv_bei(k))
                                    and e.erster_pivot_bar + 2 <= k + 1),
        etabliert=lambda e, k: (k - e.erster_pivot_bar)
        >= cfg.min_wall_alter_bars,
        blocker_lebt_gate=False,
        quartil=_V0Quartil(hi, lo, cfg))
    reko_v0, zeilen_v0 = _rekonstruiere(p0, B, cfg, v020, sc_r0)

    # --- Rekonstruktion V020-A (A_SB/A_M6L/endogener Rand) ----------------
    sc_r2 = copy.deepcopy(scan0)
    sc_r2["box_end_bar"] = BOX_END_TRACE
    edges_r2 = list(sc_r2["edges"])
    kidx_r2 = {int(e.kid): e for e in edges_r2}
    p2 = RekonPrimitive(
        name="V020-A",
        basis=lambda e, k: eng._basis_wirksam(int(e.kid), k,
                                              float(e.basis_bei(k))),
        existiert=lambda e, k, px: v020.existiert_nativ(
            v020.kantenreferenz_aus(e, k, None), k, eng.cfg, px),
        etabliert=lambda e, k: v020.etabliert_kausal(
            v020.kantenreferenz_aus(e, k, None), k, eng.cfg),
        blocker_lebt_gate=True,
        quartil=_V020Quartil(eng, edges_r2, kidx_r2, kcfg))
    reko_v2, zeilen_v2 = _rekonstruiere(p2, B, cfg, v020, sc_r2)

    # --- Fail-Loud: Rekonstruktion == echter Motorlauf --------------------
    sig_reko0, sig_echt0 = _sig(reko_v0), _sig(setups_v0)
    sig_reko2, sig_echt2 = _sig(reko_v2), _sig(setups_v2)
    assert sig_reko0 == sig_echt0, (
        "V0-Rekonstruktion weicht ab: nur-Reko="
        f"{[t for t in sig_reko0 if t not in sig_echt0]} nur-Echt="
        f"{[t for t in sig_echt0 if t not in sig_reko0]}")
    assert sig_reko2 == sig_echt2, (
        "V020-Rekonstruktion weicht ab: nur-Reko="
        f"{[t for t in sig_reko2 if t not in sig_echt2]} nur-Echt="
        f"{[t for t in sig_echt2 if t not in sig_reko2]}")
    print(f"Rekonstruktions-Assert OK (Fail-Loud): "
          f"V0 {len(sig_echt0)} Setups == Reko; "
          f"V020-A {len(sig_echt2)} Setups == Reko\n")

    # --- Gate-Ketten ------------------------------------------------------
    for name, zs in (("V0", zeilen_v0), ("V020-A", zeilen_v2)):
        print(f"===== GATE-KETTE {name} (k={K_VON}..{K_BIS}) =====")
        for z in zs:
            kd_s = f"K{z.kd}" if z.kd is not None else "-"
            blk_s = f"K{z.blocker}({z.blocker_basis:.3f})" \
                if z.blocker is not None else "-"
            geg_s = f"K{z.geg}" if z.geg is not None else "-"
            print(f"k={z.k} {z.richtung:5s} sweep={z.sweep:9.4f} "
                  f"kd={kd_s:>4s} basis={z.kd_basis:9.4f} pool={z.pool_groesse}"
                  f"[{z.pool_kids}] blocker={blk_s} "
                  f"quartil={'PASS' if z.quartil_pass else 'BLOCK'} "
                  f"stufe={z.stufe_n} f3={int(z.f3)} zyklus={int(z.zyklus)} "
                  f"geg={geg_s}")
            print(f"      K{ZIEL_KID}: exist={int(z.t_existiert)} "
                  f"etabliert={int(z.t_etabliert)} basis={z.t_basis:.4f} "
                  f"dist={z.t_dist:8.4f}% touch={z.t_touch} "
                  f"aktiv={int(z.t_aktiv)} lebt={int(z.t_lebt)} "
                  f"pool_pre={int(z.t_pool_pre)} pool_idx={z.t_pool_idx}")
            print(f"      gate: {z.quartil_info}")
            if z.kd == ZIEL_KID and z.stufe_n > 0:
                print(f"      KETTE K{ZIEL_KID}: geg={geg_s} "
                      f"gegen_basis={z.gegen_basis:.4f} tp2={z.tp2:.4f} "
                      f"poc={z.poc:.4f} entry={z.entry:.4f} sl={z.sl:.4f} "
                      f"risk={z.risk:.4f} r={z.r:+.6f} "
                      f"grund1={z.grund1} grund2={z.grund2} "
                      f"exit1={z.exit1_bar} exit2={z.exit2_bar} "
                      f"r1={z.r1:+.6f} r2={z.r2:+.6f}")
        print()

    # --- Fokus k=679 / k=680 ---------------------------------------------
    print("===== FOKUS K45: k=679 (V0-Einstieg) vs. k=680 (V020-Einstieg) "
          "=====")
    for name, zs in (("V0", zeilen_v0), ("V020-A", zeilen_v2)):
        for z in zs:
            if z.richtung != "LONG" or z.k not in (679, 680, 681):
                continue
            print(f"  {name:6s} k={z.k} {z.richtung} sweep={z.sweep:.4f} "
                  f"kd={'K'+str(z.kd) if z.kd is not None else '-'} "
                  f"pool={z.pool_groesse} "
                  f"blocker={'-' if z.blocker is None else 'K'+str(z.blocker)} "
                  f"quartil={'PASS' if z.quartil_pass else 'BLOCK'} "
                  f"stufe={z.stufe_n} f3={int(z.f3)} zyklus={int(z.zyklus)}")
            print(f"         {z.quartil_info}")
            if z.stufe_n > 0:
                print(f"         tp2={z.tp2:.4f} poc={z.poc:.4f} "
                      f"entry={z.entry:.4f} sl={z.sl:.4f} r={z.r:+.6f} "
                      f"({z.grund1}/{z.grund2}) exits={z.exit1_bar}/"
                      f"{z.exit2_bar}")
    print()

    # --- Echte Setups im Fenster -----------------------------------------
    print("===== ECHTE SETUPS im Fenster =====")
    for name, ss in (("V0", setups_v0), ("V020-A", setups_v2)):
        for x in sorted(ss, key=lambda y: (y.bar, y.kid)):
            if K_VON <= int(x.bar) <= K_BIS:
                print(f"  {name:6s} bar={x.bar} entry_bar={x.entry_bar} "
                      f"K{x.kid} {x.richtung:5s} stufe={x.stufe} "
                      f"basis={x.basis:.4f} sweep={x.sweep:.4f} "
                      f"sl={x.sl:.4f} entry={x.entry:.4f} tp2={x.tp2:.4f} "
                      f"poc={x.poc:.4f} r={x.r:+.6f} {x.resultat} "
                      f"({x.grund1}/{x.grund2}) r1={x.r1:+.6f} "
                      f"r2={x.r2:+.6f} exits={x.exit1_bar}/{x.exit2_bar}")
    print()
    for name, ss in (("V0", setups_v0), ("V020-A", setups_v2)):
        k45 = [x for x in ss if int(x.kid) == ZIEL_KID
               and K_VON <= int(x.bar) <= K_BIS]
        print(f"  K{ZIEL_KID} in {name:6s}: "
              f"{[(int(x.bar), int(x.entry_bar), float(x.r)) for x in k45]}")


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
