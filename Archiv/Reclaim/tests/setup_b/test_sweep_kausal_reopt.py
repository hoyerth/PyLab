# test/test_sweep_kausal_reopt.py
"""Kausale Parameter-Re-Optimierung Setup B (Sample 1: 2026-02-05..2026-08-28).

Nach der Lookahead-Bereinigung (31.08.2026) sind alle bisherigen Parameter-
Optima (auf Lookahead-Code entstanden) ungueltig. Dieser Sweep validiert die
Prioritaets-Parameter auf dem kausalen Code neu (Reihenfolge laut Handoff):
  1) MIN_RECLAIM_CANDLES  2) MIN_RECLAIM_BOUNCE  3) MIN_RECLAIM_CRV
  4) MIN_SIGNAL_ABSTAND_BARS (Cooldown)

Konvention: volle Trade-Dumps unter scripts/results_kausal_*.txt (bewusst
NEUER Namensraum, damit die historischen Lookahead-Ergebnisse in
scripts/results_reihe_*.txt erhalten bleiben). Kompakte Tabelle auf stdout.

Aufruf:  python test/test_sweep_kausal_reopt.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "phasen_volumen_profil.py"
TXT = ROOT / "scripts" / "phasen_volumen_profil.txt"
OUT_DIR = ROOT / "scripts"
START, ENDE = "2026-02-05", "2026-08-28"

# (Namensraum, CLI-Flag, [(suffix, wert), ...])
SWEEPS = [
    ("rcand", "--reclaim-candles=", [
        ("00", 0), ("05", 5), ("10", 10), ("15", 15), ("20", 20),
        ("25", 25), ("30", 30), ("40", 40), ("50", 50), ("60", 60),
        ("80", 80), ("100", 100),
    ]),
    ("bounce", "--bounce=", [("1", 1), ("2", 2), ("3", 3)]),
    ("crv", "--crv=", [("05", 0.5), ("10", 1.0), ("15", 1.5), ("20", 2.0), ("25", 2.5)]),
    ("cooldown", "--cooldown=", [("08", 8), ("10", 10), ("12", 12), ("14", 14), ("16", 16)]),
]


def parse_summary(txt_path):
    """Liest die Kopf-Statistik (erste 6 Zeilen) des Trade-Dumps."""
    head = {}
    for ln in txt_path.read_text(encoding="utf-8").splitlines()[:6]:
        if ln.startswith("# CALLS"):
            import re
            m = re.search(r"LONG\):\s+(\d+).*SHORT\):\s+(\d+)", ln)
            if m:
                head["calls"], head["sells"] = int(m.group(1)), int(m.group(2))
        elif ln.startswith("WINRATE"):
            import re
            m = re.search(r"(\d+)%", ln)
            if m:
                head["wr"] = int(m.group(1))
            m2 = re.search(r"(\d+)W/(\d+)L/(\d+)N", ln)
            if m2:
                head["w"], head["l"], head["n"] = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        elif ln.startswith("avg CRV"):
            head["avg_crv"] = float(ln.split(":")[1].strip())
        elif ln.startswith("Summe R"):
            head["sum_r"] = float(ln.split(":")[1].strip().replace("+", ""))
    return head


def run_one(flag, value, suffix, ns):
    """Fuehrt das Haupt-Skript mit Override aus und sichert den Trade-Dump."""
    r = subprocess.run(
        [sys.executable, str(SRC), f"--start={START}", f"--ende={ENDE}", f"{flag}{value}"],
        capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f"FEHLER bei {flag}{value}: {r.stderr[-500:]}")
        return None
    dump = OUT_DIR / f"results_kausal_{ns}{suffix}.txt"
    if TXT.exists():
        TXT.replace(dump)
    # Konsolen-Statistik (Signale/avg R/max/min) zusaetzlich ausgeben
    extra = []
    for ln in r.stdout.splitlines():
        s = ln.strip()
        if s.startswith("  Signale:") or s.startswith("  Summe R:") or s.startswith("  Trefferquote:"):
            extra.append(s)
    return {"dump": dump, "extra": extra}


def summary_only():
    """Liest vorhandene Dumps (scripts/results_kausal_*.txt) und druckt die Tabelle."""
    ns_map = {"rcand": "MIN_RECLAIM_CANDLES", "bounce": "MIN_RECLAIM_BOUNCE",
              "crv": "MIN_RECLAIM_CRV", "cooldown": "Cooldown"}
    for ns in ns_map:
        print(f"=== {ns_map[ns]} (kausal, Sample 1 {START}..{ENDE}) ===")
        print(f"{'Wert':>10} | {'Sig':>4} | {'WR%':>4} | {'W/L':>6} | {'SummeR':>8} | {'avgCRV':>6} | {'avgR':>6}")
        rows = []
        for f in sorted(OUT_DIR.glob(f"results_kausal_{ns}*.txt")):
            head = f.read_text(encoding="utf-8").splitlines()[:6]
            calls = next((ln for ln in head if ln.startswith("# CALLS")), "")
            wr = next((ln for ln in head if ln.startswith("WINRATE")), "")
            crv = next((ln for ln in head if ln.startswith("avg CRV")), "")
            sm = next((ln for ln in head if ln.startswith("Summe R")), "")
            m_c = re.search(r"LONG\):\s+(\d+).*SHORT\):\s+(\d+)", calls)
            m_w = re.search(r"(\d+)W/(\d+)L", wr)
            m_s = re.search(r"([+-][\d.]+)", sm)
            val = f.stem.replace(f"results_kausal_{ns}", "")
            n = int(m_c.group(1)) + int(m_c.group(2)) if m_c else 0
            w = int(m_w.group(1)); l = int(m_w.group(2)) if m_w else 0
            wrp = 100.0 * w / (w + l) if (w + l) else 0.0
            sumr = float(m_s.group(1)) if m_s else 0.0
            acrv = float(crv.split(":")[1].strip())
            avg_r = sumr / n if n else 0.0
            rows.append((val, n, wrp, f"{w}/{l}", sumr, acrv, avg_r))
        for r in rows:
            print(f"{r[0]:>10} | {r[1]:>4} | {r[2]:>3.0f}% | {r[3]:>6} | {r[4]:>+8.2f} | {r[5]:>6.2f} | {r[6]:>+6.2f}")
        print()


def main():
    print(f"=== KAUSALE PARAMETER-RE-OPTIMIERUNG | Sample 1: {START}..{ENDE} ===")
    print(f"Baseline (Lookahead-Optima auf kausalem Code): 201 Sig / 44% / +197.26R\n")
    for ns, flag, values in SWEEPS:
        print(f"--- {ns} ---")
        print(f"{'Wert':>8} | {'Signale':>7} | {'WR%':>4} | {'W/L/N':>10} | {'Summe R':>8} | {'avg CRV':>7} | {'avg R':>6}")
        for suffix, val in values:
            res = run_one(flag, val, suffix, ns)
            if res is None:
                continue
            h = parse_summary(res["dump"])
            avg_r = ""
            for e in res["extra"]:
                if e.startswith("  Summe R:"):
                    avg_r = e.split("avg R:")[1].split("|")[0].strip() if "avg R:" in e else ""
            wr = f"{h.get('wr', '?')}%" if "wr" in h else "?"
            wln = f"{h.get('w', '?')}/{h.get('l', '?')}/{h.get('n', '?')}"
            print(f"{val:>8} | {h.get('w',0)+h.get('l',0)+h.get('n',0):>7} | {wr:>4} | {wln:>10} "
                  f"| {h.get('sum_r', float('nan')):>+8.2f} | {h.get('avg_crv', float('nan')):>7.2f} | {avg_r:>6}")
        print()


if __name__ == "__main__":
    if "--summary-only" in sys.argv:
        summary_only()
    else:
        main()
