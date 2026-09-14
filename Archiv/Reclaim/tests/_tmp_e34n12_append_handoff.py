# -*- coding: utf-8 -*-
"""Append 'E-34n/12' an test/SESSION_HANDOFF.md (Vorbedingung: SHA 7a673094...).

Arretiert: (a) die Frage "welche Bars sind fuer touch_conf(1075) TRAGEND" samt
empirischer Widerlegung des eigenen Luecken-Verdachts bei Bar 1072,
(b) die Platzierungs-Entscheidung fuer den Geometrie-Waechter, (c) das
vollstaendige Text-Diff fuer Patch 14 (Form 14a) zur Autorisierung.
Bewusst RAW-String (Anfuehrungszeichen im Diff bleiben unangetastet).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "test" / "SESSION_HANDOFF.md"
VORBEDINGUNG = "7a673094f66f842bee4fa1bd12b02ccf639b65cc981650b86807c520af683655"

roh = HANDOFF.read_bytes()
ist = hashlib.sha256(roh).hexdigest()
print("Vorbedingung SHA256:", VORBEDINGUNG)
print("aktuell           :", ist)
if ist != VORBEDINGUNG:
    print("ABBRUCH: Vorbedingung nicht erfuellt.")
    sys.exit(1)

ABSCHNITT = r"""
## Phase 2 / E-34n/12 (2026-09-11, ae) - WAECHTER-SCHAERFUNG + TEXT-DIFF PATCH 14 (Form 14a) zur Autorisierung

Auftrag (Anwender, nach E-34n/11): Revisionspruefung des abgeleiteten
Geometrie-Waechters (welche Bars sind fuer `touch_conf(1075)` ueberhaupt
tragend?), Audit der Injektionsform 14a und Vorlage des vollstaendigen
Text-Diffs. **Rein lesend** -- es wurde keine Zeile in Engine, Renderer oder
Adapter geschrieben; die Messung nutzt ausschliesslich den bereits geladenen
Scan.

### Z1 - Zaehlweite: nur Dochte bis Bar 1073 sind fuer 1075 tragend

`touch_conf(k)` zaehlt `b + 2 <= k` (Engine Z. 2135-2137). Gemessen:

| Abfrage | gezaehlte Docht-Bars | Ergebnis |
|---|---|---|
| `touch_conf(1075)` | bis Bar **1073** | `[1031, 1056]` = **2** |
| `touch_conf(1076)` | bis Bar 1074 | `[1031, 1056]` = 2 |
| `touch_conf(1077)` | bis Bar 1075 | `[1031, 1056]` = 2 |

**Folgerung:** Ein Docht an **1074 oder 1075 erhoeht `touch_conf(1075)` NICHT**.
Tragend sind ausschliesslich Dochte an **<= 1073**. Der Sweep-Docht 1075 ist am
eigenen Bar per Konstruktion unbestaetigt - das ist dieselbe Mechanik, die in
E-34n/10 als Additivitaets-Ursache von D belegt wurde.

### Z2 - Widerlegung des eigenen Luecken-Verdachts bei Bar 1072

**Verdacht (des Assistenten, vor der Messung):** der Waechter-Entwurf prueft
1073/1074/1075, aber nicht 1072 - und 1072 ist mit `1072 + 2 = 1074 <= 1075`
ebenfalls tragend. Eine Luecke sei also denkbar.

**Messung (E-34n/12/4) - der Verdacht ist FALSCH:**

| Bar | tragend? | Docht ab `b0 >` | Abstand zu `b0 = 67.5350` |
|---|---|---|---|
| 1074 | neutral (1074+2 = 1076 > 1075) | 67.53604 | +0.00104 USD |
| **1073** | **TRAGEND** | **67.54305** | **+0.00805 USD** |
| 1072 | tragend | 67.56908 | +0.03408 USD |

Da `Schwelle(1073) < Schwelle(1072)` gilt: **jedes `b0`, das 1072 zum Docht
macht, macht vorher bereits 1073 zum Docht.** Der Waechter (der 1073 prueft)
feuert also in jedem kollaps-relevanten Fall. Der Entwurf ist **nicht luecken-
haft, sondern in der tragenden Achse exakt** und beim neutralen 1074 sogar
**konservativ** (er faengt auch das harmlose Fenster
`67.53604 < b0 <= 67.54305` ab, in dem 1074 zum Docht wuerde, ohne die Trades
zu aendern - das schuetzt zusaetzlich die Docht-Registrierung im Bild).

**Verdikt-Tabelle (gemessen):**

| `_b0`-Quelle | b0 | 1072 | 1073 | 1074 | 1075 | zusaetzliche Dochte `b+2<=1075` | `touch_conf(1075)` | Waechter | Realitaet |
|---|---|---|---|---|---|---|---|---|---|
| (a) `basis_bei(seg.start_bar)` | 67.5350 | 0.0696 r | 0.1081 r | 0.1185 r | 0.1703 D | **0** | **2** | PASS | **D (additiv)** |
| (b) statische `.basis` | 67.5455 | 0.0851 r | **0.1236 D** | 0.1340 D | 0.1858 D | 2 | **4** | **FAIL** | **KOLLAPS B** |
| (c) `basis_bei(1072)` | 67.5530 | 0.0962 r | **0.1347 D** | 0.1451 D | 0.1969 D | 2 | **4** | **FAIL** | **KOLLAPS B** |

Der Waechter ist damit **fail-loud nachweislich wirksam**: er trennt (a) von
(b)/(c) ohne einen einzigen Zahlen-Pin.

### Z3 - Platzierungs-Entscheidung (Antwort auf Leitfrage 1)

**Der Vorschlag "direkt hinter Zeile 959" wird NICHT mitgetragen.** Begruendung
(aus dem Quelltext geprueft, nicht behauptet):

1. **Zeile 959 ist ausserhalb des Modus-Gatters.** Die fail-loud-Asserts der
   uebrigen Sollwerte liegen in Z. 876-936; der V019-spezifische Zweig ist
   Z. 902-904. Ein Waechter nach Z. 959 liegt **top-level** und liefe damit in
   **allen** Modi (V01..V018). Er wuerde also einer V014-Auswertung eine
   V019-Geometrie-Invariante aufzwingen. Heute bliebe das folgenlos (alle Modi
   teilen denselben AUG-Scan, Z. 538-561), aber es ist genau die
   Vermischung, die das zweistufige Gating sonst konsequent verhindert.
2. **Zeile 902-904 ist der einzige Ort mit Modus-Isolation** - dort gehoert der
   Waechter hin.
3. **Der Einwand "`low` gibt es erst bei Z. 959" trifft nicht zu.** Der Scan
   liegt bereits vor: `scan = engine._se_scan(FENSTER, cfg)` (Z. 538). Fuer
   `scan["d"]["low"]` braucht es die Array-Zeile 959 nicht.

**Empfohlene Platzierung** (im `if KONF.mode == "V019":`-Zweig, unmittelbar
hinter Z. 904, VOR den Plot-Import Z. 939):

```python
    if KONF.mode == "V019":
        assert len(V1) - len(V1_basis) == 10, len(V1) - len(V1_basis)   # 14 -> 24
        # --- ZP-5(D) Geometrie-Waechter (E-34n/11+12): KEIN Wert-Pin.
        # Tragend ist b0 = basis_bei(seg.start_bar); mit der statischen
        # .basis (67.5455) kippt 1073, touch_conf(1075) steigt 2 -> 4 und
        # D kollabiert auf Variante B (23 / +86.640859).
        _w82 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
                    if int(e.kid) == 82)
        _b0w = float(_w82.basis_bei(ADAPTER_V019.segmente[1].start_bar))
        _lw = scan["d"]["low"].to_numpy(dtype=float)
        _dw = {b: (_b0w - float(_lw[b])) / _b0w * 100.0 for b in (1072, 1073, 1074, 1075)}
        assert _dw[1073] <= cfg.touch_band_pct, _dw   # 1073 im Rauschen (TRAGEND)
        assert _dw[1074] <= cfg.touch_band_pct, _dw   # 1074 im Rauschen (konservativ)
        assert _dw[1075] >  cfg.touch_band_pct, _dw   # 1075 ist der Durchstich
```
Hinweis: `adapter is ADAPTER_V019` ist im V019-Zweig garantiert; die
Segmentbasis wird dennoch **explizit** aus `ADAPTER_V019` gezogen, damit der
Waechter nicht vom geladenen Objekt abhaengt.

### Z4 - Audit der Injektionsform 14a (Antwort auf Leitfrage 2, Teil 1)

* **Anker:** der `seite_edges`-Block (Engine Z. 2382-2384). Lage im Renderer-
  Quelltext: **nach** den 13 `A_*`-Patches und **nach** ZP-4, `count == 1`
  (in E-34n/9, /10, /11 dreifach als assert durchgelaufen).
* **Kollisionsfreiheit:** keiner der vier ZP-4-Anker (`if dist >
  cfg.max_sweep_ueberdehnung_pct:`; `ex_hi = float(np.max(hi[:k + 1]))`;
  `if e is kd or not _existiert(e, k):`; `if not e.ist_aktiv_bei(k):`) kommt im
  ZP-5-Block vor. Das 5. Paar laeuft in derselben `for _nm, _alt, _neu`-Schleife
  wie die vier ZP-4-Paare und erbt damit das vorhandene `assert src.count(_alt)
  == 1`-Fail-Loud-Geruest.
* **SSoT:** Untergrenze `cfg.touch_band_pct` (kein Literal `0.12`), Obergrenze
  `_ueb(_kb)` (kein Literal `0.80`).
* **Gating:** Quelltext-Stufe ueber den Aufruf in Z. 763-764
  (`if KONF.mode == "V019": patched_src = _wende_zielzonen_patches_v019(...)`),
  Laufzeit-Stufe ueber `len(_hook.segmente) > 1` (Z. 786-789 / 814).

### Z5 - VOLLSTAENDIGES TEXT-DIFF PATCH 14 (Form 14a) - zur Autorisierung

**Status: NICHT eingebrannt.** Die vier Aenderungen sind unten vollstaendig
spezifiziert; erst nach ausdruecklicher Freigabe wird geschrieben.

**(1) `RendererKonfiguration`-Instanz `KONFIGURATION_V019` (Z. 394-424) - vier Felder:**

```diff
     ziel_trades_gesamt=23,
-    ziel_r_gesamt=82.614385,
+    ziel_trades_gesamt=24,
+    ziel_r_gesamt=88.116626,
     ziel_r_h1=38.919584,          # Invariante (bit-identisch V017/V018)
-    ziel_r_h2=43.694801,
-    ziel_p9_beitrag=23.435111,    # P9 arretiert, unveraendert
+    ziel_r_h2=49.197042,          # +5.502241 (K82@1172, entry_bar 1173)
+    ziel_p9_beitrag=23.435111,    # P9 arretiert, unveraendert
@@
-    ziel_delta_rb=34.798688,      # = 82.614385 - 47.815697
+    ziel_delta_rb=40.300929,      # = 88.116626 - 47.815697
     # --- adapter-abhaengige Sollwerte (E-34i/3, MESSUNG) ------------------
     neu_basis_soll=((903, 67), (980, 67), (981, 73), (1075, 62), (1122, 73),
-                    (1211, 76), (1268, 76), (1272, 73), (1280, 76)),
+                    (1172, 82), (1211, 76), (1268, 76), (1272, 73),
+                    (1280, 76)),
```
Unveraendert bleiben: `ziel_h1_trades=8`, `ziel_v0_r=42.450970`,
`ziel_v1_basis_trades=14`, `ziel_v1_basis_r=47.815697`, `referenz_soll`,
`quartett_r_soll`, `quartett_r_summe_soll`, `niveauwechsel_gesamt=66`,
`niveauwechsel_baseline=205`.

**(2) Fail-Loud-Zweig (Z. 902-904) - Delta 9 -> 10 + Geometrie-Waechter:**

```diff
     if KONF.mode == "V019":
         # E-34i: 23 - 14 = 9 (Zielzone A1/A2 traegt 6, G4 1, Quartett 2).
-        assert len(V1) - len(V1_basis) == 9, len(V1) - len(V1_basis)
+        # E-34n/12: 24 - 14 = 10 (+1 K82@1172 aus ZP-5(D)).
+        assert len(V1) - len(V1_basis) == 10, len(V1) - len(V1_basis)
+        # --- ZP-5(D) Geometrie-Waechter (E-34n/11+12): KEIN Wert-Pin.
+        # Tragend ist b0 = basis_bei(seg.start_bar); mit der statischen
+        # .basis (67.5455) kippt 1073, touch_conf(1075) steigt 2 -> 4 und
+        # D kollabiert auf Variante B (23 / +86.640859).
+        _w82 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
+                    if int(e.kid) == 82)
+        _b0w = float(_w82.basis_bei(ADAPTER_V019.segmente[1].start_bar))
+        _lw = scan["d"]["low"].to_numpy(dtype=float)
+        _dw = {b: (_b0w - float(_lw[b])) / _b0w * 100.0
+               for b in (1072, 1073, 1074, 1075)}
+        assert _dw[1073] <= cfg.touch_band_pct, _dw   # TRAGEND
+        assert _dw[1074] <= cfg.touch_band_pct, _dw   # konservativ
+        assert _dw[1075] >  cfg.touch_band_pct, _dw   # Durchstich
```

**(3) `_wende_zielzonen_patches_v019` (Z. 708-760) - Docstring + 5. Paar.**
Die Funktion endet heute mit:

```python
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
```

Das 5. Paar wird **vor** dem schliessenden `    )` eingefuegt:

```diff
          "                   else (lo[k] < e.basis_bei(k)))\n"
          "            if not (_zv(k) and _ev):\n"
          "                return False\n"
          "        return e.erster_pivot_bar + 2 <= k + 1"),
+        # (5) ZP-5(D), arretiert in E-34n/10+11: Kantenlaeufer-Durchstich.
+        #     INVARIANT: b0 = basis_bei(seg.start_bar) ist TRAGEND. Mit der
+        #     statischen .basis (67.5455) kippt Bar 1073 (1073 + 2 = 1075 <=
+        #     1075), touch_conf(1075) steigt 2 -> 4 und Variante D kollabiert
+        #     auf Variante B (23 / +86.640859 statt 24 / +88.116626).
+        #     Schwellen AUS cfg (kein Literal): unten cfg.touch_band_pct,
+        #     oben der ZP-4-Helfer _ueb (segment-lokale 0.80).
+        ("A_KL_DOCHT",
+         '    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {\n'
+         '        "OBEN": [e for e in alle if e.seite == "OBEN"],\n'
+         '        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}',
+         '    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {\n'
+         '        "OBEN": [e for e in alle if e.seite == "OBEN"],\n'
+         '        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}\n'
+         '    # --- ZP-5(D): Kantenlaeufer-Durchstich auf Segmentwaenden\n'
+         '    # ZWEISTUFIG GEGATET: diese Funktion laeuft nur bei mode == "V019"\n'
+         '    # (Quelltext-Stufe, Renderer Z. 763-764) UND der Laufzeit-Gate\n'
+         '    # len(hook.segmente) > 1 haelt V0/V1_basis inert.\n'
+         '    _kl_hook = globals().get("_hook")\n'
+         '    if _kl_hook is not None and len(getattr(_kl_hook, "segmente", ())) > 1:\n'
+         '        _kl_idx = {int(e.kid): e for e in alle}\n'
+         '        for _seg in _kl_hook.segmente:\n'
+         '            if _seg.boden_deklariert_literal is not None:\n'
+         '                continue          # P9 & Co: eigenes Boden-Literal\n'
+         '            for _ki, _kl_seite in ((_seg.boden, "UNTEN"),\n'
+         '                                   (_seg.decke, "OBEN")):\n'
+         '                _ek = _kl_idx.get(int(_ki.kid))\n'
+         '                if _ek is None:\n'
+         '                    continue\n'
+         '                _s0, _s1 = int(_seg.start_bar), int(_seg.end_bar)\n'
+         '                _b0 = float(_ek.basis_bei(_s0))   # TRAGENDE Wahl\n'
+         '                _have = {b for b, _ in _ek.wicks}\n'
+         '                for _kb in range(max(_s0, _ek.erster_pivot_bar + 2),\n'
+         '                                 _s1 + 1):\n'
+         '                    _ext = (float(lo[_kb])\n'
+         '                            if _kl_seite == "UNTEN" else float(hi[_kb]))\n'
+         '                    _dkl = ((_b0 - _ext) if _kl_seite == "UNTEN"\n'
+         '                            else (_ext - _b0)) / _b0 * 100.0\n'
+         '                    if _dkl <= cfg.touch_band_pct:\n'
+         '                        continue      # Band-Rauschen, kein Sweep\n'
+         '                    if _dkl <= _ueb(_kb) and _kb not in _have:\n'
+         '                        _ek.wicks.append((_kb, _ext))\n'
+         '                        _have.add(_kb)\n'
+         '                if _ek.schlaf_windows:        # Segmentwand schlaeft\n'
+         '                    _ek.schlaf_windows = [    # nicht im eigenen Segment\n'
+         '                        _w for _w in _ek.schlaf_windows\n'
+         '                        if not (_w[0] < _s1\n'
+         '                                and (_w[1] is None or _w[1] > _s0))]\n'
+         '                _ek.status = "AKTIV"'),
     )
```

Zusaetzlich im Docstring der Funktion (Z. 708-719) die Zeile
`"Sweep-Basis-Aktivierung"` um `+ Kantenlaeufer-Durchstich (ZP-5, E-34n)`
ergaenzen.

**Nicht** geaendert: die 13 `A_*`-Paare, die 5 Anker-Asserts in Z. 676-683,
`_lauf`, `_zv`, `_ueb`, `_reclaim_stufe_lok`, die PNG-Funktionen.

### Z6 - Sollwert-Uebersicht nach dem Einbrand (alle Werte gemessen, E-34n/9)

| Kennzahl | ZP-4 (alt) | ZP-5(D) (neu) |
|---|---|---|
| Trades | 23 | **24** |
| Summe | +82.614385 | **+88.116626** |
| H1 | 8 / +38.919584 | 8 / +38.919584 (unveraendert) |
| H2 | 15 / +43.694801 | **16 / +49.197042** |
| P9 (848..1020) | 5 / +23.435111 | 5 / +23.435111 (unveraendert) |
| Delta R1 - R_B | 34.798688 | **40.300929** |
| `NEU` | 9 Tupel | **10 Tupel** (+ (1172, 82)) |
| `V1 - V1_basis` | 9 | **10** |
| NIVEAUWECHSEL | 66 | 66 (unveraendert, gemessen) |
| V018-Gegenprobe | 17 / +65.835576 | 17 / +65.835576 (unveraendert) |

### Z7 - Artefakt-Anker E-34n/12 (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34n12_waechter.py` | 4.831 | `7b5df4caedcd7eb782e64461551209f19d54612a7b903f18849bb4f1f69fd305` |
| `_tmp_e34n12_out.txt` | 3.807 | `d79f5e2bced691914cf34365d6423e65a295b6d2d2ed70168d7a24c20016bf87` |

**Unveraenderte Anker:** Engine 196.649 B /
`4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`; Renderer
104.221 B / `eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148`;
Adapter 30.663 B /
`4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83`.

### Z8 - Entscheidungen (Textblock)

1. **Waechter-Form:** drei Asserts (1073/1074/1075), **kein** Wert-Pin -
   vom Anwender entschieden, vom Assistenten nach Messung **bestaetigt**; der
   eigene Luecken-Verdacht zu 1072 ist in Z2 **widerlegt** (Schwellen-Monotonie).
   Bar 1072 wird deshalb **nicht** zusaetzlich geprueft (redundant).
   Optional bleibt ein vierter Assert (`_dw[1072] <= cfg.touch_band_pct`) als
   reine Dokumentation - er aendert das Verhalten nicht.
2. **`_b0`-Invariante:** vom Anwender bestaetigt; im Patch-Header als
   TRAGEND dokumentiert (Kommentar im Diff unter Z5(3)).
3. **Patch-Form 14a:** vom Anwender entschieden (5. Paar in
   `_wende_zielzonen_patches_v019`); Audit in Z4 ohne Befund.
4. **Platzierung:** abweichend von Leitfrage 1 nicht hinter Z. 959, sondern in
   den V019-Zweig Z. 902-904 (Begruendung Z3). **Entscheidungsfrage:** wird
   diese Platzierung mitgetragen?
5. **Freigabe-Status:** Text-Diff liegt vor (Z5); der Einbrand bleibt
   **gesperrt** bis zur Autorisierung. Es wurde nichts geschrieben.
6. Unveraendert: **kein §75, kein S1, keine S2-Laeufe**, keine UI-/
   Regressionstests, kein `git add -f`.
"""

vorher = HANDOFF.read_text(encoding="utf-8")
if not vorher.endswith("\n"):
    vorher += "\n"
HANDOFF.write_text(vorher + ABSCHNITT, encoding="utf-8")

neu = HANDOFF.read_bytes()
print("neu SHA256:", hashlib.sha256(neu).hexdigest())
print("neu Bytes :", len(neu))
print("Zeilen    :", len(neu.decode("utf-8").splitlines()))
