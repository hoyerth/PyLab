# -*- coding: utf-8 -*-
"""LF-Append: Phase 2 / E-26 an test/SESSION_HANDOFF.md (Blob-SHA-schonend)."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"F:\Python\PyLab\test\SESSION_HANDOFF.md")
SOLL = "545d15f102ef23c9a397a69c7f3f31de9730bc6067f8060a9180fe1f3dbc833c"

vorher = P.read_bytes()
ist = hashlib.sha256(vorher).hexdigest()
assert ist == SOLL, f"Vorbedingung verletzt: {ist} != {SOLL}"
assert vorher.count(b"\r\n") == 0, "Datei ist nicht LF-clean"

TEXT = """
---

## Phase 2 / E-26 (2026-09-11, j) — Long-Blockade: **Q29 referenziert das Gesamt-Extrem**

Beantwortet Phase 2 des Explorationsplans: *„Warum emittiert die Engine in
S2-H2 exakt 0 Long-Trades?"* Antwort: **nicht wegen `KANDIDAT_NONE`, nicht
wegen fehlender Pivots und nicht wegen der Makrowaende — sondern weil Q29
(`_im_aussenquartil`) seinen Bezug auf das laufende **Gesamt**-Extrem seit
Bar 0 nimmt.** Im Aufwaertstrend ist die Long-Seite dadurch strukturell
gesperrt.

### F1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e26_long_blockade.py` | `9a4b9143d81985379d3a98430026983da42dfe14ef7054aba8d8cee8f53e57e1` | 13.298 |
| `test/_tmp_e26_long_blockade_out.txt` | `4694c867c0362fdbb4834cb2e7e7e130bd66fcf571798da723c70d4c7221dfb2` | 19.895 |
| `test/_tmp_slice.py` | `3d8562869f9f4697c9ea25db7264989f72f849772adc36a840f54e1b917e1edb` | 406 |

### F2 · Verfahren (kein Neubau der Logik) und Fidelity-Nachweis

`_se_trades` wird per **AST** aus der arretierten Engine extrahiert
(Zeilen **2361..2769**, 409 Zeilen), in einer Kopie der Engine-Globals
ausgefuehrt und **ausschliesslich in der Buchfuehrung** ersetzt:

- `stats["X"] += 1` → `_hit(_CUR, "X")` — **14 Ersetzungen**;
- nach `kd = _kandidat(...)`: `kaskade_leer` bzw. `kandidat` + Detailzeile;
- `stufe_n == 0` → `stufe0`; Dedup → `dedup`; erfolgreicher Abschluss → `SETUP`;
- `_CUR[0] = k`, `_CUR[1] = richtung` am Kopf der Richtungsschleife.

Die Entscheidungslogik bleibt **byte-gleich**. **Fidelity-Nachweis:**
Laufgrenze `scan["box_end_bar"] = n` (der Cache traegt dort 17.692 = Split)
liefert **299 Setups (LONG 5 / SHORT 294)** — identisch zur in
`_tmp_s2_vd_stresstest.py` gemessenen `BASE`-Menge (299). Damit ist die
Instrumentierung als verhaltensneutral belegt.

### F3 · Trichter je Richtung und Haelfte

| Richtung / Haelfte | Kandidaten | M6 | **Q29** | `stufe0` | Q24 jung | Zyklus | Raum | **SETUP** |
|---|---|---|---|---|---|---|---|---|
| SHORT H1 | 1972 | 286 | 301 | 611 | 112 | 520 | 14 | **240** |
| SHORT H2 | 334 | 46 | 14 | 136 | 43 | 84 | 0 | **54** |
| LONG H1 | 894 | 0 | **882** | 5 | 60 | 2 | 0 | **5** |
| LONG H2 | 144 | 0 | **144** | 0 | 28 | 0 | 0 | **0** |

**Jeder einzelne** LONG-Kandidat in H2 (144/144, 100 %) stirbt an Q29. Kein
einziger erreicht `_reclaim_stufe`. Die vollstaendige Kandidatenliste steht in
`_tmp_e26_long_blockade_out.txt` Z. 100..211; **alle** Zeilen tragen das
Sterbe-Gate `quartil_blockiert`.

### F4 · Ursache: Q29 vergleicht mit dem Gesamt-Extrem (Zeilen 2434/2435)

```python
ex_hi = float(np.max(hi[:k + 1]))     # <-- seit Bar 0, NICHT lokales Fenster
ex_lo = float(np.min(lo[:k + 1]))
distanz = ((ex_hi - sweep_px) if richtung == "SHORT"
           else (sweep_px - ex_lo)) / spanne * 100.0
return distanz <= cfg.quartil_distanz_pct          # 25.0
```

Gemessene Zeitreihe (Ausschnitt, H2):

| Bar | Datum | `ex_lo` | `ex_hi` | Spanne | LONG-Schwelle | `lo[k]` | Q29-Dist | Status |
|---|---|---|---|---|---|---|---|---|
| 17.692 | 2025-10-01 | 28,2860 | 47,1580 | 18,8720 | 33,0040 | 46,6110 | 97,1 % | GESPERRT |
| 18.172 | 2025-10-08 | 28,2860 | 48,7500 | 20,4640 | 33,4020 | 48,3120 | 97,9 % | GESPERRT |
| 18.652 | 2025-10-15 | 28,2860 | 53,5030 | 25,2170 | 34,5902 | 52,7040 | 96,8 % | GESPERRT |
| 20.092 | 2025-11-06 | 28,2860 | 54,4460 | 26,1600 | 34,8260 | 47,7500 | 74,4 % | GESPERRT |
| 21.532 | 2025-11-27 | 28,2860 | 54,4460 | 26,1600 | 34,8260 | 53,2470 | 95,4 % | GESPERRT |

**Endstand: `ex_lo` = 28,2860 (seit dem Fensterbeginn nie revisited,
eingefroren), `ex_hi` = 56,5250, Spanne 28,2390.**
Die LONG-Schwelle waere `lo[k] ≤ 35,3458 USD`. Das **H2-Tief ist 45,5300** —
**10,1842 USD ueber der Schwelle**. Q29-Distanzen liegen in H2 bei
**74,4 % bis 98,2 %**; die Zulassungsschwelle ist **25 %**.

⇒ Ein LONG ist in H2 **nicht unwahrscheinlich, sondern unmoeglich** — es sei
denn, der Preis kehrt auf ≤ 35,35 USD (Jahrestief) zurueck.

### F5 · Vergleichsgruppe: die 5 gelungenen H1-LONGs

| Bar | Datum | Kante | Q29-Dist | R | close |
|---|---|---|---|---|---|
| 6.120 | 2025-04-04 | K20 | 15,5 % | −1,00000 | 29,7770 |
| 6.121 | 2025-04-04 | K6 | 8,6 % | −1,00000 | 29,6430 |
| 6.131 | 2025-04-04 | K2 | 5,5 % | −1,00000 | 29,3650 |
| 6.323 | 2025-04-08 | K14 | 21,7 % | −1,00000 | 29,7660 |
| 6.343 | 2025-04-09 | K6 | 16,3 % | **+16,71116** | 29,4980 |

Alle fünf LONGs des gesamten S2-Fensters liegen im **April 2025** bei
**29,3–29,8 USD** — also unmittelbar am Jahrestief, wo Q29-Distanzen von
5,5–21,7 % (≤ 25 %) ueberhaupt erreichbar sind. Das ist die
Bestaetigungsgruppe: der LONG-Pfad feuert **nur am globalen Tief**, nie im
Trend.

### F6 · Interpretation

1. **Die Engine ist nicht marktblind, sondern Q29-blind.** Die Diagnose
   „54 Shorts bei 0 Longs in einem 11-USD-Aufwaertstrend" hat eine rein
   mechanische Ursache: Q29 misst die Distanz zum **laufenden Gesamt-Extrem**.
   In einem Trend waechst `ex_hi` mit dem Preis, waehrend `ex_lo` einfriert —
   die Long-Seite wird dadurch **monoton zugesperrt**, die Short-Seite
   (Distanz zu `ex_hi`) bleibt offen.
2. **Dieselbe Fehlerklasse wie E-17/E-25:** ein Gate, dessen Referenz ein
   **globales/lookback-weites Extrem** statt eines **lokalen, regime-relativen**
   ist. In Trendphasen wird diese Referenz stale.
3. **Konsequenz fuer Beschluss 3 (Long-Freigabe).** Ein Zustandswechsel nach
   `EXPANSION_OBEN` kann **keine** Longs erzeugen, solange Q29 unveraendert
   gegen das Gesamt-Extrem prueft. Die „Long-Freigabe" ist damit **kein
   Automaten-, sondern ein Q29-Problem** und muss vor jeder Automatikarbeit
   entschieden werden.

### F7 · Ratifizierte Entscheidungen (Anwender, 2026-09-11 j)

1. **Pfad B = `L960` rein strukturell, ohne ATR-Spannenschwelle.** Eine starre
   `m · ATR960`-Schwelle ist Kurvenanpassung an eine empirisch nicht
   existierende Pivot-Dichte (E-25). Die `L960`-Grenzen aus §12 (Spannweiten
   1,19–2,98 USD) spiegeln die tatsaechlichen Fensterraender.
2. **Hybrid-Schliessung verbindlich.** Eine neue Balance darf **nur** nach
   formaler Terminierung des vorherigen Regimes durch `STRUKTUR_BRUCH`
   (2 Closes jenseits des Bands) gesucht und deklariert werden. Das
   kontinuierliche Zuruecksetzen (228 freie Resets) ist ausgeschlossen; es
   hebelt den Zustandsautomaten aus (3396/3932 Bars `BALANCE`).
3. **Gate-Richtung: Long-Freigabe zwingend pruefen** — siehe F6.3 (Q29-Blocker
   vorgelagert).
4. **Metrik-Hierarchie geaendert: `USD/Trade` ist fuehrend** (mit `ATR/Trade`
   als beigeordneter Normierung). `R` und `R_adj` sind **nur deskriptiv**;
   `R_adj` ist als Zulassungskriterium **degradiert** — eine Metrik, die bei
   −8,81 USD besser aussieht als bei −1,77 USD, darf keine Weichen stellen.

**Folge fuer Phase 1 (`D2`):** Das Kriterium „`R_adj` ≤ Baseline-`R_adj` →
verworfen" ist damit **ausgesetzt**. `D1` bleibt in Kraft:
**`Q_stop` > 0,75 → Uebernahme kategorisch ausgeschlossen.**

### F8 · Offene Entscheidungen (Textblock)

1. **Q29-Referenz.** Drei Wege sind denkbar und muessen entschieden werden:
   (a) Q29 ganz auf lokale Fenster (480/960) umstellen;
   (b) Q29 richtungsasymmetrisch fuehren (SHORT Gesamt-Extrem, LONG lokales
   Tief); (c) Q29 fuer den LONG-Pfad abschalten und die Auswahl dem
   Zustandsautomaten ueberlassen. Ohne Entscheidung bleibt die Long-Seite tot.
2. **Geltungsbereich.** Aendert die Q29-Korrektur die 294 SHORTs? `_im_aussen
   quartil` ist richtungsunabhaengig kodiert — jede Aenderung trifft auch
   SHORT und damit die Baseline. Es muss daher zuerst geklaert werden, ob die
   Q29-Korrektur **regressionsfrei** (SHORT-Ergebnisse bit-identisch) moeglich
   ist oder ob sie S2 neu aufsetzt.
3. **Reihenfolge.** E-26 liegt **vor** der Automatikarbeit. Es wird
   vorgeschlagen: erst Q29-Entscheidung, danach Hybrid-Schliessung auf `L960`,
   zuletzt der Zustandsautomat.
4. **Beschluss 4 verlangt Nachlauf:** Die Phase-1-Ratifikation (`D1`–`D4`)
   ist um die Degradierung von `R_adj` zu korrigieren. Bis dahin gilt der
   Stand in F7.4.

Bis zu diesen Entscheidungen unveraendert: **kein Einbrand in
`backtest_lab/phasen_regime_adapter.py`, kein §75, kein S1-Cache.**
"""


def sha(p: str) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


neu = vorher.decode("utf-8") + TEXT
P.write_text(neu, encoding="utf-8", newline="\n")

n_b = P.read_bytes()
assert n_b.count(b"\r\n") == 0, "CRLF nach Append!"
print(f"vorher  {len(vorher)} B  {ist}")
print(f"nachher {len(n_b)} B  {hashlib.sha256(n_b).hexdigest()}")
print(f"delta   {len(n_b) - len(vorher)} B")
