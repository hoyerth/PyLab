# -*- coding: utf-8 -*-
"""READ-ONLY Rendering: Kanal-1-Haertung (B1) im EXT-Fenster (Aug-Sep).

Zweck
-----
Visuelle Bestaetigung der S2-Sonde (H20.43 Abschnitt 9 / H20.44):
Warum scheiterte K45 an Bar 680 (0.002-USD-Stopout) und warum sitzt der
Einstieg an Bar 679 (STUFE_2_KERZE_2, +6.480880 R) geometrisch sauber?

Darstellung
-----------
* Kerzen im EXT-Fenster (03.08.-12.09.), AUG-Fenster per Zeitstempel-Assert
  exakt eingebettet (kein Geister-Mapping).
* NUR handlungsrelevante Kanten (Setup-Kids + eliminierte Kids) -- keine
  Tapete mit allen 73 Linien.
* Gruene/rote Trade-Kreise (mfc=col) fuer die 30 B1-Trades, vertikale
  SL-TP2-Range, Label ``K<kid> <preis>`` (kausaler Preis, kein TP1-Horizont).
* Rotes X (#b00000) an ``bar`` (Setup-Bar) der 4 eliminierten Verluste.

ADDITIV -- Engine/Renderer/Adapter bleiben byte-identisch (SHA-Guard).

Reuse (keine Neuerfindung)
--------------------------
* Geometrie/Kerzen/Kanten/Touches : test/tmp_png_ext_sichttest_v2.py
* B1-/B0-Setups + Trade-Delta     : test/_chk_s2_sonde.py

Aufruf:
    .venv\\Scripts\\python.exe test\\_render_aug_sep_b1.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

V020_PFAD = ROOT / "test" / "tmp_kanten_engine_v020_replay.py"
BASELINE_PFAD = ROOT / "test" / "tmp_kanten_engine_replay.py"
ADAPTER_PFAD = ROOT / "backtest_lab" / "phasen_regime_adapter.py"
SONDE_PFAD = ROOT / "test" / "_chk_s2_sonde.py"
EXT_REND_PFAD = ROOT / "test" / "tmp_png_ext_sichttest_v2.py"

V020_SHA_SOLL = (
    "e79c5c29482398d8237469a79a234c7200f8718e840252cc33d2bea37f3865af")
BASELINE_SHA_SOLL = (
    "53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006")
ADAPTER_SHA_SOLL = (
    "770eda2c75aaa135961ef0d235d850759678de62cd9e00e3b5db110c8ed28f14")

FENSTER_AUG = "AUG"
FENSTER_EXT = "EXT"
EXT_VON, EXT_BIS = "2026-08-03", "2026-09-12"
AUG_N = 1288
AUG_BOX_NATIV = 644
NAHT_VON, NAHT_BIS = 630, 770

B1_SOLL_N, B1_SOLL_R = 30, 67.030055

C_UP, C_DN = "#3d8f6d", "#c05656"
C_LONG, C_SHORT = "#2ca02c", "#d62728"
C_ELIM = "#b00000"
C_SPERR = "#8e44ad"
C_KANTE = "#7f7f7f"
C_TOUCH_OBEN, C_TOUCH_UNTEN = "#8b0000", "#004d00"

OUT_UEBERSICHT = ROOT / "test" / "render_aug_sep_b1_uebersicht.png"
OUT_NAHT = ROOT / "test" / "render_aug_sep_b1_nahtstelle.png"
OUT_PROTOKOLL = ROOT / "test" / "render_aug_sep_b1_out.txt"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _assert_shas() -> None:
    """Arretierung: Engine/Baseline/Adapter muessen byte-identisch sein."""
    for p, soll in ((V020_PFAD, V020_SHA_SOLL),
                    (BASELINE_PFAD, BASELINE_SHA_SOLL),
                    (ADAPTER_PFAD, ADAPTER_SHA_SOLL)):
        ist = _sha(p)
        assert ist == soll, (
            f"Fremdstand {p.name}: {ist[:16]}... != {soll[:16]}...")


class _StdoutStub:
    """Minimaler stdout-Ersatz fuer den Modul-Import (kein echter fd).

    ``_chk_s2_sonde`` und ``tmp_png_ext_sichttest_v2`` haengen beim Import
    ``sys.stdout`` auf einen ``io.TextIOWrapper(sys.stdout.buffer)`` um. Auf
    dem ECHTEN stdout wuerde der GC dieses Wrappers den Puffer schliessen
    (ValueError: I/O operation on closed file). Der Stub liefert einen
    wegwerfbaren ``BytesIO``-Puffer -- Import-Nebenwirkungen bleiben lokal.
    """

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass


def _lade(name: str, p: Path) -> Any:
    """Modul laden, ohne den echten stdout zu beschaedigen."""
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


class _OffKante:
    """Kanten-Shim: verschiebt nur die Docht-Bars um ``off`` (EXT-Universum).

    ``_edge_profil``/``_zeichne_kanten``/``_zeichne_touches`` lesen die
    Bar-Indizes direkt aus ``e.wicks`` (AUG-Katalog). Auf dem EXT-Gitter
    muessen sie um den Offset verschoben werden; alles andere delegiert.
    """

    __slots__ = ("_e", "_off", "wicks")

    def __init__(self, e: Any, off: int) -> None:
        self._e = e
        self._off = int(off)
        self.wicks = [(int(b) + self._off, float(p)) for b, p in e.wicks]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._e, name)


def _b1_und_kontrast() -> Tuple[Any, Any, Dict[str, Any], Any, Any, List, List]:
    """Rekonstruiert B0/B1 aus der Sonde (1:1 zum Sondenlauf)."""
    v020 = _lade("v020_b1rend", V020_PFAD)
    sonde = _lade("sonde_b1rend", SONDE_PFAD)
    B = v020.baseline()
    cfg = B.StraightEdgeHarnessKonfiguration()
    kcfg = v020.V020KantenKonfiguration()
    from backtest_lab.phasen_regime_adapter import ADAPTER_V019_KAUSAL

    scan = B._se_scan(FENSTER_AUG, cfg)
    assert int(scan["n"]) == AUG_N and int(scan["box_end_bar"]) == AUG_BOX_NATIV
    scan["box_end_bar"] = AUG_N

    b0 = sonde._rekonstruiere(B, cfg, v020, kcfg, copy.deepcopy(scan),
                              ADAPTER_V019_KAUSAL, ADAPTER_V019_KAUSAL,
                              False, "B0", False)
    b1 = sonde._rekonstruiere(B, cfg, v020, kcfg, copy.deepcopy(scan),
                              ADAPTER_V019_KAUSAL, ADAPTER_V019_KAUSAL,
                              True, "B1", False)
    ist = (len(b1.setups), round(sum(x.r for x in b1.setups), 6))
    assert ist == (B1_SOLL_N, B1_SOLL_R), f"B1-Anker verletzt: {ist}"
    nr, na, _gem = sonde._diff(b0.setups, b1.setups)
    return B, cfg, scan, b0, b1, nr, na


def _offset_ext(scan_ext: Dict[str, Any], scan_aug: Dict[str, Any]) -> int:
    """Harter Beweis der Bar-Gitter-Identitaet AUG -> EXT (kein Fallback)."""
    ts_e = scan_ext["d"]["ts"].to_numpy().astype("datetime64[ns]")
    ts_a = scan_aug["d"]["ts"].to_numpy().astype("datetime64[ns]")
    i = int(np.searchsorted(ts_e, ts_a[0]))
    assert i < len(ts_e) and ts_e[i] == ts_a[0], "EXT kennt AUG-Start nicht"
    assert i + len(ts_a) <= len(ts_e), "EXT zu kurz fuer das AUG-Fenster"
    assert bool(np.array_equal(ts_e[i:i + len(ts_a)], ts_a)), (
        "Bar-Gitter AUG != EXT -- Mapping ungueltig (ABBRUCH)")
    return i


def _kanten_gefiltert(scan: Dict[str, Any], kids: Sequence[int]) -> List[Any]:
    """NUR Kanten mit Handlung (Setup-Kids + eliminierte Kids)."""
    ks = {int(k) for k in kids}
    alle = list(scan["edges"]) + list(scan["seeds"])
    return [e for e in alle if int(e.kid) in ks]


def _marker_b1(ax: Any, setups: Sequence[Any], off: int) -> None:
    """LONG/SHORT-Kreise (mfc=col), SL-TP2-Range, Label K<kid> <entry>."""
    for t in setups:
        x = int(t.entry_bar) + off
        col = C_SHORT if str(t.richtung) == "SHORT" else C_LONG
        ax.plot([x, x], [float(t.sl), float(t.tp2)], color=col, lw=1.2,
                alpha=0.55, ls=":", zorder=6)
        ax.plot(x, float(t.entry), "o", ms=10.0, color=col, mec="#1a1a1a",
                mew=0.9, mfc=col, zorder=12)
        ax.annotate(f"K{t.kid} {float(t.entry):.4f}\n{float(t.r):+.2f}R "
                    f"sig {int(t.bar)}", (x, float(t.entry)),
                    textcoords="offset points", xytext=(0, 20), ha="center",
                    fontsize=8.0, color=col, zorder=11,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              alpha=0.88, ec=col, lw=0.6))


def _marker_eliminiert(ax: Any, setups: Sequence[Any], off: int) -> None:
    """Rotes X an ``bar`` (Setup-Bar) der eliminierten Verlust-Trades."""
    for t in setups:
        x = int(t.bar) + off
        ax.plot(x, float(t.basis), "X", ms=13.0, color=C_ELIM, mec="black",
                mew=0.7, zorder=13)
        ax.annotate(f"ELIM K{t.kid} {float(t.r):+.2f}R\nbar {int(t.bar)}",
                    (x, float(t.basis)), textcoords="offset points",
                    xytext=(0, -30), ha="center", fontsize=7.5, color=C_ELIM,
                    zorder=13,
                    bbox=dict(boxstyle="round,pad=0.18", fc="#fff0f0",
                              alpha=0.9, ec=C_ELIM, lw=0.5))


def main() -> None:
    """Erzeugt Uebersicht + Nahtstellen-Zoom + Protokoll (headless Agg)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    _assert_shas()
    ext = _lade("extrend_b1", EXT_REND_PFAD)
    B, cfg, scan_aug, b0, b1, elim, neu = _b1_und_kontrast()

    B.FENSTER[FENSTER_EXT] = (EXT_VON, EXT_BIS)          # type: ignore
    scan = B._se_scan(FENSTER_EXT, cfg)                  # type: ignore
    off = _offset_ext(scan, scan_aug)
    n = int(scan["n"])

    d = scan["d"]
    idx = np.arange(n)
    op = d["open"].to_numpy(dtype=float)
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    wall = int(cfg.wall_live_bars)
    y0, y1 = float(lo.min()), float(hi.max())

    kids = [int(t.kid) for t in b1.setups] + [int(t.kid) for t in elim]
    kanten = [_OffKante(e, off) for e in _kanten_gefiltert(scan_aug, kids)]

    b0_r = sum(float(x.r) for x in b0.setups)
    b1_r = sum(float(x.r) for x in b1.setups)
    zeilen: List[str] = [
        f"RENDER B1 | Universum=EXT n={n} | AUG-Ursprung Bar {off} "
        f"(= Box-Naht 1104 - 644)",
        f"B1: {len(b1.setups)} Trades / {b1_r:+.6f} R",
        f"B0: {len(b0.setups)} Trades / {b0_r:+.6f} R",
        f"ELIMINIERT {len(elim)} ({sum(float(x.r) for x in elim):+.6f} R) | "
        f"NEU {len(neu)} ({sum(float(x.r) for x in neu):+.6f} R)",
        "ELIM: " + " | ".join(
            f"K{int(x.kid)}@bar{int(x.bar)} {float(x.r):+.6f}"
            for x in sorted(elim, key=lambda y: (y.bar, y.kid))),
        "NEU: " + " | ".join(
            f"K{int(x.kid)}@bar{int(x.bar)} {float(x.r):+.6f}"
            for x in sorted(neu, key=lambda y: (y.bar, y.kid))),
        "Kanten gezeichnet: " + ",".join(
            f"K{int(e.kid)}" for e in sorted(kanten, key=lambda x: int(x.kid))),
        f"Nahtstelle: sig/entry 679->681 (K45 NEU) vs elim 680->681 (K45 alt)",
    ]

    def _panel(ax: Any, x0: int, x1: int) -> None:
        ext._zeichne_kerzen(ax, x0, x1, idx, op, hi, lo, cl, breite=0.60)
        ext._zeichne_kanten(ax, kanten, n, wall, mit_historie=False, lw=1.5)
        ext._zeichne_touches(ax, kanten, ms=8.0)
        _marker_b1(ax, b1.setups, off)
        _marker_eliminiert(ax, elim, off)

    fig, ax = plt.subplots(figsize=(34, 13))
    _panel(ax, 0, n - 1)
    ax.set_xlim(-5, n + 5)
    ax.set_ylim(y0, y1)
    ticks = np.linspace(0, n - 1, 16).astype(int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in ticks],
                       fontsize=9, rotation=0)
    ax.grid(alpha=0.22)
    ax.axvline(off, color="black", lw=1.2, ls=":", alpha=0.85)
    ax.text(off + 3, y1, "AUG-Ursprung (10.08.)", fontsize=10, rotation=90,
            va="top", ha="left", color="#b35c00", weight="bold", zorder=14)
    ax.axvspan(off, off + AUG_N, facecolor="gray", alpha=0.05, zorder=0)
    ax.set_title(
        f"B1 Kanal-1-Haertung im EXT-Fenster (03.08.-12.09., Bars 0..{n-1}) | "
        f"{len(b1.setups)} Trades {b1_r:+.4f} R | AUG-Fenster ab Bar {off} | "
        f"{len(elim)} eliminiert", fontsize=15)
    ax.legend(handles=[
        Line2D([0], [0], marker="o", color="w", mfc=C_LONG, ms=10,
               label="LONG B1"),
        Line2D([0], [0], marker="o", color="w", mfc=C_SHORT, ms=10,
               label="SHORT B1"),
        Line2D([0], [0], marker="X", color="w", mfc=C_ELIM, ms=12,
               label="ELIMINIERT (Bar)"),
        Line2D([0], [0], color=C_KANTE, lw=1.5,
               label="handlungsrelevante Kante"),
        Line2D([0], [0], marker="^", color="w", mfc=C_TOUCH_OBEN, ms=8,
               label="Touch OBEN"),
        Line2D([0], [0], marker="v", color="w", mfc=C_TOUCH_UNTEN, ms=8,
               label="Touch UNTEN"),
    ], loc="upper left", fontsize=11, framealpha=0.92)
    fig.subplots_adjust(left=0.030, right=0.997, top=0.940, bottom=0.050)
    fig.savefig(OUT_UEBERSICHT, dpi=300)
    plt.close(fig)

    x0 = max(0, NAHT_VON + off)
    x1 = min(n - 1, NAHT_BIS + off)
    zy0 = float(lo[x0:x1 + 1].min())
    zy1 = float(hi[x0:x1 + 1].max())
    pad = (zy1 - zy0) * 0.10
    figz, axz = plt.subplots(figsize=(26, 12))
    _panel(axz, x0, x1)
    axz.set_xlim(x0 - 1, x1 + 1)
    axz.set_ylim(zy0 - pad, zy1 + pad)
    axz.grid(alpha=0.25)
    axz.axvline(679 + off, color=C_SPERR, lw=1.4, ls="--", alpha=0.85)
    axz.axvline(680 + off, color=C_ELIM, lw=1.4, ls="--", alpha=0.85)
    axz.text(679 + off, zy1 + pad, " Bar 679 (K45 NEU +6.480880)",
             fontsize=10, color="#6c3483", va="top", ha="left",
             weight="bold", zorder=15)
    axz.text(680 + off, zy1 + pad, " Bar 680 (K45 alt -1.000000)",
             fontsize=10, color=C_ELIM, va="top", ha="left",
             weight="bold", zorder=15)
    _tz = np.linspace(x0, x1, 12).astype(int)
    axz.set_xticks(_tz)
    axz.set_xticklabels([str(np.datetime64(ts[i], "D")) for i in _tz],
                        fontsize=10)
    axz.set_title(
        "Nahtstelle Bar 679/680 -- K45 NEU (+6.480880, STUFE_2) vs. "
        "eliminiert (-1.000000, STUFE_1) | K48 kein Blocker (0.9169 % > "
        "0.75 %)", fontsize=14)
    figz.subplots_adjust(left=0.050, right=0.995, top=0.930, bottom=0.070)
    figz.savefig(OUT_NAHT, dpi=200)
    plt.close(figz)

    OUT_PROTOKOLL.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    for z in zeilen:
        print(z)
    print(f"\nPNG: {OUT_UEBERSICHT}")
    print(f"PNG: {OUT_NAHT}")
    print(f"TXT: {OUT_PROTOKOLL}")


if __name__ == "__main__":
    _fehler = False
    try:
        main()
    except BaseException as exc:                    # noqa: BLE001
        _fehler = True
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        OUT_PROTOKOLL.write_text(
            f"ABBRUCH: {type(exc).__name__}: {exc}\n\n{tb}", encoding="utf-8")
    print(f"\nFehler={_fehler}")
