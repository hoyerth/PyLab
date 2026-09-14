# -*- coding: utf-8 -*-
"""Append 'E-32' an test/SESSION_HANDOFF.md (Vorbedingung: SHA d0f293a5...)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "test" / "SESSION_HANDOFF.md"
VORBEDINGUNG = "d0f293a5b07b953ff4df76a5b5bb520d121a89eb872153c7f99347ce3dddca3c"

roh = HANDOFF.read_bytes()
ist = hashlib.sha256(roh).hexdigest()
print("Vorbedingung SHA256:", VORBEDINGUNG)
print("aktuell          :", ist)
if ist != VORBEDINGUNG:
    print("ABBRUCH: Vorbedingung nicht erfuellt.")
    sys.exit(1)

ABSCHNITT = """
## Phase 2 / E-32 (2026-09-11, p) — Robustheit des MFE-Bruch-Filters: **kausal bestaetigt, regimestabil ab 0,75 R, AUG-Schranke bei 1,50 R**

Auftrag (Anwender-Freigabe, Phase 1): Stresstest des in E-31b gefundenen
MFE-Bruch-Filters — `mfe_cap` in `[0,25 .. 2,0] R` **getrennt nach
Halbierungen UND nach Volatilitaets-Regimen**, dazu die Kausalitaets-
Verifikation (MFE strikt aus abgeschlossenen Bars, ohne Look-ahead).
Grundlage: Setup-Geometrien aus E-29 (`_tmp_e29_setups_*_b60.pkl`),
Kernstandard `geg960poc`. Reine Offline-Simulation ueber die Halb-Exit-Semantik
der Engine (Z. 1596-1647) — **keine** Engine- oder Adapter-Aenderung.
Pflichtmetriken (Urkunde E-30/I4): `USD/Trade`, **`dR Gewinner`**; `Q_stop`
nur deskriptiv.

### L1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e32_robust.py` | `f86d83fa932ad1cd10f7d06a89b8d678f30930b3b9429c8a0ff9150aa0fc815b` | 10.978 |
| `test/_tmp_e32_robust_s2_out.txt` | `ce159bc56f8f904a7f69fceabe4743f776c94d07a90ee8af3b1fe3ee1bf201b4` | 8.094 |
| `test/_tmp_e32_robust_aug_out.txt` | `7f32a5d64aef7ef37225b63cc226a1cd6bf6c89371056eaee3957b20b17150cf` | 8.000 |

Fidelity: der Simulator reproduziert die arretierten Basen bit-identisch —
S2 `USD/Tr +0,0526` (n = 271), AUG `+1,4077` (n = 8).

### L2 · Kausalitaet — **bestaetigt**

1. **Monotonie** der MFE-Reihe je Trade: fuer alle 271 (S2) bzw. 8 (AUG)
   Trades nicht-fallend (`True`).
2. **Unabhaengige Neuberechnung** von `mfes[j-1]` ausschliesslich aus den
   Bars `entry_bar .. Bruch-Bar-1`: **0 Abweichungen** von 153 (S2) bzw. 2
   (AUG) geprueften Trades.
3. **Look-ahead-Gegenprobe** (MFE absichtlich inkl. Bruch-Bar, also
   verletzend):

| | kausal USD/Tr | Look-ahead USD/Tr | Differenz | Feuer kausal/LA |
|---|---|---|---|---|
| S2 | +0,0727 | +0,0723 | **−0,0003** | 158 / 157 |
| AUG | +1,4330 | +1,4330 | +0,0000 | 1 / 1 |

Der Zeitpunkt ist damit **messbar**: in S2 verschiebt der Look-ahead genau
**einen** Trade und senkt `USD/Tr` um 0,0003; in AUG (eine Feuerung) ist die
Differenz null. Der **strukturelle** Nachweis (Punkte 1-2) traegt die
Kausalitaet; die Gegenprobe belegt nur, dass eine Verletzung ueberhaupt
sichtbar waere. **Der Filter ist strikt kausal.**

### L3 · Stresstest nach Halbierungen (1.1a)

**GESAMT (n = 271; Basis +0,0526 USD/Tr):**

| mfe_cap | USD/Tr | Delta | ATR/Tr | Q_stop | Feuer | dR Gew | dR Verl | getoetet |
|---|---|---|---|---|---|---|---|---|
| 0,25 | +0,0633 | +0,0107 | 0,4991 | 0,520 | 121 | −17,77 | +36,05 | 4 |
| 0,50 | +0,0672 | +0,0146 | 0,5473 | 0,472 | 142 | −17,77 | +44,30 | 4 |
| **0,75** | **+0,0727** | **+0,0201** | **0,5952** | **0,435** | 158 | **−17,77** | +51,23 | **4** |
| 1,00 | +0,0698 | +0,0173 | 0,5794 | 0,395 | 175 | −33,17 | +58,07 | 6 |
| 1,25 | +0,0701 | +0,0175 | 0,5742 | 0,380 | 187 | −35,83 | +61,09 | 7 |
| 1,50 | +0,0713 | +0,0187 | 0,5903 | 0,362 | 196 | −35,83 | +64,23 | 7 |
| 2,00 | +0,0685 | +0,0159 | 0,5630 | 0,339 | 214 | −39,97 | +67,13 | 8 |
| aus | +0,0684 | +0,0158 | 0,5717 | 0,299 | 254 | −40,59 | +74,40 | 8 |

**H1 (n = 232; Basis +0,0186):**

| mfe_cap | USD/Tr | Delta | ATR/Tr | Q_stop | Feuer | dR Gew | getoetet |
|---|---|---|---|---|---|---|---|
| 0,25 | +0,0283 | +0,0097 | 0,3187 | 0,491 | 107 | −17,77 | 4 |
| 0,50 | +0,0321 | +0,0135 | 0,3696 | 0,440 | 126 | −17,77 | 4 |
| **0,75** | **+0,0353** | **+0,0168** | **0,4085** | **0,409** | 136 | **−17,77** | **4** |
| 1,00 | +0,0320 | +0,0135 | 0,3900 | 0,362 | 153 | −33,17 | 6 |
| 1,25 | +0,0321 | +0,0135 | 0,3827 | 0,349 | 164 | −35,83 | 7 |
| 1,50 | +0,0329 | +0,0144 | 0,3981 | 0,332 | 171 | −35,83 | 7 |
| 2,00 | +0,0295 | +0,0109 | 0,3648 | 0,310 | 187 | −39,97 | 8 |
| aus | +0,0286 | +0,0101 | 0,3707 | 0,276 | 219 | −40,59 | 8 |

**H2 (n = 39; Basis +0,2549):**

| mfe_cap | USD/Tr | Delta | ATR/Tr | Q_stop | Feuer | dR Gew | getoetet |
|---|---|---|---|---|---|---|---|
| 0,25 | +0,2715 | +0,0166 | 1,5727 | 0,692 | 14 | +0,00 | 0 |
| 0,50 | +0,2762 | +0,0213 | 1,6049 | 0,667 | 16 | +0,00 | 0 |
| **0,75** | **+0,2948** | **+0,0399** | 1,7058 | 0,590 | 22 | **+0,00** | **0** |
| 1,00 | +0,2948 | +0,0399 | 1,7058 | 0,590 | 22 | +0,00 | 0 |
| 1,25 | +0,2962 | +0,0413 | 1,7133 | 0,564 | 23 | +0,00 | 0 |
| 1,50 | +0,2994 | +0,0445 | 1,7336 | 0,538 | 25 | +0,00 | 0 |
| 2,00 | +0,3006 | +0,0457 | 1,7424 | 0,513 | 27 | +0,00 | 0 |
| aus | +0,3048 | +0,0499 | 1,7672 | 0,436 | 35 | +0,00 | 0 |

**H2-Beobachtung:** im H2 verschmaelert der Filter **keinen einzigen
Gewinner** (`dR Gew = 0,00` ueber alle Caps) — der gesamt beobachtete
`dR Gew −17,77` stammt vollstaendig aus H1. Die H2-Verbesserung ist rein
verlustseitig (`dR Verl +5,48` bei Cap 0,75).

### L4 · Stresstest nach Volatilitaets-Regimen (1.1b)

Tercile von `ATR14(m)/Entry` (dimensionslos): `q1 = 0,1912 %`,
`q2 = 0,3008 %` (S2).

**T1 ruhig (n = 90; Basis −0,0085):**

| mfe_cap | USD/Tr | Delta | Q_stop | Feuer | dR Gew | getoetet |
|---|---|---|---|---|---|---|
| 0,25 | −0,0106 | −0,0022 | 0,444 | 43 | −16,56 | 3 |
| 0,50 | −0,0086 | −0,0001 | 0,411 | 49 | −16,56 | 3 |
| 0,75 | −0,0066 | +0,0019 | 0,378 | 54 | −16,56 | 3 |
| 1,00 | −0,0008 | +0,0077 | 0,289 | 63 | −16,56 | 3 |
| 1,25 | −0,0030 | +0,0055 | 0,289 | 69 | −19,22 | 4 |
| 1,50 | −0,0012 | +0,0073 | 0,256 | 72 | −19,22 | 4 |
| 2,00 | +0,0004 | +0,0089 | 0,233 | 75 | −19,22 | 4 |
| aus | +0,0043 | +0,0128 | 0,189 | 87 | −18,69 | 4 |

**T2 mittel (n = 91; Basis +0,0555):**

| mfe_cap | USD/Tr | Delta | Q_stop | Feuer | dR Gew | getoetet |
|---|---|---|---|---|---|---|
| 0,25 | +0,0787 | +0,0232 | 0,527 | 42 | +0,00 | 0 |
| 0,50 | +0,0832 | +0,0277 | 0,462 | 50 | +0,00 | 0 |
| **0,75** | **+0,0896** | **+0,0341** | 0,418 | 56 | **+0,00** | **0** |
| 1,00 | +0,0835 | +0,0280 | 0,385 | 62 | −8,18 | 1 |
| 1,25 | +0,0845 | +0,0290 | 0,374 | 64 | −8,18 | 1 |
| 1,50 | +0,0845 | +0,0290 | 0,374 | 65 | −8,18 | 1 |
| 2,00 | +0,0739 | +0,0184 | 0,341 | 74 | −12,33 | 2 |
| aus | +0,0768 | +0,0212 | 0,319 | 85 | −11,68 | 2 |

**T3 volatil (n = 90; Basis +0,1106):**

| mfe_cap | USD/Tr | Delta | Q_stop | Feuer | dR Gew | getoetet |
|---|---|---|---|---|---|---|
| 0,25 | +0,1215 | +0,0109 | 0,589 | 36 | −1,21 | 1 |
| 0,50 | +0,1268 | +0,0161 | 0,544 | 43 | −1,21 | 1 |
| **0,75** | **+0,1348** | **+0,0242** | 0,511 | 48 | **−1,21** | **1** |
| 1,00 | +0,1266 | +0,0160 | 0,511 | 50 | −8,43 | 2 |
| 1,25 | +0,1286 | +0,0180 | 0,478 | 54 | −8,43 | 2 |
| 1,50 | +0,1303 | +0,0197 | 0,456 | 59 | −8,43 | 2 |
| 2,00 | +0,1310 | +0,0204 | 0,444 | 65 | −8,43 | 2 |
| aus | +0,1239 | +0,0133 | 0,389 | 82 | −10,23 | 2 |

### L5 · Robustheitskennzahl — Vorzeichen-Stabilitaet ueber alle 3 Regime (1.1c)

| mfe_cap | T1 ruhig | T2 mittel | T3 volatil | alle drei > 0? | min Delta |
|---|---|---|---|---|---|
| 0,25 | −0,0022 | +0,0232 | +0,0109 | **nein** | −0,0022 |
| 0,50 | −0,0001 | +0,0277 | +0,0161 | **nein** | −0,0001 |
| 0,75 | +0,0019 | +0,0341 | +0,0242 | ja | +0,0019 |
| 1,00 | +0,0077 | +0,0280 | +0,0160 | ja | **+0,0077** |
| 1,25 | +0,0055 | +0,0290 | +0,0180 | ja | +0,0055 |
| 1,50 | +0,0073 | +0,0290 | +0,0197 | ja | +0,0073 |
| 2,00 | +0,0089 | +0,0184 | +0,0204 | ja | +0,0089 |
| aus | +0,0128 | +0,0212 | +0,0133 | ja | +0,0128 |

Die Caps 0,25/0,50 **kippen im ruhigen Regime ins Negative** (zu eng: sie
schneiden die wenigen, langsam aufgebauten Gewinner ab, ohne die Verluste
entsprechend zu mildern). Ab 0,75 R ist das Vorzeichen in **allen** drei
Regimen stabil.

### L6 · Schwellenvergleich 0,75 vs 1,00 ueber alle Schnitte (1.1d)

| Schnitt | USD/Tr 0,75 | USD/Tr 1,00 | besser | dR Gew 0,75 | dR Gew 1,00 |
|---|---|---|---|---|---|
| gesamt | +0,0727 | +0,0698 | **0,75** | −17,77 | −33,17 |
| H1 | +0,0353 | +0,0320 | **0,75** | −17,77 | −33,17 |
| H2 | +0,2948 | +0,2948 | gleich | +0,00 | +0,00 |
| ruhig (T1) | −0,0066 | −0,0008 | **1,00** | −16,56 | −16,56 |
| mittel (T2) | +0,0896 | +0,0835 | **0,75** | +0,00 | −8,18 |
| volatil (T3) | +0,1348 | +0,1266 | **0,75** | −1,21 | −8,43 |

### L7 · AUG-Stresstest (n = 8; Basis +1,4077)

| mfe_cap | USD/Tr | Delta | Q_stop | Feuer | dR Gew | getoetet |
|---|---|---|---|---|---|---|
| **0,25–1,25** | **+1,4330** | **+0,0254** | 0,000 | 1 | **+0,00** | **0** |
| 1,50 | +1,0798 | **−0,3278** | 0,000 | 2 | −7,03 | 1 |
| 2,00 | +1,0798 | −0,3278 | 0,000 | 2 | −7,03 | 1 |
| aus | +1,0798 | −0,3278 | 0,000 | 3 | −7,03 | 1 |

**AUG setzt eine harte Obergrenze:** im Band `0,25–1,25 R` ist AUG
**indifferent** (genau eine Feuerung, `dR Gew = 0`). Ab `1,50 R` kippt AUG
von +1,4330 auf +1,0798 (−0,3278 USD/Tr) und **toetet einen Gewinner**
(im volatilen T3 allein: −0,9418 USD/Tr). AUG-H2 ist leer (n = 0); AUG ist
faktisch H1-only. Die AUG-Einschraenkung aus E-31b (nur 1 Feuerung) bleibt
bestehen: AUG ist **neutral, nicht bestaetigend**.

### L8 · Verdikt

1. **Kausalitaet bestaetigt** (Monotonie, unabhaengige Neuberechnung ohne
   Abweichung, Look-ahead-Gegenprobe sichtbar).
2. **Der Filter generalisiert ueber die Volatilitaets-Regime ab 0,75 R** —
   vorzeichenstabil in T1/T2/T3. 0,25/0,50 R sind zu eng (T1 negativ).
3. **0,75 R = Aggregat-Optimum** (gesamt +0,0727 · H1 +0,0353 · T2 · T3)
   **und** bester Gewinnerschutz (`dR Gew −17,77`, 4 getoetet).
4. **1,00 R = regimestabilstes Optimum** (max `min Delta` = +0,0077 unter
   den engen Caps). Preis: Verdopplung der Gewinner-Schmaelerung (−33,17)
   und 6 statt 4 getoetete Gewinner.
5. **AUG-Bindung:** `mfe_cap < 1,50 R`. Das ratifizierte 1,00 R liegt sicher,
   0,75 R ebenfalls; jede spaetere Erhoehung ueber 1,25 R ist AUG-verboten.
6. **Ehrliche Einschraenkung:** die T1-Absolutwerte sind winzig (Basis
   −0,0085 USD/Tr); die T1-Vorzeichen entscheiden in der dritten Dezimale und
   sind **kein Handelshebel**, sondern ein Stabilitaetskriterium.
7. Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`,
   kein §75, kein S1-Cache, keine S1-Untersuchung.**

### L9 · Offene Entscheidungen (Textblock)

1. **`mfe_cap` 0,75 vs 1,00.** Das Aggregat spricht fuer **0,75** (besserer
   `USD/Tr` und halbierter Gewinnerschaden), die Regime-Stabilitaet fuer
   **1,00** (groesseres `min Delta`). Die Ratifikation (1,00 = Standard,
   0,75 = Benchmark) wird von E-32 **nicht widerlegt**; die Spannung ist jetzt
   exakt dokumentiert. Zu entscheiden, ob der Standard bei 1,00 bleibt.
2. **AUG-Obergrenze** (`< 1,50 R`) ist ab jetzt bindend fuer jede
   Parameteraenderung.
3. **Offen:** H1/H2-getrennte AUG-Auswertung (Anwender-Entscheidung #2) —
   AUG hat H1 8 / H2 0, sie ist faktisch H1-only; **S1-Konflikt** (Vorgabe
   "keine S1" vs. "S1-Scan vorziehen") weiterhin ungeloest.
4. **Naechster Schritt unveraendert:** Typisierung als `SchliessKriterium` im
   Vertragsentwurf (`test/_tmp_vd_vertrag_entwurf.py`) inkl. Type Hints;
   danach die Verdrahtungsentscheidung (Engine-Stop vs. Block A).

"""

with HANDOFF.open("a", encoding="utf-8", newline="\n") as fh:
    fh.write(ABSCHNITT)

neu = HANDOFF.read_bytes()
print("neue Bytes  :", len(neu))
print("neue SHA256 :", hashlib.sha256(neu).hexdigest())
txt = HANDOFF.read_text(encoding="utf-8")
print("LF:", txt.count("\n"), "CRLF:", txt.count("\r\n"))
print("ENDE append ok")
