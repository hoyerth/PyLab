## Phase 2 / E-34b (2026-09-11, s) — Klippenkarte des `MIN_BARS`: **die Klippe liegt bei 41, nicht bei 47/48 — das "47-Bar-Maerchen" ist falsifiziert**

### P0 · Anlass (Anwender-Frage a/b)

Frage a): "MIN_BARS = 48 ist begruendet — macht eine absichtliche Ausweitung
auf **49** Sinn, um moegliche Brueche an dieser Stelle auszuschliessen?"

Frage b): `MIN_BARS` soll als **freier Parameter fuer Reihenuntersuchungen**
verfuegbar sein.

### P1 · Parametrisierung (Frage b — umgesetzt)

`test/_tmp_e34_auto.py` akzeptiert seit E-34b **jede ganze Zahl**
(`MIN0` … `MIN999`); `RAW` == `MIN0`. Die aufgeloeste Zuordnung erfolgt in
`_min_bars_aus()` (Type Hints, Google-Docstring). Zusaetzlich neu:

| Datei | Zweck |
|---|---|
| `test/_tmp_e34b_sweep.py` | Reihenlauf `MIN<n>` fuer `lo..hi`, protokolliert H1/H2/ZIEL, Segmentzahl und Segmentgrenzen je Wert; markiert Klippen automatisch |
| `test/_tmp_e34b_klippenkarte_out.txt` | Ergebnis der Reihe `0..130` |

### P2 · Klippenkarte (AUG, n = 1288, `MIN_BARS` = 0 … 130)

| Kennzahl | Klippe | Uebergang |
|---|---|---|
| **PnL** | **41** | +74,054425 → **+82,614385** (H2 +35,134841 → +43,694801, ZIEL +8,218849 → +16,778809) |
| **PnL** | **115** | +82,614385 → +79,318499 (20 statt 23 Setups, ZIEL +13,482922, `Q_stop` 0,200) |
| Struktur (PnL-neutral) | 3, 4, 5 | 7 → 6 → 5 → 4 Segmente |
| Struktur (PnL-neutral) | 49 | 3 → 2 Segmente (1033..1173, 1174..1287) |

**Plateaus:**

| Bereich | Segmente | gesamt R | H2 R | ZIEL R |
|---|---|---|---|---|
| 0 … 2 | 7 | +74,054425 | +35,134841 | +8,218849 |
| 5 … 40 | 4 · 1033..1076, 1077..1123, 1124..1173, 1174..1287 | +74,054425 | +35,134841 | +8,218849 |
| **41 … 114** | **3 · 1033..1123, 1124..1173, 1174..1287** | **+82,614385** | **+43,694801** | **+16,778809** |
| 115 … 130 | 1 · 1033..1287 | +79,318499 | +40,398914 | +13,482922 |

**Wichtig:** `MIN41` und `MIN48` liefern **bit-identische Segmentgrenzen**
(1033..1123 / 1124..1173 / 1174..1287) **und bit-identische Ergebnisse**. Die
Struktur-Klippe bei **49** ist **PnL-neutral** (1124..1171 = 48 Bars
verschmilzt; das Ergebnis bleibt +82,614385). Eine Ausweitung auf 49 testet
daher **nichts** — sie kreuzt eine Strukturgrenze ohne PnL-Wirkung.

### P3 · Falsifikation des "47-Bar-Maerchens"

Das bei `MIN <= 40` sichtbare Segment **1077..1123 (47 Bars)** ist ein
**Artefakt der einpassigen Verschmelzung**, kein Rohsegment:

```
Rohsegmente (MIN0)   : 1077..1116 (40)  1117..1119 (3)  1120..1123 (4)
MIN 3..40  (einpassig): 1077..1116 (40) < MIN  -> verschmolzen
                        1117..1119  (3) < MIN  -> verschmolzen
                        1120..1123  (4) < MIN  -> verschmolzen
                        => 1077..1123 (47)   <-- NIE als 47er geprueft
MIN >= 41             : 1077..1116 (40) >= MIN -> NEUES Segment
                        => 1033..1076 | 1077..1123 bleibt aus
```

Die PnL-Klippe bei **41** wird also nicht von einem 47-Bar-Segment, sondern von
**genau 40 Bars** (1077..1116) ausgeloest: `min_bars > 40` verwirft es, und
erst dann entsteht `1033..1123` (K67/K82), in dem Trade **1122** ueberlebt.

**Damit ist die institutionelle 12-Stunden-Begruendung von `48` nicht
tragfaehig** — sie beschreibt 48 Bars, die Klippe liegt aber bei 41 Bar
(≈ 10,25 h), und `48` liegt **7 Bars ueber** der Klippe und **66 Bars unter**
der oberen Klippe (115). Die belastbare Aussage lautet nicht "48 ist
institutionell begruendet", sondern:

> **Das Ergebnis ist stabil fuer JEDEN Wert in [41, 114] — ein Plateau von
> 74 Werten. `MIN_BARS = 48` liegt mitten in diesem Plateau.**

Ein einzelner Wert innerhalb eines Plateaus ist kein Fitting; die Wahl 48 ist
allerdings auch nicht *besser* begruendet als 41. Die ehrliche Formulierung:
die Zahl ist innerhalb des Plateaus **frei waehlbar**, und `48` wurde gewaehlt,
weil sie arretierte Naehe zu `wall_live_bars`-Skalen (2× 24) hat.

### P4 · Hook-1-Pool-Semantik — Code-Beleg (Schritt 2, rein lesend, Teil 1)

`backtest_lab/phasen_regime_adapter.py`, `hook_1_freigabe_kid` (Z. 443 ff.),
Invarianten 4/5 im Modul-Docstring:

```
seite_kid = seg.decke.kid if richtung == "SHORT" else seg.boden.kid
for kid, basis_k in kanten:
    if kid != seite_kid: continue      # Entscheidung #6: nur die Segmentwand
    ...
    if richtung == "LONG" and sweep_px <= basis_k: continue   # nur Docht-Defizit
    diff = abs(sweep_px - basis_k);  if diff <= toleranz: gueltige.append(...)
```

Die freigegebene Kante ist damit **per Konstruktion die vom Markt
ueberstochene/unterstochene sweep-bildende Wand** — also genau die Linie, deren
Durchstich das Reclaim-Setup ausloest. Der Harness entfernt sie anschliessend
aus dem Kandidaten-Pool (`pool = [e for e in pool if e.kid != _freigabe_kid]`)
und handelt die **Innenlinie**. Das ist **keine Blockade, sondern die
arretierte Semantik**: *die Wand triggert, die Innenlinie exekutiert*
(Regel Q1 "K73-Umweg").

Fuer den dritten avisierten Trade (Bar 1172, LONG) folgt daraus praezise:
in E-33 wurde `P12` (1171..1287, boden **K82**) gesetzt ⇒ `seite_kid = 82` ⇒
K82 wurde freigegeben **und** aus dem Pool entfernt ⇒ Kaskade fiel auf **K62**
⇒ `entry > poc` ⇒ `kein_raum`.

**Wichtiger Nebenbefund aus E-34:** In der **endogenen** Segmentierung
(MIN ≥ 41) liegt Bar 1172 im Segment **1124..1173** mit boden **K85** — die
Freigabe trifft dort also **K85, nicht K82**. Ob K82 deshalb im Pool bleibt
und der Trade 1172 aufgeht, ist mit dieser Inspektion **nicht** entschieden;
das bleibt Schritt 2 (eigener Messlauf).

### P5 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34_auto.py` (parametrisiert) | 17.521 | `44463e520708d47c570805cb417e2c8fca627f9dd91ddd0dd3062caa0bcad184` |
| `_tmp_e34b_sweep.py` | 2.876 | `baefddab0d9460788f4aa423d335d26e0666885ceea28d8ba555bc8f4fc9ae77` |
| `_tmp_e34b_klippenkarte_out.txt` | 11.461 | `7bfa4ec9e122530080c7ec31c1b123f017e69b8a4ce9d680378d0ea870b58dce` |
| `_tmp_e34_auto_MIN40_out.txt` | 4.447 | `9637319860a4d05bf7aa093b92ffb42cbc2a1494d0857d076777af00c2df9320` |
| `_tmp_e34_auto_MIN41_out.txt` | 4.373 | `c941725c8bd5bb9490ce586d07695c1d87d9f80f227f7ec409b5238191669610` |
| `_tmp_e34_auto_MIN114_out.txt` | 4.302 | `41746548eb5143b9050cdd83553f924b0c2d2f493e051e768fd70cd24b06dec3` |
| `_tmp_e34_auto_MIN115_out.txt` | 4.042 | `3380484cb3fb2e46f243cc981ae1920cab448da6b105d95de7024879c7c4882d` |

### P6 · Verdikt

1. **Klippen sind lokalisiert und sind Naturgesetze der Segmentbildung**, keine
   Fitting-Kante: 41 (untere) und 115 (obere). Das Plateau [41, 114] ist
   **74 Werte breit**.
2. **Die 47-Bar-Erzaehlung ist widerlegt** (es sind 40 Bars). Die 12-Stunden-
   Begruendung fuer 48 ist damit **post hoc** und wird **nicht** als Begruendung
   uebernommen.
3. **49 zu testen ist sinnlos** (PnL-neutral); die sinnvollen Bracket-Paare
   sind **40|41** und **114|115** — beide bereits gemessen.
4. `MIN_BARS` ist ab jetzt **freier Reihenparameter** (Frage b erfuellt).
5. **Trade 1122 bleibt alternativlos der Traeger** (+8,56 R = der gesamte
   Plateau-Sprung). Das ist transparent zu fuehren und nicht zu kaschieren.

### P7 · Offene Entscheidungen (Textblock)

1. **Traegst du die korrigierte Begruendung?** Nicht "48 = 12 h
   institutionell", sondern "Plateau [41, 114], 48 ist eine zulaessige Wahl
   darin". Andernfalls muesste ein *inhaltliches* Kriterium fuer die Untergrenze
   der Phasenreife benannt werden (41 Bars ≈ 10,25 h).
2. **Fuehrst du Trade 1122 als Einzeltreffer-Transparenz** (Anteil 64 % des
   Zuwachses) im V019-Vertrag mit, wie in E-33/M6 und hier §P6.5 gefordert?
3. **Freigabe fuer Schritt 2** (Hook-1-Pool-Semantik, rein lesend): soll
   geprueft werden, ob die Freigabe-Unterdrueckung der Segmentwand
   (`kid != _freigabe_kid`) den Trade 1172 in der **endogenen** Segmentierung
   freischaltet und was das fuer H1/H2/ZIEL bedeutet? **Kein Einbrand.**
4. **V019-Vertrag** (Schritt 3) bleibt bis zur Freigabe **unspezifiziert**.
5. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.**
