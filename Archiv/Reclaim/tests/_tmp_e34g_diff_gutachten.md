# E-34g — Diff-Gutachten: Generation V019 (`backtest_lab/phasen_regime_adapter.py`)

**Status:** ENTWURF, rein deskriptiv. **Kein Einbrand.**
**Ziel-Datei (unberuehrt):** `backtest_lab/phasen_regime_adapter.py`
SHA256 `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` (25.783 B).
**Engine (unberuehrt):** `test/tmp_kanten_engine_replay.py`
SHA256 `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`.
**Vorbedingung:** Commit `f46c894` (E-34f), Handoff-SHA `99f3a7fb19e271bc...`.

---

## A · Gegenstand und Umfang

Gegenstand ist **ausschliesslich** die additive Einhaengung einer neuen
Generation `V019` in den Adapter. **Keine** bestehende Zeile wird geaendert.
Der gesamte Block wird **am Dateiende** angehaengt (nach `ADAPTER_V015`).

| Aspekt | Befund |
|---|---|
| Neue Imports noetig? | **Nein.** `dataclass`, `Tuple`, `Optional`, `Sequence` sind bereits importiert. Die Import-Zeile wird **nicht** angefasst. |
| Bestehende Strukturen veraendert? | **Nein.** `P9`, `AKTIVE_DEFAULT_SEGMENTE`, `DEFAULT_ADAPTER`, `ADAPTER_V014`, `ADAPTER_V015`, `RESERVE_SEGMENTE` bleiben bit-identisch. |
| P9-Herkunft | **Uebernommen**, nicht neu deklariert (E-34f §T1). |
| Toleranz | `provenienz_toleranz_pct` Default ist bereits **1.0** (Feld-Default im `PhasenSegmentEintrag`). Explizit gesetzt = selbst-dokumentierend, verhaltensneutral. |

---

## B · Der vollstaendige Diff (Anhang an das Dateiende)

```python
# --- v0.24/V019: endogene Segmentbildung (E-34 .. E-34f) -------------------
# Anwender-Ratifizierung 2026-09-11 (v): §S0 (Basis +82.614385 R, kein (a))
# und §S1 (Plateau [41, 114], Referenz 77). V019 loest V018 als
# Betriebsstandard ab.
#
# Die Zielfenster A1 (1033..1173) und A2 (1174..1287) sind ZIELFREI aus EINER
# Regel hergeleitet (E-34 §O1): eine Kante lebt, solange ihr letzter
# BESTAETIGTER Docht b+2 <= k juenger als cfg.wall_live_bars (96) ist; die
# Segmentgrenze ist der Wechsel des Paares (aeusserste lebende Linie je Seite).
#
# Die Fenster werden hier als ARRETIERTE KONSTANTEN gefuehrt, NICHT zur
# Laufzeit neu berechnet: der Adapter bleibt eine reine Wertedomaene ohne
# Engine-Import (Invariante 1, Modul-Docstring). Die endogene Regel ist die
# Herleitung, das arretierte Fenster die Vollzugsform.
#
# Herkunft/Limit der Plateaugrenzen: Klippenkarte
# test/_tmp_e34b_klippenkarte_out.txt,
# SHA256 7bfa4ec9e122530080c7ec31c1b123f017e69b8a4ce9d680378d0ea870b58dce.
# Das Plateau ist AUG-SPEZIFISCH; eine Verallgemeinerung ist NICHT belegt.
PLATEAU_MIN_BARS: int = 41          # untere PnL-Klippe (§S1)
PLATEAU_MAX_BARS: int = 114         # obere PnL-Klippe (§S1, 115 = 1 Segment)
PLATEAU_REFERENZ_BARS: int = 77     # Plateaumitte, max. Klippenabstand


@dataclass(frozen=True, slots=True)
class PhasenReifeKonfiguration:
    """SSoT des PnL-invarianten Phasen-Plateaus (endogene Segmentbildung).

    WICHTIG (Semantik, E-34e §S1): gesteuert wird die VERSCHMELZUNGS-
    SCHWELLE, nicht die Segmentlaenge. Ein gueltiges Segment kann aus
    mehreren verschmolzenen Teilstuecken entstehen; die Pruefung
    ``ist_im_plateau`` ist daher eine Aussage ueber den PARAMETER, nicht
    ueber ein Ergebnis-Segment.

    Args:
        verschmelzungs_schwelle: Ersatzwert fuer ``cfg.wall_live_bars`` der
            endogenen Regel. Default = Plateaumitte (max. Klippenabstand).
    """

    verschmelzungs_schwelle: int = PLATEAU_REFERENZ_BARS

    def ist_im_plateau(self) -> bool:
        """True gdw. die gewaehlte Schwelle im invarianten Plateau liegt."""
        return (PLATEAU_MIN_BARS <= self.verschmelzungs_schwelle
                <= PLATEAU_MAX_BARS)


# --- v0.24/V019: Zielzone A1/A2 (endogen, MIN77) ---------------------------
# P9 wird NICHT neu deklariert, sondern aus ``P9_BODEN_RECLAIM`` uebernommen
# (E-34f §T1): eine Neudeklaration mit vertauschten Rollen (K77 als Decke)
# scheitert an ``verifiziere_gegen_scan``; ausserdem gingen der Niveau-Override
# 69.87 und das Boden-Literal 68.40 verloren (Trade @1020 entfaellt).
#
# A1/A2 tragen KEIN ``boden_deklariert_literal`` -> Hook 3 (Regel G4) bleibt
# dort inert; die G4-Regel handelt ausschliesslich im arretierten P9.

# A1 (1033..1173): Decke K67 (69.8990), Boden K82 (67.5350).
A1_AUTO_77: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="A1_AUTO_77",
    start_bar=1033,
    end_bar=1173,
    decke=PhasenKanteInfo(kid=67, provenienz_basis=69.8990),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5350),
    ziel_preis_short=67.5350,
    ziel_preis_long=69.8990,
    provenienz_toleranz_pct=1.0,        # == Feld-Default; explizit ausgewiesen
)

# A2 (1174..1287): Decke K73 (69.6380), Boden K82 (67.5530).
#
# K82-DOPPELROLLE (dokumentationspflichtig, E-34f §T8.4 / E-34g): K82 ist
# Boden in A1 UND A2, traegt aber ZWEI Provenienz-Werte (67.5350 / 67.5530,
# Differenz 1.80 Cent). Das ist KEIN Widerspruch, sondern der Preisschritt der
# Kante an der Segmentgrenze: basis_bei(1173) = 67.5350, basis_bei(1174) =
# 67.5530. Beide Provenienz-Werte sind exakt der kausale Basiswert am
# jeweiligen Segmentstart (Abweichung 0.0000 %; Nachweis E-34g
# test/_tmp_e34g_toleranz_out.txt). Fuer die Signalmechanik entscheidet dieser
# Cent ueber ``dist < 0`` vs. ``dist >= 0`` --- die Hook-Pruefung nutzt
# ohnehin ausschliesslich ``basis_bei(k)`` (Invariante 2).
A2_AUTO_77: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="A2_AUTO_77",
    start_bar=1174,
    end_bar=1287,
    decke=PhasenKanteInfo(kid=73, provenienz_basis=69.6380),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.5530),
    ziel_preis_short=67.5530,
    ziel_preis_long=69.6380,
    provenienz_toleranz_pct=1.0,        # == Feld-Default; explizit ausgewiesen
)

# Selektionsliste der V019-Generation (explizit, NICHT Default).
# Reihenfolge = chronologisch. Die Luecke 1021..1032 bleibt offen ->
# fail-closed (eliminiert den E-33-Verlust-Trade @1028).
AKTIVE_SEGMENTE_V019: Tuple[PhasenSegmentEintrag, ...] = (
    P9_BODEN_RECLAIM, A1_AUTO_77, A2_AUTO_77)

# Fail-Loud beim Aufbau - analog ``ADAPTER_V014`` / ``ADAPTER_V015``.
# ``verifiziere_gegen_scan`` bewusst NICHT hier: sie braucht den Scan-Katalog
# und laeuft im Renderer/Test (engine-freie Wertedomaene, Invariante 1).
ADAPTER_V019: PhasenRegimeAdapter = PhasenRegimeAdapter(
    segmente=AKTIVE_SEGMENTE_V019)
ADAPTER_V019.verifiziere_niveau_overrides()
ADAPTER_V019.verifiziere_boden_literale()
```

**Wichtig — `DEFAULT_ADAPTER` bleibt unveraendert.** Der Renderer faehrt den
Referenzlauf `V0` (`_lauf(DEFAULT_ADAPTER, False)`) und die v0.1-Basis
`V1_basis` (`_lauf(DEFAULT_ADAPTER, True)`) mit dem Default-Adapter
(Z. 663/664). Wuerde `DEFAULT_ADAPTER` auf V019 umgestellt, kippten `V0`,
`R_B`, `H1` und die Altsatz-Garantie. V019 wird **ausschliesslich** ueber den
neuen Modus gebunden.

---

## C · Verifikations-Nachweis (E-34g, read-only)

Skript `test/_tmp_e34g_toleranz.py`, Output `test/_tmp_e34g_toleranz_out.txt`.
Der Entwurf wurde **in-memory** (ohne Schreiben) gegen die echten Pruefer
gebaut.

| Pruefer | REF 848 | REF 980 | REF 1259 |
|---|---|---|---|
| `verifiziere_gegen_scan` | **OK** | **OK** | **OK** |
| `verifiziere_niveau_overrides` | **OK** | | |
| `verifiziere_boden_literale` | **OK** | | |

**Maximale Abweichung `provenienz_basis` vs. `basis_bei(k)`** ueber alle
7 Audit-Bars:

| Phase | Rolle | Kante | max. Abweichung | ≤ 1 % |
|---|---|---|---|---|
| P9 | decke | K67 | 0,0873 % | OK |
| P9 | boden | K77 | 0,0629 % | OK |
| A1_AUTO_77 | decke | K67 | 0,1087 % | OK |
| A1_AUTO_77 | boden | K82 | 0,0962 % | OK |
| A2_AUTO_77 | decke | K73 | 0,1106 % | OK |
| A2_AUTO_77 | boden | K82 | 0,0696 % | OK |

→ Die **1-%-Toleranz traegt** mit Faktor ≈ 9 Reserve. **Kein Sonderfall
noetig**; die explizite Angabe ist reine Audit-Klarheit.

**K82-Doppelrolle, exakt:** `basis_bei(1033)=67.5350` (0,0000 %), 
`basis_bei(1174)=67.5530` (0,0000 %). Der Preisschritt liegt genau auf Bar 1174.

**Sollwert-Arithmetik (schliesst exakt):**
`26.915992 (V018-H2) + 16.778809 (ZIEL A1/A2) = 43.694801 (V019-H2)` und
`38.919584 (H1) + 43.694801 (H2) = 82.614385 (gesamt)`.

**Inertheit-Isolation:** `ADAPTER_V015.segmente == ('P9',)` unveraendert;
Entwurf `('P9','A1_AUTO_77','A2_AUTO_77')`. Adapter-Datei-SHA und
Engine-SHA waehrend der gesamten Analyse bit-identisch.

### C.1 · Syntax-/Konstruktionsprobe des §B-Codeblocks

Skript `test/_tmp_e34g_syntaxprobe.py`, Output
`test/_tmp_e34g_syntaxprobe_out.txt`. Der **wörtliche** §B-Block (104 Zeilen)
wird extrahiert und im echten Adapter-Namespace per `exec` ausgefuehrt
(kein Schreiben):

```
exec: OK (syntaktisch korrekt)
Neue Namen: A1_AUTO_77, A2_AUTO_77, ADAPTER_V019, AKTIVE_SEGMENTE_V019,
            PLATEAU_MAX_BARS, PLATEAU_MIN_BARS, PLATEAU_REFERENZ_BARS,
            PhasenReifeKonfiguration            <- keine Namenskollision
P9 uebernommen: literal 68.4 | override 69.87 | `is P9_BODEN_RECLAIM` True
A1_AUTO_77: 1033..1173 K67/K82 tol=1.0 literal=None
A2_AUTO_77: 1174..1287 K73/K82 tol=1.0 literal=None
Plateau: d=40 False | d=41 True | d=77 True | d=114 True | d=115 False
Nahtstellen: 1020 PHASE | 1021/1032 BLOCKIERT | 1033/1173/1174/1287 PHASE
             | 1288 BLOCKIERT | aktiv 255/267
Pruefer: REF 848/980/1259 OK | niveau_overrides OK | boden_literale OK
Bestand : DEFAULT_ADAPTER ['P9'] | ADAPTER_V015 ['P9']  (unveraendert)
Adapter-SHA vorher == nachher: True  (bit-identisch)
```

### C.2 · Artefakt-Anker E-34g (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34g_diff_gutachten.md` | 12.655 (vor C.1) | `d3febd2f4fde6835198fcb6eedc8b7759236566107eff3bf59a255f6f696d791` |
| `_tmp_e34g_toleranz.py` | 6.029 | `e67305cafcf72d65b02c6ae59d29b43b0f79534ecd20626b7543d8fff9fd5ba1` |
| `_tmp_e34g_toleranz_out.txt` | 3.125 | `ba2052eac3049b947243d7b42d696e3d2594422a5ad2977a3ed4829a7decc241` |
| `_tmp_e34g_syntaxprobe.py` | 5.668 | `e4e25a40487d1543a76861c9df02bd14978800b5b302c2d13e0c2ce382f2ba8b` |
| `_tmp_e34g_syntaxprobe_out.txt` | 2.003 | `1f9dbc1513e96c136c1fb4bb0f4cac3b13cf90ec12754fae007a5d7b5d496278` |

---

## D · Renderer-Prüfung (Schritt 2, read-only) — `test/tmp_png_aug_sichttest.py`

Der Renderer liest die Segmente **generisch** aus `adapter.segmente`
(Z. 698/830) — die Kernpfade (G4_SEG, P9_BEITRAG, Niveau-Override) sind **ohne
Anpassung** V019-faehig. Es braucht jedoch folgende **Ergaenzungen**:

1. **Z. 147** `AdapterMode` um `"V019"` erweitern (Literal).
2. **Z. 135–141** `ADAPTER_V019` importieren.
3. **Z. 381–383** `_KONFIGURATIONEN["V019"] = KONFIGURATION_V019`.
4. **Neu `KONFIGURATION_V019`** (Werte siehe §E).
5. **Z. 428–431** Adapter-Wahl **erweiternd** (nicht ersetzend):
   ```python
   adapter: PhasenRegimeAdapter = (
       ADAPTER_V019 if KONF.mode == "V019"
       else (ADAPTER_V015 if KONF.g4_aktiv
             else (ADAPTER_V014 if KONF.k67_override_aktiv
                   else DEFAULT_ADAPTER)))
   ```
   Begruendung: V019 traegt ebenfalls `g4_aktiv=True` — die bestehende
   Bool-Kette wuerde sonst faelschlich `ADAPTER_V015` binden.
6. **Z. 462–475** `_V19`-Flag, `_NEU = _V17 or _V18 or _V19`,
   `_VTAG`/`_VER_TEXT` um V019-Zweig ("v0.24 (endogene Segmente A1/A2)").
7. **Z. 497–506** Engine-Guard: V019 nutzt die **V018-Engine**
   (`box_end == 644`); eigener Fail-Loud-Guard noetig.
8. **Z. 739** `assert len(V1) - len(V1_basis) in (2, 3)` → **reisst** fuer V019
   (23 − 14 = **9**). Braucht einen V019-Zweig (oder Generationsparameter).
9. **Fail-Loud-Sollwerte**, die neu gemessen werden **muessen** (nicht raten!):
   - `neu_basis_soll` (Z. 221) — adapter-abhaengige Neuzugangs-Menge,
   - `referenz_soll` (Z. 223) — entfallene v0.1-Trades,
   - `quartett_r_soll` (Z. 224) / `quartett_r_summe_soll`,
   - ggf. `alt_trades`-Einblendung.

**Nicht betroffen** (Engine- bzw. Default-Adapter-determiniert, unveraendert):
`ziel_v0_r=42.450970`, `ziel_v1_basis_trades=14`, `ziel_v1_basis_r=47.815697`,
`ziel_h1_trades=8`, `niveauwechsel_gesamt=66`, `niveauwechsel_baseline=205`.

---

## E · Vorgeschlagene `KONFIGURATION_V019` (Renderer, Entwurf)

```python
KONFIGURATION_V019: Final[RendererKonfiguration] = RendererKonfiguration(
    mode="V019",
    ausgabe_praefix="aug_sichttest_v019_",
    protokoll_datei="test/tmp_png_aug_sichttest_v019_out.txt",
    ziel_trades_gesamt=23,
    ziel_r_gesamt=82.614385,
    ziel_r_h1=38.919584,          # Invariante (bit-identisch zu V018)
    ziel_r_h2=43.694801,
    ziel_p9_beitrag=23.435111,    # P9 arretiert, unveraendert
    k67_override_aktiv=True,
    niveau_override_wert=K67_OVERRIDE_69_87,
    alt_trades_einblenden=True,
    quartett_bars=QUARTETT_V014_BARS,
    g4_aktiv=True,
    auflagen_aktiv=True,
    # --- Engine-Generation unveraendert (V018-Engine, BKZ/UTC) ------------
    ziel_v0_r=42.450970,
    ziel_v1_basis_trades=14,
    ziel_v1_basis_r=47.815697,
    ziel_h1_trades=8,
    ziel_delta_rb=34.798688,      # = 82.614385 - 47.815697
    # --- adapter-abhaengig: MESSEN, nicht raten (Punkt D.9) ----------------
    # neu_basis_soll=..., referenz_soll=..., quartett_r_soll=...,
    niveauwechsel_gesamt=66,
    niveauwechsel_baseline=205,
)
```

---

## F · Sollwerte V019 (gemessen, MIN77 + arretiertes P9)

| Kennzahl | Sollwert |
|---|---|
| gesamt | **+82,614385 R** (23 Setups) |
| H1 | **8 / +38,919584 R** — Invariante |
| H2 | **+43,694801 R** |
| ZIEL (A1/A2, 1021..1287) | **6 / +16,778809 R** |
| P9-Beitrag | +23,435111 R |
| `Q_stop` gesamt | 0,217 |
| `USD/Trade` | +0,9819 |
| aktive Phasen | 255 / 267 |

---

## G · Leitplanken (unveraendert)

Kein §75, kein S1, keine S2-Laeufe, keine UI-/Regressionstests. Adapter und
Engine bleiben bis zur ausdruecklichen Freigabe **bit-identisch**. Der
Renderer wird **getrennt** nach dem Adapter-Einbrand erweitert.

---

## H · Offene Entscheidungen (Textblock)

1. **Namenskonvention** — `V019` (numerisch, konsistent zu V01/V014…V018,
   `--mode`-Kanal bleibt einheitlich) oder `V019_ENDOGEN_77` (sprechender, aber
   bricht das Literal-/Dict-Konventionsmuster)?
2. **Freigabe Schritt 1** — Diff wie in §B freigegeben?
3. **`provenienz_toleranz_pct=1.0` explizit** setzen (auditklar) oder Default
   belassen (minimal-invasiv)?
4. **Renderer-Werte §D.9 / §E** (`neu_basis_soll`, `referenz_soll`,
   `quartett_r_soll`) — im separaten Renderer-Schritt messen? 
5. **Renderer-Zeitpunkt** — bestaetigt getrennt nach dem Adapter-Einbrand?

---

## ERRATUM E-34i (gemessen, 2026-09-11) — §B/§D sind **unvollstaendig**: V019 braucht das Zielzonen-Patchset ZP-4

**Status:** Der Adapter-Einbrand (§B) ist **korrekt und eingebrannt**
(Commit `68ac3af`, SHA `4f50b6b0…`). Dieses Erratum betrifft **§D**
(Renderer-Umfang) — der dort beschriebene „9-Stellen-Diff" ist **nicht
hinreichend**.

**Befund (E-34i, gemessen):** `ADAPTER_V019` am bestehenden Renderer-Patch
liefert **V018** (`17 / +65.835576`, `ZIEL 0 Trades`). Die Segmente A1/A2 sind
ohne die vier engine-seitigen Zielzonen-Regeln **inert**.

**Erforderlich sind vier zusaetzliche Patches** (Herkunft
`test/_tmp_e34_auto.py`), die im Renderer `patched_src` fehlen:

| Patch | Wirkung |
|---|---|
| `A_UEB1` | Ueberdehnungsschranke `_ueb(k)` = 0,80 segment-lokal |
| `A_VC` | `ex_hi/ex_lo` ab Segmentstart (`_q0 = seg.start_bar`) |
| `A_M6L` | M6-Blocker ueberspringt Nicht-`_lebt`-Linien in der Zone |
| `A_SB` | gesweepte Linie zaehlt in der Zone als aktiv |

plus Injektion `_zv`/`_ueb` und Wrapper `_reclaim_stufe` (0,80 lokal).
Mit diesen erscheint V019 exakt: `23 / +82.614385` (E-34i/2).

**Zweistufiges Gating (Pflicht):**
1. **Quelltext:** ZP-4 nur anwenden, wenn `mode == "V019"`
   (→ V01..V018 bleiben byte-identisch).
2. **Laufzeit:** `_zv(k)` **nur** wahr, wenn der *gebundene Adapter* V019 ist
   (`len(hook.segmente) > 1` / `hook is ADAPTER_V019`) — NICHT am globalen
   Modus, sonst faengt der V019-Lauf auch `V0`/`V1_basis` mit ein.

**Ehrliche Einschraenkung:** Ein Hazard-Test zeigt, dass **un-gegatet** sowohl
`DEFAULT_ADAPTER` (14 / +47.815697) als auch `ADAPTER_V015` (V018,
17 / +65.835576) in AUG numerisch **unveraendert** bleiben. Die Gate-Pflicht
ist damit **Vorsorge/Guarantee**, kein gemessener Bruch. Sie bleibt bestehen
(Zukunftssicherheit + strukturelle Korrektheit).

**Sollwerte (gemessen, E-34i/3):** `referenz_soll = ((980,73),)` ·
`neu_basis_soll` (ohne G4) = 9 Eintraege (siehe Handoff §W1) ·
`quartett_r_soll = ((903,4.119775),(980,9.987676),(981,2.695488),(1020,3.003157))`
· Summe `+19.806095`.

**Lehre:** V019 ist kein reiner Datensatz, sondern ein **gekoppeltes System**
aus Segmentgrenzen (Adapter) **und** Zielzonen-Engine-Regeln (Renderer).
Invariante 1 (Adapter engine-frei) bleibt formal gewahrt.
