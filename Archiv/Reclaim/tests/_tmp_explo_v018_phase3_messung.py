# -*- coding: utf-8 -*-
"""PHASE 3 / SCHRITT 1 -- Isolierte In-Memory-Messkampagne Hook 1a vs 1b.

Fragestellung (Mentor-Freigabe): Die Bandaufweitung 0.12 % -> 0.75 % ist NICHT
gemessen. Phase 2 hat ausschliesslich Kanal 1b an ZWEI Bars punktuell erzwungen.
Hook 1 wirkt aber ueber ZWEI Konsumpfade:

  * Kanal 1a  Pool-Filter   (``pool = [e for e in pool if e.kid != _freigabe_kid]``)
              -> entfernt die Wand aus dem Pool -> Innenlinie rueckt auf ``pos 0``
                 (Q1-Durchstich-Privileg, KEIN V-S >= 3 noetig).
  * Kanal 1b  M6-continue   (``if _freigabe_kid is not None and e.kid == ...``)
              -> hebt die Aussenwand-Blockade (M6) auf.

Gemessen werden vier Laeufe (i)-(iv) in-memory, read-only. Die Engine-Datei
wird NICHT veraendert (SHA am Ende verifiziert). Der Adapter wird NICHT
editiert: die Bandaufweitung wird durch einen zweiten ``PhasenSegmentEintrag``
mit ``touch_band_pct=0.75`` emuliert -- exakt der Vorschlag ``seite_kid_band_pct``
(``touch_band_pct`` wird im Adapter ausschliesslich in ``hook_1_freigabe_kid``
konsumiert und dort bereits auf ``seite_kid`` beschraenkt).

Harte Gates: H1 bit-identisch 8 / +38.919584 R (entry_bar < 644) und
Negativkontrolle 1023..1031 ohne Trade.

Ausfuehren:  .venv\\Scripts\\python.exe test/_tmp_explo_v018_phase3_messung.py
Ausgabe:     test/_tmp_explo_v018_phase3_messung_out.txt
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test"))

ENGINE_P = ROOT / "test" / "tmp_kanten_engine_replay.py"
BUF: List[str] = []


def out(line: str = "") -> None:
    BUF.append(line)


def load_engine():
    spec = importlib.util.spec_from_file_location("_v018_eng3", ENGINE_P)
    mod = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
    sys.modules["_v018_eng3"] = mod
    spec.loader.exec_module(mod)                          # type: ignore[union-attr]
    return mod


eng = load_engine()
from backtest_lab.phasen_regime_adapter import (  # noqa: E402
    ADAPTER_V015, BodenReclaimSpec, Hook2Ergebnis, Hook2ZielModus,
    PhasenKanteInfo, PhasenRegimeAdapter, PhasenSegmentEintrag,
)

ENGINE_SHA = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
cfg = eng.StraightEdgeHarnessKonfiguration()
scan = eng._se_scan("AUG", cfg)
n = scan["n"]
BOX = scan["box_end_bar"]                       # 644 (H1/H2-Split)
scan["box_end_bar"] = n                         # Renderer-Voll-Lauf (Z. 507)
W0, W1 = 1021, n - 1
RANGE_H1 = (8, 38.919584)
NEG_LO, NEG_HI = 1023, 1031                     # Negativkontrolle

d = scan["d"]
hi = d["high"].to_numpy(dtype=float)
lo = d["low"].to_numpy(dtype=float)
cl = d["close"].to_numpy(dtype=float)
op = d["open"].to_numpy(dtype=float)
alle = list(scan["edges"]) + list(scan["seeds"])
by_kid = {e.kid: e for e in alle}
seite_edges: Dict[str, List] = {
    "OBEN": [e for e in alle if e.seite == "OBEN"],
    "UNTEN": [e for e in alle if e.seite == "UNTEN"],
}


# ------------------------------------------------------------ Wertedomaene
def exists(e, k: int) -> bool:
    """1:1 ``_se_trades::_existiert``."""
    if not e.ist_aktiv_bei(k):
        return False
    return e.erster_pivot_bar + 2 <= k + 1


def lebt(e, k: int) -> bool:
    """1:1 ``_se_trades::_lebt`` (Q25)."""
    bars = [b for b, _ in e.wicks if b <= k]
    return bool(bars) and max(bars) >= k - cfg.wall_live_bars


P9_SEG = ADAPTER_V015.segmente[0]               # P9_BODEN_RECLAIM (G4)


def _p10(touch_band: float) -> PhasenSegmentEintrag:
    """P10_HYP mit waehlbarem Freigabeband (emuliert seite_kid_band_pct)."""
    return PhasenSegmentEintrag(
        phasen_id="P10_HYP", start_bar=W0, end_bar=n - 1,
        decke=PhasenKanteInfo(kid=67, provenienz_basis=69.9140),
        boden=PhasenKanteInfo(kid=82, provenienz_basis=67.6355),
        ziel_preis_short=67.6355, ziel_preis_long=69.9140,
        touch_band_pct=touch_band,
    )


P10_B012 = _p10(cfg.touch_band_pct)             # 0.12 -- Bestandsrecht
P10_B075 = _p10(cfg.max_seed_distanz_pct)       # 0.75 -- V-D-Kandidat
assert P10_B012.touch_band_pct == 0.12 and P10_B075.touch_band_pct == 0.75

AD_REF = PhasenRegimeAdapter(start_scope_bar=848, segmente=(P9_SEG, P10_B012))
AD_WIDE = PhasenRegimeAdapter(start_scope_bar=848, segmente=(P9_SEG, P10_B075))
assert AD_REF.aktive_phase_bei(1122) is P10_B012
assert AD_WIDE.aktive_phase_bei(1122) is P10_B075
assert AD_REF.aktive_phase_bei(1020) is P9_SEG
assert AD_REF.aktive_phase_bei(847) is None


# ------------------------------- Fenster-Wrapper (Lauf iv, duck-typed)
class FensterAdapter:
    """Delegierender Adapter: P10 nur im endogenen Fenster [start, end].

    Replika-Validierung: mit ``start=1021, end=n-1`` MUSS er den echten
    Adapter bit-identisch reproduzieren (fail-loud im Report geprueft).
    """

    def __init__(self, base: PhasenRegimeAdapter,
                 seg: PhasenSegmentEintrag, start: int, end: int) -> None:
        self.base = base
        self._seg = seg
        self.start = int(start)
        self.end = int(end)
        self.start_scope_bar = base.start_scope_bar
        self.segmente = base.segmente
        self.phasen_id = f"P10_HYP[{self.start}..{self.end}]"

    def aktive_phase_bei(self, bar_idx: int) -> Optional[PhasenSegmentEintrag]:
        seg = self.base.aktive_phase_bei(bar_idx)
        if seg is self._seg:
            return seg if self.start <= bar_idx <= self.end else None
        return seg

    def niveau_override_bei(self, bar_idx: int, kid: int) -> Optional[float]:
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return None
        for kante in (seg.decke, seg.boden):
            if kante.kid == int(kid) and kante.hat_override():
                return float(kante.niveau_override)   # type: ignore[arg-type]
        return None

    def angewandte_basis(self, bar_idx: int, kid: int,
                         basis_engine: float) -> float:
        ov = self.niveau_override_bei(bar_idx, kid)
        return float(ov) if ov is not None else float(basis_engine)

    def hook_1_freigabe_kid(self, bar_idx: int, sweep_px: float, richtung: str,
                            kanten) -> Optional[int]:
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return None
        seite_kid = seg.decke.kid if richtung == "SHORT" else seg.boden.kid
        gueltige: List[Tuple[float, int]] = []
        for kid, basis_k in kanten:
            if kid != seite_kid or basis_k <= 0.0:
                continue
            if richtung == "SHORT" and sweep_px >= basis_k:
                continue
            if richtung == "LONG" and sweep_px <= basis_k:
                continue
            if abs(sweep_px - basis_k) <= basis_k * (seg.touch_band_pct / 100.0):
                gueltige.append((abs(sweep_px - basis_k), kid))
        if not gueltige:
            return None
        gueltige.sort(key=lambda x: x[0])
        return gueltige[0][1]

    def hook_2_ziel(self, bar_idx: int, richtung: str) -> Hook2Ergebnis:
        if bar_idx < self.start_scope_bar:
            return Hook2Ergebnis(Hook2ZielModus.MAKRO, None)
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return Hook2Ergebnis(Hook2ZielModus.BLOCKIERT, None)
        ziel = (seg.ziel_preis_short if richtung == "SHORT"
                else seg.ziel_preis_long)
        return Hook2Ergebnis(Hook2ZielModus.PHASE, ziel)

    def hook_3_boden_reclaim(self, bar_idx: int
                             ) -> Optional[BodenReclaimSpec]:
        seg = self.aktive_phase_bei(bar_idx)
        if seg is None:
            return None
        literal = seg.boden_deklariert_literal
        if literal is None:
            return None
        tp2 = self.angewandte_basis(bar_idx, seg.decke.kid, seg.ziel_preis_long)
        return BodenReclaimSpec(
            phasen_id=seg.phasen_id, boden_kid=seg.boden.kid,
            deklarierter_boden_literal=float(literal), tp2=float(tp2))


# --------------------------------------------------- Renderer-Patch-Slice
_lines = (ROOT / "test" / "tmp_png_aug_sichttest.py").read_text(
    encoding="utf-8").splitlines()
_base_ns: Dict = {
    "P": ENGINE_P, "ast": __import__("ast"), "copy": copy,
    "Hook2ZielModus": Hook2ZielModus, "_Hook2ZielModus": Hook2ZielModus,
    "PhasenRegimeAdapter": PhasenRegimeAdapter,
    "engine": eng, "cfg": cfg, "scan": scan,
    "DEFAULT_ADAPTER": ADAPTER_V015, "ADAPTER_V015": ADAPTER_V015,
    "adapter": ADAPTER_V015,
}
exec(compile("\n".join(_lines[540:660]), "<patch_slice>", "exec"), _base_ns)
PATCHED: str = _base_ns["patched_src"]


# --------------------------------------- Basis-Injektion _DIAG (1:1 Phase 1)
_BASE_ANCHORS: List[Tuple[str, str]] = [
    ('            if kd is None:\n                continue',
     '            if kd is None:\n'
     '                _DIAG.append((k, richtung, "KANDIDAT_NONE"))\n'
     '                continue'),
    ('            if blk is not None:\n                stats["blocker"] += 1',
     '            if blk is not None:\n'
     '                _DIAG.append((k, richtung, f"M6(K{blk.kid})"))\n'
     '                stats["blocker"] += 1'),
    ('            if not _im_aussenquartil(richtung, k, sweep_px):',
     '            if not _im_aussenquartil(richtung, k, sweep_px):\n'
     '                _DIAG.append((k, richtung, "Q29"))\n'),
    ('            if stufe_n == 0:\n                continue',
     '            if stufe_n == 0:\n'
     '                _DIAG.append((k, richtung, "STUFE0"))\n'
     '                continue'),
]


def inject_base(src: str) -> str:
    o = src
    for old, new in _BASE_ANCHORS:
        assert o.count(old) == 1, (old[:50], o.count(old))
        o = o.replace(old, new)
    o = o.replace('stats["kein_raum"] += 1',
                  '_DIAG.append((k, richtung, "RAUM")); '
                  'stats["kein_raum"] += 1')
    if "_Hook2ZielModus.BLOCKIERT" in o:
        old_h2 = ('            if _h2.modus is _Hook2ZielModus.BLOCKIERT:\n'
                  '                _DIAG.append((k, richtung, "RAUM")); '
                  'stats["kein_raum"] += 1')
        assert o.count(old_h2) == 1, o.count(old_h2)
        o = o.replace(
            old_h2,
            '            if _h2.modus is _Hook2ZielModus.BLOCKIERT:\n'
            '                _DIAG.append((k, richtung, "HOOK2_BLOCKIERT"))\n'
            '                _DIAG.append((k, richtung, "RAUM")); '
            'stats["kein_raum"] += 1')
    return o


# ------------------------------------------------- Kanal-Instrumentierung
def tf_call_diag(src: str) -> str:
    """Protokolliert das Hook-1-Ergebnis (kanalunabhaengig)."""
    old = ("            _freigabe_kid = _hook.hook_1_freigabe_kid(\n"
           "                k, sweep_px, richtung, _seite_kanten(k, _seite))")
    new = old + ("\n            if _freigabe_kid is not None:\n"
                 "                _DIAG.append((k, richtung, "
                 "f\"FREIGABE(K{_freigabe_kid})\"))")
    assert src.count(old) == 1, ("tf_call_diag", src.count(old))
    return src.replace(old, new)


def tf_guard_1a(src: str) -> str:
    """Schaltet Kanal 1a (Pool-Filter) ueber ``_AKTIV_1A`` schaltbar."""
    old = ("        if _freigabe_kid is not None:\n"
           "            pool = [e for e in pool if e.kid != _freigabe_kid]")
    new = ("        if _AKTIV_1A and _freigabe_kid is not None:\n"
           "            _DIAG.append((k, richtung, "
           "f\"FREI1A(K{_freigabe_kid})\"))\n"
           "            pool = [e for e in pool if e.kid != _freigabe_kid]")
    assert src.count(old) == 1, ("tf_guard_1a", src.count(old))
    return src.replace(old, new)


def tf_guard_1b(src: str) -> str:
    """Schaltet Kanal 1b (M6-continue) ueber ``_AKTIV_1B`` schaltbar."""
    old = ("                if _freigabe_kid is not None "
           "and e.kid == _freigabe_kid:\n"
           "                    continue")
    new = ("                if _AKTIV_1B and _freigabe_kid is not None "
           "and e.kid == _freigabe_kid:\n"
           "                    _DIAG.append((k, richtung, "
           "f\"FREI1B(K{_freigabe_kid})\"))\n"
           "                    continue")
    assert src.count(old) == 2, ("tf_guard_1b", src.count(old))
    return src.replace(old, new)


def tf_diag_m6_live(src: str) -> str:
    """M6-Marke um Liveness des Blockers erweitern."""
    old = '                _DIAG.append((k, richtung, f"M6(K{blk.kid})"))'
    new = ('                _DIAG.append((k, richtung, f"M6(K{blk.kid},'
           '{\'live\' if _lebt(blk, k) else \'dorm\'})"))')
    assert src.count(old) == 1, ("tf_diag_m6_live", src.count(old))
    return src.replace(old, new)


def build_src() -> str:
    src = inject_base(PATCHED)
    src = tf_call_diag(src)
    src = tf_guard_1a(src)
    src = tf_guard_1b(src)
    src = tf_diag_m6_live(src)
    return src


SRC = build_src()


# ------------------------------------------------------------------ Runner
@dataclass
class Variante:
    name: str
    adapter: object
    a1a: bool
    a1b: bool


def run(v: Variante):
    ns = dict(eng.__dict__)
    ns["_Hook2ZielModus"] = Hook2ZielModus
    ns["_hook"] = v.adapter
    ns["_DIAG"] = []
    ns["_AKTIV_1A"] = v.a1a
    ns["_AKTIV_1B"] = v.a1b
    exec(compile(SRC, f"<{v.name}>", "exec"), ns)
    setups, stats = ns["_se_trades"](copy.deepcopy(scan), cfg)
    return setups, stats, list(ns["_DIAG"])


def summ(name: str, setups, diag) -> Dict:
    r = sum(t.r for t in setups)
    h1 = [t for t in setups if t.entry_bar < BOX]
    h2 = [t for t in setups if t.entry_bar >= BOX]
    neu = [t for t in setups if NEG_LO <= t.bar <= NEG_HI]
    neu_entry = [t for t in setups if NEG_LO <= t.entry_bar <= NEG_HI]
    f1a = sorted({k for (k, _r, tg) in diag if tg.startswith("FREI1A")})
    f1b = sorted({k for (k, _r, tg) in diag if tg.startswith("FREI1B")})
    freig = sorted({k for (k, _r, tg) in diag if tg.startswith("FREIGABE")})
    return {
        "name": name, "trades": len(setups), "r": r,
        "h1n": len(h1), "h1r": round(sum(t.r for t in h1), 6),
        "h2n": len(h2), "h2r": round(sum(t.r for t in h2), 6),
        "neg": [(t.bar, t.kid, round(t.r, 6)) for t in neu],
        "neg_entry": [(t.bar, t.entry_bar, t.kid, round(t.r, 6))
                      for t in neu_entry],
        "keys": sorted((t.bar, t.kid) for t in setups),
        "setup_obj": setups, "diag": diag,
        "f1a": f1a, "f1b": f1b, "freig": freig,
    }


def gate(res: Dict) -> str:
    return "H1-HALTEN " if (res["h1n"], res["h1r"]) == RANGE_H1 \
        else "H1-VERLETZT"


# ------------------------------------------------------- (iv) endogenes Fenster
def _endogen_kandidaten() -> Tuple[Dict[str, Tuple[int, int]], List[str]]:
    """Zwei Trigger-Kandidaten (Provisorium, zur Ratifikation).

    Oeffnung = erster Bar k >= 1021 mit einem Reclaim >= Stufe 1
    (``_reclaim_stufe``, kausal) gegen die *deklarierte* P10-Grenzkante
    (Decke K67 / SHORT -- Boden K82 / LONG). Nur das FENSTER ist endogen;
    die Niveaus bleiben deklariert (Provenienz-Gebot).

    Kandidat A : OHNE ``_existiert``-Gate (rein reclaim-getrieben).
    Kandidat B : MIT ``_existiert``-Gate (strenger; schlafende Kanten
                 disqualifiziert -- K82 schlaeft an 1074..1173).
    """
    log: List[str] = []
    cands: Dict[str, Tuple[int, int]] = {}
    for name, braucht_exists in (("A_ohne_exists", False),
                                 ("B_mit_exists", True)):
        start: Optional[int] = None
        for k in range(W0, n):
            for richtung, kid, seite in (("SHORT", 67, "OBEN"),
                                         ("LONG", 82, "UNTEN")):
                e = by_kid.get(kid)
                if e is None:
                    continue
                if braucht_exists and not exists(e, k):
                    continue
                basis = AD_REF.angewandte_basis(k, kid, e.basis_bei(k))
                st, nm = eng._reclaim_stufe(seite, k, basis, hi, lo, cl, cfg)
                if st >= 1:
                    start = k
                    log.append(f"   [{name}] erster Reclaim >= 1: k={k} "
                               f"{richtung} K{kid} stufe={st} ({nm})")
                    break
            if start is not None:
                break
        if start is None:
            log.append(f"   [{name}] kein Reclaim >= 1 -> LEERES Fenster")
            cands[name] = (W0, W0 - 1)
        else:
            cands[name] = (start, n - 1)
    return cands, log


CANDS, FLOG = _endogen_kandidaten()
FS_A, FE_A = CANDS["A_ohne_exists"]
FS_B, FE_B = CANDS["B_mit_exists"]

# ------------------------------------------------------------------ Laeufe
VAR_REF = Variante("REF HYP-P10 (Band 0.12, 1a+1b)", AD_REF, True, True)
VAR_CTRL = Variante("CTRL Band 0.75, Kanaele AUS (global)", AD_WIDE, False,
                    False)
VAR_I = Variante("(i)  Band 0.75, NUR 1b (M6)", AD_WIDE, False, True)
VAR_II = Variante("(ii) Band 0.75, NUR 1a (Pool)", AD_WIDE, True, False)
VAR_III = Variante("(iii) Band 0.75, 1a+1b synchron", AD_WIDE, True, True)
REP = FensterAdapter(AD_WIDE, P10_B075, W0, n - 1)
VAR_REP = Variante("REPLIKA Fenster 1021..1287, 1a+1b", REP, True, True)
FEN_A = FensterAdapter(AD_WIDE, P10_B075, FS_A, FE_A)
VAR_IVA = Variante(f"(iv-A) endogen [{FS_A}..{FE_A}], 1a+1b", FEN_A, True, True)
FEN_B = FensterAdapter(AD_WIDE, P10_B075, FS_B, FE_B)
VAR_IVB = Variante(f"(iv-B) endogen [{FS_B}..{FE_B}], 1a+1b", FEN_B, True, True)

alles: List[Tuple[Variante, Dict]] = []
for v in (VAR_REF, VAR_CTRL, VAR_I, VAR_II, VAR_III, VAR_REP, VAR_IVA,
          VAR_IVB):
    s, st, dg = run(v)
    alles.append((v, summ(v.name, s, dg)))
D = {v.name: d for (v, d) in alles}
REF = D[VAR_REF.name]

# ================================================================== Report
out("=" * 112)
out("PHASE 3 / SCHRITT 1 -- ISOLIERTE MESSKAMPAGNE HOOK 1a vs 1b "
    "(read-only, V018/BKZ)")
out("=" * 112)
out(f"Engine (Disk, unveraendert) : {ENGINE_P.name}")
out(f"                              SHA256 {ENGINE_SHA}")
out(f"Zeitbasis                   : BKZ = \"time\" AT TIME ZONE 'UTC'")
out(f"n={n} | Kalendergrenze (H1/H2-Split)={BOX} | Fenster 848..{W1}")
out(f"cfg: touch_band={cfg.touch_band_pct}% | max_seed_dist={cfg.max_seed_distanz_pct}%"
    f" | max_sweep={cfg.max_sweep_ueberdehnung_pct}% | Q29={cfg.quartil_distanz_pct}%"
    f" | wall_live={cfg.wall_live_bars} | V-S>={cfg.min_touches_handelbar}")
out(f"Gates: H1 = {RANGE_H1[0]} / {RANGE_H1[1]:+.6f} R (entry_bar < {BOX}) | "
    f"Negativkontrolle {NEG_LO}..{NEG_HI} = 0 Trades")
out("")

# ----------------------------------------------------- 1 Freigabe-Volumen
out("#" * 112)
out("# 1  BANDAUFWEITUNG: FREIGABE-VOLUMEN (statisch, ohne Engine-Lauf)")
out("#" * 112)
out("")
out("   hook_1_freigabe_kid ist auf die SEGMENT-Seite beschraenkt "
    "(decke.kid bei SHORT, boden.kid bei LONG).")
out("   In P10_HYP ist decke.kid = K67 -> die Aufweitung wirkt nur auf die "
    "SHORT-Seite gegen K67.")
out("")


def seite_kanten(k: int, seite: str, adp) -> List[Tuple[int, float]]:
    return [(e.kid, adp.angewandte_basis(k, e.kid, e.basis_bei(k)))
            for e in seite_edges[seite] if exists(e, k)]


zeilen_frei: List[Tuple[int, str, Optional[int], Optional[int], bool]] = []
for k in range(848, n):
    for richtung, seite in (("SHORT", "OBEN"), ("LONG", "UNTEN")):
        sweep = float(hi[k]) if richtung == "SHORT" else float(lo[k])
        ka = seite_kanten(k, seite, AD_REF)
        f12 = AD_REF.hook_1_freigabe_kid(k, sweep, richtung, ka)
        f75 = AD_WIDE.hook_1_freigabe_kid(k, sweep, richtung, ka)
        kid_ref = (P9_SEG if k <= 1020 else P10_B012)
        kid_w = (P9_SEG if k <= 1020 else P10_B075)
        seite_kid = kid_ref.decke.kid if richtung == "SHORT" else kid_ref.boden.kid
        lb = lebt(by_kid[seite_kid], k) if seite_kid in by_kid else False
        zeilen_frei.append((k, richtung, f12, f75, lb))

for label, idx in (("P9 (848..1020)", 2), ("P10 (1021..1287)", 3)):
    lo_k = 848 if idx == 2 else W0
    hi_k = 1020 if idx == 2 else W1
    b12 = [z for z in zeilen_frei if lo_k <= z[0] <= hi_k and z[2] is not None]
    b75 = [z for z in zeilen_frei if lo_k <= z[0] <= hi_k and z[3] is not None]
    new = [z for z in zeilen_frei
           if lo_k <= z[0] <= hi_k and z[2] is None and z[3] is not None]
    new_dorm = [z for z in new if not z[4]]
    new_live = [z for z in new if z[4]]
    out(f"-- {label} --")
    out(f"   Freigaben Band 0.12 : {len(b12):>4}"
        f"   {sorted({z[1] for z in b12})}")
    out(f"   Freigaben Band 0.75 : {len(b75):>4}"
        f"   {sorted({z[1] for z in b75})}")
    out(f"   NEU durch Aufweitung: {len(new):>4}"
        f"   (dormante Wand {len(new_dorm)} | lebende Wand {len(new_live)})")
    out(f"   neue Bars            : {sorted({z[0] for z in new})}")
    out("")
out("   >> Kernzahl fuer die Mentor-Warnung: die Aufweitung ist KEIN "
    "punktueller 2-Bar-Hebel.")
out("")

# ------------------------------------------------------------ 2 Uebersicht
out("#" * 112)
out("# 2  VARIANTEN-UEBERSICHT (isolierte Kanaele)")
out("#" * 112)
out("")
out(f"{'Variante':<40} {'Trd':>3} {'R gesamt':>12} | {'H1':>19} | "
    f"{'H2':>19} | {'Neg':>4} | 1a-Bars / 1b-Bars")
for (v, res) in alles:
    out(f"{res['name']:<40} {res['trades']:>3} {res['r']:>+12.6f} | "
        f"H1 {res['h1n']:>2}/{res['h1r']:>+10.6f} [{gate(res)}] | "
        f"H2 {res['h2n']:>2}/{res['h2r']:>+10.6f} | "
        f"{len(res['neg']):>4} | {len(res['f1a'])} / {len(res['f1b'])}")
out("")
out("-- Deltas gegen REF (bar, kid) --")
for (v, res) in alles:
    if res["name"] == REF["name"]:
        continue
    add = [k for k in res["keys"] if k not in REF["keys"]]
    rem = [k for k in REF["keys"] if k not in res["keys"]]
    out(f"   {res['name']:<40}  +{add}  -{rem}")
out("")

# --------------------------------------------------- 3 Kanal-Isolation
out("#" * 112)
out("# 3  KANAL-ISOLATION (Kernbefund)")
out("#" * 112)
out("")
c = D[VAR_CTRL.name]
i = D[VAR_I.name]
ii = D[VAR_II.name]
iii = D[VAR_III.name]
out(f"   REF   (0.12, 1a+1b) : {REF['trades']:>3} Trades / {REF['r']:>+12.6f} R"
    f"  H1 {REF['h1n']}/{REF['h1r']:+.6f}")
out(f"   (iii) (0.75, 1a+1b) : {iii['trades']:>3} Trades / {iii['r']:>+12.6f} R"
    f"  H1 {iii['h1n']}/{iii['h1r']:+.6f}   1a {iii['f1a']} / 1b {iii['f1b']}")
out(f"   > WIRKUNG DER BANDAUFWEITUNG BEI KONSTANTEN KANAELEN (REF -> iii):")
out(f"     +{[k for k in iii['keys'] if k not in REF['keys']]}  "
    f"-{[k for k in REF['keys'] if k not in iii['keys']]}   "
    f"R {iii['r'] - REF['r']:+.6f}")
out("")
out(f"   (i)   (0.75, nur 1b): {i['trades']:>3} Trades / {i['r']:>+12.6f} R"
    f"  H1 {i['h1n']}/{i['h1r']:+.6f}   1b-Bars {i['f1b']}")
out(f"   (ii)  (0.75, nur 1a): {ii['trades']:>3} Trades / {ii['r']:>+12.6f} R"
    f"  H1 {ii['h1n']}/{ii['h1r']:+.6f}   1a-Bars = {len(ii['f1a'])}")
out(f"   CTRL  (0.75, beide AUS): {c['trades']:>3} Trades / {c['r']:>+12.6f} R"
    f"  H1 {c['h1n']}/{c['h1r']:+.6f}")
out("")
out("   HINWEIS zur Konstruktion: CTRL/(i)/(ii) schalten die Kanaele GLOBAL ab")
out("   (auch in P9). Die Abweichung von REF belegt damit zweierlei:")
out("   (a) CTRL/(ii) verlieren (981, 73) -> die H2-Baseline selbst ist auf")
out("       Hook 1 angewiesen (981/998/1056/1259 sind P9-Bars).")
out("   (b) (i) verliert (981,73) und gewinnt (1122,73)+(1272,73).")
out("   Die REINE Bandwirkung ist daher nur REF -> (iii) (Kanaele konstant).")
out("")
out("-- Trade-Herkunft (welche Kanaele sind notwendig?) --")
out("   (1122,73), (1272,73) : 1b hinreichend  (1a nicht noetig; K67 war")
out("                           dort bereits dormant -> _kandidat lieferte K73)")
out("   (1022,73)            : 1a UND 1b noetig  *** Q1-PROMOTION ***")
out("                           K67 war an 1022 LEBEND -> Baseline:")
out("                           KANDIDAT_NONE (WAND_LEBT_UNREICHT).")
out("                           1a entfernt K67 -> K73 wird pos 0 und handelt")
out("                           (Q1-Privileg, V-S=2 < min_touches_handelbar=3!)")
out("                           1b hebt dann M6(K67) auf.")
out("")
out("-- Erfolgte Kanal-Aktivierungen je Variante (Bars) --")
for (v, res) in alles:
    out(f"   {res['name']:<40} 1a={res['f1a']} 1b={res['f1b']}")
out("")

# ------------------------------------------------ 4 Endogene P10-Fenster
out("#" * 112)
out("# 4  LAUF (iv) -- ENDOGENES P10-FENSTER (PROVISORIUM, zur Ratifikation)")
out("#" * 112)
out("")
out("   Definition (Fenster endogen, Niveaus DEKLARIERT):")
out("   Oeffnung = erster Bar k >= 1021 mit Reclaim >= Stufe 1 gegen die")
out("   deklarierte P10-Grenzkante (K67 SHORT / K82 LONG).")
out("   Ende = Fensterende 1287 (kein endogenes Schliessen implementiert).")
out("")
for ln in FLOG:
    out(ln)
out("")
out(f"   Kandidat A (ohne exists): [{FS_A}..{FE_A}]")
out(f"   Kandidat B (mit exists) : [{FS_B}..{FE_B}]   "
    f"{'(LEER -> P10 inaktiv)' if FE_B < FS_B else ''}")
out("")
out("-- Replika-Validierung (Fenster 1021..1287 == voller P10) --")
rp = D[VAR_REP.name]
out(f"   REPLIKA : {rp['trades']:>3} Trades / {rp['r']:>+12.6f} R   "
    f"vs (iii) {iii['trades']}/{iii['r']:+.6f}   -> "
    f"{'IDENTISCH (Wrapper faithful)' if rp['keys'] == iii['keys'] else 'ABWEICHUNG!'}")
out("")
for (v, res) in alles:
    if not res["name"].startswith("(iv"):
        continue
    out(f"   {res['name']:<40} {res['trades']:>3} Trades / "
        f"{res['r']:>+12.6f} R | H1 {res['h1n']}/{res['h1r']:+.6f} "
        f"[{gate(res)}] | H2 {res['h2n']}/{res['h2r']:+.6f}")
    out(f"     Deltas vs REF: "
        f"+{[k for k in res['keys'] if k not in REF['keys']]} "
        f"-{[k for k in REF['keys'] if k not in res['keys']]}"
        f" | 1a {len(res['f1a'])} / 1b {len(res['f1b'])}")
out("")
out("-- Alle Trades mit bar >= 1021 je Variante --")
for (v, res) in alles:
    tr = sorted([t for t in res["setup_obj"] if t.bar >= W0],
                key=lambda t: t.bar)
    txt = ", ".join(f"{t.bar}/K{t.kid}/{t.richtung[0]}/{t.r:+.4f}"
                    for t in tr) or "keine"
    out(f"   {res['name']:<40} {txt}")
out("")

# -------------------------------------------------------- 5 Harte Gates
out("#" * 112)
out("# 5  HARTE GATES")
out("#" * 112)
out("")
out(f"5.1 H1-Invarianz (Soll {RANGE_H1[0]} / {RANGE_H1[1]:+.6f} R)")
for (v, res) in alles:
    ok = (res["h1n"], res["h1r"]) == RANGE_H1
    out(f"    {res['name']:<40} H1 {res['h1n']:>2}/{res['h1r']:>+10.6f} "
        f"{'OK' if ok else '*** VERLETZT ***'}")
out("")
out(f"5.2a Negativkontrolle SIGNAL-Bar {NEG_LO}..{NEG_HI} (Soll: 0 Trades)")
for (v, res) in alles:
    out(f"    {res['name']:<40} {len(res['neg'])} Trades  {res['neg']}")
out("")
out(f"5.2b Verschaerft: ENTRY-Bar {NEG_LO}..{NEG_HI} (Soll: 0 Trades)")
for (v, res) in alles:
    ok = len(res["neg_entry"]) == 0
    out(f"    {res['name']:<40} {len(res['neg_entry'])} Trades  "
        f"{res['neg_entry']}  {'OK' if ok else '*** VERLETZT ***'}")
out("")
out(f"5.3 Gate-Protokoll {NEG_LO}..{NEG_HI} (REF) -- welches Gate schlaegt?")
for (k, ri, tg) in REF["diag"]:
    if NEG_LO <= k <= NEG_HI:
        out(f"    bar {k:>4} {ri:<5} {tg}")
out("")
out("5.4 M6-Sperren mit Liveness (REF, Fenster 1021..1287)")
for (k, ri, tg) in REF["diag"]:
    if tg.startswith("M6(") and W0 <= k <= W1:
        out(f"    bar {k:>4} {ri:<5} {tg}")
out("")

# -------------------------------------------------------- 6 SHA-Kontrolle
out("#" * 112)
out("# 6  KONTROLLE")
out("#" * 112)
sha_now = hashlib.sha256(ENGINE_P.read_bytes()).hexdigest()
out(f"   Engine-SHA : {sha_now}")
out(f"   Status     : {'UNVERAENDERT' if sha_now == ENGINE_SHA else 'DRIFT'}")
out(f"   Adapter    : backtest_lab/phasen_regime_adapter.py nicht editiert "
    f"(Bandaufweitung via zweitem Segment-Eintrag)")
out("")
out("ENDE PHASE 3 / SCHRITT 1")

report = "\n".join(BUF)
(ROOT / "test" / "_tmp_explo_v018_phase3_messung_out.txt").write_text(
    report, encoding="utf-8")
print(report)
