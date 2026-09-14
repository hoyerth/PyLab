# -*- coding: utf-8 -*-
"""LF-Append: E-31 / E-31b (Diskrimination der Hybrid-Schliessung)."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"F:\Python\PyLab\test\SESSION_HANDOFF.md")
SOLL = "cf8d942b685af68ede4616c6ec5d7d610bcbb3acde2d7cb74d3656f6cd144f00"

vorher = P.read_bytes()
ist = hashlib.sha256(vorher).hexdigest()
assert ist == SOLL, f"Vorbedingung verletzt: {ist} != {SOLL}"
assert vorher.count(b"\r\n") == 0, "Datei ist nicht LF-clean"

TEXT = """
---

## Phase 2 / E-31 + E-31b (2026-09-11, o) — Diskrimination der Hybrid-Schliessung: **der Abstand trennt nicht, die Vorgeschichte trennt**

Auftrag (Anwender-Freigabe, Schritt 2): die Spanne zwischen der oberen
Schranke `T4b` (+115,10 R) und der unteren Schranke `T4c` (-52,61 R) auf
`L960` vermessen — **welche kausale Marktstruktur unterscheidet die
berechtigten Stopp-Outs von den getoeteten Gewinnern?**

Grundlage: Setup-Geometrien aus E-29 (`_tmp_e29_setups_*_b60.pkl`),
Kernstandard `geg960poc`. Reine Offline-Simulation ueber die Halb-Exit-Semantik
der Engine (Z. 1596-1647) — **keine** Engine- oder Adapter-Aenderung.
Pflichtmetriken (Urkunde E-30/I4): `USD/Trade`, **`dR Gewinner`**, `Q_stop`.

### K0 · Praezisierung gegenueber E-29/H8

E-29/H8 hat den Bruch-Exit als "Close jenseits der Einstiegskante" gemessen,
dabei aber den **Gesamt-R** des Trades durch den **Einzel-Halb-R** am
Bruch-Close ersetzt (und damit auch Haelften, die bereits natuerlich
geschlossen waren). E-31 schliesst **praezise je noch offener Haelfte**: eine
Haelfte, die TP1/TP2/SL bereits erreicht hat, behaelt ihr Ergebnis. Die
Zahlen weichen daher deutlich ab; die Richtung des Befunds nicht.

### K1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e31_break_disk.py` | `2537f2f01a24273ca20ce045008f2cbe718fc8a53c40195bfd9975165d69ede4` | 11.393 |
| `test/_tmp_e31b_mfe.py` | `7248d49e86c43278cc5fbd7fc17267782810439075ec69bb2a993fdd13932acb` | 7.601 |
| `test/_tmp_e31_break_disk_s2_out.txt` | `5a09019e5dfb193fc155c7e9e2af7f747977f928c8fc89b860c968244f1a8b01` | 5.254 |
| `test/_tmp_e31_break_disk_aug_out.txt` | `1b906a3205c69143405f892445c484332a227337d2feb15903eaddef2ffc0be5` | 5.252 |
| `test/_tmp_e31b_mfe_s2_out.txt` | `02c798e3041dce89168f1a4a811588d596877c7a5767cb1b1e2752cb34ff60d5` | 1.926 |
| `test/_tmp_e31b_mfe_aug_out.txt` | `b75c028e672c3b38aaf793f30d31b8610f162e34ec46b44f7674b2d7dd5951ef` | 1.934 |

Fidelity: der Simulator reproduziert die arretierte Basis bit-identisch
(S2 R +55,871446 · USD/Tr +0,0526 · AUG R +38,919584 · USD/Tr +1,4077).

### K2 · Antwort auf die Bruch-Kausalitaet: **beide Achsen sind untauglich**

Gemessen wurde die 2D-Matrix `n_consec ∈ {1,2,3}` konsekutive Closes ×
`d ∈ {0; 0,25; 0,5; 1,0} × ATR14(m)` (Abstand am **Bruch-Bar**, kausal).
Zusaetzlich die Variante `loss_only`.

S2 (`n = 271`, Basis USD/Tr +0,0526), Auszug:

| n | d [ATR] | R ges. | USD/Tr | Q_stop | Feuer | Prec | Rec | getoetet | dR Gew | dR Verl |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0,00 | +89,6785 | **+0,0684** | 0,299 | 254 | 0,917 | 0,987 | 8 | -40,59 | +74,40 |
| 1 | 0,25 | +66,9792 | +0,0583 | 0,391 | 246 | 0,915 | 0,953 | 7 | -39,32 | +50,42 |
| 1 | 0,50 | +55,0180 | +0,0530 | 0,498 | 216 | 0,921 | 0,843 | 5 | -31,51 | +30,66 |
| 1 | 1,00 | +55,3783 | +0,0524 | 0,616 | 147 | 0,918 | 0,572 | 2 | -11,26 | +10,76 |
| 2 | 0,00 | +59,0935 | +0,0566 | 0,491 | 146 | 0,911 | 0,564 | 6 | -36,14 | +39,36 |
| 2 | 0,50 | +42,8859 | +0,0489 | 0,594 | 79 | 0,899 | 0,301 | 5 | -29,96 | +16,97 |
| 3 | 0,50 | +60,8976 | +0,0571 | 0,642 | 48 | 0,979 | 0,199 | 1 | -6,65 | +11,68 |

**Auf S2 verbessert der naive Bruch-Exit (n=1, d=0) `USD/Trade` um +30 %**
(+0,0526 → +0,0684) und drueckt `Q_stop` auf 0,299. **Auf AUG kippt das
Vorzeichen:**

| | S2 | AUG |
|---|---|---|
| Basis USD/Tr | +0,0526 | +1,4077 |
| n=1, d=0 | **+0,0684** | **+1,0798** (−23 %) |
| Feuerungen | 254 / 271 | 3 / 8 |
| getoetete Gewinner | 8 | 1 |

**Der naive Bruch-Exit generalisiert nicht** — er ist eine Regime-Wette
("schliesst fast alles"), keine Diskrimination. Der Grund: er feuert auf S2
in **94 %** aller Trades, auf AUG in 38 %.

### K3 · Der entscheidende Negativbefund — der Abstand trennt NICHT

`P5` vergleicht die Bruch-Distanz der Basis-Gewinner gegen die der
Basis-Verlierer (n=1, d=0):

| Gruppe | p25 | median | p75 | Anteil < 0,25 ATR | Anteil < 0,5 ATR |
|---|---|---|---|---|---|
| Basis-Gewinner | 0,18 | **0,39** | 0,48 | 33,3 % | 76,2 % |
| Basis-Verlierer | 0,17 | **0,36** | 0,77 | 35,6 % | 60,9 % |

**Die Verteilungen sind praktisch identisch.** Kein Mindestabstand, keine
`n_consec`-Schwelle kann Gewinner von Verlierern trennen — die Antwort auf
die Anwenderfrage lautet: **weder 2 Closes noch ein ATR-Mindestabstand.**

### K4 · Der Diskriminator: **die Vorgeschichte (MFE vor dem Bruch)**

`P4`/`P6b` zeigen, wo der Unterschied wirklich liegt:

| Gruppe | n (mit Bruch) | Bruch nach … Bars (med) | Dist [ATR] (med) | **MFE vor Bruch (med)** | base_R med |
|---|---|---|---|---|---|
| Basis-Gewinner | 21 | **84,0** | 0,39 | **2,75 R** | +2,81 |
| Basis-Verlierer | 233 | **1,0** | 0,36 | **0,23 R** | −1,00 |

**Nicht "wie weit bricht es", sondern "hat der Trade vorher gearbeitet"
diskriminiert.** Verlierer brechen nach **1 Bar** mit MFE 0,23 R; Gewinner
brechen nach **84 Bars** mit MFE 2,75 R.

### K5 · E-31b — die MFE-bedingte Schliessung generalisiert

Regel: Bruch schliesst **nur**, wenn `MFE vor dem Bruch < mfe_cap R`.

S2 (`n = 271`, Basis +0,0526):

| mfe_cap | R ges. | USD/Tr | ATR/Tr | Q_stop | Feuer | Skip | Prec | Rec | getoetet | **dR Gew** | dR Verl |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,25 | +74,1463 | +0,0633 | +0,4991 | 0,520 | 121 | 133 | 0,967 | 0,496 | 4 | −17,77 | +36,05 |
| 0,50 | +82,4036 | +0,0672 | +0,5473 | 0,472 | 142 | 112 | 0,972 | 0,585 | 4 | **−17,77** | +44,30 |
| **0,75** | **+89,3250** | **+0,0727** | **+0,5952** | **0,435** | 158 | 96 | 0,975 | 0,653 | **4** | **−17,77** | +51,23 |
| 1,00 | +80,7729 | +0,0698 | +0,5794 | 0,395 | 175 | 79 | 0,966 | 0,716 | 6 | −33,17 | +58,07 |
| 1,50 | +84,2742 | +0,0713 | +0,5903 | 0,362 | 196 | 58 | 0,964 | 0,801 | 7 | −35,83 | +64,23 |
| aus | +89,6785 | +0,0684 | +0,5717 | 0,299 | 254 | 0 | 0,917 | 0,987 | 8 | −40,59 | +74,40 |

AUG (`n = 8`, Basis +1,4077):

| mfe_cap | R ges. | USD/Tr | Q_stop | Feuer | Skip | getoetet | dR Gew | dR Verl |
|---|---|---|---|---|---|---|---|---|
| **0,25–1,25** | **+39,7798** | **+1,4330** | 0,000 | 1 | 2 | **0** | **+0,00** | +0,86 |
| 1,50–3,00 | +32,7511 | +1,0798 | 0,000 | 2 | 1 | 1 | −7,03 | +0,86 |
| aus | +32,7511 | +1,0798 | 0,000 | 3 | 0 | 1 | −7,03 | +0,86 |

**Der MFE-Cap repariert genau den AUG-Schaden des naiven Bruchs**
(+1,0798 → +1,4330). Verdikt:

1. **S2: +0,0526 → +0,0727 USD/Trade (+38 %)** bei `Q_stop` 0,435 ≤ 0,75.
2. **`dR Gewinner` halbiert sich: −40,59 → −17,77 R** (Cap 0,75).
3. **Getoetete Gewinner: 8 → 4.**
4. **AUG: keine Verschlechterung** (+1,4330 vs +1,4077), `dR Gewinner = 0`.
5. Die Regel ist **kausal** (MFE bis zum Vortag) und **generalisierend** —
   anders als der naive Bruch (K2).

**Ehrliche Einschraenkung:** auf AUG feuert der Cap in nur **1 von 8** Trades;
der AUG-"Zugewinn" (+0,0253 USD/Tr) ruht auf einem einzigen Trade. AUG ist
damit **neutral, nicht bestaetigend**. Die S2-Verbesserung dagegen ist breit
(158 Feuerungen, `dR Verl +51,23`).

### K6 · Abstand zur oberen Schranke

| | R | USD/Tr |
|---|---|---|
| Basis | +55,8714 | +0,0526 |
| **E-31b, Cap 0,75** | **+89,3250** | **+0,0727** |
| `T4b` obere Schranke (E-29, ex post) | +115,10 | +0,0836 |

Die Regel schliesst **~65 %** der Luecke zur ex-post-idealen Schranke
((0,0727−0,0526)/(0,0836−0,0526) = 0,0201/0,0310) und **~78 %** in `R`.

### K7 · Offene Entscheidungen (Textblock)

1. **Parameterwahl `mfe_cap`.** S2 bevorzugt 0,75 (bester `USD/Trade` und
   bester `dR Gewinner`), AUG ist im Band 0,25–1,25 indifferent.
   Vorgeschlagen wird **`mfe_cap = 0,75 R`** (S2-optimum mit maximalem
   Gewinnerschutz) — alternativ `1,0 R` als runde, PineScript-taugliche Zahl
   (S2: +0,0698, `dR Gew −33,17`). Zu entscheiden.
2. **AUG-Evidenz ist duenn** (1 Feuerung). Zu klaeren, ob vor dem Einbrand
   eine dritte Datenreihe (oder eine H1/H2-getrennte AUG-Auswertung)
   herangezogen werden soll.
3. **Interaktion mit `D1`.** Die Regel drueckt `Q_stop` deutlich unter 0,75
   (0,435). Da `Q_stop` nur Ausschluss-Gate ist, darf das **nicht** als
   Begruendung zaehlen — massgeblich ist `USD/Trade` (+0,0727) und
   `dR Gewinner` (−17,77).
4. **Naechster Schritt.** Formulierung als Schliesskriterium im Vertragsentwurf
   (`SchliessKriterium`) inkl. Type Hints. Vorher ist zu entscheiden, ob die
   Bedingung als **Regime-Ende** (Zustandsautomat, Block A) oder als
   **Stop-Variante** (Engine-seitig) implementiert wird — die Wirkung ist
   identisch, die Verdrahtung nicht.

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache, keine S1-Untersuchung.**
"""

neu = vorher.decode("utf-8") + TEXT
P.write_text(neu, encoding="utf-8", newline="\n")
n_b = P.read_bytes()
assert n_b.count(b"\r\n") == 0, "CRLF nach Append!"
print(f"vorher  {len(vorher)} B  {ist}")
print(f"nachher {len(n_b)} B  {hashlib.sha256(n_b).hexdigest()}")
print(f"delta   {len(n_b) - len(vorher)} B")
