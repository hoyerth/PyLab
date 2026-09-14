"""
test/tmp_inspect_freezed.py - Rein lesende Inspektion des Freeze-Siegels
========================================================================
Verifiziert test/regime_schwellen_freezed.json (Schritt-4-Abnahme):
  - 4 Schwellenwerte gegen die Soll-Freeze-Zentren
  - 64-stellige SHA-256-Hashes (Format + Uebereinstimmung tmp_regime_freezed.txt)
  - Konsistenz historie_defaults / metrik_config / gate_config / schwellen_obj_repr
Kein Schreiben, kein Kalibrier-Pfad, kein OOS-Zugriff.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Dict, List

_TEST_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent
_SIEGEL: pathlib.Path = _TEST_DIR / "regime_schwellen_freezed.json"
_UEBERSICHT: pathlib.Path = _TEST_DIR / "tmp_regime_freezed.txt"

_SOLL: Dict[str, float] = {
    "ema_slope_min": 0.07,
    "ema_slope_max": -0.03,
    "adx_schwelle_min": 25.0,
    "tol_band_quote_max": 0.60,
}


def _main() -> int:
    if not _SIEGEL.exists():
        print(f"FEHLER: Siegel fehlt: {_SIEGEL}")
        return 1
    d: Dict = json.loads(_SIEGEL.read_text(encoding="utf-8"))
    fehler: int = 0

    def check(name: str, ok: bool, detail: str) -> None:
        nonlocal fehler
        if not ok:
            fehler += 1
        print(f"  [{('OK ' if ok else 'FEHLER')}] {name}: {detail}")

    print(f"version: {d.get('version')} | datum: {d.get('datum')}")
    print(f"quelle_fenster: {d.get('quelle_fenster')}")

    # 1) Schwellenwerte
    schw: Dict[str, float] = d["schwellen"]
    check("Schwellen-Anzahl", len(schw) == 4, f"IST {len(schw)} SOLL 4")
    for k, v in _SOLL.items():
        ist: float = float(schw[k])
        ok: bool = abs(ist - v) < 1e-9
        check(f"Schwelle {k}", ok, f"IST={ist:.6f} SOLL={v:.6f}")

    # 2) Hashes: Format + Uebereinstimmung mit der Uebersicht
    for name in ("sha256_states_s1", "sha256_states_s2"):
        h: str = str(d[name])
        ok_fmt: bool = re.fullmatch(r"[0-9a-f]{64}", h) is not None
        check(f"Hash-Format {name}", ok_fmt, f"laenge={len(h)} hex64={ok_fmt}")
    ueb: str = _UEBERSICHT.read_text(encoding="utf-8") if _UEBERSICHT.exists() else ""
    for name in ("sha256_states_s1", "sha256_states_s2"):
        h = str(d[name])
        ok_ueb: bool = h in ueb
        check(f"Uebersicht {name}", ok_ueb, "im tmp_regime_freezed.txt enthalten")

    # 3) Konsistenz
    hd: Dict[str, float] = d["historie_defaults"]
    check(
        "historie_defaults deckungsgleich",
        set(hd.keys()) == set(_SOLL.keys()),
        f"keys={sorted(hd.keys())}",
    )
    mc: List[str] = list(d["metrik_config"].keys())
    check(
        "metrik_config vollstaendig",
        all(
            k in mc
            for k in (
                "tol",
                "ema_slope_lookback",
                "atr_periode",
                "ema_periode",
                "adx_periode",
                "tol_band_messfenster_bars",
                "durchstoss_fenster_bars",
                "konsolidierung_min_bars",
            )
        ),
        f"keys={mc}",
    )
    gc: Dict = d["gate_config"]
    check(
        "gate_config Sollwerte",
        (
            gc["hysterese_puffer"] == 0.05
            and gc["kaltstart_min_bars"] == 46
            and gc["fallback_horizont"] == 48
            and gc["fallback_nur_raw_a"] is True
        ),
        f"IST={gc}",
    )
    check(
        "schwellen_obj_repr vorhanden",
        "RegimeSchwellen" in str(d.get("schwellen_obj_repr", "")),
        str(d.get("schwellen_obj_repr"))[:100],
    )

    print(f"\nERGEBNIS: {'OK' if fehler == 0 else f'{fehler} FEHLER'}")
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())
