# -*- coding: utf-8 -*-
"""READ-ONLY S2-Sonde: Dreikanal-Trennung, Bar 674..684, Modus-B-Regression.

Zweck
-----
H20.43 belegt: S2 (A_SB / ``existiert_nativ``) ist im KANDIDATEN-POOL der
alles bestimmende Schalter (H1 +2.000000 R schaedlich, H2 +7.457766 R
rettend), waehrend S2 im BLOCKER-Pfad ueber BEIDE Fenster inert ist
(H1-B == H1-BP, H2-B == H2-BP). Diese Sonde MESSET die Hypothese:

    Eine im Kandidaten-Pool auf "reif UND lebend UND real durchstochen"
    geschaerfte Reaktivierung heilt den H2-Fall (K45@679 -> H2-B), ohne
    den Blocker-Pfad und ohne Hook 1 anzutasten (Modus B integer).

Dreikanal-Trennung (nicht verhandelbar)
---------------------------------------
Kanal 1 (Kandidaten-Pool, ``_exist_pool``)    : GESCHAERFT.
Kanal 2 (Blocker-Pool, ``_exist_blocker``)    : UNVERAENDERT (existiert_nativ).
Kanal 3 (Hook-1-Eingang ``_sk``)              : UNVERAENDERT (existiert_nativ).

Schaerfungsdefinition (Kanal 1)
-------------------------------
    ist_aktiv            ->  pivot + 2 <= k + 1
    sonst (Reaktivierung) ->  pivot + min_wall_alter_bars <= k
                              UND lebt_kausal(ref, k, kcfg)
                              UND hat_durchstich(seite, basis, preis)

``hat_durchstich`` ist STRENG (kein Toleranzband, kein Puffer).

Fail-Loud-Anker (Zero-Trust)
----------------------------
1. Durchstich-Aequivalenz (Faktorisierung == existiert_nativ, alle k).
2. ``A0`` == echter ``_se_trades_v020``(hook=None), Vollsignatur.
3. ``B0`` == echter ``_se_trades_v020``(hook=wd=ADAPTER), Vollsignatur.
4. ``B_real``-Klammern == Literale aus ``_chk_v020_erstlauf_out.txt``.
5. ``A0`` == H2-0-Klammern (29 / +23.389914; H1 14/+27.327383;
   H2 15/-3.937470).
6. K82@1172 existiert NICHT (Klasse-III-Docht, tolerierte Ausnahme).

Hypothesen (BERICHT, kein Abbruch)
----------------------------------
H-A: ``A1`` == H2-B-Klammern und enthaelt K45@679 / +6.480880.
H-B: ``B1`` == ``B0`` in Vollsignatur UND Zaehlern (insb. blocker == 83).

Read-only-Garantie: SHA-Guards auf Baseline/V020/Adapter (NICHT Handoff).
Je Lauf eine eigene ``deepcopy``. Einzige Schreiboperation:
``test/_chk_s2_sonde_out.txt``.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
PROTOKOLL = ROOT / "test" / "_chk_s2_sonde_out.txt"

V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

FENSTER = "AUG"
BOX_END = 1288
H1_GRENZE = 644
SONDE_VON = 674
SONDE_BIS = 684
KOMPAKT = True

MB_N, MB_R = 33, 56.549174
MB_H1 = (14, 27.327383)
MB_H2 = (19, 29.221791)
MB_LONG = (10, -1.119762)
MB_SHORT = (23, 57.668937)
MB_ZAEHLER: Dict[str, int] = {
    "blocker": 83, "quartil_blockiert": 42, "kein_raum": 37, "kein_gegner": 0,
    "zyklus_blockiert": 26, "f3": 0, "frisch_blockiert": 94,
    "concurrency_blockiert": 0}
TOLERIERT_TOT: Set[Tuple[int, int]] = {(1172, 82)}

A0_N, A0_R = 29, 23.389914
A0_H1 = (14, 27.327383)
A0_H2 = (15, -3.937470)
H2B_N, H2B_R = 24, 32.847680
H2B_H1 = (12, 29.327383)
H2B_H2 = (12, 3.520297)
K45_ZIEL = (679, 45, 6.480880)

R_TOL = 1e-9
ZAEHLER_KEYS = ("blocker", "quartil_blockiert", "frisch_blockiert",
                "zyklus_blockiert", "kein_raum", "kein_gegner", "f3",
                "concurrency_blockiert", "quartil_undefiniert")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(name: str, p: Path) -> Any:
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__file__ = str(p)
    sys.modules[name] = mod
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
    return mod


def _bilanz(ss: Sequence[Any]) -> Tuple[int, float]:
    return len(ss), float(sum(x.r for x in ss))


def _h1(ss: Sequence[Any]) -> List[Any]:
    return [x for x in ss if int(x.entry_bar) < H1_GRENZE]


def _h2(ss: Sequence[Any]) -> List[Any]:
    return [x for x in ss if int(x.entry_bar) >= H1_GRENZE]


def _key(x: Any) -> Tuple[int, int, str]:
    return (int(x.bar), int(x.kid), str(x.richtung))


def _sig(x: Any) -> Tuple[Any, ...]:
    return (int(x.bar), int(x.kid), str(x.richtung), float(x.r),
            int(x.entry_bar), float(x.sl), float(x.tp2), int(x.exit1_bar),
            int(x.exit2_bar), float(x.r1), float(x.r2), str(x.stufe))


def _sig_karte(ss: Sequence[Any]) -> Dict[Tuple[int, int, str], Tuple]:
    return {_key(x): _sig(x) for x in ss}


def _diff(ref: Sequence[Any], akt: Sequence[Any]
          ) -> Tuple[List[Any], List[Any], List[Tuple[Any, Any, float]]]:
    kr = {_key(x): x for x in ref}
    ka = {_key(x): x for x in akt}
    nr = [kr[k] for k in kr if k not in ka]
    na = [ka[k] for k in ka if k not in kr]
    gem: List[Tuple[Any, Any, float]] = []
    for k in kr:
        if k in ka:
            dr = float(ka[k].r) - float(kr[k].r)
            if abs(dr) > R_TOL:
                gem.append((kr[k], ka[k], dr))
    gem.sort(key=lambda t: -abs(t[2]))
    return nr, na, gem


def _report_diff(titel: str, ref: Sequence[Any], akt: Sequence[Any]) -> None:
    nr, na, gem = _diff(ref, akt)
    print(f"  {titel}: NUR_REF {len(nr)} ({sum(x.r for x in nr):+.6f} R) | "
          f"NUR_AKT {len(na)} ({sum(x.r for x in na):+.6f} R) | "
          f"GEMEINSAM_DELTA_R {len(gem)} ({sum(g[2] for g in gem):+.6f} R)")
    for x in sorted(nr, key=lambda y: (y.bar, y.kid)):
        print(f"      NUR_REF bar={x.bar} entry={x.entry_bar} K{x.kid} "
              f"{x.richtung:5s} r={x.r:+.6f} sl={x.sl:.4f} tp2={x.tp2:.4f} "
              f"stufe={x.stufe}")
    for x in sorted(na, key=lambda y: (y.bar, y.kid)):
        print(f"      NUR_AKT bar={x.bar} entry={x.entry_bar} K{x.kid} "
              f"{x.richtung:5s} r={x.r:+.6f} sl={x.sl:.4f} tp2={x.tp2:.4f} "
              f"stufe={x.stufe}")
    for a, b, dr in gem:
        print(f"      DELTA_R={dr:+.6f} bar={a.bar} K{a.kid} {a.richtung:5s} "
              f"sl {a.sl:.4f}->{b.sl:.4f} entry {a.entry:.4f}->{b.entry:.4f} "
              f"tp2 {a.tp2:.4f}->{b.tp2:.4f} exit2 {a.exit2_bar}->{b.exit2_bar}")


# ---------------------------------------------------------------- Durchstich
def hat_durchstich(seite: Any, basis: float, sweep_px: float) -> bool:
    """Strenger Durchstich -- exakt der Durchstich-Zweig von existiert_nativ."""
    if str(getattr(seite, "value", seite)) == "OBEN":
        return float(sweep_px) > float(basis)
    return float(sweep_px) < float(basis)


def _anker_aequivalenz(alle: List[Any], v020: Any, kcfg: Any,
                       hi: np.ndarray, lo: np.ndarray, n: int) -> None:
    """Anker 1: Faktorisierung == existiert_nativ (alle Linien, alle k)."""
    pruefungen = 0
    durchstiche = 0
    for e in alle:
        for k in range(2, n - 3):
            for richtung, sweep in (("SHORT", float(hi[k])),
                                    ("LONG", float(lo[k]))):
                seite = "OBEN" if richtung == "SHORT" else "UNTEN"
                if str(e.seite) != seite:
                    continue
                ref = v020.kantenreferenz_aus(e, k, None)
                echt = bool(v020.existiert_nativ(ref, k, kcfg, sweep))
                reko = (ref.erster_pivot_bar + 2 <= k + 1) and (
                    ref.ist_aktiv
                    or hat_durchstich(ref.seite, ref.basis_bei_k, sweep))
                assert echt == reko, (int(e.kid), k, richtung, echt, reko)
                pruefungen += 1
                if (not ref.ist_aktiv) and hat_durchstich(
                        ref.seite, ref.basis_bei_k, sweep):
                    durchstiche += 1
    print(f"Anker 1 OK: Durchstich-Aequivalent ({pruefungen:,} Pruefungen, "
          f"davon {durchstiche:,} Reaktivierungs-Durchstiche)")


# --------------------------------------------------------- Rekonstruktion
@dataclass
class _Lauf:
    """Ergebnis eines Sondenlaufs."""

    label: str
    modus: str
    schaerfen: bool
    setups: List[Any]
    stats: Dict[str, int]
    dumps: List[str]


def _rekonstruiere(B: Any, cfg: Any, v020: Any, kcfg: Any, scan: Dict[str, Any],
                   hook: Optional[Any], wd: Optional[Any], schaerfen: bool,
                   label: str, dump: bool) -> _Lauf:
    """Vollauf mit Dreikanal-Trennung (Kanal 1 geschaerft, 2+3 unveraendert).

    Faithful-Spiegel von ``V020KantenEngine._se_trades_v020`` mit genau EINER
    zusaetzlichen Freiheit: dem Schalter ``schaerfen`` fuer ``_exist_pool``.
    """
    eng = v020.V020KantenEngine(hook=hook, wertedomaene=wd, cfg=kcfg)
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    edges: List[Any] = list(scan["edges"])
    seeds: List[Any] = list(scan["seeds"])
    alle: List[Any] = edges + seeds
    kanten_index: Dict[int, Any] = {int(e.kid): e for e in edges}
    seite_edges: Dict[str, List[Any]] = {
        "OBEN": [e for e in alle if e.seite == "OBEN"],
        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}
    setups: List[Any] = []
    stats: Dict[str, int] = {k: 0 for k in ZAEHLER_KEYS}
    dumps: List[str] = []
    poc_start = 0
    letzter_trade: Dict[int, Any] = {}
    getradete: Set[int] = set()

    def _basis(e: Any, kk: int) -> float:
        return eng._basis_wirksam(int(e.kid), kk, float(e.basis_bei(kk)))

    def _lebt_wicks(e: Any, kk: int) -> bool:
        bars = [b for b, _ in e.wicks if b <= kk]
        return bool(bars) and max(bars) >= kk - cfg.wall_live_bars

    # --- Kanal 1 (geschaerft) / Kanal 2+3 unveraendert -------------------
    def _exist_pool(e: Any, kk: int, preis: float,
                    refs: Dict[int, Any], scharf: bool) -> bool:
        ref = refs[int(e.kid)]
        if not scharf:
            return bool(v020.existiert_nativ(ref, kk, kcfg, preis))
        if ref.ist_aktiv:
            return ref.erster_pivot_bar + 2 <= kk + 1
        if ref.erster_pivot_bar + cfg.min_wall_alter_bars > kk:
            return False
        if not bool(v020.lebt_kausal(ref, kk, kcfg)):
            return False
        return hat_durchstich(ref.seite, ref.basis_bei_k, preis)

    def _exist_blocker(e: Any, kk: int, preis: float,
                       refs: Dict[int, Any]) -> bool:
        return bool(v020.existiert_nativ(refs[int(e.kid)], kk, kcfg, preis))

    def _etabliert(e: Any, kk: int) -> bool:
        return kk - e.erster_pivot_bar >= cfg.min_wall_alter_bars

    def _dist(richtung: str, e: Any, kk: int, sweep: float) -> float:
        b = _basis(e, kk)
        if richtung == "SHORT":
            return (sweep - b) / b * 100.0
        return (b - sweep) / b * 100.0

    def _pool_bauen(richtung: str, kk: int, sweep: float, refs: Dict[int, Any],
                    scharf: bool, st: Dict[str, int]) -> List[Any]:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"
        pool: List[Any] = []
        for e in seite_edges[seite]:
            if not _exist_pool(e, kk, sweep, refs, scharf):
                continue
            if not ((e.ist_prim_anker and kk >= e.promoviert_ab_bar)
                    or e.touch_conf(kk) >= 2):
                continue
            if not _etabliert(e, kk):
                if _dist(richtung, e, kk, sweep) > cfg.touch_band_pct:
                    st["frisch_blockiert"] += 1
                continue
            pool.append(e)
        for e in seite_edges[seite]:
            if (e in pool or e.ist_prim_anker
                    or not _exist_pool(e, kk, sweep, refs, scharf)):
                continue
            if e.touch_conf(kk) >= 2 or not _etabliert(e, kk):
                continue
            dd = _dist(richtung, e, kk, sweep)
            if (cfg.sweep_mindestdurchstich_pct
                    < dd <= cfg.max_sweep_ueberdehnung_pct):
                pool.append(e)
        pool.sort(key=lambda e: _basis(e, kk), reverse=(seite == "OBEN"))
        return pool

    def _kaskade(richtung: str, kk: int, pool_in: List[Any],
                 freigabe: Optional[int], sweep: float
                 ) -> Tuple[Optional[Any], List[Any]]:
        pool = list(pool_in)
        if freigabe is not None:
            pool = [e for e in pool if int(e.kid) != int(freigabe)]
        for pos, e in enumerate(pool):
            dist = _dist(richtung, e, kk, sweep)
            if dist < 0.0:
                if _lebt_wicks(e, kk):
                    return None, pool
                continue
            if dist > cfg.max_sweep_ueberdehnung_pct:
                return None, pool
            if dist <= cfg.sweep_mindestdurchstich_pct:
                continue
            if pos == 0:
                return e, pool
            if e.touch_conf(kk) < cfg.min_touches_handelbar:
                continue
            return e, pool
        return None, pool

    def _blockiert(richtung: str, kk: int, kd: Any, sweep: float,
                   refs: Dict[int, Any], freigabe: Optional[int]
                   ) -> Optional[Any]:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"
        basis_k = _basis(kd, kk)
        aussen: Optional[Any] = None
        for e in seite_edges[seite]:
            if e is kd or not _exist_blocker(e, kk, sweep, refs):
                continue
            if freigabe is not None and int(e.kid) == int(freigabe):
                continue
            if not _lebt_wicks(e, kk):
                continue                       # A_M6L (unveraendert)
            b = _basis(e, kk)
            if seite == "OBEN":
                if b <= sweep:
                    continue
                if aussen is None or b > _basis(aussen, kk):
                    aussen = e
            else:
                if b >= sweep:
                    continue
                if aussen is None or b < _basis(aussen, kk):
                    aussen = e
        if aussen is None:
            return None
        b = _basis(aussen, kk)
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
            return max(pool, key=lambda e: _basis(e, kk))
        return min(pool, key=lambda e: _basis(e, kk))

    def _dump_zeile(kk: int, richtung: str, refs: Dict[int, Any], sweep: float,
                    freigabe: Optional[int], sk_kids: Optional[Set[int]],
                    seite_kid: Optional[int]) -> None:
        seite = "OBEN" if richtung == "SHORT" else "UNTEN"
        st_probe: Dict[str, int] = {x: 0 for x in ZAEHLER_KEYS}
        pool_alt = _pool_bauen(richtung, kk, sweep, refs, False, st_probe)
        pool_neu = _pool_bauen(richtung, kk, sweep, refs, True, st_probe)
        kd_alt, pool_alt = _kaskade(richtung, kk, pool_alt, freigabe, sweep)
        kd_neu, pool_neu = _kaskade(richtung, kk, pool_neu, freigabe, sweep)
        blk_alt = None if kd_alt is None else _blockiert(
            richtung, kk, kd_alt, sweep, refs, freigabe)
        blk_neu = None if kd_neu is None else _blockiert(
            richtung, kk, kd_neu, sweep, refs, freigabe)
        ridx_alt = {int(e.kid): i for i, e in enumerate(pool_alt)}
        ridx_neu = {int(e.kid): i for i, e in enumerate(pool_neu)}

        dumps.append(
            f"  [{label}] bar={kk} {richtung:5s} seite={seite} "
            f"sweep={sweep:.4f} freigabe={freigabe} "
            f"kd_alt={'K'+str(kd_alt.kid) if kd_alt else '-'} "
            f"kd_neu={'K'+str(kd_neu.kid) if kd_neu else '-'} "
            f"blk_alt={'K'+str(blk_alt.kid) if blk_alt else '-'} "
            f"blk_neu={'K'+str(blk_neu.kid) if blk_neu else '-'}")

        inert: List[int] = []
        for e in alle:
            kid = int(e.kid)
            sb = str(e.seite)
            basis = _basis(e, kk)
            aktiv = bool(e.ist_aktiv_bei(kk))
            alter = kk - int(e.erster_pivot_bar)
            wb = [b for b, _ in e.wicks if b <= kk]
            ltb = max(wb) if wb else -1
            bst = (kk - ltb) if ltb >= 0 else -1
            lebt = _lebt_wicks(e, kk)
            etab = _etabliert(e, kk)
            schlaf = ""
            if not aktiv:
                for s0, s1 in e.schlaf_windows:
                    if s0 <= kk and (s1 is None or kk < s1):
                        schlaf = f"{s0}-{s1}"
                        break
            tconf = int(e.touch_conf(kk))
            ex_alt = _exist_pool(e, kk, sweep, refs, False)
            ex_neu = _exist_pool(e, kk, sweep, refs, True)
            ds = hat_durchstich(e.seite, basis, sweep)
            d_pct = _dist(richtung, e, kk, sweep)
            in_band = d_pct <= cfg.touch_band_pct
            in_alt = kid in ridx_alt
            in_neu = kid in ridx_neu
            rel = (sb == seite)
            if (KOMPAKT and (not aktiv) and (not ex_alt) and (not ex_neu)
                    and (not in_alt) and (not in_neu) and (not ds)):
                inert.append(kid)
                continue
            dumps.append(
                f"    K{kid:<3d} {sb:5s} rel={int(rel)} basis={basis:8.4f} "
                f"aktiv={int(aktiv)} alter={alter:4d} ltb={ltb:5d} "
                f"bst={bst:4d} lebt={int(lebt)} etab={int(etab)} "
                f"schlaf={schlaf:>9s} anker={int(bool(e.ist_prim_anker))} "
                f"prom={int(e.promoviert_ab_bar):5d} tconf={tconf:2d} "
                f"d_pct={d_pct:+7.3f} band={int(in_band)} ds={int(ds)} "
                f"ex_alt={int(ex_alt)} ex_neu={int(ex_neu)} "
                f"pool_alt={int(in_alt)} r_alt={ridx_alt.get(kid, -1):2d} "
                f"pool_neu={int(in_neu)} r_neu={ridx_neu.get(kid, -1):2d} "
                f"reakt_alt={int((not aktiv) and ex_alt)} "
                f"reakt_neu={int((not aktiv) and ex_neu)}")
        if inert:
            dumps.append(f"    [INERT/kompakt: {len(inert)} Linien] "
                         f"{sorted(inert)}")
        if sk_kids is not None:
            dumps.append(f"    Kanal-3: |_sk|={len(sk_kids)} "
                         f"seite_kid={seite_kid} "
                         f"seite_kid_in_sk={seite_kid in sk_kids} "
                         f"sk={sorted(sk_kids)}")

    # ------------------------------------------------------------------ Loop
    for k in range(2, int(scan["box_end_bar"]) - 3):
        refs = eng._referenzen(alle, k)
        rand_k = eng._marktrand([refs[int(e.kid)] for e in edges], k,
                                kanten_index)
        for richtung in ("SHORT", "LONG"):
            sweep = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            seite = "OBEN" if richtung == "SHORT" else "UNTEN"
            freigabe: Optional[int] = None
            sk_kids: Optional[Set[int]] = None
            seite_kid: Optional[int] = None
            if hook is not None:                   # Kanal 3: UNVERAENDERT
                _sk = [(int(e.kid), _basis(e, k)) for e in seite_edges[seite]
                       if _exist_blocker(e, k, sweep, refs)]
                sk_kids = {kk2 for kk2, _ in _sk}
                seg = hook.aktive_phase_bei(k)
                if seg is not None:
                    seite_kid = int(seg.decke.kid if richtung == "SHORT"
                                    else seg.boden.kid)
                freigabe = hook.hook_1_freigabe_kid(k, sweep, richtung, _sk)

            if dump and SONDE_VON <= k <= SONDE_BIS:
                _dump_zeile(k, richtung, refs, sweep, freigabe, sk_kids,
                            seite_kid)

            pool = _pool_bauen(richtung, k, sweep, refs, schaerfen, stats)
            kd, pool = _kaskade(richtung, k, pool, freigabe, sweep)
            if kd is None:
                continue
            blk = _blockiert(richtung, k, kd, sweep, refs, freigabe)
            if blk is not None:
                stats["blocker"] += 1
                continue
            if rand_k is None or (rand_k.decke - rand_k.boden) <= 0.0:
                stats["quartil_undefiniert"] += 1
            elif not v020.im_aeusseren_quartil(
                    sweep, rand_k, v020.SignalRichtung(richtung),
                    kcfg.quartil_distanz_pct):
                stats["quartil_blockiert"] += 1
                continue
            basis = _basis(kd, k)
            stufe_n, stufe_name = B._reclaim_stufe(seite, k, basis, hi, lo,
                                                   cl, cfg)
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
            _vor = letzter_trade.get(int(kd.kid))
            if (_vor is not None
                    and entry_bar - _vor.entry_bar < cfg.retest_zyklus_bars):
                stats["zyklus_blockiert"] += 1
                continue
            geg = _gegen(richtung, k)
            if geg is None:
                stats["kein_gegner"] += 1
                continue
            gegen_basis = _basis(geg, k)
            if hook is not None:                   # TP2-Hook (unveraendert)
                _h2 = hook.hook_2_ziel(k, richtung)
                _modus = getattr(getattr(_h2, "modus", None), "value", None)
                if _modus == "BLOCKIERT":
                    stats["kein_raum"] += 1
                    continue
                if _modus == "PHASE":
                    _zp = getattr(_h2, "ziel_preis", None)
                    if _zp is not None:
                        gegen_basis = float(_zp)
            if richtung == "SHORT":
                if not (gegen_basis < basis) or (
                        abs(basis - gegen_basis) / basis * 100.0
                        < float(v020.V3_TP_MINDIST_PCT)):
                    stats["kein_raum"] += 1
                    continue
                unter, ober = gegen_basis, basis
            else:
                if not (gegen_basis > basis) or (
                        abs(gegen_basis - basis) / basis * 100.0
                        < float(v020.V3_TP_MINDIST_PCT)):
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
            if abs(sl - entry) <= 0:
                stats["kein_raum"] += 1
                continue
            trade = B._c_loese_trade(hi, lo, cl, entry_bar, entry, richtung,
                                     sl, poc, tp2, cfg.tp1_anteil_pct)
            if cfg.max_gleichzeitig_je_richtung > 0:
                offen = B._konkurrenz_aktiv(
                    setups, richtung, entry_bar, trade.exit1_bar,
                    trade.exit2_bar)
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
            setups.append(B._SESetup(
                bar=k, richtung=richtung, kid=kd.kid, basis=basis, sweep=sweep,
                trigger_close=float(cl[k]), touch_n=kd.touch_conf(k),
                poc=float(poc), tp2=float(tp2), sl=sl, entry=entry,
                r=trade.r_mult, resultat=trade.resultat,
                stufe=stufe_name or "STUFE_1_IN_BAR", reclaim_bar=reclaim_bar,
                entry_bar=entry_bar, ist_prim_anker=kd.ist_prim_anker,
                grund1=trade.grund1, exit1_bar=trade.exit1_bar,
                exit2_bar=trade.exit2_bar, grund2=trade.grund2,
                r1=trade.r1, r2=trade.r2))
            letzter_trade[int(kd.kid)] = setups[-1]   # Q21: Retest-Zyklus

    # --- Hook 3 / G4 (nur Modus B; unveraendert) -------------------------
    if hook is not None:
        _kid_g4: Dict[int, Any] = {int(e.kid): e for e in alle}
        for _seg in getattr(hook, "segmente", ()):
            _lit = getattr(_seg, "boden_deklariert_literal", None)
            if _lit is None:
                continue
            for _k in range(int(_seg.start_bar), int(_seg.end_bar) + 1):
                if not (lo[_k] < _lit < cl[_k]):
                    continue
                _spec = hook.hook_3_boden_reclaim(_k)
                if _spec is None:
                    continue
                assert abs(float(_spec.deklarierter_boden_literal)
                           - float(_lit)) < 1e-12, _spec
                _kante = _kid_g4.get(int(_spec.boden_kid))
                if _kante is None:
                    continue
                if _kante.touch_conf(_k) < cfg.min_touches_handelbar:
                    continue
                _eb = _k + 1
                if _eb in getradete:
                    continue
                _entry = float(op[_eb])
                _sl = float(lo[_k:_eb + 1].min()) - cfg.sl_buffer_usd
                _poc = B.berechne_kausalen_histogramm_poc(
                    d, int(_seg.start_bar), _k, float(_lit),
                    float(_spec.tp2), cfg.num_bins)
                if not (_sl < _entry < _poc < float(_spec.tp2)):
                    continue
                _tr = B._c_loese_trade(hi, lo, cl, _eb, _entry, "LONG", _sl,
                                       _poc, float(_spec.tp2),
                                       cfg.tp1_anteil_pct)
                if cfg.max_gleichzeitig_je_richtung > 0:
                    _off = B._konkurrenz_aktiv(setups, "LONG", _eb,
                                               _tr.exit1_bar, _tr.exit2_bar)
                    if _off > cfg.max_gleichzeitig_je_richtung:
                        stats["concurrency_blockiert"] += 1
                        continue
                getradete.add(_eb)
                setups.append(B._SESetup(
                    bar=_k, richtung="LONG", kid=int(_spec.boden_kid),
                    basis=float(_basis(_kante, _k)), sweep=float(lo[_k]),
                    trigger_close=float(cl[_k]),
                    touch_n=int(_kante.touch_conf(_k)), poc=float(_poc),
                    tp2=float(_spec.tp2), sl=_sl, entry=_entry,
                    r=float(_tr.r_mult), resultat=_tr.resultat,
                    stufe="STUFE_1_IN_BAR", reclaim_bar=_eb, entry_bar=_eb,
                    ist_prim_anker=False, grund1=_tr.grund1,
                    exit1_bar=int(_tr.exit1_bar), exit2_bar=int(_tr.exit2_bar),
                    grund2=_tr.grund2, r1=_tr.r1, r2=_tr.r2))

    return _Lauf(label=label, modus=("B" if hook is not None else "A"),
                 schaerfen=schaerfen, setups=setups, stats=stats, dumps=dumps)


# ------------------------------------------------------------------- Anker
def _klammer_assert(name: str, ist: Tuple[int, float],
                    soll: Tuple[int, float]) -> None:
    ist_r = (ist[0], round(ist[1], 6))
    assert ist_r == soll, f"{name}: {ist_r} != {soll}"
    print(f"  {name:10s} {ist_r[0]:3d} / {ist_r[1]:+12.6f} == {soll}")


def _zaehler_assert(name: str, st: Dict[str, Any]) -> None:
    for k, v in MB_ZAEHLER.items():
        assert int(st.get(k, 0)) == int(v), (name, k, st.get(k), v)
    print(f"  {name}: Zaehler OK ({len(MB_ZAEHLER)} Schluessel; "
          f"blocker={int(st['blocker'])})")


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
          "Adapter 770eda2c (Handoff bewusst NICHT gelesen)")

    v020 = _load("v020_s2_sonde", V020_PFAD)
    B = v020.baseline()
    from backtest_lab.phasen_regime_adapter import (  # noqa: E402
        ADAPTER_V019_KAUSAL)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = v020.V020KantenKonfiguration()
    assert cfg.wall_live_bars == kcfg.wall_live_bars == 96
    assert cfg.min_wall_alter_bars == kcfg.min_wall_alter_bars == 24
    print(f"Konfigurationsgleichheit OK: wall_live_bars="
          f"{cfg.wall_live_bars}/{kcfg.wall_live_bars}, "
          f"min_wall_alter_bars={cfg.min_wall_alter_bars}/"
          f"{kcfg.min_wall_alter_bars}")

    scan0 = B._se_scan(FENSTER, cfg)
    n = int(scan0["n"])
    assert n == BOX_END and int(scan0["box_end_bar"]) == H1_GRENZE
    scan0["box_end_bar"] = BOX_END
    alle0 = list(scan0["edges"]) + list(scan0["seeds"])
    print(f"FENSTER {FENSTER} n={n} box_end_nativ={H1_GRENZE} "
          f"edges={len(scan0['edges'])} seeds={len(scan0['seeds'])} "
          f"| Sonde k={SONDE_VON}..{SONDE_BIS}")

    hi = scan0["d"]["high"].to_numpy(dtype=float)
    lo = scan0["d"]["low"].to_numpy(dtype=float)

    print("\n===== ANKER 1: DURCHSTICH-AEQUIVALENZ =====")
    _anker_aequivalenz(alle0, v020, kcfg, hi, lo, n)

    engA = v020.V020KantenEngine(hook=None, wertedomaene=None, cfg=kcfg)
    realA, realA_st = engA._se_trades_v020(copy.deepcopy(scan0), cfg)
    realA = list(realA)

    engB = v020.V020KantenEngine(hook=ADAPTER_V019_KAUSAL,
                                 wertedomaene=ADAPTER_V019_KAUSAL, cfg=kcfg)
    realB, realB_st = engB._se_trades_v020(copy.deepcopy(scan0), cfg)
    realB = list(realB)

    print("\n===== ANKER 4: MODUS-B-KLAMMERN (realer Motor vs. Literale) =====")
    _klammer_assert("B_total", _bilanz(realB), (MB_N, MB_R))
    _klammer_assert("B_H1", _bilanz(_h1(realB)), MB_H1)
    _klammer_assert("B_H2", _bilanz(_h2(realB)), MB_H2)
    _klammer_assert("B_LONG",
                    _bilanz([x for x in realB if x.richtung == "LONG"]),
                    MB_LONG)
    _klammer_assert("B_SHORT",
                    _bilanz([x for x in realB if x.richtung == "SHORT"]),
                    MB_SHORT)
    _zaehler_assert("B_real", realB_st)
    assert not any(int(x.bar) == 1172 and int(x.kid) == 82 for x in realB), \
        "K82@1172 existiert -- tolerierte Ausnahme verletzt"
    print("  K82@1172: nicht vorhanden (Klasse-III-Docht, toleriert)")

    print("\n===== ANKER 6: A0-KLAMMERN (echter Motor) =====")
    _klammer_assert("realA_total", _bilanz(realA), (A0_N, A0_R))
    _klammer_assert("realA_H1", _bilanz(_h1(realA)), A0_H1)
    _klammer_assert("realA_H2", _bilanz(_h2(realA)), A0_H2)

    laeufe: Dict[str, _Lauf] = {}
    for lab, hook, wd, scharf, dmp in (
            ("A0", None, None, False, False),
            ("A1", None, None, True, True),
            ("B0", ADAPTER_V019_KAUSAL, ADAPTER_V019_KAUSAL, False, False),
            ("B1", ADAPTER_V019_KAUSAL, ADAPTER_V019_KAUSAL, True, True)):
        laeufe[lab] = _rekonstruiere(
            B, cfg, v020, kcfg, copy.deepcopy(scan0), hook, wd, scharf, lab,
            dmp)

    print("\n===== ANKER 2/3: VOLLSIGNATUR-REKONSTRUKTIONEN =====")
    assert _sig_karte(laeufe["A0"].setups) == _sig_karte(realA), \
        "A0 != echter Modus-A-Motor"
    print("  A0 == echter _se_trades_v020 (hook=None, Vollsignatur)")
    assert _sig_karte(laeufe["B0"].setups) == _sig_karte(realB), \
        "B0 != echter Modus-B-Motor"
    print("  B0 == echter _se_trades_v020 (hook=wd=ADAPTER, Vollsignatur)")
    print("\n===== ANKER 5: A0-KLAMMERN (Rekonstruktion) =====")
    _klammer_assert("A0_total", _bilanz(laeufe["A0"].setups), (A0_N, A0_R))
    _klammer_assert("A0_H1", _bilanz(_h1(laeufe["A0"].setups)), A0_H1)
    _klammer_assert("A0_H2", _bilanz(_h2(laeufe["A0"].setups)), A0_H2)

    print("\n===== LAUF-MATRIX =====")
    print(f"  {'Lauf':5s} {'Modus':5s} {'Schaerfe':8s} {'Trades':>7s} "
          f"{'R':>13s} | {'H1 n/R':>20s} | {'H2 n/R':>20s}")
    for lab in ("A0", "A1", "B0", "B1"):
        lf = laeufe[lab]
        a, br = _bilanz(_h1(lf.setups))
        c, dr = _bilanz(_h2(lf.setups))
        print(f"  {lab:5s} {lf.modus:5s} "
              f"{'AN' if lf.schaerfen else 'AUS':>8s} "
              f"{len(lf.setups):7d} {sum(x.r for x in lf.setups):+13.6f} | "
              f"{a:2d} {br:+16.6f} | {c:2d} {dr:+16.6f}")

    print("\n===== HYPOTHESE H-A: KANAL 1 (Modus A) =====")
    a1 = laeufe["A1"]
    ist = _bilanz(a1.setups)
    a1_h1 = _bilanz(_h1(a1.setups))
    a1_h2 = _bilanz(_h2(a1.setups))
    ziel = (ist[0], round(ist[1], 6))
    print(f"  A1 total {ziel[0]} / {ziel[1]:+.6f}  Ziel(H2-B) {H2B_N} / "
          f"{H2B_R:+.6f}  "
          f"{'== H2-B' if ziel == (H2B_N, round(H2B_R, 6)) else 'ABWEICHUNG'}")
    print(f"  A1 H1    {a1_h1[0]} / {a1_h1[1]:+.6f}  Ziel {H2B_H1}  "
          f"{'OK' if (a1_h1[0], round(a1_h1[1], 6)) == H2B_H1 else 'ABWEICHUNG'}")
    print(f"  A1 H2    {a1_h2[0]} / {a1_h2[1]:+.6f}  Ziel {H2B_H2}  "
          f"{'OK' if (a1_h2[0], round(a1_h2[1], 6)) == H2B_H2 else 'ABWEICHUNG'}")
    k45 = [x for x in a1.setups if int(x.bar) == K45_ZIEL[0]
           and int(x.kid) == K45_ZIEL[1]]
    ok45 = (len(k45) == 1 and abs(float(k45[0].r) - K45_ZIEL[2]) < 1e-6)
    print("  K45@679: " + (f"OK r={k45[0].r:+.6f} sl={k45[0].sl:.4f} "
                           f"stufe={k45[0].stufe}" if ok45
                           else "FEHLT/abweichend"))
    _report_diff("A0 -> A1 (Modus A, nur Kanal 1)", laeufe["A0"].setups,
                 a1.setups)

    print("\n===== HYPOTHESE H-B: KANAL 2+3 (Modus B) =====")
    b0, b1 = laeufe["B0"], laeufe["B1"]
    _report_diff("B0 -> B1 (Modus B, nur Kanal 1)", b0.setups, b1.setups)
    sig_ok = _sig_karte(b0.setups) == _sig_karte(b1.setups)
    print(f"  Vollsignatur B1 == B0: {sig_ok}")
    print(f"  blocker  B0={int(b0.stats['blocker'])}  B1="
          f"{int(b1.stats['blocker'])}  (Soll 83)  "
          f"{'OK' if int(b1.stats['blocker']) == 83 else 'ABWEICHUNG'}")
    for k in ZAEHLER_KEYS:
        if int(b0.stats[k]) != int(b1.stats[k]):
            print(f"    Zaehler-Abweichung {k}: B0={int(b0.stats[k])} "
                  f"B1={int(b1.stats[k])}")

    print("\n===== MECHANIK-DUMP 674..684 (Dreikanal) =====")
    for lab in ("A1", "B1"):
        print(f"\n--- Dump {lab} "
              f"({'Modus A' if laeufe[lab].modus == 'A' else 'Modus B'}, "
              f"Kanal 1 {'AN' if laeufe[lab].schaerfen else 'AUS'}) ---")
        for z in laeufe[lab].dumps:
            print(z)

    print("\n===== GESAMTBILANZ =====")
    for lab in ("A0", "A1", "B0", "B1"):
        lf = laeufe[lab]
        print(f"  {lab:5s} {len(lf.setups):3d} Trades / "
              f"{sum(x.r for x in lf.setups):+12.6f} R")


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
