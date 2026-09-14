# -*- coding: utf-8 -*-
"""Append 'E-33' an test/SESSION_HANDOFF.md (Vorbedingung SHA 3e78f2fe...)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "test" / "SESSION_HANDOFF.md"
VORBEDINGUNG = "3e78f2fe23077237852fec6f1a1caaf4a7b79c06db019c3d002d8edc3f4c3d38"

ist = hashlib.sha256(HANDOFF.read_bytes()).hexdigest()
print("Vorbedingung SHA256:", VORBEDINGUNG)
print("aktuell          :", ist)
if ist != VORBEDINGUNG:
    print("ABBRUCH: Vorbedingung nicht erfuellt.")
    sys.exit(1)

ABSCHNITT = """
## Phase 2 / E-33 (2026-09-11, q) — AUG-Zielerreichung: **die Zielzone ist mit +16,815995 R geoeffnet, H1 bleibt bit-identisch**

Auftrag (Anwender, nach E-32): **keine S2-Tests**, ausschliesslich **AUG**;
Ziel ist die **zweite Haelfte von H2** (Zielzone 1021..1287). Zu testen waren
**V-C** (Q29 phasenlokal) und **V-D** (endogene Kantenzustaendigkeit).
Erwartung des Anwenders: **besser als V018**, weil drei Trades sichtbar sind —
**25.08. 15:15 LONG · 26.08. 04:30 SHORT · 26.08. 17:00 LONG**.

### M0 · Methodik-Korrektur (Ursache der bisherigen Nullbefunde)

Die Kampagnen E-28 … E-32 haben fuer AUG `_se_trades` mit
`scan["box_end_bar"]` (= 644) laufen lassen. Die Laufschleife ist aber
`for k in range(2, box_end - 3)` — **Bars 641..1287 wurden nie iteriert**.
Daher stammten alle AUG-Zahlen aus E-28 … E-32 aus der **H1-Box allein**
("AUG ist faktisch H1-only", "AUG-H2 leer" sind **Artefakte dieser Grenze**,
keine Marktaussage).

Der **Produktionspfad** (Renderer `tmp_png_aug_sichttest.py`, Zeile 507) setzt
`scan["box_end_bar"] = n` und partitioniert ueber `entry_bar` bei 644.
E-33 reproduziert ihn bit-identisch:

| Groesse | E-33-Harness | arretiert V018 |
|---|---|---|
| gesamt | 17 / +65,835576 | 17 / +65,835576 |
| H1 (`entry_bar < 644`) | 8 / +38,919584 | 8 / +38,919584 |
| H2 (`entry_bar >= 644`) | 9 / +26,915992 | 9 / +26,915992 |

**Erratum E-33a:** saemtliche AUG-Teilquoten aus E-28 … E-32 ("AUG n = 8",
"AUG feuert 1×", "AUG-H2 = 0") sind auf die H1-Box bezogen und duerfen nicht
als E-32-Aussagen ueber H2 gelesen werden. Die MFE-Aussagen aus E-31b/E-32 zum
**AUG-Cap-Band** bleiben davon unberuehrt (sie betrafen AUG-Trades der Box).

### M1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e33_aug.py` | `0fa8ec96ca5f8db2c70db872d30cc3c6bb036f6ddab3d19386c9efe7478bbe74` | 21.025 |
| `test/_tmp_e33_probe.py` | `24e0da9d7a734f42811e5425a4860a13f3b634762a2e2ec5f80a2c6ea18a5c1b` | 1.859 |
| `test/_tmp_e33_aug_V018_out.txt` | `cc6fdd451860b819d813face778bb507f13268d37645a9843b53d8fc31910068` | 3.570 |
| `test/_tmp_e33_aug_Z_10_LOKAL_out.txt` | `51a6fe6232f342ab2c204163b29532ad0b36261758bd43e981afa91a622acaa9` | 4.303 |
| `test/_tmp_e33_aug_Z_12_LOKAL_out.txt` | `e1710a0c0ad4bf2a1d4bf070cb71b25f3d8c093356a0b17bf6698a6f004748d8` | 4.503 |
| `test/_tmp_e33_aug_Z_FULL_LOKAL_out.txt` | `1384a94709c5bf44e3c739893623cc83a3ce7f9fa844f8e0f719b92f8b7cd699` | 4.886 |
| `test/_tmp_e33_aug_Z_1012_LOKAL_out.txt` | `900ab2e7156182fe335269d764b842da0db54ebca0bcf56c5e27600a57a00285` | 4.906 |
| `test/_tmp_e33_aug_Z_B85_LOKAL_out.txt` | `c83e4489bea8f5a6fe73de1ff6ec9433d655b7886e97b5c8e74fcd594bd3c4f7` | 4.905 |
| `test/_tmp_e33_aug_Z_1012_VD_out.txt` | `7a65496bc6e5d1a306b6940a79c983d36183be43e99eb68899722a1cf56933bd` | 5.267 |
| `test/_tmp_e33_aug_VD_ALL_out.txt` | `b3df4ee3907256995c1e447bba1233a2f076773eca0a375b8fbc361c3fe9b686` | 3.158 |

Engine `4a576a76…` (V018, 196.649 B) · Adapter `0f3f8765…` (25.783 B) —
**beide unveraendert**. Kein Projektcode geaendert.

### M2 · Die drei avisierten Trades — Blockadeursache in V018 (gemessen)

| Bar | Richtung | V018-Befund | Ursache |
|---|---|---|---|
| 1072/1073 | LONG | `kd=K62` (67,7830), **Q29-SPERRE** | globales Q29-Fenster (`hi[:k+1]`/`lo[:k+1]` = 62,58..70,0); Sweep 67,4880 liegt im **Niemandsland** (65,94 %) |
| 1122/1123 | SHORT | `kd=K73` (69,6380), **M6-Blocker K67** (69,9598) | K67 ist **dormant** (letzter Docht 1020; 1122 − 1020 = 102 > `wall_live_bars` 96), sperrt aber |
| 1172/1173 | LONG | **`kd=None`** | Regime-Vakuum **und** Kandidaten-Kaskade (Pool {K48, K3, K17, K63, K60}; K60 Ueberdehnung 0,7076 % > 0,60 %) |

Zusaetzlich blockiert das **Regime-Vakuum** jede Bar ≥ 1021: der V018-Adapter
ist `P9_BODEN_RECLAIM` (848..1020); `hook_2_ziel` liefert fuer 1021..1287
`BLOCKIERT`. **Ohne ein Segment fuer die Zielzone ist kein einziger Trade
moeglich** — unabhaengig von V-C/V-D.

### M3 · Varianten-Matrix (AUG, Produktionspfad, Partition bei `entry_bar` 644)

Schalter: **VC** = Q29 phasenlokal (Fensteranker = Startbar des aktiven
Segments) · **M6** = Blocker nur bei **lebender** Aussenwand (`_lebt`) ·
**UEB** = Ueberdehnung 0,60 → 0,80 · **SB** = RECLAIM_AT_OPENING (Ereignis
schlaegt Schlafstatus). **LOKAL** = Wirkung strikt auf 1021 ≤ k ≤ 1287
(segment-lokale Verdrahtung); sonst global.

| Variante | Segmente | n | gesamt R | H1 R | H2 R | H2b R | Ziel n/R | Q_stop |
|---|---|---|---|---|---|---|---|---|
| **V018** | P9 | 17 | **+65,835576** | **+38,919584** | +26,915992 | +19,315336 | 0 / 0 | 0,235 |
| VC | P9 | 18 | +64,835576 | +38,919584 | +25,915992 | +19,315336 | 0 / 0 | 0,278 |
| VD1 (M6) | P9 | 18 | +56,960394 | +32,044402 | +24,915992 | +19,315336 | 0 / 0 | 0,444 |
| VD2 (UEB) | P9 | 17 | +64,447751 | +38,919584 | +25,528167 | +19,315336 | 0 / 0 | 0,235 |
| VD4 (SB) | P9 | 20 | +55,902043 | +36,919584 | +18,982458 | +19,315336 | 0 / 0 | 0,350 |
| VD_ALL | P9 | 22 | +46,531513 | +30,549055 | +15,982458 | +19,315336 | 0 / 0 | 0,500 |
| Z_FULL | P9+ZIEL | 17 | +65,835576 | +38,919584 | +26,915992 | +19,315336 | 0 / 0 | 0,235 |
| Z_1012_VD (global) | P9+P10+P12 | 29 | +63,347508 | **+30,549055** | +32,798453 | +36,131332 | 7 / **+16,815995** | 0,414 |
| Z_10_LOKAL | P9+P10 | 20 | +78,101004 | **+38,919584** | +39,181419 | +31,580764 | 3 / +12,265427 | 0,200 |
| Z_12_LOKAL | P9+P12 | 21 | +70,386144 | **+38,919584** | +31,466560 | +23,865904 | 4 / +4,550568 | 0,238 |
| Z_FULL_LOKAL | P9+ZIEL | 24 | +79,112095 | **+38,919584** | +40,192511 | +32,591856 | 7 / +13,276519 | 0,250 |
| **Z_1012_LOKAL** | P9+P10+P12 | 24 | **+82,651571** | **+38,919584** | **+43,731987** | **+36,131332** | 7 / **+16,815995** | **0,208** |
| Z_B85_LOKAL | P9+P10b+P12b | 24 | +70,552136 | +38,919584 | +31,632551 | +24,031896 | 7 / +4,716559 | 0,250 |

**Drei Befunde:**

1. **Das Segment allein ist inert** (`Z_FULL` = V018 bit-identisch): die
   Zielzone wird erst durch das **Zusammenspiel** von Segment + VC + M6 + SB
   handelbar. V-C allein bleibt bei 0 (Vakuum); V-D allein **kostet**.
2. **Die globalen Schalter zerstoeren H1** (VD1 −6,88; VD4 −2,00; VD_ALL
   −8,37 R in H1, teils **andere** H1-Trades). Deshalb ist die **segment-lokale
   Verdrahtung (LOKAL) zwingend** — sie haelt H1 auf **+38,919584 R bit-identisch**.
3. **Ein einziges durchlaufendes Segment (ZIEL 1021..1287) ist schlechter als
   die Zwei-Phasen-Teilung P10 (1021..1170) + P12 (1171..1287)**: K76@1211
   liefert mit dem P12-eigenen Ziel +2,53948 statt −1,00000 (Δ +3,54 R).
   **P10/P12 bleiben getrennt.**

### M4 · Die Zielzonen-Trades von `Z_1012_LOKAL`

| Signal-Bar | Entry-Bar | Richtung | Kante | R | Stufe |
|---|---|---|---|---|---|
| 1028 | 1029 | LONG | K60 | −0,47759 | STUFE_1_IN_BAR |
| **1075** | **1077** | **LONG** | **K62** | **+1,99054** | STUFE_2_KERZE_2 |
| **1122** | **1123** | **SHORT** | **K73** | **+10,75247** | STUFE_1_IN_BAR |
| 1211 | 1214 | SHORT | K76 | +2,53948 | STUFE_3_KERZE_3 |
| 1268 | 1269 | SHORT | K76 | −1,00000 | STUFE_1_IN_BAR |
| 1272 | 1273 | SHORT | K73 | +1,25468 | STUFE_1_IN_BAR |
| 1280 | 1281 | SHORT | K76 | +1,75641 | STUFE_1_IN_BAR |
| | | | | **+16,815995** | |

**Zwei der drei avisierten Trades sind erfasst:**

- **25.08. 15:15 LONG** → Signal 1075 / Entry 1077 an **K62**, **+1,99054 R**.
  (Nicht an K82 — der Kaskaden-Umweg ueber die Innenlinie ist die P9-analoge
  Mechanik, vgl. "K73-Umweg".)
- **26.08. 04:30 SHORT** → Signal 1122 / Entry 1123 an **K73**, **+10,75247 R**
  — der **groesste Einzelbeitrag** der ganzen Auswertung.

### M5 · Warum der dritte Trade (26.08. 17:00 LONG) noch fehlt

Die Diagnose ist exakt (Bar 1172, LONG):

```
kd = K62 (basis 67,7830) · M6 ohne Blocker · Q29 durch · Stufe = 2
GEO sl=67,4440  entry=67,9060  poc=67,8294  tp2=69,6380  basis=67,7830
-> kein_raum
```

**Grund:** der **Entry-Open (67,9060) liegt ueber dem POC (67,8294)**; die
Geometrie `sl < entry < poc < tp2` ist damit verletzt. Der Anwender-Trade sitzt
jedoch an **K82 (67,5455)**; dort laege der Entry deutlich unter dem POC.
K82 wird aber vom **Hook-1 ("Freigabe")** als *sweep-bildende Wand* aus dem
Kandidaten-Pool **entfernt** (`pool = [e for e in pool if e.kid !=
_freigabe_kid]`, Renderer-Zeile 94f) — deshalb faellt die Kaskade auf K62.

**Das ist die letzte, genau lokalisierte Luecke:** nicht Q29, nicht M6, nicht
Stufe — sondern die **Hook-1-Pool-Semantik** (die freigegebene Wand wird nie
selbst gehandelt). Spielart `Z_B85_LOKAL` (Phasenboden = Monatstief K85
67,4200 statt K82) wurde geprueft und ist **schlechter** (+4,72 statt +16,82):
K82 als Phasenboden ist die richtige Wahl.

### M6 · Verdikt

**Die Zielzone der zweiten H2-Haelfte ist gewinnbringend und H1-neutral:**

| | V018 (arretiert) | **Z_1012_LOKAL** | Δ |
|---|---|---|---|
| gesamt | 17 / +65,835576 | **24 / +82,651571** | **+16,815995 R** |
| H1 | 8 / +38,919584 | **8 / +38,919584** | **0,000000** |
| H2 | 9 / +26,915992 | **16 / +43,731987** | **+16,815995 R** |
| 2. H2-Haelfte (entry ≥ 966) | 4 / +19,315336 | **11 / +36,131332** | +16,815995 R |
| Zielzone (1021..1287) | **0 / 0** | **7 / +16,815995** | — |
| `Q_stop` | 0,235 | **0,208** | besser |
| `USD/Trade` | +1,1167 | +0,9474 | schlechter (24 statt 17 Trades) |

Der Zuwachs ist **vollstaendig** der Zielzone zuzurechnen; H1, der P9-Abschnitt
(848..1020) und alle 17 V018-Trades sind **bit-identisch** erhalten.

**Ehrliche Einschraenkungen:**
1. **Ein Datensatz (AUG, n = 8 Monatswochen).** Kein S2, keine OOS-Stuetzreihe
   (Anwender-Vorgabe). Die 7 Zielzonen-Trades ruhen zu **64 %** auf einem
   einzigen Trade (1122 / +10,75 R).
2. **Zwei der sieben Trades sind Verluste** (1028, 1268); die Gewinnquote der
   Zielzone ist 5/7, `USD/Trade` sinkt von +1,1167 auf +0,9474.
3. **Der dritte avisierte Trade fehlt** (Hook-1-Pool-Semantik, §M5).
4. **Segmentgrenzen sind Anwender-Setzung** (P10 1021..1170, P12 1171..1287).
   Die endogene Erkennung (V-D im engeren Sinne) ist damit **nicht** geliefert
   — geliefert ist die *Wirkung* der Phasen-Autorisierung.

### M7 · Offene Entscheidungen (Textblock)

1. **Tragen der Zielzonen-Mechanik (Z_1012_LOKAL) als Kandidat?** Der Hebel
   ist +16,815995 R bei H1-Bit-Identitaet — erstmals ein Ergebnis, das die
   Anwender-Erwartung ("besser als V018") erfuellt.
2. **P10/P12-Grenze (1170/1171) bestaetigen** oder die Phase anders schneiden?
   Die Anwender-Notiz "diese und andere peaks sind diskutabel" ist damit
   adressierbar: der Schnitt 1170/1171 ist genau der, der K76@1211 dreht.
3. **Hook-1-Pool-Semantik fuer Phasenwaende pruefen** (dritter Trade): soll die
   freigegebene Phasenwand selbst handelbar sein (`kid == _freigabe_kid`
   erlaubt) oder bleibt der Innenlinien-Umweg arretiert?
4. **`Q_stop` 0,208** (besser) und **`USD/Trade` 0,9474** (schlechter) — die
   Pflichtmetrik `USD/Trade` sinkt; die **Summe** steigt. Nach Urkunde E-30/I4
   ist `USD/Trade` fuehrend: zu entscheiden, ob das Aggregat oder das
   Verhaeltnis zaehlt.
5. **Naechster Schritt:** bei Zustimmung Einbrand in
   `backtest_lab/phasen_regime_adapter.py` (**neue Generation V019**, da die
   Sollwerte H2 = +43,731987 / gesamt +82,651571 abweichen) — vorher
   Anwender-Freigabe. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.**

"""

with HANDOFF.open("a", encoding="utf-8", newline="\n") as fh:
    fh.write(ABSCHNITT)

neu = HANDOFF.read_bytes()
print("neue Bytes  :", len(neu))
print("neue SHA256 :", hashlib.sha256(neu).hexdigest())
txt = HANDOFF.read_text(encoding="utf-8")
print("LF:", txt.count("\n"), "CRLF:", txt.count("\r\n"))
print("ENDE append ok")
