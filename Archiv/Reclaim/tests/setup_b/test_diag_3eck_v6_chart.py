# test/test_diag_3eck_v6_chart.py
"""CHART zur SEGMENTIERUNG v6 (3-Eckpunkte + 1.5%-Weite).

Zeigt den AKTUELLEN v6-Stand (01.09.2026) auf dem August-Fenster:
- Boxen B1/B2/B3 (Reife Phase = eigenes Segment, nicht-reife Phase = Arm)
- Reife-Zeitpunkt je Box (gestrichelte vertikale Linie)
- Finale Volume-Zone je Box (U_zone gruen / L_zone rot / POC orange,
  wie im Hauptskript: Berechnung ueber die ganze Box, nur fuer die Grafik)
- Setup-B-Signale auf der laufenden Zone (kausal, WIN/LOSS markiert)
- Statistik-Box je Box + Gesamt (identische Zahlen wie test_diag_3eck_v6.py)

Aufruf: python test/test_diag_3eck_v6_chart.py
Ausgabe: test/diag_3eck_v6_chart.png
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "tmp_phasen_volumen_profil.py"
OUT_PNG = Path(__file__).resolve().parent / "diag_3eck_v6_chart.png"

src = SRC.read_text(encoding="utf-8")
cut = src.index("reclaim_signals = []")
ns = {"__file__": str(SRC), "__name__": "test_diag_3eck_v6_chart"}
exec(compile(src[:cut], str(SRC), "exec"), ns)

df = ns["df"]
phases = ns["phases"]
piv = ns["piv"]
_laufende_zone = ns["_laufende_zone"]
_bounce_nr = ns["_bounce_nr"]
_aufloesen = ns["_aufloesen"]
compute_volume_zone = ns["compute_volume_zone"]
level_schnittmenge = ns["level_schnittmenge"]
pd = ns["pd"]
np = ns["np"]

TOL_KANTE = 0.30       # gleiche Kante: |H1-H2| bzw. |L1-L2| <= TOL_KANTE
MIN_WEITE_PCT = 1.5    # min. Weite in %


def reife_check(P, tol_kante=TOL_KANTE, min_weite_pct=MIN_WEITE_PCT):
    """3-Eckpunkte direkt aus den PIVOTS (H-L-H oder L-H-L).
    Rueckgabe: (reif, t_reif, tripel)"""
    h_prices = P.get("h_prices", P.get("h", []))
    h_ts = P.get("h_ts", [])
    l_prices = P.get("l_prices", P.get("l", []))
    l_ts = P.get("l_ts", [])
    events = sorted([(t, "H", float(p)) for p, t in zip(h_prices, h_ts)] +
                    [(t, "L", float(p)) for p, t in zip(l_prices, l_ts)])
    for i in range(len(events) - 2):
        t1, typ1, p1 = events[i]
        t2, typ2, p2 = events[i + 1]
        t3, typ3, p3 = events[i + 2]
        if typ1 == typ2 or typ2 == typ3:
            continue
        if typ1 != typ3:
            continue
        if abs(p1 - p3) > tol_kante:
            continue
        weite = abs(p2 - p1) / min(p1, p2) * 100.0
        if weite >= min_weite_pct:
            return True, t3, (typ1, p1, typ2, p2, typ3, p3)
    return False, None, None


def find_signals_box(ns, box):
    """Setup B an der laufenden Volume-Zone der Box (kausal ab i_start)."""
    df = ns["df"]
    p = {"i_start": box["i_start"], "i_ende": box["i_ende"],
         "h_prices": box["h"], "h_ts": box["h_ts"],
         "l_prices": box["l"], "l_ts": box["l_ts"]}
    sigs = []
    hi, lo, cl, op = (df["high"].values, df["low"].values,
                      df["close"].values, df["open"].values)
    ts = df["ts"].values
    last_bar = {"SHORT": -10 ** 9, "LONG": -10 ** 9}
    for k in range(box["i_start"], box["i_ende"]):
        vz = _laufende_zone(df, p, k)
        if vz is None:
            continue
        U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
        ts_k = ts[k]
        nb_h, nb_l = _bounce_nr(box["h"], box["h_ts"], box["l"], box["l_ts"],
                                ts_k, U, L)
        if hi[k] > U:
            if cl[k] <= U:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] <= U:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis > POC
                    and nb_h >= ns["MIN_RECLAIM_BOUNCE"]
                    and k - last_bar["SHORT"] >= ns["MIN_SIGNAL_ABSTAND_BARS"]):
                sl = e_preis * (1 + ns["SL_PCT"] / 100.0)
                tp1 = POC
                tp2 = L * (1 + ns["TP2_PUFFER_PCT"] / 100.0)
                crv = abs(tp1 - e_preis) / abs(sl - e_preis) if sl != e_preis else 0
                if crv >= ns["MIN_RECLAIM_CRV"]:
                    last_bar["SHORT"] = k
                    s = {"typ": "SHORT", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U,
                         "L_laufend": L, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_h}
                    s.update(_aufloesen(df, s))
                    sigs.append(s)
        if lo[k] < L:
            if cl[k] >= L:
                e_bar, e_preis, rec = k + 1, float(op[k + 1]), "in_bar"
            elif k + 2 <= box["i_ende"] and cl[k + 1] >= L:
                e_bar, e_preis, rec = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, rec = None, None
            if (rec is not None and e_bar <= box["i_ende"] and e_preis < POC
                    and nb_l >= ns["MIN_RECLAIM_BOUNCE"]
                    and k - last_bar["LONG"] >= ns["MIN_SIGNAL_ABSTAND_BARS"]):
                sl = e_preis * (1 - ns["SL_PCT"] / 100.0)
                tp1 = POC
                tp2 = U * (1 - ns["TP2_PUFFER_PCT"] / 100.0)
                crv = abs(tp1 - e_preis) / abs(sl - e_preis) if sl != e_preis else 0
                if crv >= ns["MIN_RECLAIM_CRV"]:
                    last_bar["LONG"] = k
                    s = {"typ": "LONG", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                         "reclaim": rec, "einstieg_bar": int(e_bar),
                         "einstieg_preis": e_preis, "U_laufend": U,
                         "L_laufend": L, "POC": POC, "tp1": tp1, "tp2": tp2,
                         "sl": sl, "crv": crv, "bounce_nr": nb_l}
                    s.update(_aufloesen(df, s))
                    sigs.append(s)
    return sigs


print("=== SEGMENTIERUNG v6: 3-ECKPUNKTE (H-L-H/L-H-L) + 1.5%-WEITE (CHART) ===")

# 1) Reife je Phase
reif_info = []
for i, P in enumerate(phases, 1):
    reif, t_reif, tripel = reife_check(P)
    tr = f"{t_reif:%d.%m %H:%M}" if t_reif is not None else "-"
    print(f"  P{i}: {'REIF' if reif else 'nicht reif':<11} {tr}")
    reif_info.append((P, reif, t_reif))

# 2) Boxen (Verschmelzung): reif = eigenes Segment, sonst Arm
boxen = []
aktive = None
for i, (P, reif, t_reif) in enumerate(reif_info):
    if reif:
        if aktive is not None:
            boxen.append(aktive)
        aktive = {"i_start": P["i_start"], "i_ende": P["i_ende"],
                  "phasen": [i + 1], "reif": True, "t_reif": t_reif,
                  "h": list(P["h_prices"]), "h_ts": list(P["h_ts"]),
                  "l": list(P["l_prices"]), "l_ts": list(P["l_ts"]),
                  "start": P["start"], "ende": P["ende"]}
    else:
        if aktive is None:
            aktive = {"i_start": P["i_start"], "i_ende": P["i_ende"],
                      "phasen": [i + 1], "reif": False, "t_reif": None,
                      "h": list(P["h_prices"]), "h_ts": list(P["h_ts"]),
                      "l": list(P["l_prices"]), "l_ts": list(P["l_ts"]),
                      "start": P["start"], "ende": P["ende"]}
        else:
            aktive["i_ende"] = P["i_ende"]
            aktive["ende"] = P["ende"]
            aktive["phasen"].append(i + 1)
            aktive["h"].extend(P["h_prices"])
            aktive["h_ts"].extend(P["h_ts"])
            aktive["l"].extend(P["l_prices"])
            aktive["l_ts"].extend(P["l_ts"])
boxen.append(aktive)

# 3) Signale je Box + finale Volume-Zone je Box (nur fuer die Grafik)
alle = []
for bi, b in enumerate(boxen, 1):
    b["sigs"] = find_signals_box(ns, b)
    b["vol_zone"] = compute_volume_zone(
        df.iloc[b["i_start"]:b["i_ende"] + 1])
    w = sum(1 for s in b["sigs"] if s["resultat"] == "GEWONNEN")
    l = sum(1 for s in b["sigs"] if s["resultat"] == "VERLOREN")
    r = sum(s["r_mult"] for s in b["sigs"])
    ph = "+".join(f"P{p}" for p in b["phasen"])
    b["n_w"], b["n_l"], b["sum_r"] = w, l, r
    print(f"  B{bi} ({b['start']:%d.%m %H:%M}-{b['ende']:%d.%m %H:%M}) Phasen {ph}: "
          f"{len(b['sigs']):2d} Sig | {100.0*w/(w+l) if w+l else 0:.0f}% | {r:+8.2f}R")
    for s in b["sigs"]:
        s["box"] = bi
        alle.append(s)

w = sum(1 for s in alle if s["resultat"] == "GEWONNEN")
l = sum(1 for s in alle if s["resultat"] == "VERLOREN")
r = sum(s["r_mult"] for s in alle)
print(f"  GESAMT v6: {len(alle):2d} Sig | {w}W/{l}L | "
      f"{100.0*w/(w+l) if w+l else 0:.0f}% | {r:+8.2f}R")

# ---------- 4) Chart ----------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

fig, ax = plt.subplots(figsize=(17, 9))
idx = df["idx"].values
ax.plot(idx, df["high"], color="#bbb", lw=0.5)
ax.plot(idx, df["low"], color="#bbb", lw=0.5)

box_colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

for bi, b in enumerate(boxen):
    c = box_colors[bi % len(box_colors)]
    ax.axvspan(b["i_start"], b["i_ende"], color=c, alpha=0.08)

    # Box-Label (Name + Phasen + Reife-Status)
    ph = "+".join(f"P{p}" for p in b["phasen"])
    status = f"REIF ab {b['t_reif']:%d.%m %H:%M}" if b.get("t_reif") is not None else "ARM-SAMMLUNG"
    ax.text((b["i_start"] + b["i_ende"]) / 2, ax.get_ylim()[1], f"B{bi} ({ph}) - {status}",
            fontsize=9, color=c, ha="center", va="bottom", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.7))

    # Reife-Zeitpunkt (gestrichelte vertikale Linie)
    if b.get("t_reif") is not None:
        m = df["idx"][df["ts"] == b["t_reif"]]
        if len(m):
            ax.axvline(int(m.iloc[0]), color=c, lw=1.4, ls="--", alpha=0.7)

    # ALTE Phasen-Zonen (VAH/VAL/POC je Baseline-Phase) als gestrichelte Linien
    # -> zeigt die urspruengliche Segmentierung gegen die neue Box-Zone
    for pi in b["phasen"]:
        P = phases[pi - 1]
        vz = P.get("vol_zone")
        if vz is None:
            continue
        # VAH je Phase (grau gestrichelt)
        ax.hlines(vz["U_zone"], P["i_start"], P["i_ende"],
                  color="0.40", lw=1.3, ls="--", alpha=0.9, zorder=3)
        ax.text(P["i_start"] + 2, vz["U_zone"] + 0.06, f"P{pi} VAH {vz['U_zone']:.2f}",
                fontsize=6.5, color="0.40", va="bottom", fontweight="bold", zorder=5)
        # VAL je Phase (grau gestrichelt)
        ax.hlines(vz["L_zone"], P["i_start"], P["i_ende"],
                  color="0.40", lw=1.3, ls="--", alpha=0.9, zorder=3)
        ax.text(P["i_start"] + 2, vz["L_zone"] - 0.06, f"P{pi} VAL {vz['L_zone']:.2f}",
                fontsize=6.5, color="0.40", va="top", fontweight="bold", zorder=5)
        # POC je Phase (hellgrau strich-punkt)
        ax.hlines(vz["POC"], P["i_start"], P["i_ende"],
                  color="0.60", lw=1.0, ls="-.", alpha=0.8, zorder=3)

    # Finale Volume-Zone der Box (U/L/POC ueber die ganze Box, fuer die Grafik)
    vz = b.get("vol_zone")
    if vz is not None:
        ax.hlines(vz["U_zone"], b["i_start"], b["i_ende"], color="#1a7d1a", lw=2.4, alpha=0.95, zorder=4)
        ax.hlines(vz["L_zone"], b["i_start"], b["i_ende"], color="#c00000", lw=2.4, alpha=0.95, zorder=4)
        ax.hlines(vz["POC"], b["i_start"], b["i_ende"], color="#e07b00", lw=1.8, ls="-.", zorder=4)
        ax.text(b["i_start"] + 2, vz["U_zone"] + 0.10, f"OBEN(VAH) {vz['U_zone']:.2f}",
                fontsize=8, color="#1a7d1a", fontweight="bold", va="bottom")
        ax.text(b["i_start"] + 2, vz["L_zone"] - 0.10, f"UNTEN(VAL) {vz['L_zone']:.2f}",
                fontsize=8, color="#c00000", fontweight="bold", va="top")
        ax.text(b["i_start"] + 2, vz["POC"] + 0.10, f"POC {vz['POC']:.2f}",
                fontsize=8, color="#e07b00", fontweight="bold", va="bottom")

    # Setup-B-Signale der Box (auf der laufenden Zone berechnet)
    for s in b["sigs"]:
        x = s["bar"]
        if s["typ"] == "SHORT":
            y = float(df["high"].iloc[x])
            ax.scatter(x, y, marker="v", s=85, color="#c00000", zorder=6,
                       edgecolor="w", linewidths=0.5)
            txt = f"S {s['einstieg_preis']:.2f} Bo{s['bounce_nr']} {s['r_mult']:+.2f}R"
        else:
            y = float(df["low"].iloc[x])
            ax.scatter(x, y, marker="^", s=85, color="#1a7d1a", zorder=6,
                       edgecolor="w", linewidths=0.5)
            txt = f"L {s['einstieg_preis']:.2f} Bo{s['bounce_nr']} {s['r_mult']:+.2f}R"
        if s["resultat"] == "GEWONNEN":
            txt += " WIN"
        elif s["resultat"] == "VERLOREN":
            txt += " LOSS"
        ax.annotate(txt, (x, y),
                    xytext=(x, y + (0.45 if s["typ"] == "SHORT" else -0.45)),
                    fontsize=7.5, ha="center",
                    color="#c00000" if s["typ"] == "SHORT" else "#1a7d1a",
                    fontweight="bold")

step = max(8, len(df) // 16)
ticks = np.arange(0, len(df), step)
ax.set_xticks(ticks)
ax.set_xticklabels([df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks],
                   rotation=45, ha="right", fontsize=8)
ax.set_xlim(-1, len(df))
ax.set_title("SILVER M15 10.08-27.08.2026 - SEGMENTIERUNG v6 (3-Eckpunkte+1.5%): "
             "B1 Arm-Sammlung | B2 REIF 11.08 | B3 REIF 24.08 - Volume-Zonen + Setup B",
             fontsize=11)
ax.set_ylabel("USD")
ax.grid(alpha=0.3)

legend_elements = [
    Line2D([0], [0], color="#1a7d1a", lw=2.4, label="Box-Zone OBEN (VAH, solid)"),
    Line2D([0], [0], color="#c00000", lw=2.4, label="Box-Zone UNTEN (VAL, solid)"),
    Line2D([0], [0], color="#e07b00", lw=1.8, ls="-.", label="Box-Zone MITTE (POC)"),
    Line2D([0], [0], color="0.40", lw=1.3, ls="--", label="alte Phasen-VAH/VAL (P1-P12, gestrichelt)"),
    Line2D([0], [0], color="0.60", lw=1.0, ls="-.", label="alte Phasen-POC"),
    Line2D([0], [0], color="gray", lw=1.4, ls="--", label="Reife-Zeitpunkt (3. Eckpunkt)"),
    Line2D([0], [0], marker="v", color="w", markerfacecolor="#c00000", ms=8,
           label="Setup B: Reclaim SHORT (laufende Zone)"),
    Line2D([0], [0], marker="^", color="w", markerfacecolor="#1a7d1a", ms=8,
           label="Setup B: Reclaim LONG (laufende Zone)"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=8, framealpha=0.9)

# Statistik-Box
_stat_lines = [f"v6 GESAMT (10.08-27.08):",
               f"Signale: {len(alle)} | {w}W/{l}L | {100.0*w/(w+l) if w+l else 0:.0f}% WR",
               f"Summe R: {r:+.2f} | avg R: {r/len(alle) if alle else 0:+.2f}"]
for bi, b in enumerate(boxen):
    ph = "+".join(f"P{p}" for p in b["phasen"])
    _w, _l, _r = b["n_w"], b["n_l"], b["sum_r"]
    _wr = 100.0 * _w / (_w + _l) if (_w + _l) else 0.0
    _stat_lines.append(f"B{bi} ({ph}): {len(b['sigs']):2d} Sig | {_wr:.0f}% | {_r:+.2f}R")
ax.text(0.30, 0.985, "\n".join(_stat_lines), transform=ax.transAxes,
        fontsize=8, va="top", ha="left", family="monospace",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#fdf6e3",
                  edgecolor="gray", alpha=0.95))

fig.tight_layout()
fig.savefig(OUT_PNG, dpi=130)
print(f"\nChart gespeichert: {OUT_PNG}")
