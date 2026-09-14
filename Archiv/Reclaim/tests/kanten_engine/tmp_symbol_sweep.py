"""Generischer Parameter-Sweep (Reihenuntersuchung) fuer die Symbol-Engine.

Fuehrt test/tmp_phasen_volumen_profil_symbol.py fuer SYMBOL+Fenster ueber eine
Parameter-Wertliste aus und protokolliert die [STATS-EXPORT]-Kernzeile.

Aufruf:
  python test/tmp_symbol_sweep.py SYMBOL FENSTER PARAM WERTE [KEY=VAL ...]
  SYMBOL: z.B. Cocoa | FENSTER: AUG|S1|S2
  PARAM : va-pct | sl-pct | min-spread-pct | min-candles | min-touches
  WERTE : kommaseparierte Zahlen
  KEY=VAL: optionale Fix-Parameter (z.B. va-pct=0.91) fuer Sweeps anderer Params

Fenster-Basissets (ATR-skaliert, siehe tmp_symbol_params.py).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent
ENGINE = TEST / "tmp_phasen_volumen_profil_symbol.py"
PY = r".venv/Scripts/python.exe"

# ATR-skalierte Basissets je Symbol/Fenster: (start, ende, tol, tol_touch,
# density, shift, sl_pct). Ergänzt je SYMBOL aus tmp_symbol_params.py.
BASE = {
    "Coffee": {
        "AUG": ("2026-08-10", "2026-08-28", "2.8946", "1.2770", "1.2770", "0.4257", "0.5363"),
        "S1": ("2026-02-05", "2026-08-28", "1.3531", "0.5970", "0.5970", "0.1990", "0.4481"),
        "S2": ("2025-01-01", "2025-12-01", "6.5852", "2.9052", "2.9052", "0.9684", "0.4502"),
    },
    "Cocoa": {
        "AUG": ("2026-08-10", "2026-08-28", "66.1328", "29.1763", "29.1763", "9.7254", "0.6718"),
        "S1": ("2026-02-05", "2026-08-28", "31.2673", "13.7944", "13.7944", "4.5981", "0.7005"),
        "S2": ("2025-01-01", "2025-12-01", "216.0518", "95.3170", "95.3170", "31.7723", "0.6133"),
    },
    "NGas": {
        "AUG": ("2026-08-10", "2026-08-28", "0.0139", "0.0061", "0.0061", "0.0020", "0.3001"),
        "S1": ("2026-02-05", "2026-08-28", "0.0118", "0.0052", "0.0052", "0.0017", "0.3885"),
        "S2": ("2025-01-01", "2025-12-01", "0.0573", "0.0253", "0.0253", "0.0084", "0.3972"),
    },
    "EURUSD": {
        "AUG": ("2026-08-10", "2026-08-28", "0.0006", "0.0003", "0.0003", "0.0001", "0.0317"),
        "S1": ("2026-02-05", "2026-08-28", "0.0005", "0.0002", "0.0002", "0.0001", "0.0449"),
        "S2": ("2025-01-01", "2025-12-01", "0.0028", "0.0012", "0.0012", "0.0004", "0.0608"),
    },
    "Ger40": {
        "AUG": ("2026-08-10", "2026-08-28", "34.5576", "15.2460", "15.2460", "5.0820", "0.0786"),
        "S1": ("2026-02-05", "2026-08-28", "36.5340", "16.1179", "16.1179", "5.3726", "0.1429"),
        "S2": ("2025-01-01", "2025-12-01", "118.4990", "52.2790", "52.2790", "17.4263", "0.1270"),
    },
}


def run_engine(symbol: str, fenster: str, extra: list[str]) -> dict:
    st, en, tol, tt, db, sh, sl = BASE[symbol][fenster]
    cmd = [
        PY, str(ENGINE), f"--symbol={symbol}",
        f"--start={st}", f"--ende={en}",
        f"--stats-txt={TEST / f'stats_trades_{symbol}_{fenster}.txt'}",
        f"--tol={tol}", f"--tol-touch={tt}", f"--density-band={db}",
        f"--shift-tol={sh}", f"--sl-pct={sl}",
        *extra,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"Engine-Fehler {symbol} {fenster} {extra}:\n{r.stderr[-2500:]}")
    for line in reversed(r.stdout.splitlines()):
        if f"[STATS-EXPORT] {symbol}_{fenster}" in line and "| Baseline" in line:
            d: dict = {"label": f"{symbol}_{fenster}"}
            for p in [x.strip() for x in line.split("|")]:
                p = p.replace("[STATS-EXPORT] ", "")
                if p.startswith("n="):
                    d["n"] = int(p[2:])
                elif p.startswith("WR "):
                    d["wr"] = float(p.split()[1].rstrip("%"))
                elif p.startswith("SumR "):
                    d["sumr"] = float(p.split()[1].rstrip("R"))
                elif p.startswith("AvgW "):
                    d["avgw"] = float(p.split()[1].rstrip("R"))
                elif p.startswith("AvgL "):
                    d["avgl"] = float(p.split()[1].rstrip("R"))
                elif p.startswith("PF "):
                    pf = p.split()[1]
                    d["pf"] = float(pf) if pf != "unendl." else float("inf")
            if d:
                return d
    raise RuntimeError(f"STATS-EXPORT-Zeile fehlt {symbol} {fenster}")


def main() -> None:
    if len(sys.argv) < 5:
        raise SystemExit("Aufruf: tmp_symbol_sweep.py SYMBOL FENSTER PARAM WERTE")
    symbol = sys.argv[1]
    fenster = sys.argv[2]
    param = sys.argv[3]
    values = [float(x) for x in sys.argv[4].split(",")]
    fixed = {}
    for a in sys.argv[5:]:
        if "=" in a:
            k, v = a.split("=", 1)
            fixed[f"--{k}"] = v
    # Sweep-Parameter selbst niemals als Fix setzen
    fixed.pop(f"--{param}", None)
    # Bei Fix-Parametern eigener Protokollname (Idempotenz sonst falsch).
    tag = ""
    if fixed:
        tag = "_" + "_".join(k.strip("-") + v for k, v in sorted(fixed.items()))
    out_file = TEST / f"tmp_{symbol}_{param.replace('-', '_')}_sweep_{fenster}{tag}.txt"
    done = set()
    if out_file.exists():
        for line in out_file.read_text(encoding="utf-8").splitlines():
            try:
                done.add(float(line.split()[0]))
            except (ValueError, IndexError):
                pass

    sl_pct = float(BASE[symbol][fenster][6])
    rows = []
    for v in values:
        if v in done:
            print(f"[{symbol} {fenster} {param}={v}] uebersprungen (vorhanden)")
            continue
        extra = {f"--{param}": f"{v}"}
        cli_extra = [f"{k}={val}" for k, val in {**fixed, **extra}.items()]
        d = run_engine(symbol, fenster, cli_extra)
        # Kursrendite in %/Trade = SumR x SL_PCT (%) / Trades
        sl_eff = v if param == "sl-pct" else sl_pct
        kurs = d["sumr"] * sl_eff / d["n"] if d["n"] else 0.0
        line = f"{v:<8.4f} {d['n']:>4d} {d['wr']:>6.1f} {d['sumr']:>+9.2f} {d['pf']:>6.2f} {d['avgw']:>+6.2f} {d['avgl']:>+6.2f} {kurs:>+8.4f}"
        print(f"[{symbol} {fenster} {param}={v}]: {line}")
        with out_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        rows.append(line)
    print(f"Protokoll: {out_file}")


if __name__ == "__main__":
    main()
