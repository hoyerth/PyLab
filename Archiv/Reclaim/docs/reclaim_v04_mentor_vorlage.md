# v0.4 Mentor-Vorlage — S2-Diagnose & Radius-Simulation (02.09.2026)

> **Kommunikation:** Deutsch · **Code/Bezeichner:** Englisch (Regel).
> **Zweck:** Entscheidungsvorlage für den Mentor. Basislage: Signal-Loop
> Design v0.3 (E3-Fallback + E5-Seiten-Konsistenz) arretiert. Die OOS-
> Validierung v0.3 ist fehlgeschlagen; Diagnose + quantitative Simulation
> (Option 4) sind abgeschlossen. Hier: Befunde + offene Design-Entscheidungen.
> **Diagnose-Skripte:** `test/tmp_v03_s2_diag.py` (P7-Detail),
> `test/tmp_v03_s2_entfallen_check.py` (Systematik 7/7),
> `test/tmp_v04_sim.py` + `test/tmp_v04_sim_results.txt` (f-Sweep).

---

## 1. Ausgangslage: v0.3-OOS-Validierung

| Fenster | Baseline | v0.3 | Δ | Status |
|---|---|---|---|---|
| AUG (2026-08-10..08-28) | 27 Sig / +24.97R | 24 Sig / +28.17R | **+3.20R** | ✓ |
| S1 (2026-02-05..08-28) | 201 Sig / +197.26R | 179 Sig / +203.31R | **+6.05R** | ✓ |
| S2 (2025-01-01..12-01) | 210 Sig / +99.88R | 205 Sig / +74.58R | **−25.30R** | ✗ |
| **S1+S2 kumuliert** | +297.14R | +277.89R | −16.05R | **< +292.14 → VERFEHLT** |

Qualitatives Kriterium ebenso verfehlt: Entfallen-Listen enthalten
Netto-Gewinner-Cluster (S2: +23.56R netto entfallen), neuer P5-Typ auf
der LOWER-Seite.

---

## 2. Diagnose — wasserdicht, alle 7 entfallenen S2-Gewinner

**Alle 7 entfallenen Gewinner sind LONG (LOWER-Seite).** Zwei unabhängige
Fehlerklassen:

### Klasse A — Kanten-Verdrängung → E4-Fail (4/7)
Der Tier-2-Anker verdrängt die atmende lokale L_zone. Die Signal-Bar
penetriert die L_zone sauber, erreicht den (entfernteren/überrannten)
Anker aber nicht → `penetriert=False` → Signal stirbt.

| Signal | lokale L_zone | Tier-2-Anker | Anker-Distanz | Alter |
|---|---|---|---|---|
| P7 09.04 +9.39R | 29.359 | 29.525 ev2 | 0.109 | 4 Ph. (Jan) |
| P26 17.09 +3.10R | 41.359 | 41.373 ev2 | **0.014** | 2 Ph. |
| P39 09.10 +3.22R | 48.622 | **47.383 ev2** | **1.31** | überrundet |
| P49 05.11 +8.63R | 47.174 | **45.978 ev4** | **1.21** | überrundet |

### Klasse B — Cooldown-Killer (5/7)
v0.3-NEU-Signale belegen `last_bar["LONG"]` 1–9 Bars vor dem Baseline-
Signal (`MIN_SIGNAL_ABSTAND_BARS = 12`) → Block. Hauptverursacher: 4×
Tier-2-Magnet-Signale des Januar-Ankers 29.706 (07.–09.04, je −1.00R).
P42/P27 sind faktisch kompensiert (Neu +8.43R/+1.84R).

**Netto-Schaden S2 durch den Anker-Komplex ≈ −29R** (P7-Cluster −13.4R,
P49 −8.6R, P26 −4.1R, P39 −3.2R).

### E5-Seiten-Konsistenz ist NICHT asymmetrie-fehlerhaft
Die geometrische Dualität (UPPER `center > price − tol` / LOWER
`center < price + tol`) ist korrekt. Das Versagen liegt in der
**E3-Kanten-Wahl**: Anker übernehmen die Kanten-Hoheit, obwohl die lokale
L_zone näher an der Auktion liegt und von der Bar sauber getestet wird.

---

## 3. Quantitative Simulation (Option 4): max_dist_factor-Sweep

Replikat der `--macro-live`-Schleife; `resolve_active_edge.__kwdefaults__
['max_dist_factor']` ∈ {4, 6, 8, 10, 12}. f=12 reproduziert die v0.3-
Referenzen exakt (Validierung).

### AUG (P5-Schutz) — Baseline 27/+24.97R
| f | Sig | SumR | Δ | P5-Schutz |
|---|---|---|---|---|
| 4 | 27 | +25.17 | +0.19 | **1/4 Konter eliminiert** |
| 6 | 25 | +27.17 | +2.19 | 3/4 |
| 8–12 | 24 | +28.17 | +3.19 | **4/4** ← Schwelle |

T2-Gewinner 66.364 (17.08 17:45, +6.90R) überlebt **alle** f (Distanz ~0.06).

### S1 — Baseline 201/+197.26R (monoton: kleinerer Radius besser)
| f | 4 | 6 | 8 | 10 | 12 |
|---|---|---|---|---|---|
| SumR | **+224.49** | +215.03 | +209.23 | +208.77 | +203.31 |
| Δ | **+27.23** | +17.77 | +11.97 | +11.51 | +6.05 |

### S2 — Baseline 210/+99.88R (NICHT monoton)
| f | 4 | 6 | 8 | 10 | 12 |
|---|---|---|---|---|---|
| SumR | **+80.21** | +68.36 | +68.36 | +70.41 | +74.58 |
| Δ | −19.67 | −31.52 | −31.52 | −29.46 | −25.29 |
| 7 Gewinner zurück | **3/7** (P39,P42,P49) | 1/7 | 1/7 | 0/7 | 0/7 |

### S1+S2 kumuliert (Ziel ≥ 292.14R)
**f=4 → 304.70 ✓** · f=6 → 283.39 ✗ · f=8 → 277.59 ✗ · f=10 → 279.18 ✗ · f=12 → 277.89 ✗

---

## 4. Kernbefund: Der radiale Radius ist das falsche Gate

1. **P5 stirbt bei f ≤ 6, P49 lebt nur bei f ≤ 4 auf** — es gibt **kein f**,
   das AUG-P5-Schutz UND S2-Befreiung gleichzeitig liefert.
2. **Near-stale Anker sind radius-immun:** P7 (29.525 @ 0.109) und P26
   (41.373 @ **0.014**) sitzen direkt an der Auktion. Nur die far-stale
   Anker P39/P49 (1.2–1.3) sind radius-erreichbar. Ein Radius, der 0.014-
   Anker ausschließt, würde auch den P5-Schutz-Anker 66.364 bei Konter-
   Distanzen bis ~1.0 töten.
3. **S2-Kurve nicht monoton** (f=6/8 = −31.5R, schlechter als f=12):
   Signal-Präsenz kaskadiert über Cooldown-Ketten (Klasse B). Radius-
   Tuning ist kein sauberer Hebel.
4. **S1 profitiert monoton** (Δ +6 → +27R) — auch dort kapern Anker die
   lokale Auktion; kleinere Reichweite entkoppelt die Makro-Kanten.

### Zwei stale-Typen (geometrische Schärfung)
- **Typ „überrannt":** P7 — Anker 29.525 liegt über der L_zone 29.359,
  aber der Close 29.416 steht **unter** dem Anker → der Support ist
  bereits gebrochen (überrannt), kann kein LONG-Reclaim-Support sein.
- **Typ „fern-left_behind":** P39/P49 — Anker 1.2–1.3 unter dem Markt aus
  alten Phasen (R4-left_behind nach UP-Bruch), ungebrochen aber außerhalb
  jeder M15-Auktion.
- **P5-Schutz-Anker 66.364:** liegt ÜBER dem Markt in Bewegungsrichtung
  („riegelt die Konter-SHORTs ab") — der legitime Verdrängungsfall.

---

## 5. Offene Design-Entscheidungen (Mentor)

Die Simulation zeigt: **Option 2 (Radius) ist weder hinreichend noch
sauber.** Die Wurzel ist die E3-Kanten-Wahl. Kandidaten für die
„Kanten-Kapselung" (Verdrängung nur, wenn der Anker die Bewegung
abriegelt statt sie zu kapern):

**D1 — Kapselungs-Regel (Klasse A, primärer Hebel):**
Ein Tier-2-Anker darf die unbestätigte lokale Kante nur verdrängen, wenn
er die Bewegung in Signalrichtung abriegelt — nicht, wenn er bereits
überrannt (Typ „überrannt") oder irrelevant fern (Typ „fern") ist.
Konkrete Formulierungen zu prüfen:
  - (a) UPPER: `anch.center ≥ lokal_kante − tol` (wie bisher); LOWER:
        `anch.center ≥ lokal_kante − tol` (Anker nicht signifikant unter
        dem lokalen Support — killt P49/P39; P7-Anker 29.525 ≥ 29.209
        bliebe allerdings erlaubt → P7 bräuchte Zusatzbedingung).
  - (b) Überrannt-Test: LOWER-Anker nur, wenn `anch.center < current_price`
        (Markt steht über dem Support = ungebrochen). P7: 29.525 > close
        29.416 → überrannt → kein Verdränger ✓. P49: 45.978 < 47.191 →
        ungebrochen → bliebe Verdränger → P49 bräuchte (a) oder Radius.
  - (c) Kombination (a)+(b) + bestehender Radius.
  **Empfehlung:** Kandidaten quantitativ im Testskript simulieren
  (AUG/S1/S2-Gesamt-R + Marker P5/P7/P26/P39/P49), erst dann v0.4-Arretierung.

**D2 — Cooldown-Trennung (Klasse B, sekundärer Hebel):**
Signale an unbestätigten Tier-2-Ankern (tier=2 ∧ bestaetigt=False) sollen
keinen Cooldown für Tier-1-Signale auslösen (oder getrennte Zähler).
Begründung: Ein Makro-Magnet-Signal (Januar-Anker 29.706) blockiert
legitime lokale Reclaims 12 Bars lang. **Achtung:** Löst man Klasse A,
verschwinden viele toxische Trigger — Klasse B heilt sich teilweise selbst.
Daher erst nach D1-Simulation bewerten.

**D3 — S1-Nutzen sichern:** S1 (2026) profitiert stark von entkoppelten
Makro-Kanten (f=4: +27R). Die Kapselung muss diesen Nutzen erhalten
(kleinere effektive Reichweite in UP-Dominanz), ohne AUG-P5-Schutz zu
verlieren.

---

## 6. Nächste Schritte (Vorschlag)

1. **Kapselungs-Kandidaten (D1 a/b/c) als v0.4-Sim** im Testskript
   quantifizieren (kein `scripts/`-Eingriff): AUG/S1/S2-Gesamt-R, Delta,
   Marker-Status P5/P7/P26/P39/P49, Entfallen/Neu-Bilanz.
2. Beste Variante → Design-Doku v0.4 (§2/E3, §8 IST, Historie) +
   `scripts/macro_persistence.py`-Implementierung (additiv, Default
   bitgenau Baseline).
3. Danach D2 (Cooldown) nur falls Klasse-B-Rest schädlich bleibt.
4. Volle OOS-Validierung AUG/S1/S2 gegen Akzeptanzkriterium (+292.14R).
