# -*- coding: utf-8 -*-
"""Handoff-Checkpoint E-34n/14 (read-only Analytik) — Append.

Vorbedingungs-gated (Datei-SHA, Binaer-I/O wegen CRLF).
Abschnitt ist ASCII-only (Umlaute ae/oe/ue, Paragraph erlaubt).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
VORBEDINGUNG = "cbf53427536f7bf13ba97e9aafb3dd52787e5b7b0c1dcf1c162730224f91dfe4"

ABSCHNITT = """

## Phase 2 / E-34n/14 (2026-09-11, ae) - CHECKPOINT: DATENKANTE, OFFENE HAELFTEN, CONCURRENCY

Auftrag (Anwender): rein analytische Durchdringung von drei Punkten an der
Datenkante -- (1) Ausschluss unvollendeter Trades (Mark-to-Market-Bereinigung),
(2) Concurrency-Schranke gegen die "Positions-Armada", (3) Status.
**Rein lesend**: Engine, Renderer, Adapter und Handoff blieben waehrend der
Untersuchung byte-identisch; der einzige neue Stand ist dieser Checkpoint.

### C1 - Ausgangslage und Vorbedingung

Vorbedingung: Handoff-SHA
`cbf53427536f7bf13ba97e9aafb3dd52787e5b7b0c1dcf1c162730224f91dfe4`
(343.574 B / 6.084 Zeilen, aus E-34n/13) - vor dem Append binaer verglichen.

| Anker | Bytes | SHA256 |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` | 196.649 | `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` |
| `backtest_lab/phasen_regime_adapter.py` | 30.663 | `4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83` |
| `test/tmp_png_aug_sichttest.py` (ZP-5(D)) | 109.022 | `7dab7a300e69c4ffae230b1cb547da508dae8a3801cb6a2fed2f63c5bc6d7a28` |

Methode (read-only): AST-Extraktion von `_se_trades` + arretierte Renderer-
Patches, Ausfuehrung in flachem Namespace; Rekonstruktion BEIDER Haelften je
Trade ueber die Engine-Funktion `_c_loese_trade` (die `_SESetup`-Felder
`r1`/`r2`/`grund2` werden nicht gespeichert), abgesichert per Assert:
`0.5*r1 + 0.5*r2 == t.r` sowie `grund1`/`exit1_bar`/`exit2_bar` bit-identisch.
`tp1_anteil_pct = 50.0` -> **50/50**, NICHT 25/75.

### C2 - Befund 1: Mechanik des Fensterendes

Der Not-Exit liegt in `_c_loese_trade` (Engine Z. 1624-1637):
`else: r1, ex1, g1, ex1_bar = _r(cc[-1]), cc[-1], "ENDE", e_bar + nb - 1`
mit `nb = n - e_bar`. Das `ENDE`-Exit liegt damit immer auf **Bar n-1 = 1287**;
`cc[-1]` = letzter Close = Mark-to-Market.

**Praezisierung:** 1287 ist NICHT `box_end`. `box_end` der Engine = 644
(19.08.); der Renderer ueberschreibt Z. 562 `scan["box_end_bar"] = n`
(Voll-Lauf). Bezeichnung "Bar 1287 (box_end)" ist zu trennen.

Typisierte Trennung HEUTE nur ueber `grund1`/`exit1_bar`/`exit2_bar == n-1`
(ein `grund2`/`r1`/`r2` fehlt in `_SESetup`, Z. 2337-2358).

### C3 - Befund 2: offene Haelften im V019-Lauf (arretiert)

6 Einzelhaelften in **4** Trades; `R_brutto = +88.116626` (aktueller Sollwert).

| Bar | Zeit | Kante | Ri | e_bar | h1 | h2 (offen, ENDE 1287) | r_gew |
|---|---|---|---|---|---|---|---|
| 1075 | 25.08. 15:45 | K62 | LONG | 1077 | TP1 +0.0217 | **+2.9298** | +1.475768 |
| 1172 | 26.08. 17:00 | K82 | LONG | 1173 | TP1 +0.1562 | **+10.8483** | +5.502241 |
| 1272 | 27.08. 19:00 | K73 | SHORT | 1273 | ENDE +1.2547 | +1.2547 | +1.254682 |
| 1280 | 27.08. 21:00 | K76 | SHORT | 1281 | ENDE +1.7564 | +1.7564 | +1.756410 |

Bereinigte Performance (drei Definitionen, alle gemessen):
- **(a)** Trade mit offener Haelfte voll ausgeschlossen: **+78.127525** (20 volle Trades)
- **(b)** nur geschlossene Haelften (offene = 0, 50/50 gewichtet): **+78.216484**
- Differenz (a) vs. (b): **0.088959 R** = die realisierten TP1-Haelften von 1075/1172.

**Denkfehler im Briefing:** (1) **K82@1172 wird unterschlagen** - die groesste
offene Haelfte (+10.8483). Ohne sie: 88.116626 - 1.254682 - 1.756410 -
1.475768 = **+83.629766**, nicht ~78,14. (2) Die Rechnung "88,12 - 1,25 - 1,76
- 2,93 = 82,18" widerspricht der eigenen Zielzahl 78,14. (3) **1268 und 1280
sind SHORT K76**, nicht LONG. (4) 1075 h2 = +2.9298 ist korrekt. (5) "Monat"
trifft nicht: Fenster 12.08.-27.08. (~16 Tage).

### C4 - Befund 3: Concurrency (max gleichzeitig, bar-genau)

| Modus | max gleichzeitig | LONG max | SHORT max | Peak |
|---|---|---|---|---|
| V019 | **4** | 2 | **3** | Bar 1269: 2 LONG + 2 SHORT |
| V018 | 3 | 1 | **3** | Bar 982: 3 SHORT |

**Der 3-fach-SHORT-Cluster liegt am 24.08. (Bars 982-991), NICHT am 27.08.:**
K67@903 [905..991], K67@980 [981..991], K73@981 [982..991] - **in V018
identisch**. Am 27.08. (Peak Bar 1269) sind es 2 LONG (K62@1075, K82@1172) +
2 SHORT (K76@1211, K76@1268), letztere **dieselbe Kante K76**. Danach
K73@1272 X K76@1280 (2 SHORT, Ueberlappung 1281-1287).

**Nirgends 4-5 Trades derselben Richtung.** Same-edge-Doppel sind zudem
strukturell und in der arretierten H1-Basis vorhanden: K20@229 X K20@242
(154 Ueberlappungsbars) und K20@529 X K20@564 (75 Bars).

### C5 - Befund 4: Cap-Simulation (First-Order) und Invarianz-Verdikt

Greedy in Einstiegsreihenfolge (NICHT kausal identisch mit einem Gate in
`_se_trades` - dort verschieben verworfene Trades `letzter_trade`/Zyklus).

| Regel | V019 | H1 | V018 | Verdikt |
|---|---|---|---|---|
| global max 2 / Richtung | 23 / +85.421139 | **8/+38.919584** | 16 / +63.140088 | entfernt nur K73@981 (+2.695488); V018 NICHT invariant |
| je Kante max 1 | 20 / +59.333795 | **6/+19.124429** | 14 / +36.052745 | killt K20@242 +3.9251 UND K20@564 **+15.8700** (H1) |
| global max 1 / Richtung | 17 / +49.379656 | 6/+19.124429 | 13 / +33.357257 | katastrophal |

**Kernbefund:** Ein **globales Cap-2 wirkt am 27.08. ueberhaupt nicht** (dort
zu keinem Einstiegszeitpunkt >= 2 gleichgerichtete aktiv) - es greift nur am
24.08. (K73@981) und **veraendert V018**. Ein **Kanten-Cap-1 zerstoert H1**
(K20-Doppel, inkl. des besten Einzeltrades +15.87). Es gibt keinen kostenlosen
Schutzschirm: die einzige H1- UND V018-invariante Variante ist **Cap >= 3 je
Richtung** - dann bleibt der 24.08.-Triple unangetastet.

### C6 - Zusammenfassung der Denkfehler

1. K82@1172 unterschlagen (groesste offene Haelfte).
2. Arithmetik (82,18) vs. Zielzahl (78,14) inkonsistent.
3. Richtung von 1268/1280 falsch (SHORT, nicht LONG).
4. "Armada am 27.08." - Peak gleicher Richtung liegt am **24.08.**; am 27.08.
   max 2/Richtung.
5. Global-Cap-2 loest das 27.08.-Problem NICHT.
6. Same-edge-Doppel liegen in der **arretierten H1-Basis** (K20) -> jede
   Kanten-Regel bricht die Arretierung.
7. 1287 ist Fensterende, nicht `box_end` (644).
8. "Monat" vs. 16-Tage-Fenster.

### C7 - Untersuchungsmatrix fuer den naechsten Schritt (Tag 2)

| # | Pruefung | Erwartung |
|---|---|---|
| 1 | `_SESetup` um `grund2/r1/r2` erweitern (typsicher) | == `_c_loese_trade`-Rekonstruktion (Assert) |
| 2 | Renderer: zweite Bilanzzeile `R_realisiert` | 78.13-78.22, Definition fixieren (Q1) |
| 3 | **Kausales** Gate in `_se_trades` (Loop, nicht Post-Filter), vor `getradete_entry_bars`/`letzter_trade` | echte Differenz zu C5 messen |
| 4 | Cap-Gate doppelt gaten (nur V019 + `len(hook.segmente) > 1`) | V0/V1_basis/V018-Quelltext inert |
| 5 | H1-Invarianz-Assert (`entry_bar < 644`) | 8 / +38.919584 bleiben |
| 6 | V018-Gegenprobe | erwartete Abweichung explizit protokollieren (K73@981) |
| 7 | Edge-Cooldown kalibrieren (falls Q2 = B) | H1-K20-Doppel (Entry-Abstand 14) darf nicht kippen |

### C8 - Leitfragen des Anwenders: Antworten + offene Entscheidungen

**(1) Zwei getrennte Summenzeilen?** Ja, aber die Definition ist zu fixieren.
Methodisch korrekt ist **(b)**: eine bei TP1 geschlossene Haelfte ist
vollstaendig realisiert; ihre Streichung (a) unterzeichnet die Strategie um
0.088959 R. **Empfehlung:** `R_brutto` (arretiert, +88.116626) **plus**
`R_realisiert = (b) +78.216484`, ausgewiesen als
`R_realisiert = R_brutto - Summe(offene Haelften)`.

**(2) Global vs. kanten-spezifisch?** Beide Reinformen sind widerlegt:
global-2 wirkt am 27.08. nicht und aendert V018; Kanten-1 zerstoert H1.
**Empfehlung:** global-2 (nur als Klumpenrisiko-Deckel) **plus** separater
Kanten-Cooldown fuer die 27.08.-K76-Re-Entry, mit dokumentierter und neu
arretierter V018-Abweichung (Verlust K73@981, -2.695488).

**ENTSCHEIDUNGSFRAGEN (offen):**
- **Q1:** Bilanzierung als (a) Trade-Ausschluss (+78.127525) oder (b) je
  Haelfte (+78.216484)?
- **Q2:** Schranke als (A) nur global-2 (H1-invariant, V018 -2.695488),
  (B) global-2 + Kanten-Cooldown >= X (X in Tag 2 kalibrieren) oder
  (C) den 24.08.-Triple bewusst erhalten und Cap >= 3 setzen?

**(3) Pausen-Bestaetigung:** Der Code ruhte waehrend der gesamten Analyse. Der
einzige neue Stand ist dieser Checkpoint + die read-only Artefakte (C9).

### C9 - Artefakt-Anker E-34n/14 (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/_tmp_e34n13_forensik.py` | 12.000 | `a185f5ecbff3cf99cd5bd2ec394f34f12e20f82d1ed03daaf64522c3fa2512e8` |
| `test/_tmp_e34n13_forensik_out.txt` | 11.099 | `ded0041d1b8529471c6a6c0f4fd4b6d53bfdba5f1033de85cbcc44eef3149a99` |
| `test/_tmp_e34n13_forensik_console.txt` | 67 | `fa8c8bb29166199f1324a27a1a24a32886b281c6a74cba33bd52f12ea08575af` |

Unveraendert bleiben die Engine-/Adapter-/Renderer-Anker aus C1; **kein** §75,
**kein** S1, **keine** S2-Laeufe, **keine** UI-/Regressionstests, **kein**
`git add -f`.
"""


def main() -> None:
    # Binaer-I/O: der Anker-SHA ist der Datei-SHA (CRLF bleibt erhalten);
    # read_text() wuerde CRLF -> LF normalisieren und den Vergleich brechen.
    vorher = HANDOFF.read_bytes()
    ist = hashlib.sha256(vorher).hexdigest()
    assert ist == VORBEDINGUNG, (
        "Vorbedingung verletzt: Handoff-SHA", ist, "!=", VORBEDINGUNG)
    assert vorher.count(b"\r\n") == vorher.count(b"\n"), "gemischte Zeilenenden"
    anhang = ABSCHNITT.replace("\n", "\r\n").encode("utf-8")
    HANDOFF.write_bytes(vorher + anhang)
    neu = HANDOFF.read_bytes()
    print("OK  bytes", len(neu), "CRLF", neu.count(b"\r\n"),
          "LF", neu.count(b"\n"))
    print("neuer SHA256", hashlib.sha256(neu).hexdigest())
    print("replacement-zeichen", neu.decode("utf-8").count("\ufffd"))
    print("nicht-ASCII im Abschnitt", sorted({c for c in ABSCHNITT if ord(c) > 127}))


if __name__ == "__main__":
    main()
