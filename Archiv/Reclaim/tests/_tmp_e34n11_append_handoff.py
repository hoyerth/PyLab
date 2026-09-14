# -*- coding: utf-8 -*-
"""Append 'E-34n/11' an test/SESSION_HANDOFF.md (Vorbedingung: SHA 236354f2...).

Arretiert (Schritt 1) das Spaltmass-Audit: die tragende Konstruktion ist die
WAHL DER EINGEFRORENEN WANDBASIS b0, nicht das Touch-Band; mit der statischen
.basis kollabiert Variante D zurueck auf Variante B. Dazu (Schritt 2) das
Schnittstellen-Audit fuer Patch 14 (A_KL_DOCHT) inklusive des exakten
Text-Diffs zur Autorisierung und der Liste der Fail-Loud-Sollwerte, sowie
(Schritt 3) die Bewertung des typisierten Datenvertrags. Bewusst ASCII-only.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "test" / "SESSION_HANDOFF.md"
VORBEDINGUNG = "236354f2aa54fb5abbfa0bafd879a21f6616e39117406b02b1c2528c0fe45355"

roh = HANDOFF.read_bytes()
ist = hashlib.sha256(roh).hexdigest()
print("Vorbedingung SHA256:", VORBEDINGUNG)
print("aktuell           :", ist)
if ist != VORBEDINGUNG:
    print("ABBRUCH: Vorbedingung nicht erfuellt.")
    sys.exit(1)

ABSCHNITT = """
## Phase 2 / E-34n/11 (2026-09-11, ad) - SPALT-MASS-AUDIT: die tragende Konstruktion ist `_b0`, nicht das Band

Auftrag (Anwender, Schritte 1-3 nach E-34n/10): Revisionspruefung der
Spaltmass-Sensitivitaet an Bar 1074, Audit der Schnittstelle fuer Patch 14
(`A_KL_DOCHT`) im Renderer-Harness und Bewertung des typisierten Datenvertrags.
**Rein lesend** -- keine Zeile in Engine, Renderer oder Adapter geaendert; die
ZP-5-Sonde wurde ausschliesslich als Quelltext-Injektion in die deepkopierte
Scan-Kopie angewandt.

### Y1 - Schritt 1: Sensitivitaet liegt an `_b0`, nicht an `touch_band_pct`

**Widerlegte Annahme.** Der in E-34n/10 als "Rasiermesser" benannte Abstand
ist **nicht** die Bandgrenze, sondern die **Wahl der eingefrorenen Wandbasis**.
Gemessen mit der ZP-5(D)-Regel:

| b0-Kandidat | Wert | 1072 | 1073 | 1074 | 1075 |
|---|---|---|---|---|---|
| (a) `basis_bei(seg.start_bar)` | 67.5350 | 0.0696 rausch | 0.1081 rausch | **0.1185 rausch** | **0.1703 DOCHT** |
| (b) statische `.basis` | 67.5455 | 0.0851 rausch | **0.1236 DOCHT** | **0.1340 DOCHT** | 0.1858 DOCHT |
| (c) `basis_bei(1072)` | 67.5530 | 0.0962 rausch | **0.1347 DOCHT** | **0.1451 DOCHT** | 0.1969 DOCHT |

**Schwellen (exakt, aus den Lows):** 1074 wird Docht ab `b0 > 67.53604`
(Reserve ab (a): +0.00104 USD = +0.00154 %); 1073 ab `b0 > 67.54305`
(+0.00805 USD = +0.01192 %); 1072 ab `b0 > 67.56908` (+0.03408 USD).

**Wirkungskette (die eigentliche Gefahr):** 1074 allein kippt D **nicht**
(1074 + 2 = 1076 > 1075 -> zaehlt an 1075 noch nicht). Erst sobald **1073**
Docht wird (1073 + 2 = 1075 <= 1075), steigt `touch_conf(1075)` von 2 auf 3,
K82 wird Kandidat an 1075, scheitert an `RAUM_LONG_ORDNUNG` und **nimmt K62@1075
(+1.475768 R) weg**.

**Empirische Falsifikation (drei Laeufe, gleiche Sonde, nur `_b0` getauscht):**

| `_b0`-Quelle | K82-Dochte | `tc(1075)` | Ergebnis | Bewertung |
|---|---|---|---|---|
| (a) `basis_bei(seg.start_bar)` | 1031, 1056, 1172, 1259, **1075** | 2 | **24 / +88.116626** | additiv (Variante D) |
| (b) statische `.basis` | 1031, 1056, 1172, 1259, **1073, 1074, 1075** | **3** | **23 / +86.640859** | **KOLLAPS -> Variante B** |
| (c) `basis_bei(1072)` | 1031, 1056, 1172, 1259, **1073, 1074, 1075** | **3** | **23 / +86.640859** | **KOLLAPS -> Variante B** |

**Die statische `.basis` (67.5455) liegt nur +0.0105 USD ueber der tragenden
Basis und kollabiert D sofort.** Damit ist `_b0 = basis_bei(seg.start_bar)`
**keine Kosmetik, sondern eine tragende Konstruktion**: sie ist der Grund,
warum 1072-1074 im Band bleiben. Der Vertrag muss diese Wahl festschreiben und
fail-loud pruefen -- ein Assert auf `cfg.touch_band_pct == 0.12` schuetzt
**nicht** (er pinnt einen Wert und laesst die eigentliche Fehlerquelle offen).

**Seiteneffekt geprueft:** `NIVEAUWECHSEL` bleibt in **allen** Varianten (a/b/c)
**66** = arretriertes Soll. Die zusaetzlichen K82-Dochte veraendern die
sichtbare Niveauwechsel-Kennzahl nicht (der laufende Maximalwert 67.5530 bleibt
fuehrend, der erste Bestaetigungs-Bar 1033 unveraendert).

### Y2 - Schritt 2: Schnittstellen-Audit Patch 14 (`A_KL_DOCHT`)

**Injektionsstelle (verifiziert):** der `seite_edges`-Block in `_se_trades`,
Engine Z. **2382-2384**:

```python
    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {
        "OBEN": [e for e in alle if e.seite == "OBEN"],
        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}
```
Er liegt **nach** der Definition von `hi/lo/cl/op/alle` (Z. 2377-2381) und
**vor** der Hauptschleife (Z. 2564) -- genau richtig fuer eine Vorab-
Registrierung der Dochte. Im Renderer-Quelltext kommt er nach den 13
`A_*`-Patches und nach ZP-4 **exakt einmal** vor (`count == 1`, fail-loud; in
den Laeufen E-34n/9, /10 und /11 dreifach belegt).

**Zweistufiges Gating (beide Stufen gemessen):**

1. **Quelltext-Stufe:** der Patch wird -- wie ZP-4 -- **innerhalb**
   `_wende_zielzonen_patches_v019` eingewoben; diese Funktion wird nur unter
   `if KONF.mode == "V019":` aufgerufen (Renderer Z. 763-764). V01..V018
   erhalten den Block damit gar nicht erst.
   *Alternative (nicht empfohlen):* als 14. `A_*`-Paar in der 13er-Kette
   (Z. 676-696). Dann liegt der Block im Quelltext **aller** Modi und ist nur
   laufzeit-inert -- schwaecher als die Konstruktions-Garantie.
2. **Laufzeit-Stufe:** `len(_hook.segmente) > 1`. `ns["_hook"]` wird in `_lauf`
   (Z. 814) **vor** `exec` gebunden; V0 und V1_basis laufen mit
   `DEFAULT_ADAPTER` (1 Segment) und bleiben inert.

**Reihenfolge / Kollisionsfreiheit:** ZP-4 zuerst, ZP-5 danach. Geprueft: keiner
der vier ZP-4-Anker (`if dist > cfg.max_sweep_ueberdehnung_pct:`;
`ex_hi = float(np.max(hi[:k + 1]))`; `if e is kd or not _existiert(e, k):`;
`if not e.ist_aktiv_bei(k):`) kommt im ZP-5-Block vor -> die `count == 1`-
Asserts bleiben gueltig, unabhaengig von der Reihenfolge.

**Single Source of Truth (SSoT):** der Block darf **keinen** zweiten
Schwellenwert fuehren:
* Untergrenze zur Laufzeit: `if _dkl <= cfg.touch_band_pct: continue`
  (kein Literal `0.12`).
* Obergrenze: `<= _ueb(_kb)` statt Literal `0.80` -- `_ueb` ist der
  bestehende segment-lokale ZP-4-Helfer (Z. 792-794), der fuer A1/A2 0.80
  liefert und sonst die arretierte `cfg.max_sweep_ueberdehnung_pct` (0.6).
  Ein hartes `0.80` im Patch waere eine **Duplikation** der Schranke.

**Text-Diff zur Autorisierung (rein lesend vorbereitet, noch NICHT
eingebrannt).** Vorschlag: den ZP-5-Block als **5. Paar** in die bestehende
`paare`-Tupel von `_wende_zielzonen_patches_v019` aufnehmen -- damit erbt er
das vorhandene Fail-Loud-Geruest (`assert src.count(_alt) == 1` +
`src.replace`), und `return src` bleibt unveraendert:

```python
        # (5) ZP-5 (E-34n, arretiert in E-34n/10): Kantenlaeufer-Durchstich
        #     auf deklarierten Segmentwaenden. b0 = basis_bei(seg.start_bar)
        #     ist TRAGEND: mit der statischen .basis (67.5455) wuerde auch
        #     1073 zum Docht, touch_conf(1075) stiege auf 3 und D kollabierte
        #     auf Variante B (23 / +86.640859 statt 24 / +88.116626).
        ("A_KL_DOCHT",
         '    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {\\n'
         '        "OBEN": [e for e in alle if e.seite == "OBEN"],\\n'
         '        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}',
         '    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {\\n'
         '        "OBEN": [e for e in alle if e.seite == "OBEN"],\\n'
         '        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}\\n'
         '    # --- ZP-5(D): Kantenlaeufer-Durchstich auf Segmentwaenden\\n'
         '    _kl_hook = globals().get("_hook")\\n'
         '    if _kl_hook is not None\\n'
         '            and len(getattr(_kl_hook, "segmente", ())) > 1:\\n'
         '        _kl_idx = {int(e.kid): e for e in alle}\\n'
         '        for _seg in _kl_hook.segmente:\\n'
         '            if _seg.boden_deklariert_literal is not None:\\n'
         '                continue          # P9 & Co: eigenes Boden-Literal\\n'
         '            for _ki, _kl_seite in ((_seg.boden, "UNTEN"),\\n'
         '                                   (_seg.decke, "OBEN")):\\n'
         '                _ek = _kl_idx.get(int(_ki.kid))\\n'
         '                if _ek is None:\\n'
         '                    continue\\n'
         '                _s0, _s1 = int(_seg.start_bar), int(_seg.end_bar)\\n'
         '                _b0 = float(_ek.basis_bei(_s0))   # TRAGENDE Wahl\\n'
         '                _have = {b for b, _ in _ek.wicks}\\n'
         '                for _kb in range(max(_s0, _ek.erster_pivot_bar + 2),\\n'
         '                                 _s1 + 1):\\n'
         '                    _ext = (float(lo[_kb])\\n'
         '                            if _kl_seite == "UNTEN" else float(hi[_kb]))\\n'
         '                    _dkl = ((_b0 - _ext) if _kl_seite == "UNTEN"\\n'
         '                            else (_ext - _b0)) / _b0 * 100.0\\n'
         '                    if _dkl <= cfg.touch_band_pct:\\n'
         '                        continue      # Band-Rauschen, kein Sweep\\n'
         '                    if _dkl <= _ueb(_kb) and _kb not in _have:\\n'
         '                        _ek.wicks.append((_kb, _ext))\\n'
         '                        _have.add(_kb)\\n'
         '                if _ek.schlaf_windows:   # Wand schlaeft nicht im\\n'
         '                    _ek.schlaf_windows = [   # eigenen Segment\\n'
         '                        _w for _w in _ek.schlaf_windows\\n'
         '                        if not (_w[0] < _s1\\n'
         '                                and (_w[1] is None or _w[1] > _s0))]\\n'
         '                _ek.status = "AKTIV"\\n'),
```

**Fail-Loud-Sollwerte, die der Einbrand mitziehen MUSS** (alle Stellen
gemessen, keine geraten):

| Stelle | alt | neu |
|---|---|---|
| `KONFIGURATION_V019.ziel_trades_gesamt` | 23 | **24** |
| `KONFIGURATION_V019.ziel_r_gesamt` | 82.614385 | **88.116626** |
| `KONFIGURATION_V019.ziel_r_h2` | 43.694801 | **49.197042** |
| `KONFIGURATION_V019.ziel_delta_rb` | 34.798688 | **40.300929** |
| `KONFIGURATION_V019.neu_basis_soll` | 9 Tupel | **+ (1172, 82)** |
| Renderer Z. 904 (V019-Zweig) | `== 9` | **`== 10`** |
| `ziel_r_h1` | 38.919584 | unveraendert |
| `ziel_p9_beitrag` | 23.435111 | unveraendert |
| `niveauwechsel_gesamt` | 66 | unveraendert (gemessen 66) |
| `quartett_*`, `referenz_soll`, G4 | - | unveraendert |

**Empfohlener zusaetzlicher Waechter (abgeleitete Geometrie-Invariante statt
Wert-Pin).** Er gehoert in den bestehenden `if KONF.mode == "V019":`-Zweig
(Renderer Z. 902-904). Achtung: `lo`/`hi` sind zu diesem Zeitpunkt NOCH NICHT
definiert (erst Z. 957-959) -- deshalb ueber `scan["d"]["low"]`:

```python
    if KONF.mode == "V019":
        _k82 = next(e for e in list(scan["edges"]) + list(scan["seeds"])
                    if int(e.kid) == 82)
        _b0s = float(_k82.basis_bei(ADAPTER_V019.segmente[1].start_bar))
        _low = scan["d"]["low"].to_numpy(dtype=float)
        _dd = [(_b0s - float(_low[b])) / _b0s * 100.0
               for b in (1072, 1073, 1074, 1075)]
        # ZP-5(D) setzt voraus: nur 1075 durchstoesst das Band.
        assert _dd[1] <= cfg.touch_band_pct, _dd   # 1073 im Band
        assert _dd[2] <= cfg.touch_band_pct, _dd   # 1074 im Band
        assert _dd[3] > cfg.touch_band_pct, _dd    # 1075 echter Sweep
```
Dieser Waechter stoppt laut, sobald jemand `_b0` umstellt, das Band senkt oder
die Kante/V019-Segmentgrenzen verschiebt -- also genau bei den drei realen
Kollaps-Ursachen. Er pinnt **keinen** Zahlenwert und braucht keine zweite
Konstante.

### Y3 - Schritt 3: Bewertung des typisierten Datenvertrags

Der Entwurf `KantenlaeuferFilterPruefer`/`SweepDurchstichKonfiguration` ist in
der **Haltung** richtig (SSoT, `Protocol`, `frozen`, `slots`), in der
**Ausgestaltung** aber nachzubessern:

1. **Keine Schwellen kopieren.** `touch_band_pct`/`max_sweep_ueberdehnung_pct`
   duerfen im Vertrag nicht als `Final`-Defaults wiederholt werden (das waere
   die zweite Wahrheit). Der Vertrag haelt nur die **Referenz** auf `cfg`.
2. **`verifiziere_bar_1074_abstand` ist die richtige Idee, aber zu schwach
   parametrisiert.** Die tragende Invariante ist nicht "1074 <= Band", sondern
   "**nur 1075** durchstoesst" -- und zwar mit der **gleichen** b0-Quelle wie
   der Patch. Als Wert-Pin (`== 0.12`) ist der Schutz wirkungslos (siehe Y1).
3. **`sicherheits_abstand_min_pct = 0.0010` ist in Prozentpunkten irrefuehrend**
   -- der gemessene Abstand ist `0.12 - 0.1185 = 0.0015` **Prozentpunkte**
   (= 0.0015, nicht 0.0010). Ein Puffer von 10 Basispunkten waere groesser als
   der gesamte Spalt. Vorschlag: den geforderten Mindestabstand als
   **relative** Reserve ausdruecken (Ist: `0.0015 / 0.12 = 1.24 %`) und
   fail-loud pruefen.
4. **Empfehlung:** den Vertrag als *Dokumentation* am Klassenkopf der
   ZP-5-Regel belassen (PineScript-Stil, direkt unter dem Header-Docstring) und
   die Pruefung als **abgeleiteten Assert** aus Y2 ausfuehren -- nicht als
   zweite Datenklasse mit eigenen Defaults.

### Y4 - Artefakt-Anker E-34n/11 (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34n11_spaltmass.py` | 11.718 | `3b863bc0761a6ac32b334c7d1cf040c76b62cd6f62d83532d2c7207927a9e3c1` |
| `_tmp_e34n11_out.txt` | 3.668 | `452d5b7add350dcd31c0e9bddca6622f72f0c78cc5f6bf0b4ef2626866a87676` |
| `_tmp_e34n11_console.txt` | 3.787 | `aa69996a301dab103ef275c335d3a07c125440239344d80b4a456a25b668d559` |

**Unveraenderte Anker:** Engine 196.649 B /
`4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`; Renderer
104.221 B / `eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148`;
Adapter 30.663 B /
`4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83`.

### Y5 - Entscheidungen (Textblock)

1. **Spaltmass-Schutz:** dem Anwender-Vorschlag `cfg.touch_band_pct` als SSoT
   beizubehalten wird **zugestimmt**; dem vorgeschlagenen Assert
   `assert cfg.touch_band_pct == 0.12` wird **widersprochen** -- er pinnt einen
   Wert und schuetzt nicht gegen die gemessene Hauptursache (`_b0`-Wahl).
   Vorgeschlagen ist stattdessen der **abgeleitete Geometrie-Waechter** aus Y2
   (drei Asserts, kein Zahlen-Pin).
   **Entscheidungsfrage:** Soll der Waechter so (abgeleitet) oder zusaetzlich
   zum Wert-Pin eingebaut werden?
2. **`_b0`-Festschreibung:** `basis_bei(seg.start_bar)` ist als tragende
   Konstruktion zu kommentieren (Kollaps-Nachweis in E-34n/11 Y1) und darf
   nicht auf `.basis` umgestellt werden. **Entscheidungsfrage:** Einverstanden,
   dass die Wahl im Patch-Docstring als **invariant** dokumentiert wird?
3. **Patch-14-Form:** Empfehlung **(14a)** -- ZP-5 als 5. Paar **innerhalb**
   `_wende_zielzonen_patches_v019` (Quelltext-Gate). Alternative **(14b)** --
   14. `A_*`-Paar (nur Laufzeit-Gate), schwaecher.
   **Entscheidungsfrage:** 14a oder 14b?
4. **Freigabe-Status:** der exakte Text-Diff (siehe Y2) liegt vor; der Einbrand
   bleibt **gesperrt**, bis er autorisiert ist. Es wurde nichts geschrieben.
5. Unveraendert: **kein §75, kein S1, keine S2-Laeufe**, keine UI-/
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
