# -*- coding: utf-8 -*-
"""LF-Append: E-30/S1 (Zielabstand + TP1-Deckelung) an SESSION_HANDOFF.md."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"F:\Python\PyLab\test\SESSION_HANDOFF.md")
SOLL = "48e893f7c5d06ff20e89643d70e1ac39b21122b70c177e7925255bf9f496f928"

vorher = P.read_bytes()
ist = hashlib.sha256(vorher).hexdigest()
assert ist == SOLL, f"Vorbedingung verletzt: {ist} != {SOLL}"
assert vorher.count(b"\r\n") == 0, "Datei ist nicht LF-clean"

TEXT = """
---

## Phase 2 / E-30 Schritt 1 (2026-09-11, n) — Zielabstand & TP1-Deckelung: **auch der Ziel-Hebel ist falsifiziert**

Auftrag (Anwender-Freigabe): (1) Zielabstands-Geometrie vermessen,
(2) pruefen, welcher **TP1-Deckel** die 18 H2-Trades mit `MFE >= 1 R`
monetarisiert haette, ohne das TP2-Makroziel anzutasten. Read-only; die
Messung laeuft vollstaendig ueber die in E-29 gesicherten Setup-Geometrien
(`_tmp_e29_setups_*_b60.pkl`) und die identische Halb-Exit-Semantik der
Engine (Z. 1596-1647) — **keine** Engine- oder Adapter-Aenderung.

### I0 · Reproduktions-Fidelity

Der Offline-Simulator reproduziert die arretierte Bilanz **bit-identisch**:
S2 `0,5·Σr1 + 0,5·Σr2 = 0,5·(+49,004) + 0,5·(+62,739) = +55,871` — exakt der
E-28/E-29-Wert. AUG analog `+38,920`. Die Ziel-Erkennung deckt sich mit den
von der Engine gespeicherten `grund1`: **201 SL / 70 TP1** (S2), **1 SL / 7 TP1**
(AUG). **ENDE-Exits treten in der armierten Konfiguration nicht auf (0)** —
bei ~1 ATR Stop wird praktisch immer entweder der Stop oder das Ziel
beruehrt.

### I1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e30_tp1.py` | `112c8e9c4d3b08f56b875319b9f5f07acfd4bcd79fca91eecaeb7a111bc4b070` | 13.041 |
| `test/_tmp_e30_tp1_s2_out.txt` | `03e5a62d550faac8a3b9a6065731d0f181183b64ab043f78d5cc6ce47392405e` | 6.664 |
| `test/_tmp_e30_tp1_aug_out.txt` | `02e7ebeec4e00bfc7ed59f3a4a5eb08882a5f52274004d47bae7f26cb695efb4` | 6.082 |

### I2 · Z1 — Zielabstaende

| Gruppe | Groesse | min | p25 | **median** | p75 | p90 | max |
|---|---|---|---|---|---|---|---|
| gesamt | d TP1 [R] | 0,01 | 1,87 | 6,72 | 13,41 | 22,18 | 74,32 |
| gesamt | d TP1 [ATR] | 0,01 | 3,05 | 9,72 | 19,09 | 26,70 | 45,03 |
| gesamt | d TP1 [%] | 0,00 | 0,78 | 2,17 | 4,47 | 7,61 | 14,83 |
| gesamt | d TP2 [R] | 3,70 | 14,03 | 20,20 | 28,88 | 42,74 | 121,85 |
| **H1** | d TP1 [R] | 0,01 | 1,62 | **5,86** | 11,94 | 18,65 | 48,06 |
| **H2** | d TP1 [R] | 0,15 | 5,82 | **13,29** | 29,18 | 44,40 | 74,32 |
| H2 | d TP1 [ATR] | 0,22 | 6,81 | **18,90** | 24,27 | 29,11 | 45,03 |
| H2 | d TP1 [%] | 0,04 | 2,83 | **5,95** | 8,46 | 9,50 | 10,56 |
| H2 | d TP2 [R] | 13,29 | 20,56 | **32,72** | 51,60 | 65,64 | 121,85 |
| H2 | risk [ATR] | 0,32 | 0,68 | **0,96** | 1,84 | 2,07 | 3,12 |

Der H2-Befund ist bestaetigt und praezisiert: **TP1 liegt bei 13,29 R /
18,90 ATR / 5,95 % Kursweg**, waehrend der Stop nur **0,96 ATR** entfernt ist.
Das Verhaeltnis Ziel:Stop betraegt in H2 also ≈ **20 : 1**.

### I3 · Z2 — MFE-Anatomie der Stop-Outs

| Haelfte | n_Stop | MFE >= 1 R | MFE >= 2 R | MFE median | Rueckgabe median |
|---|---|---|---|---|---|
| gesamt | 201 | 86 | 44 | 0,69 | 1,69 |
| H1 | 169 | 68 | 35 | 0,58 | 1,58 |
| **H2** | **32** | **18** | **9** | **1,16** | **2,16** |

Die 18 H2-Trades mit `MFE >= 1 R` sind damit **nicht** als Gruppe von
"Gewinnern, die man haette retten muessen" bestaetigt: der Median-MFE aller
32 H2-Stop-Outs liegt bei **1,16 R** — die meisten liefen also knapp 1 R weit
und drehten dann. Das genuegt, um die Break-Even-Falle (E-29/H7) zu
erklaeren, aber es genuegt **nicht** fuer einen profitablen Teil-Exit.

### I4 · Z3 — TP1-Deckelung: **jeder Deckel verschlechtert `USD/Trade`**

Pflichtmetriken (Anwender-Vorgabe). `dR Gewinner` = R-Summe der Aenderung auf
den Basis-Gewinnern; `dR Verlier` analog auf den Basis-Verlierern.

S2 (`n = 271`, Basis `USD/Tr = +0,0526`):

| Variante | R ges. | USD/Tr | Q_stop | getoetet | gerettet | **dR Gewinner** | dR Verlier | USD-Delta |
|---|---|---|---|---|---|---|---|---|
| **BASIS** | +55,87145 | **+0,0526** | 0,742 | 0 | 0 | 0,000 | 0,000 | 0,0000 |
| Cap_R = 0,50 R | +25,36122 | +0,0318 | 0,339 | 15 | 0 | **-112,137** | +81,626 | **-5,6232** |
| Cap_R = 1,00 R | +37,23478 | +0,0382 | 0,424 | 14 | 2 | **-104,637** | +86,000 | **-3,8844** |
| Cap_R = 1,25 R | +35,98478 | +0,0353 | 0,476 | **0** | 72 | **-100,887** | +81,000 | **-4,6816** |
| Cap_R = 1,50 R | +38,65852 | +0,0356 | 0,506 | **0** | 64 | -97,213 | +80,000 | -4,6045 |
| Cap_R = 2,00 R | +31,30330 | +0,0323 | 0,579 | **0** | 44 | -90,568 | +66,000 | -5,4946 |
| Cap_R = 4,00 R | +31,98029 | +0,0338 | 0,675 | 0 | 18 | -68,891 | +45,000 | -5,0957 |
| Cap_R = 8,00 R | +44,78918 | +0,0397 | 0,716 | 0 | 7 | -42,582 | +31,500 | -3,4762 |
| Cap_ATR = 1,50 | +36,98218 | +0,0379 | 0,450 | 7 | 40 | -103,702 | +84,813 | -3,9848 |
| Cap_ATR = 2,00 | +35,79321 | +0,0361 | 0,509 | 3 | 43 | -98,678 | +78,600 | -4,4747 |

AUG (`n = 8`, Basis `USD/Tr = +1,4077`) verhaelt sich **noch schaerfer**: in
**jeder** Zeile ist `dR Verlier = 0` (kein einziger Verlierer wird gerettet)
und `dR Gewinner < 0`; das beste Cap (`Cap_R = 8 R`) bleibt mit `+1,3753`
unter der Basis.

**Kernaussage I4: In *keinem* der 21 getesteten Deckel-Werte erreicht
`USD/Trade` die Basis.** Der Deckel schmaelert die Gewinner immer staerker,
als er Verlierer rettet (S2: -112 gegen +82 R; AUG: reine Zerstoerung).

**Methodik-Erweiterung (bindend, aus I4):** Der Sign-Flip-Zaehler
"getoetete Gewinner" ist **zu grob**. Bei `Cap_R >= 1,25 R` meldet er **0**
getoetete Gewinner — und trotzdem verliert die Variante **-4,68 USD**. Die
richtige Pflichtmetrik ist **`dR Gewinner`** (R-Schmaelerung auf den
Basis-Gewinnern), nicht nur der Vorzeichenwechsel.

### I5 · Z4 — Dekomposition: **beide Haelften tragen, keine ist ein Verlusttraeger**

| Gruppe | n | H1 TP | H1 SL | H2 TP | H2 SL | Σ r1 | Σ r2 | 0,5·Σ(r1+r2) |
|---|---|---|---|---|---|---|---|---|
| gesamt | 271 | **70** | 201 | **20** | 251 | +49,004 | +62,739 | +55,871 |
| H1 | 232 | 63 | 169 | 17 | 215 | -2,844 | +27,096 | +12,126 |
| H2 | 39 | 7 | 32 | 3 | 36 | **+51,849** | +35,642 | +43,745 |

Damit ist die Arbeitsannahme aus Z5 ("die zweite Haelfte ist ein
Verlusttraeger") fuer die arretierte Konfiguration **widerlegt**: die
TP2-Haelfte (Gegenkante) traegt mit **+62,74 R sogar mehr** bei als die
TP1-Haelfte (POC, +49,00 R). Der Grund liegt im Lotterieprofil: TP2 wird nur
in **20 von 271** Faellen erreicht (7,4 %), dann aber mit grossem Hebel
(Median-`d TP2` = 20,20 R); TP1 wird in **70 von 271** Faellen erreicht
(25,8 %). **H2 wird von der TP1-Haelfte dominiert** (+51,85 der +43,75 R
Beitrag) — genau die Haelfte, die der Deckel kaputtmachen wuerde.

### I6 · Z5 — Gewichts-Sweep `w1`: monoton, aber **nicht zulassungsfaehig**

`w1 = tp1_anteil_pct / 100` (TP-Ziele unveraendert):

| w1 | S2 R ges. | S2 USD/Tr | S2 Q_stop | AUG R ges. | AUG USD/Tr | AUG Q_stop |
|---|---|---|---|---|---|---|
| 0,00 | +62,73853 | +0,0656 | **0,926** | +47,13183 | +1,6606 | 0,375 |
| 0,25 | +59,30499 | +0,0591 | 0,742 | +43,02571 | +1,5341 | 0,125 |
| **0,50 (arretiert)** | **+55,87145** | **+0,0526** | **0,742** | **+38,91958** | **+1,4077** | **0,125** |
| 0,75 | +52,43791 | +0,0461 | 0,742 | +34,81346 | +1,2812 | 0,125 |
| 1,00 | +49,00436 | +0,0395 | 0,742 | +30,70734 | +1,1547 | 0,125 |

Die Wirkung ist **monoton in `w1`** (je weniger Gewicht auf der nahen
TP1-Haelfte, desto besser `USD/Trade`). Zwei Gruende, sie **nicht** zu
verfolgen:

1. **`w1 = 0` verletzt `D1`** (`Q_stop = 0,926 > 0,75`). Der beste USD-Wert
   liegt genau auf der Grenze des zulaessigen Bereichs — ein Warnsignal,
   nicht eine Empfehlung.
2. **`tp1_anteil_pct` ist AUG-kritisch** — wie `num_bins` (E-29/H4), nicht wie
   die Lokalisierung. Die Aenderung 50 → 25 verschiebt den August-Anker von
   `+38,91958` auf `+43,02571`, d. h. V018 wird **nicht** geschuetzt. Eine
   Invarianz gibt es hier nicht.

Hinzu kommt: der Effekt haengt in S2 an **20** und in AUG an **5**
TP2-Treffern. Das ist eine statistisch nicht tragfaehige Grundlage fuer eine
Parameteraenderung. **`tp1_anteil_pct = 50 % bleibt arretiert** (Anwender-Vorgabe
E-29/H9.3).

### I7 · Ehrliche Bilanz E-30/S1 — **drei Hebel getestet, drei falsifiziert**

| Hebel | Ergebnis | Verdikt |
|---|---|---|
| Break-Even-Stop (E-29/H7) | `USD/Tr` faellt in *jedem* Wert | verworfen |
| **TP1-Deckelung (I4)** | `USD/Tr` faellt in *jedem* der 21 Werte | **verworfen** |
| Gewicht `w1` (I6) | monoton besser, aber grenzwertig + AUG-kritisch + n=20/5 | **verworfen** |

**Kernbefund E-30/S1:** Die arretierte Zielgeometrie ist **nicht defekt**.
Der grosse H2-Zielabstand (13,29 R) ist **die Kehrseite des billigen Stops**
(0,96 ATR) — nicht eine Fehlkalibrierung. Wer `R` misst, sieht grosse Zahlen;
wer `USD/Trade` misst, sieht ein System, das beide Haelften profitabel nutzt.
Die Mentor-Warnung ("13 R gegen die Physik des Orderbuchs") ist damit
**empirisch nicht bestaetigt**: genau die weiten Ziele tragen den Ertrag.

Der verbleibende Hebel liegt folglich **nicht** in der Zielgeometrie, sondern
in **(a) der Diskriminationsschaerfe der Schliessung** (E-29/H8: Spanne
+115,10 bis -52,61 R) — das ist Schritt 2 — oder **(b) der Trade-Auswahl**
(Einstiegsseite). Die Einstiegsseite ist durch I5 nicht entlastet: 25,8 %
TP1-Trefferquote bzw. 7,4 % TP2-Trefferquote sind die eigentliche Kennzahl,
an der eine Verbesserung ansetzen muss.

### I8 · Offene Entscheidungen (Textblock)

1. **Zielgeometrie ist geschlossen.** Alle drei Ziel-/Exit-Hebel sind
   gemessen und verworfen. Vorgeschlagen wird, den Zielabstand **nicht**
   weiter zu bearbeiten und direkt zu **Schritt 2 (Diskrimination der
   Hybrid-Schliessung)** ueberzugehen.
2. **Einstiegsseite als zweiter Kandidat.** Die Trefferquoten (TP1 25,8 % /
   TP2 7,4 %) sind der eigentliche Engpass. Zu entscheiden ist, ob parallel
   zur Hybrid-Schliessung die Einstiegsseite (Q29-Quartil, `V3_TP_MINDIST_PCT`,
   12-Bar-Zyklus, Cluster) vermessen werden soll — oder erst nach Schritt 3.
3. **Pflichtmetrik erweitert.** Ab jetzt ist **`dR Gewinner`** (nicht nur der
   Sign-Flip) zu berichten (I4). `Q_stop` bleibt reines Ausschluss-Gate (`D1`).
4. **Kein Parameterwechsel ohne Anker-Pruefung.** `tp1_anteil_pct` und
   `num_bins` sind AUG-kritisch; jede Aenderung an ihnen bricht V018. Diese
   Klasse von Parametern ist vor jeder Messung zu kennzeichnen.

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
