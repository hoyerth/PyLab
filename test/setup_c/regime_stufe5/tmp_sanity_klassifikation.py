"""
test/tmp_sanity_klassifikation.py - Logik-Sanity-Check (Umbau 05.09.2026)
==========================================================================
Kleiner, synthetischer Test der neuen gewichteten additiven
Klassifikation in scripts/regime_filter.klassifiziere_regime:

  F1 Kaltstart (kurze Konsolidierung)            -> UNKLAR
  F2 NaN-Metrik (ema_slope)                      -> UNKLAR
  F3 Klarer TREND                                -> TREND (konf ~ t)
  F4 Momentum-Kollaps + Fakeout                  -> SHAKEOUT (konf ~ k)
  F5 Null-Evidenz                                -> UNKLAR (kein Latch)
  F6 Konfliktzone (t>0 und k>0, |s|<buffer)      -> UNKLAR
  F7 Nach F5/UNKLAR mit schwacher TREND-Evidenz  -> UNKLAR (kein Latch)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

_PROJEKT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_PROJEKT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJEKT_ROOT))

from scripts.regime_filter import (  # noqa: E402
    RegimeGateConfig,
    RegimeSchwellen,
    RegimeState,
    klassifiziere_regime,
)


def _st(
    nr: int,
    *,
    kons_bars: int = 150,
    ema_slope: float = 0.0,
    adx: float = 25.0,
    spread_atr: float = 3.0,
    tol_band: float = 0.4,
    spread_usd: float = 10.0,
    dichte: float = 0.3,
) -> RegimeState:
    return RegimeState(
        phase_nr=nr,
        brk_idx=1000 + nr,
        phase_spread_usd=spread_usd,
        phase_spread_atr_ratio=spread_atr,
        durchstoss_dichte=dichte,
        tol_band_quote=tol_band,
        konsolidierung_bars=kons_bars,
        ema_slope=ema_slope,
        adx_val=adx,
    )


def _run() -> int:
    gate: RegimeGateConfig = RegimeGateConfig()  # buffer 0.05, kaltstart 46
    schw: RegimeSchwellen = RegimeSchwellen()
    fehler: int = 0

    def check(name: str, ist: str, soll: str) -> None:
        nonlocal fehler
        ok: bool = ist == soll
        if not ok:
            fehler += 1
        print(f"  [{('OK ' if ok else 'FEHLER')}] {name}: ist={ist} soll={soll}")

    # F1: Kaltstart (kons < 46)
    r = klassifiziere_regime([_st(1, kons_bars=40)], schw, gate)[0]
    check("F1 Kaltstart", r.regime, "UNKLAR")
    # F2: NaN ema_slope
    import math
    r = klassifiziere_regime(
        [_st(2, ema_slope=float("nan"))], schw, gate
    )[0]
    check("F2 NaN-Metrik", r.regime, "UNKLAR")
    # F3: starker TREND (alle vier Trend-Merkmale klar positiv)
    r = klassifiziere_regime(
        [
            _st(
                3,
                ema_slope=0.10,
                adx=30.0,
                spread_atr=6.0,
                tol_band=0.2,
                kons_bars=160,
            )
        ],
        schw,
        gate,
    )[0]
    check("F3 TREND", r.regime, "TREND")
    # V2-Formel: t = 0.65*0.25 + 0.35*0.25 = 0.25 (beide S_oben bei 25%).
    assert r.konfidenz > 0.2, f"F3 konf unerwartet: {r.konfidenz}"
    # F4: SHAKEOUT (Momentum-Kollaps + hohe Fakeout-Quote)
    r = klassifiziere_regime(
        [
            _st(
                4,
                ema_slope=-0.15,
                adx=12.0,
                spread_atr=1.0,
                tol_band=0.80,
                kons_bars=80,
            )
        ],
        schw,
        gate,
    )[0]
    check("F4 SHAKEOUT", r.regime, "SHAKEOUT")
    # V2-Formel: k = 0.70*0.65 + 0.30*0.40 = 0.575
    assert r.konfidenz > 0.5, f"F4 konf unerwartet: {r.konfidenz}"
    # F5: Null-Evidenz -> UNKLAR (kein Vorregime-Latch)
    # V2: kons_bars geht nicht mehr in den Trend-Score ein; nur Kaltstart
    # (46) ist zu vermeiden -> 60 ist sicher oberhalb.
    r = klassifiziere_regime(
        [
            _st(
                5,
                ema_slope=0.0,
                adx=10.0,
                spread_atr=0.8,
                tol_band=0.2,
                kons_bars=60,
            )
        ],
        schw,
        gate,
    )[0]
    check("F5 Null-Evidenz", r.regime, "UNKLAR")
    # F6: Konfliktzone (t>0 UND k>0, |s| < buffer) -> UNKLAR
    r = klassifiziere_regime(
        [
            _st(
                6,
                ema_slope=-0.025,  # leicht unter ema_slope_max -> k > 0
                adx=25.2,          # knapp ueber adx_schwelle_min -> t > 0
                spread_atr=2.52,
                tol_band=0.61,
                kons_bars=101,
            )
        ],
        schw,
        gate,
    )[0]
    check("F6 Konfliktzone", r.regime, "UNKLAR")
    # F7: UNKLAR-Vorregime + nur schwache TREND-Evidenz -> kein Latch
    r = klassifiziere_regime(
        [
            _st(
                7,
                ema_slope=0.0,
                adx=10.0,
                spread_atr=0.8,
                tol_band=0.2,
                kons_bars=60,
            ),
            _st(
                8,
                ema_slope=0.06,  # knapp ueber min -> t klein, k = 0
                adx=10.0,
                spread_atr=0.8,
                tol_band=0.2,
                kons_bars=60,
            ),
        ],
        schw,
        gate,
    )[1]
    check("F7 UNKLAR-Latch-negativ", r.regime, "UNKLAR")
    # F8: TREND-Vorregime + schwache TREND-Evidenz in Totzone -> Halten
    r = klassifiziere_regime(
        [
            _st(
                9,
                ema_slope=0.10,
                adx=30.0,
                spread_atr=6.0,
                tol_band=0.2,
                kons_bars=160,
            ),
            _st(
                10,
                ema_slope=0.06,  # t klein > EPS, k = 0 -> s in Totzone
                adx=10.0,
                spread_atr=0.8,
                tol_band=0.2,
                kons_bars=60,
            ),
        ],
        schw,
        gate,
    )[1]
    check("F8 TREND-Halten-Totzone", r.regime, "TREND")

    print(f"\nERGEBNIS: {'OK' if fehler == 0 else f'{fehler} FEHLER'}")
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_run())
