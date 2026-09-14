# -*- coding: utf-8 -*-
"""READ-ONLY Kausalitaets-Probe AUG_SEP (Schritt 4 der DuckDB-Roadmap).

Fenster (Anwendervorgabe): erster Handelstag August 2026 = 2026-08-03,
Ende 2026-09-12 (exklusiv). Das ist das EXT-Universum aus H20.44 Abschnitt 11b.

Beweisziel (KEIN Praefix, sondern BINNENSEGMENT):
  (1) ts_ext[460:1748] == ts_aug  (Bar-Indizes verschieben sich um +460)
  (2) searchsorted(ts_ext, "2026-08-19") == 1104 == 460 + 644
  (3) FENSTER-INVARIANZ gemessen: A0/B0 auf EXT mit box_end = 1748 vs. AUG.
      Erwartung war Feldgleichheit; gemessen wird die tatsaechliche Differenz
      (kein erzwungener Assert).
  (4) Vollauf EXT (box_end = n): H1/H2-Wachstum, neue Frontier.

Read-only: FENSTER-Eintrag wird NUR in der geladenen Modul-Instanz injiziert;
keine Datei-, Motor- oder DB-Mutation. Einzige Schreiboperation: dieses
Protokoll `_chk_augsep_probe_out.txt`.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
PROTOKOLL = ROOT / "test" / "_chk_augsep_probe_out.txt"

BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

FENSTER_NEU = ("2026-08-03", "2026-09-12")
N_AUG = 1288
BOX_END_AUG = 644
OFFSET_SOLL = 460
BOX_END_EXT_SOLL = 1104
H1_GRENZE_AUG = 644
ZAEHLER_KEYS = ("blocker", "quartil_blockiert", "frisch_blockiert",
                "zyklus_blockiert", "kein_raum", "kein_gegner", "f3",
                "concurrency_blockiert", "quartil_undefiniert")
ANKER = {"A0": (29, 23.389914), "B0": (33, 56.549174)}
ANKER_H1_AUG = {"A0": (14, 27.327383), "B0": (14, 27.327383)}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class _StdoutStub:
    """fd-freier stdout-Ersatz (Baseline haengt beim exec sys.stdout um)."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _load(name: str, p: Path) -> Any:
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


def _sig(x: Any) -> Tuple[Any, ...]:
    return (int(x.kid), str(x.richtung), float(x.r), int(x.entry_bar),
            round(float(x.sl), 6), round(float(x.tp2), 6),
            int(x.exit1_bar), int(x.exit2_bar), str(x.stufe))


def main() -> None:
    zeilen: List[str] = []
    assert _sha(BASELINE_PFAD) == BASELINE_SHA_SOLL, "Baseline-Fremdstand"
    assert _sha(V020_PFAD) == V020_SHA_SOLL, "V020-Fremdstand"
    assert _sha(ADAPTER_PFAD) == ADAPTER_SHA_SOLL, "Adapter-Fremdstand"
    zeilen.append("SHA-Guards OK: Baseline 53f28e1b / V020 e79c5c29 / "
                  "Adapter 770eda2c")
    zeilen.append(f"NEUES FENSTER: {FENSTER_NEU[0]} .. {FENSTER_NEU[1]} "
                  f"(exklusiv) | bestehendes AUG: 2026-08-10 .. 2026-08-28")

    B = _load("basis_probe", BASELINE_PFAD)
    v020 = _load("v020_probe", V020_PFAD)
    from backtest_lab.phasen_regime_adapter import (  # noqa: E402
        ADAPTER_V019_KAUSAL)
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = v020.V020KantenKonfiguration()

    # --- Fenster injizieren (nur Modul-Instanz, keine Datei) ----------------
    assert "AUG_SEP" not in B.FENSTER
    B.FENSTER["AUG_SEP"] = FENSTER_NEU

    ts_aug = B._lade_fenster("AUG")["ts"].to_numpy().astype("datetime64[ns]")
    ts_ext = B._lade_fenster("AUG_SEP")["ts"].to_numpy().astype("datetime64[ns]")
    n_aug, n_ext = int(ts_aug.size), int(ts_ext.size)
    assert n_aug == N_AUG, f"AUG n={n_aug}"
    zeilen.append("")
    zeilen.append("===== BEWEIS 1: BINNENSEGMENT (kein Praefix) =====")
    zeilen.append(f"  AUG n={n_aug} | AUG_SEP n={n_ext} "
                  f"(Differenz {n_ext - n_aug})")
    zeilen.append(f"  AUG erste Kerze : {ts_aug[0]}")
    zeilen.append(f"  AUG_SEP erste   : {ts_ext[0]}")
    zeilen.append(f"  AUG_SEP letzte  : {ts_ext[-1]}")
    assert ts_ext[0] != ts_aug[0], "Doch Praefix? unerwartet"
    assert np.array_equal(ts_ext[OFFSET_SOLL:OFFSET_SOLL + n_aug], ts_aug), \
        "Binnensegment-Beweis verletzt"
    zeilen.append(f"  OK: ts_ext[{OFFSET_SOLL}:{OFFSET_SOLL + n_aug}] == "
                  f"ts_aug (Offset {OFFSET_SOLL} = 5 Handelstage x 92)")
    zeilen.append("  FOLGE: AUG ist KEIN Praefix; alle AUG-Bar-Indizes "
                  "liegen im AUG_SEP-Frame um +460 verschoben.")

    scan_ext = B._se_scan("AUG_SEP", cfg)
    zeilen.append("")
    zeilen.append("===== BEWEIS 2: BOX-GRENZE (Kanon K6) =====")
    zeilen.append(f"  box_end_bar(AUG_SEP, '{cfg.box_end_datum}') = "
                  f"{int(scan_ext['box_end_bar'])}")
    zeilen.append(f"  Erwartung: {BOX_END_EXT_SOLL} = {OFFSET_SOLL} + "
                  f"{BOX_END_AUG}")
    assert int(scan_ext["box_end_bar"]) == BOX_END_EXT_SOLL, "Box-Grenze"
    zeilen.append(f"  OK: edges={len(scan_ext['edges'])} "
                  f"seeds={len(scan_ext['seeds'])} n={int(scan_ext['n'])}")

    # --- Beweis 3: Kausalitaet (AUG-Binnensegment) --------------------------
    scan_aug = B._se_scan("AUG", cfg)
    scan_aug["box_end_bar"] = N_AUG                     # Vollauf-Konvention
    scan_ext_seg = copy.deepcopy(scan_ext)
    scan_ext_seg["box_end_bar"] = OFFSET_SOLL + N_AUG   # gleiche Basis-Bars

    zeilen.append("")
    zeilen.append("===== BEWEIS 3: FENSTER-INVARIANZ (gemessen, NICHT erzwungen) "
                  "=====")
    invariant_ok = True
    for lab, hook, wd in (("A0", None, None),
                          ("B0", ADAPTER_V019_KAUSAL, ADAPTER_V019_KAUSAL)):
        eng = v020.V020KantenEngine(hook=hook, wertedomaene=wd, cfg=kcfg)
        s_aug, _ = eng._se_trades_v020(copy.deepcopy(scan_aug), cfg)
        eng2 = v020.V020KantenEngine(hook=hook, wertedomaene=wd, cfg=kcfg)
        s_ext, _ = eng2._se_trades_v020(copy.deepcopy(scan_ext_seg), cfg)
        s_aug = list(s_aug)
        s_ext = list(s_ext)
        n_a, r_a = len(s_aug), float(sum(x.r for x in s_aug))
        h1a = [x for x in s_aug if int(x.entry_bar) < H1_GRENZE_AUG]
        soll = ANKER[lab]
        assert (n_a, round(r_a, 6)) == soll, (lab, n_a, r_a, soll)
        assert (len(h1a), round(float(sum(x.r for x in h1a)), 6)) == \
            ANKER_H1_AUG[lab], (lab, "H1")
        seg = [x for x in s_ext
               if OFFSET_SOLL <= int(x.entry_bar) < OFFSET_SOLL + N_AUG]
        ka = {(int(x.entry_bar), str(x.richtung)): x for x in s_aug}
        ke = {(int(x.entry_bar) - OFFSET_SOLL, str(x.richtung)): x
              for x in seg}
        gem = sorted(set(ka) & set(ke))
        nur_a = sorted(set(ka) - set(ke))
        nur_e = sorted(set(ke) - set(ka))
        div = [kk for kk in gem
               if abs(float(ka[kk].r) - float(ke[kk].r)) >= 1e-9]
        if len(seg) != n_a or nur_a or nur_e or div:
            invariant_ok = False
        zeilen.append(
            f"  {lab}: AUG {n_a} / {r_a:+.6f} (Klammer {soll})  |  "
            f"EXT-Segment {len(seg)} / "
            f"{float(sum(x.r for x in seg)):+.6f}")
        zeilen.append(
            f"    gemeinsame (entry,richtung) {len(gem)}: R-identisch "
            f"{len(gem) - len(div)}, R-abweichend {len(div)}  |  "
            f"nur-AUG {len(nur_a)}  nur-EXT {len(nur_e)}")
        for kk in div[:12]:
            zeilen.append(
                f"      DIV entry={kk[0]} {kk[1]:5s} "
                f"AUG K{ka[kk].kid} r={ka[kk].r:+.6f} -> "
                f"EXT K{ke[kk].kid} r={ke[kk].r:+.6f}")
        for kk in nur_a[:12]:
            zeilen.append(f"      NUR-AUG entry={kk[0]} {kk[1]:5s} "
                          f"K{ka[kk].kid} r={ka[kk].r:+.6f}")
        for kk in nur_e[:12]:
            zeilen.append(f"      NUR-EXT entry={kk[0]} {kk[1]:5s} "
                          f"K{ke[kk].kid} r={ke[kk].r:+.6f}")
    zeilen.append(
        "  VERDIKT: " + ("FENSTER-INVARIANT" if invariant_ok
                        else "NICHT invariant -- der Scan ist fenster-global "
                             "(Basis-VWAP ueber alle Touches, R21-Tombstone, "
                             "Kid-Renumbering). Die AUG-SSoT uebertraegt sich "
                             "NICHT auf ein laengeres Fenster."))

    # --- Beweis 4: Vollauf EXT (neue Frontier) ------------------------------
    scan_ext_full = copy.deepcopy(scan_ext)
    scan_ext_full["box_end_bar"] = int(scan_ext["n"])
    zeilen.append("")
    zeilen.append("===== BEWEIS 4: VOLLAUF EXT (neue Frontier, box_end=n) =====")
    for lab, hook, wd in (("A0", None, None),
                          ("B0", ADAPTER_V019_KAUSAL, ADAPTER_V019_KAUSAL)):
        eng = v020.V020KantenEngine(hook=hook, wertedomaene=wd, cfg=kcfg)
        ss, st = eng._se_trades_v020(copy.deepcopy(scan_ext_full), cfg)
        ss = list(ss)
        tot_n, tot_r = len(ss), float(sum(x.r for x in ss))
        seg = [x for x in ss
               if OFFSET_SOLL <= int(x.entry_bar) < OFFSET_SOLL + N_AUG]
        h1 = [x for x in ss if int(x.entry_bar) < OFFSET_SOLL + H1_GRENZE_AUG]
        h2 = [x for x in ss if int(x.entry_bar) >= OFFSET_SOLL + H1_GRENZE_AUG]
        new = [x for x in ss if int(x.bar) >= OFFSET_SOLL + N_AUG]
        zeilen.append(
            f"  {lab}: total {tot_n} / {tot_r:+.6f}  |  AUG-Segment "
            f"{len(seg)} / {float(sum(x.r for x in seg)):+.6f}  |  "
            f"H1(<{OFFSET_SOLL + H1_GRENZE_AUG}) {len(h1)} / "
            f"{float(sum(x.r for x in h1)):+.6f}  |  H2 {len(h2)} / "
            f"{float(sum(x.r for x in h2)):+.6f}  |  nur-Sep (bar>={OFFSET_SOLL + N_AUG}) "
            f"{len(new)} / {float(sum(x.r for x in new)):+.6f}")

    zeilen.append("")
    zeilen.append("===== VERDIKT =====")
    zeilen.append("  1. ts-Binnensegment OK (AUG = AUG_SEP[460:1748]); "
                  "AUG ist KEIN Praefix.")
    zeilen.append("  2. Box-Grenze OK (searchsorted '2026-08-19' = 1104 = "
                  "460 + 644, Kanon K6).")
    zeilen.append("  3. FENSTER-INVARIANZ: " + (
        "gegeben." if invariant_ok else
        "VERLETZT. Der Scan ist fenster-global: Kanten-Basis (VWAP ueber "
        "alle Touches), R21-Tombstone-Loeschung und Kid-Vergabe haengen vom "
        "GESAMTEN Fenster ab. Eine Verlaengerung veraendert rueckwirkend "
        "AUG-Trades (nicht nur die Kid-Nummern)."))
    zeilen.append("  FOLGE fuer die Roadmap: 'AUG bit-identisch in einem "
                  "laengeren Fenster' gilt fuer die ROH-OHLC-Zeitachse, "
                  "NICHT fuer Scan/Trades. Vor Schritt-4-Implementierung ist "
                  "eine kausalitaets-invariante Scan-Variante zu spezifizieren.")

    PROTOKOLL.write_text("\n".join(zeilen) + "\n", encoding="utf-8",
                         newline="\n")
    for zl in zeilen:
        print(zl)
    print(f"\nProtokoll -> {PROTOKOLL}  ({PROTOKOLL.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
