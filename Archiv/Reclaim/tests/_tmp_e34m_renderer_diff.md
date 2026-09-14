# E-34m — Text-Diff-Gutachten: Renderer-Modus `"V019"` (`test/tmp_png_aug_sichttest.py`)

**Status:** ENTWURF, rein deskriptiv. **Kein Schreibzugriff.**
**Ziel-Datei (unberuehrt):** `test/tmp_png_aug_sichttest.py` — 97.160 B / 2.075 Z.
**Adapter (arretiert):** `backtest_lab/phasen_regime_adapter.py`
SHA `4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83` (Commit `68ac3af`).
**Engine (unberuehrt):** `test/tmp_kanten_engine_replay.py`
SHA `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`.
**Vorbedingung:** Commit `8b7886d` (E-34i), Handoff-SHA `f0871a28…`.

---

## A · Warum mehr als 9 Zeilen — und warum zweistufig gegatet

Messung E-34i: `ADAPTER_V019` allein → **V018** (17 / +65.835576, ZIEL 0).
Erst das **Zielzonen-Patchset ZP-4** (`A_UEB1`, `A_VC`, `A_M6L`, `A_SB` +
`_zv`/`_ueb` + `_reclaim_stufe`-Wrapper) liefert V019 (**23 / +82.614385**).

**Zweistufiges Gating (Pflicht, E-34i §W4):**

| Stufe | Diskriminator | Zweck |
|---|---|---|
| **Quelltext** | `KONF.mode == "V019"` | ZP-4 nur in den `_se_trades`-Quelltext einweben → V01..V018 **byte-identisch** |
| **Laufzeit** | **gebundener Adapter** (`len(ns["_hook"].segmente) > 1`) | `_zv(k)` darf im V019-Lauf **nicht** auch `V0`/`V1_basis` (DEFAULT, 1 Segment) erfassen |

Ein **globaler** Gate `mode == "V019"` waere fuer alle drei `_lauf`-Aufrufe wahr
und damit strukturell zu grob (Erratum E-34i §W4).

---

## B · Der Diff (Hunks)

### H1 — Docstring (ergaenzend)

```python
   * ``KONFIGURATION_V018`` -- v0.23: S3-Zeitbasis-Kanon (Weg A). ...
+  * ``KONFIGURATION_V019`` -- v0.24: endogene Segmentbildung (E-34..E-34i).
+    Adapter A1/A2, dazu das Zielzonen-Patchset ZP-4 (A_UEB1/A_VC/A_M6L/A_SB),
+    strikt auf diesen Modus gegatet. Satz ``aug_sichttest_v019_01..05.png``,
+    Protokoll ``..._v019_out.txt``.
```

### H2 — Imports

```python
 from backtest_lab.phasen_regime_adapter import (  # noqa: E402
-    ADAPTER_V014, ADAPTER_V015, BASELINE_V01_H2_R, BENCHMARK_V014_DELTA_R,
+    ADAPTER_V014, ADAPTER_V015, ADAPTER_V019, BASELINE_V01_H2_R,
+    BENCHMARK_V014_DELTA_R,
     BENCHMARK_V014_GESAMT_R, BENCHMARK_V014_H2_R, DEFAULT_ADAPTER,
     K67_OVERRIDE_69_87, P9, P9_BODEN_RECLAIM, P12_RESERVE,
     QUARTETT_V014_BARS,
     Hook2ZielModus, PhasenRegimeAdapter,
 )
```

Zusaetzlich im Import-Block (fuer den `_reclaim_stufe`-Wrapper):

```python
 import ast
 import copy
+import dataclasses
 import hashlib
```

### H3 — `AdapterMode`

```python
-AdapterMode = Literal["V01", "V014", "V015", "V016", "V017", "V018"]
+AdapterMode = Literal["V01", "V014", "V015", "V016", "V017", "V018", "V019"]
```

### H4 — Neue `KONFIGURATION_V019` (nach V018)

```python
+# V019 = endogene Segmentbildung (E-34..E-34i). Eigener Praefix: die
+# arretierten Saetze V01..V018 bleiben unberuehrt. Engine-Generation =
+# V018-Engine (BKZ/UTC, box_end 644); zusaetzlich greift das Zielzonen-
+# Patchset ZP-4 (nur in diesem Modus).
+KONFIGURATION_V019: Final[RendererKonfiguration] = RendererKonfiguration(
+    mode="V019",
+    ausgabe_praefix="aug_sichttest_v019_",
+    protokoll_datei="test/tmp_png_aug_sichttest_v019_out.txt",
+    ziel_trades_gesamt=23,
+    ziel_r_gesamt=82.614385,
+    ziel_r_h1=38.919584,          # Invariante (bit-identisch V017/V018)
+    ziel_r_h2=43.694801,
+    ziel_p9_beitrag=23.435111,    # P9 arretiert, unveraendert
+    k67_override_aktiv=True,
+    niveau_override_wert=K67_OVERRIDE_69_87,
+    alt_trades_einblenden=True,
+    quartett_bars=QUARTETT_V014_BARS,
+    g4_aktiv=True,
+    auflagen_aktiv=True,
+    # --- Engine-Generation unveraendert (V018-Engine, BKZ/UTC) ------------
+    ziel_v0_r=42.450970,
+    ziel_v1_basis_trades=14,
+    ziel_v1_basis_r=47.815697,
+    ziel_h1_trades=8,
+    ziel_delta_rb=34.798688,      # = 82.614385 - 47.815697
+    # --- adapter-abhaengige Sollwerte (E-34i/3, MESSUNG) ------------------
+    neu_basis_soll=((903, 67), (980, 67), (981, 73), (1075, 62), (1122, 73),
+                    (1211, 76), (1268, 76), (1272, 73), (1280, 76)),
+    referenz_soll=((980, 73),),
+    quartett_r_soll=((903, 4.119775), (980, 9.987676), (981, 2.695488),
+                     (1020, 3.003157)),
+    quartett_r_summe_soll=19.806095,
+    niveauwechsel_gesamt=66,
+    niveauwechsel_baseline=205,
+)
```

### H5 — Registry

```python
 _KONFIGURATIONEN = {"V01": KONFIGURATION_V01, "V014": KONFIGURATION_V014,
                     "V015": KONFIGURATION_V015, "V016": KONFIGURATION_V016,
-                    "V017": KONFIGURATION_V017, "V018": KONFIGURATION_V018}
+                    "V017": KONFIGURATION_V017, "V018": KONFIGURATION_V018,
+                    "V019": KONFIGURATION_V019}
```

### H6 — Adapter-Wahl (V019-Zweig VOR der `g4_aktiv`-Kette)

```python
-adapter: PhasenRegimeAdapter = (ADAPTER_V015 if KONF.g4_aktiv
-                                else (ADAPTER_V014
-                                      if KONF.k67_override_aktiv
-                                      else DEFAULT_ADAPTER))
+adapter: PhasenRegimeAdapter = (
+    ADAPTER_V019 if KONF.mode == "V019"
+    else (ADAPTER_V015 if KONF.g4_aktiv
+          else (ADAPTER_V014 if KONF.k67_override_aktiv
+                else DEFAULT_ADAPTER)))
```

> Grund: V019 traegt ebenfalls `g4_aktiv=True`; ohne den ersten Zweig bindet
> die Bool-Kette faelschlich `ADAPTER_V015`.

### H7 — Generation-Flags

```python
 _V17: Final[bool] = KONF.mode == "V017"
 _V18: Final[bool] = KONF.mode == "V018"
-_NEU: Final[bool] = _V17 or _V18
+_V19: Final[bool] = KONF.mode == "V019"
+_NEU: Final[bool] = _V17 or _V18 or _V19
 # Versionskuerzel fuer Titel/Annotationen (V017 bzw. V018).
-_VTAG: Final[str] = "V018" if _V18 else "V017"
+_VTAG: Final[str] = "V019" if _V19 else ("V018" if _V18 else "V017")
 _VER_TEXT: Final[str] = (
-    "v0.18 (BKZ/UTC + Kanten-Extremum + M6-Heilung)" if _V18
+    "v0.24 (endogene Segmente A1/A2 + Zielzonen-Patchset ZP-4)" if _V19
+    else ("v0.18 (BKZ/UTC + Kanten-Extremum + M6-Heilung)" if _V18
     else ("v0.17 (Kanten-Extremum + M6-Heilung)" if _V17
           else ("v0.16 (G4 + A-1..A-4)" if _AUFL
                 else ("v0.15 G4" if KONF.g4_aktiv
                       else ("v0.14" if KONF.k67_override_aktiv
-                            else "v0.1")))))
+                            else "v0.1"))))))
```

### H8 — Engine-Guard (V019 nutzt die V018-Engine)

```python
 if KONF.mode == "V018" and box_end != 644:
     raise SystemExit(...)
+if KONF.mode == "V019" and box_end != 644:
+    raise SystemExit(
+        f"Modus V019 erfordert die V018-Engine (BKZ/UTC, box_end 644), "
+        f"geladen wurde box_end={box_end} ({ENGINE_NAME} "
+        f"{ENGINE_SHA[:16]}...).")
```

### H9 — Zielzonen-Patchset ZP-4 (dedizierte Hilfsfunktion)

Einfuegen **nach** der Konstruktion von `patched_src` (Z. ~642), **vor**
`ORIG = engine._se_trades`.

```python
# ------------------------------- Zielzonen-Patchset ZP-4 (nur Modus V019)
# Herkunft: test/_tmp_e34_auto.py (E-34..E-34i). Die vier Regeln sind
# KOPPLUNGSPHYSIK, kein Datensatz: ohne sie ist die Zielzone inert (ZIEL 0).
#
# ZWEISTUFIGES GATING:
#   (1) Quelltext: diese Funktion wird NUR bei mode == "V019" aufgerufen
#       -> V01..V018 behalten ihren Quelltext byte-identisch.
#   (2) Laufzeit: die injizierte ``_zv(k)`` prueft den GEBUNDENEN Adapter
#       (ns["_hook"]), nicht den Modus -> V0/V1_basis (DEFAULT_ADAPTER,
#       1 Segment) bleiben unberuehrt.
def _wende_zielzonen_patches_v019(src: str) -> str:
    """Wevt die vier Zielzonen-Engine-Regeln in den ``_se_trades``-Quelltext.

    Args:
        src: Quelltextsegment der Funktion ``_se_trades`` (bereits mit den
            13 Bestands-Patches des Renderers).

    Returns:
        Quelltext mit ZP-4 (Ueberdehnung, Quartil-Reset, M6-Schlaf-Filter,
        Sweep-Basis-Aktivierung).

    Raises:
        AssertionError: ein Anker kommt nicht genau einmal vor (Fail-Loud).
    """
    paare = (
        # (1) Ueberdehnungsschranke segment-lokal 0.80
        ("A_UEB1",
         "            if dist > cfg.max_sweep_ueberdehnung_pct:",
         "            if dist > _ueb(k):"),
        # (2) Quartil-Extremum ab Segmentstart statt global
        ("A_VC",
         "        ex_hi = float(np.max(hi[:k + 1]))\n"
         "        ex_lo = float(np.min(lo[:k + 1]))",
         "        _q0 = 0\n"
         "        if _zv(k):\n"
         "            _sq = _hook.aktive_phase_bei(k)\n"
         "            if _sq is not None:\n"
         "                _q0 = int(_sq.start_bar)\n"
         "        ex_hi = float(np.max(hi[_q0:k + 1]))\n"
         "        ex_lo = float(np.min(lo[_q0:k + 1]))"),
        # (3) M6-Blocker ueberspringt schlafende Linien in der Zone
        ("A_M6L",
         "            if e is kd or not _existiert(e, k):\n"
         "                continue",
         "            if e is kd or not _existiert(e, k) or (\n"
         "                    _zv(k) and not _lebt(e, k)):\n"
         "                continue"),
        # (4) gesweepte Linie zaehlt in der Zone als aktiv
        ("A_SB",
         "        if not e.ist_aktiv_bei(k):\n"
         "            return False\n"
         "        return e.erster_pivot_bar + 2 <= k + 1",
         "        if not e.ist_aktiv_bei(k):\n"
         "            _ev = ((hi[k] > e.basis_bei(k)) if e.seite == \"OBEN\"\n"
         "                   else (lo[k] < e.basis_bei(k)))\n"
         "            if not (_zv(k) and _ev):\n"
         "                return False\n"
         "        return e.erster_pivot_bar + 2 <= k + 1"),
    )
    for _nm, _alt, _neu in paare:
        assert src.count(_alt) == 1, (_nm, src.count(_alt))
        src = src.replace(_alt, _neu)
    return src


if KONF.mode == "V019":
    patched_src = _wende_zielzonen_patches_v019(patched_src)
```

### H10 — Laufzeit-Injektion `_zv` / `_ueb` / `_reclaim_stufe`

Direkt **nach** `ns = dict(engine.__dict__)` und `ns["_Hook2ZielModus"] = …`.

```python
 ns = dict(engine.__dict__)
 ns["_Hook2ZielModus"] = Hook2ZielModus
+
+# --- ZP-4 Laufzeit-Gate (nur wirksam, wenn der gebundene Adapter V019 ist)
+# Fenster aus dem Adapter abgeleitet - kein Bar-Literal.
+_ZZ_START: Final[int] = ADAPTER_V019.segmente[1].start_bar
+_ZZ_ENDE:  Final[int] = ADAPTER_V019.segmente[-1].end_bar
+_P9_START: Final[int] = ADAPTER_V019.segmente[0].start_bar
+_P9_ENDE:  Final[int] = ADAPTER_V019.segmente[0].end_bar
+
+
+def _zv(kk: int) -> bool:
+    """Zielzonen-Fenster -- NUR wenn der GEBUNDENE Adapter mehrsegments ist.
+
+    Damit schuetzt das Gate die drei Laeufe desselben Prozesses: V0 und
+    V1_basis (DEFAULT_ADAPTER, 1 Segment) bleiben unberuehrt, nur V1_aktiv
+    (ADAPTER_V019, 3 Segmente) erhaelt die ZP-4-Regeln.
+    """
+    _hk = ns.get("_hook")
+    return (KONF.mode == "V019" and _hk is not None
+            and len(_hk.segmente) > 1
+            and _ZZ_START <= kk <= _ZZ_ENDE
+            and not (_P9_START <= kk <= _P9_ENDE))
+
+
+def _ueb(kk: int) -> float:
+    """Ueberdehnungs-Schranke: 0.80 segment-lokal, sonst arretierte cfg."""
+    return 0.80 if _zv(kk) else cfg.max_sweep_ueberdehnung_pct
+
+
+_RS_ORIG = engine._reclaim_stufe
+
+
+def _reclaim_stufe_lok(seite, kk, basis, hi, lo, cl, c):
+    """Wrapper: Schranke 0.80 segment-lokal (sonst arretierte cfg)."""
+    if _zv(kk):
+        c = dataclasses.replace(c, max_sweep_ueberdehnung_pct=0.80)
+    return _RS_ORIG(seite, kk, basis, hi, lo, cl, c)
+
+
+ns["_zv"] = _zv
+ns["_ueb"] = _ueb
+ns["_reclaim_stufe"] = _reclaim_stufe_lok
```

### H11 — Laengen-Assert (Z. 739)

```python
     assert KONF.niveau_override_wert == 69.87, KONF.niveau_override_wert
-    assert len(V1) - len(V1_basis) in (2, 3), len(V1) - len(V1_basis)
+    if KONF.mode == "V019":
+        # E-34i: 23 - 14 = 9 (Zielzone A1/A2 traegt 6, G4 1, Quartett-Tausch 2).
+        assert len(V1) - len(V1_basis) == 9, len(V1) - len(V1_basis)
+    else:
+        assert len(V1) - len(V1_basis) in (2, 3), len(V1) - len(V1_basis)
```

---

## C · Erwartete Fail-Loud-Sollwerte (aus der Messung, E-34i/3)

| Assert | Sollwert V019 |
|---|---|
| `len(V1)` | 23 |
| `R1` | +82.614385 |
| `len(h1_1)` / `sum(h1_1.r)` | 8 / +38.919584 |
| `sum(h2_1.r)` | +43.694801 |
| `P9_BEITRAG` (848..1020) | +23.435111 |
| `R1 - RB` | +34.798688 |
| `len(V1) - len(V1_basis)` | 9 |
| `NIVEAUWECHSEL` | 66 |
| `REFERENZ` keys | `[(980, 73)]` |
| `NEU` keys (mit G4) | 10 Eintraege |
| Quartett-R | +19.806095 |

---

## D · Offene Entscheidungen (Textblock)

1. ZP-4-Hilfsfunktion `_wende_zielzonen_patches_v019(src) -> str` —
   Freigabe dieses Entwurfs?
2. Zweistufiges Gating (Quelltext = Modus, Laufzeit `_zv` = gebundener
   Adapter) — bestaetigt?
3. `_ZZ_START`/`_ZZ_ENDE` aus `ADAPTER_V019.segmente` abgeleitet — bestaetigt
   (kein Bar-Literal)?
4. Renderer-Einbrand erst nach ausdruecklicher Freigabe (getrennt vom
   Adapter-Commit `68ac3af`).
5. Unveraendert: kein §75, kein S1, keine S2-Laeufe.
