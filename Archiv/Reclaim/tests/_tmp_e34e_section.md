## Phase 2 / E-34e (2026-09-11, v) — Entscheidung: **(a) lokal wird VERWORFEN — und der Kontrakt-Entwurf ist zweifach widerlegt** (er ist nicht (a), und er kostet 5,82 R)

### S0 · Entscheidung §R8.1 — **`(a) lokal` verworfen** (Empfehlung getragen)

Ich trage das Mentor-Urteil **mit**, aus vier gemessenen Gruenden — nicht aus
Meinung:

1. **Der Zielzustand wird ohnehin nicht erreicht.** `(a) lokal` liefert
   *weiterhin nur zwei* der drei avisierten Trades: es **tauscht**
   1075 (25.08. 15:15, +1,47577) gegen 1172 (26.08. 17:00, **+7,12112**).
   Basis: 1075 + 1122. Variante: 1122 + 1172. **Nie alle drei.**
2. **Beide Pflichtmetriken degradieren** (Phasen-1-D1/D2: beide fuehrend):
   `Q_stop` 0,217 → **0,250**, `USD/Trade` +0,9819 → **+0,9522**.
3. **Der Netto-Gewinn ruht auf einem Einzeltreffer**, der zwei gegenlaeufige
   Posten mitfinanziert: +7,12112 brutto gegen +4,645353 netto
   (neu 1120 / −1,00000; entfaellt 1075 / −1,47577).
4. **Der Eingriff ist nur lokal zulaessig** — global reisst er das H1-Gate
   (E-34d §R1: Bar 252 / K28 / −0,42572). Ein Mechanismus, der nur hinter
   einer Bereichsmaske haelt, ist keine Verbesserung, sondern ein Sonderfall.

**Entscheidung: Basis bleibt `MIN_BARS`-endogen ohne Pool-Eingriff —
gesamt +82,614385 / H1 8 / +38,919584 / H2 +43,694801 / ZIEL 6 / +16,778809.**
Kein Einbrand. Kein `(a)`.

### S1 · Plateau-Entscheidung §R8.4 — **[41, 114] als SSoT, Referenzwert 77**

Getragen, **mit** einer neuen Einschraenkung, die aber die Entscheidung
*stuetzt*: die Plateau-Invarianz gilt **nur fuer die Basis-Konfiguration**.

| Konfiguration | MIN 41…48 | MIN 49…114 | Befund |
|---|---|---|---|
| **Basis (ohne Eingriff)** | +82,614385 | **+82,614385** | **bit-identisch, 74 Werte** |
| **`(a) lokal`** | **+87,259738** | **+85,640859** | **neue Klippe bei 49** |

**Unter `(a)` kollabiert das Plateau auf [41, 48] (8 Werte), und `MIN48`
liegt genau EINE Bar unter der neuen Klippe 49.** Damit ist `48` in der
`(a)`-Konfiguration die denkbar fragilste Wahl. Ein weiterer, unabhaengiger
Grund gegen `(a)`.

Nach der Entscheidung §S0 (kein `(a)`) gilt unveraendert:

- **Plateau [41, 114]** = SSoT (74 Werte, bit-identisch, Klippenkarte
  `7bfa4ec9…`).
- **Referenzwert 77** = Plateaumitte, **36 / 38 Bars** Abstand zu den Klippen
  41 / 115 (statt 7 / 67 bei 48).
- **48** bleibt als dokumentierte *strenge* Alternative im Register.
- Die 12-h-Erzaehlung bleibt **verworfen** (E-34b §P3).

**Nebenbefund:** `MIN77` erzeugt eine **andere Segmentstruktur** als `MIN48`
(2 statt 3 Segmente, A1 wird 1033..1173) — **bei identischem Ergebnis**. Das
ist der Beweis, dass die Grenz-Etiketten (K67/K82 → K73/K82) und nicht die
Schnittstellen den Ertrag tragen.

### S2 · Kandidat (b) — **bleibt vom Tisch** (bestaetigt)

Wie vorgeschlagen: `(b)` wird **nicht** gebaut. Die Aufweichung der
`b + 2`-Kausalitaet ist der richtige Einwand, und `(a) lokal` trifft dieselbe
Ursache — mit dem Preis, den §S0 beziffert. Kein Bedarf.

### S3 · Der korrigierte Kontrakt-Entwurf ist **widerlegt** (gemessen)

Der Entwurf `bereinige_zielzonen_pool` („behalten nur `lebt AND dist >= 0`")
wurde als eigener Schalter `--poolhart` implementiert und gemessen:

| Variante (AUG, MIN48) | n | gesamt R | H1 R | H2 R | ZIEL n/R | `Q_stop` | `USD/Trade` |
|---|---|---|---|---|---|---|---|
| **Basis** | 23 | **+82,614385** | 8 / +38,919584 | +43,694801 | **6 / +16,778809** | **0,217** | **+0,9819** |
| **Kontrakt `--poolhart`** | **35** | **+76,798219** | 8 / +38,919584 | +37,878635 | 18 / +10,962643 | **0,457** | **+0,5865** |
| (a) lokal `--poolalok` | 24 | +87,259738 | 8 / +38,919584 | +48,340154 | 7 / +21,424162 | 0,250 | +0,9522 |

**Der Entwurf ist zwei Fehler weit von der Messung entfernt:**

1. **Er ist NICHT `(a)`.** `(a)` entfernt nur `dist < 0 AND not lebt`
   (**unerreichte** Schlaf-Linien). Der Entwurf entfernt zusaetzlich
   `dist >= 0 AND not lebt` — also **erreichte, aber schlafende** Linien.
   Genau diese traegt die **Q1-Regel** („die erreichte Wand handelt").
2. **Er zerstoert den Mechanismus:** 35 statt 23 Trades, ZIEL 18 Trades bei
   `USD/Trade` **+0,0858** und `Q_stop` **0,667** — ein Rausch-Erzeuger.
   Trade 1172 (+7,12112) wird zwar ebenfalls gefunden, aber von
   **12 zusaetzlichen ZIEL-Trades** begleitet, die +5,816166 R vernichten.

**Verdikt: Kontrakt in dieser Form verworfen.** Verwertbar sind aus ihm nur
zwei Punkte — die `Final`-Redundanz zu `frozen=True` wurde bereits
zurueckgenommen, und `dist` **muss** als vorzeichenbehaftete Groesse gefuehrt
werden.

### S4 · V019-Vertrag — ENTWURF (rein deskriptiv, **kein Einbrand**)

`backtest_lab/phasen_regime_adapter.py` bleibt **unberuehrt**. Der Entwurf ist
Beschreibung, keine Aenderung; der Einbrand braucht separate Freigabe.

```python
# --- E-34/V019-Entwurf: Phasen-Reife (endogene Segmentbildung) -------------
# Herkunft: Klippenkarte test/_tmp_e34b_klippenkarte_out.txt
#           SHA256 7bfa4ec9e122530080c7ec31c1b123f017e69b8a4ce9d680378d0ea870b58dce
# Plateau ist AUG-spezifisch; eine Verallgemeinerung ist NICHT belegt.
PLATEAU_MIN_BARS: Final[int] = 41      # untere Klippe (PnL-Sprung 41)
PLATEAU_MAX_BARS: Final[int] = 114     # obere Klippe (115 = 1 Segment)
PLATEAU_REFERENZ_BARS: Final[int] = 77 # Plateaumitte, max. Klippenabstand


@dataclass(frozen=True, slots=True)
class PhasenReifeKonfiguration:
    """SSoT des PnL-invarianten Phasen-Plateaus (endogene Segmentbildung).

    WICHTIG (Semantik, E-34e §S1): gesteuert wird die
    VERSCHMELZUNGSSCHWELLE, nicht die Segmentlaenge. Ein gueltiges Segment
    kann aus mehreren verschmolzenen Teilstuecken entstehen; die Pruefung
    ``ist_im_plateau`` ist daher eine Aussage ueber den PARAMETER, nicht
    ueber ein Ergebnis-Segment.
    """

    verschmelzungs_schwelle: int = PLATEAU_REFERENZ_BARS

    def ist_im_plateau(self) -> bool:
        """True gdw. die gewaehlte Schwelle im invarianten Plateau liegt."""
        return PLATEAU_MIN_BARS <= self.verschmelzungs_schwelle <= PLATEAU_MAX_BARS
```

Zugehoerige Sollwerte (AUG, MIN77 + arretiertes P9):

| Kennzahl | Sollwert |
|---|---|
| gesamt | **+82,614385 R** (23 Setups) |
| H1 | **8 / +38,919584 R** (`Q_stop` 0,125) — **Invariante** |
| H2 | **+43,694801 R** (`Q_stop` 0,267) |
| ZIEL (1021..1287) | **6 / +16,778809 R** |
| Segmente | **P9 arretiert** (848..1020, decke K67-Override 69,87, boden K77) · **A1** 1033..1173 (decke K67 69,8990, boden K82 67,5350) · **A2** 1174..1287 (decke K73 69,6380, boden K82 67,5530) |

**Offen vor Einbrand:** (i) Anwender-Freigabe; (ii) `A1`/`A2` als
`PhasenSegmentEintrag` mit `provenienz_basis` (nicht `basis_bei`) — die
Fail-Loud-Pruefung `verifiziere_gegen_scan` ist auf Toleranz 1 % auszulegen;
(iii) der Boden K82 traegt in A1/A2 **verschiedene** Basiswerte
(67,5350 / 67,5530) — das ist zulaessig, aber zu dokumentieren.

### S5 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34_auto.py` (Schalter `--poolhart`) | 22.826 | `edb7365e588ba78a1a3f82e6874ede80930603bdab7929409f68eb8420f15884` |
| `_tmp_e34_auto_MIN48_ph_out.txt` (Kontrakt) | 5.119 | `139097cf7119786f717f5a8816b636d8a984676757625ebf45230d26f14082ef` |
| `_tmp_e34_auto_MIN77_out.txt` (Referenz) | 4.298 | `8d865d851a8264fc9860cf0e2d3bd78cdd937b6d329c82202db6db09162597a5` |
| `_tmp_e34_auto_MIN77_pal_out.txt` | 4.360 | `7c44ce68743747e2a0b8d24c6c632fe04e36e786df2cdbb3a5a63fd162db2e3f` |
| `_tmp_e34_auto_MIN48_out.txt` (Basis, unveraendert) | 4.373 | `a862222e7bb461f0f9bd2accc815fc1fae808eb8d99edce7cb495b5eda118b4d` |
| `_tmp_e34_auto_MIN48_pal_out.txt` | 4.435 | `d53d907b48eee2746c8aa2f4e47b8db1f393593e1278f77880fdf5e3295f88c0` |

### S6 · Ehrliche Einschraenkungen

1. **Ein Datensatz (AUG).** Kein S2, kein OOS. Das Plateau und **beide**
   Klippen sind AUG-spezifisch.
2. Der dritte avisierte Trade (1172) bleibt **ohne** das verworfene `(a)`
   **ungemessen im Modell** — er ist beziffert (+7,12112), aber nicht
   handelbar, ohne 1075 zu opfern.
3. **Der Schalter-Parsing-Fehler ist korrigiert** (erste `--poolhart`-Messung
   lief faelschlich als Basis; nach Fix reproduziert `--poolalok` exakt die
   E-34d-Werte +87,259738 / 0,250 / +0,9522 — Fidelity bestaetigt).
4. `ZIEL` in `--poolhart` enthaelt 18 Trades bei `USD/Trade` +0,0858 — ein
   robustes Warnsignal gegen jede weitere Aufweichung des V-S-Gates.

### S7 · Offene Entscheidungen (Textblock)

1. **Bestaetigung §S0** (Basis +82,614385, kein `(a)`) und **§S1**
   ([41, 114] + Referenz 77) — beide Entscheidungen sind noch nicht
   ratifiziert.
2. **V019-Entwurf (Schritt 2):** soll er als Dataclass-Spezifikation
   ausgearbeitet und in `phasen_regime_adapter.py` **eingebrannt** werden
   (dann eigene Generation mit eigenen Sollwerten) — oder zunaechst nur als
   Spezifikation im Handoff stehen bleiben?
3. **Ratifizierung (Schritt 3):** Plateau [41, 114] / 77 im Handoff
   arretieren — mit oder ohne den `MIN48`-Alternativwert?
4. **Kontrakt-Entwurf:** endgueltig verworfen (§S3), oder soll die
   *unterschiedliche* Semantik `dist < 0 AND not lebt` als Kandidat (a)
   erhalten bleiben (verworfen, aber dokumentiert)?
5. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.**
