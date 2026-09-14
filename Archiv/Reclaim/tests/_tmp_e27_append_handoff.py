# -*- coding: utf-8 -*-
"""LF-Append: E-27 + Bereinigung D1-D4 an test/SESSION_HANDOFF.md."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"F:\Python\PyLab\test\SESSION_HANDOFF.md")
SOLL = "087b4d68e1c32bf40a6fcf202badcd8c2d7652d6954cbc5c706f188d2a08f414"

vorher = P.read_bytes()
ist = hashlib.sha256(vorher).hexdigest()
assert ist == SOLL, f"Vorbedingung verletzt: {ist} != {SOLL}"
assert vorher.count(b"\r\n") == 0, "Datei ist nicht LF-clean"

TEXT = """
---

## Phase 2 / E-27 (2026-09-11, k) — Q29-Lokalisierung: **die Long-Seite ist heilbar**

Ratifiziert wurde Weg **(a)**: Q29 symmetrisch auf das lokale Erkennungsfenster
umstellen — keine Richtungs-Asymmetrie, kein Abschalten. Gemessen wurden
`GLOBAL (0..k)` als Kontrolle und `LOKAL 960` / `LOKAL 480`.

### F0 · Erratum der Messmethodik (wichtig, betrifft alle kuenftigen Laeufe)

`_se_trades` **mutiert den Kantenzustand** (`letzter_signal_bar`,
`letzter_sweep_bar`, `cluster_hoch`, `cluster_tief`). Mehrere Q29-Varianten in
**einem** Prozess sind daher **kontaminiert** — der erste E-27-Entwurf lieferte
genau deshalb falsche Werte (`LOKAL 960` = 106 Setups / 51 SHORTs). Der
kontaminierte Output wurde geloescht. **Regel: ein Variantenlauf = ein
Prozess.** Alle unten genannten Zahlen stammen aus je einem frischen Prozess.

### F1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e27_q29_lokal.py` | `3489afacb03bf79e25827b76277b39565e0b113c2346ad06493b344d23d0ad26` | 8.750 |
| `test/_tmp_e27_q29_lokal_s2_0_out.txt` | `cadd1fd91c9b83880cef2552b0d5221cd0d1f1c134a1ff017f73c8e80f9f55e2` | 33.676 |
| `test/_tmp_e27_q29_lokal_s2_960_out.txt` | `03109fb9cf857d311d4537731820b04e4a82d716029eed4dbc775063bc333dcc` | 29.565 |
| `test/_tmp_e27_q29_lokal_s2_480_out.txt` | `a98e18f5909cf845dae7d9073367218866b12e03499326d19d170c1977a1b1f4` | 35.398 |
| `test/_tmp_e27_q29_lokal_aug_0_out.txt` | `a4e6b7db0c65fc1800247406109e2b0b6860074f18dd3144de5d6fd4fda6726f` | 2.233 |
| `test/_tmp_e27_q29_lokal_aug_960_out.txt` | `1f08e73abe6aa9a9785d38cbe85f8eab527528ca617604a21ec945543a9fd9ac` | 2.231 |
| `test/_tmp_e27_q29_lokal_aug_480_out.txt` | `104d579f6c0238a71fb025e849f4cdb296161cc0d4cfa6bd36f34826a8bb1c44` | 2.123 |

**Eingriff (einzige Aenderung, Zeilen 2434/2435 der Engine):**

```python
ex_hi = float(np.max(hi[:k + 1]))       # vorher: global seit Bar 0
ex_lo = float(np.min(lo[:k + 1]))
# -> _a29 = _LB0(k)   # 0 = global; k-LB+1 fuer lokalen Lookback
ex_hi = float(np.max(hi[_a29:k + 1]))
ex_lo = float(np.min(lo[_a29:k + 1]))
```

### F2 · Schritt 1 — S2 (Laufgrenze `box_end_bar = n` = 21.624, Split 17.692)

| Variante | n ges. | R ges. | R_adj | USD | USD/Tr | ATR/Tr | Q_stop | LONG | SHORT | H1 n | H2 n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **GLOBAL 0..k** | 299 | −186,055940 | −206,891794 | −20,1030 | −0,0672 | −0,9094 | 0,799 | 5 | 294 | 245 | 54 |
| **LOKAL 960** | 261 | **−70,813603** | −91,649458 | **−5,3805** | −0,0206 | −0,3367 | 0,667 | **59** | 202 | 221 | 40 |
| **LOKAL 480** | 315 | −90,046026 | −123,416092 | −10,0489 | −0,0319 | −0,4306 | **0,644** | 82 | 233 | 260 | 55 |

Nur H2:

| Variante | H2 n | H2 R | H2 R_adj | H2 USD/Tr | H2 ATR/Tr | H2 Q_stop |
|---|---|---|---|---|---|---|
| GLOBAL 0..k | 54 | −45,589707 | −47,417525 | −0,1698 | −1,1273 | 0,926 |
| LOKAL 960 | 40 | **−10,859370** | −30,300143 | −0,0664 | −0,4939 | 0,775 |
| LOKAL 480 | 55 | **−8,039071** | −41,409136 | −0,0758 | −0,3293 | 0,727 |

**Fidelity:** `GLOBAL` reproduziert die `BASE`-Baseline **bit-identisch**
(299 Setups, R −186,055940, H2 54 / −45,589707, LONG 5 / SHORT 294).

### F3 · Der Q29-Durchlass (Kernfrage des Anwenders)

| Variante | Haelfte | Richtung | Kandidaten | Q29-Sperre | passiert | Anteil | SETUP |
|---|---|---|---|---|---|---|---|
| GLOBAL | H2 | LONG | 144 | **144** | 0 | **0,0 %** | 0 |
| GLOBAL | H2 | SHORT | 334 | 14 | 320 | 95,8 % | 54 |
| **LOKAL 960** | H2 | LONG | 144 | **102** | **42** | **29,2 %** | **11** |
| **LOKAL 960** | H2 | SHORT | 334 | 144 | 190 | 56,9 % | 29 |
| **LOKAL 480** | H2 | LONG | 144 | **62** | **82** | **56,9 %** | **19** |
| **LOKAL 480** | H2 | SHORT | 334 | 102 | 232 | 69,5 % | 36 |

Vollstaendig (auch H1):

| Variante | Haelfte | Richtung | Kandidaten | Q29 | passiert | Anteil | SETUP |
|---|---|---|---|---|---|---|---|
| GLOBAL | H1 | SHORT | 1972 | 301 | 1671 | 84,7 % | 240 |
| GLOBAL | H1 | LONG | 894 | 882 | 12 | 1,3 % | 5 |
| LOKAL 960 | H1 | SHORT | 1972 | 720 | 1252 | 63,5 % | 173 |
| LOKAL 960 | H1 | LONG | 894 | 672 | 222 | 24,8 % | 48 |
| LOKAL 480 | H1 | SHORT | 1972 | 579 | 1393 | 70,6 % | 197 |
| LOKAL 480 | H1 | LONG | 894 | 565 | 329 | 36,8 % | 63 |

**LONG H2: 0,0 % → 29,2 % (960) bzw. 56,9 % (480) Durchlass.**
Der Automat bekommt damit erstmals ueberhaupt LONG-Material (11 bzw. 19 Setups).

### F4 · Die Long-Seite traegt sofort PnL (Beispiele H2, LOKAL 960)

| Bar | Datum (BKZ) | Richtung | Kante | R | entry | sl | tp2 |
|---|---|---|---|---|---|---|---|
| 19.040 | 2025-10-21T16:00 | LONG | K451 | −1,00000 | 48,8960 | 48,7290 | 54,3610 |
| 19.285 | 2025-10-24T08:15 | LONG | K435 | −0,25290 | 48,2800 | 48,0000 | 54,3610 |
| 19.293 | 2025-10-24T10:15 | LONG | K444 | **+0,17525** | 47,8820 | 47,7830 | 54,3610 |
| 19.398 | 2025-10-27T12:30 | LONG | K424 | −0,01726 | 47,3920 | 47,2580 | 54,3610 |
| **19.957** | **2025-11-04T15:30** | **LONG** | **K415** | **+19,44077** | 46,9940 | 46,8030 | 54,3610 |

(Unter `LOKAL 480` feuert derselbe K415-Cluster bei Bar 19.993 mit **R
+33,37007**.) Die Short-Seite verliert dabei ihren toxischen Kern: H2-SHORTs
54 → 29 (960) bzw. 36 (480), das H2-R verbessert sich von −45,59 auf −10,86
(960) bzw. −8,04 (480).

### F5 · Schritt 2 — August-Baseline: **unter 960 strukturell identisch**

Der AUG-Lauf hat `box_end_bar = **644**` (2026-08-19) bei `n = 1288`. Fuer
**jeden** Bar der Box gilt `k ≤ 644 < 960` ⇒ `_a29 = max(0, k − 960 + 1) = 0`
⇒ die Q29-Referenz ist **bit-identisch** zum bisherigen Verhalten. Die
August-Baseline (V018: 17 Trades / +65,835576 R) ist unter `LOKAL 960` daher
**konstruktionsbedingt nicht beruehrbar** — unabhaengig von der
Hook-Verdrahtung.

| AUG-Variante | Setups | R ges. | R_adj | USD/Tr | Q_stop |
|---|---|---|---|---|---|
| GLOBAL 0..k | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 |
| **LOKAL 960** | **8** | **+38,919584** | **+23,049550** | **+1,4077** | **0,125** |
| LOKAL 480 | 7 | +39,267031 | +23,396996 | +1,6134 | 0,143 |

`LOKAL 960` ist **zeilenweise identisch** zu `GLOBAL` (auch die Trade-Liste).
`LOKAL 480` verliert genau einen Trade (Bar 509 SHORT K16, R −0,34745).

**Praezisierung zur Baseline:** Der unbewehrte Engine-Lauf liefert in AUG
**8 Setups / +38,919584 R**. Die arretierte Zahl **17 Trades / +65,835576 R**
stammt aus dem **adapter-verdrahteten** Renderer-Harness (Hook-1-Freigabe,
`REF 0,12 %`), nicht aus `_se_trades` allein. Beide Groessen sind daher
auseinanderzuhalten; die Invarianz unter 960 gilt fuer **beide** (sie folgt
aus `_a29 = 0`, nicht aus der Hook-Verdrahtung).

### F6 · Bereinigung D1–D4 (Nachlauf Phase 1, ratifiziert)

| Kennung | Vorher | **Jetzt verbindlich** |
|---|---|---|
| `D1` | `Q_stop > 0,75` → kategorisch ausgeschlossen | **bestaetigt** — hartes Ausschlusskriterium |
| `D2` | `R_adj ≤ Baseline-R_adj` → verworfen | **SUSPENDIERT** (irrefuehrend, s. E-25/F7) |
| `D3` | Vortrag R, R_adj, Q_stop | **ersetzt**: fuehrend **`USD/Trade` > 0** und **`ATR/Trade`**; `R`/`R_adj` nur deskriptiv |
| `D4` | Dual-Ausweis USD/ATR | **bestaetigt** |

**Harte Gate-Bedingungen (Stand jetzt):** `Q_stop ≤ 0,75` **und**
`USD/Trade > 0`.

**Konsequenz fuer E-27 (ehrliche Bilanz):** Keine der drei S2-Varianten
erfuellt `USD/Trade > 0` —

| Variante | Q_stop ≤ 0,75? | USD/Trade > 0? | Verdikt |
|---|---|---|---|
| GLOBAL 0..k | nein (0,799) | nein (−0,0672) | verworfen |
| LOKAL 960 | ja (0,667) | **nein** (−0,0206) | **verworfen** |
| LOKAL 480 | ja (0,644) | **nein** (−0,0319) | **verworfen** |

Die Lokalisierung **heilt die Mechanik** (Long-Seite oeffnet, `Q_stop` faellt
unter 0,75, R −186 → −71), aber sie erzeugt **noch kein positives
Erwartungswert-Signal**. Der Restverlust sitzt in der Gegenkante (`tp2`
28,4320 / POC auf dem Niveau 32,3–32,8 — d. h. die Ziele liegen weit ausserhalb
der aktuellen Handelsspanne).

### F7 · Interpretation

1. **E-26 bestaetigt und verschaerft:** Q29 war nicht nur ein Long-Blocker,
   sondern ein **globaler Trend-Blindmacher**. Seine Lokalisierung auf das
   Erkennungsfenster ist die erste Massnahme in S2, die die Bilanz in
   **beiden** Richtungen verbessert.
2. **Die §12-Fensterlogik ist jetzt durchgaengig konsistent:** `L960` steuert
   bereits die Balance-Deklaration (E-25/F6). Q29 nutzt dasselbe Fenster.
   Damit gibt es in S2 **eine** Zeitbasis fuer Struktur und Quartil.
3. **960 ist gegenueber 480 zu bevorzugen** — nicht wegen der S2-Zahlen
   (480 ist dort sogar leicht besser), sondern wegen (a) der
   `box_end < LB`-Invarianz, die die AUG-Baseline **beweisbar** schuetzt, und
   (b) der Deckungsgleichheit mit dem Block-A-Erkennungsfenster.
   `LOKAL 480` verletzt die AUG-Baseline (1 Trade).
4. **Der naechste Blocker ist die Zielgeometrie, nicht das Gate.** Mit
   geoeffneter Long-Seite zeigt sich: `tp2`/POC liegen bei den H2-Trades
   weiterhin auf dem Niveau der Januar-Struktur (28,43 / 32,5). Das ist
   dieselbe Krankheit wie E-25/F5 — eine **globale** Referenz im
   Zielsystem.

### F8 · Offene Entscheidungen (Textblock)

1. **Fensterwahl verbindlich machen.** Vorzuschlagen ist `Q29 = L960`
   (Deckung mit Block A, AUG-Baseline beweisbar invariant). `LOKAL 480` waere
   zu verwerfen. Gegenstimmen sind ueber die S2-Zahlen allein nicht zu
   begruenden, wohl aber ueber den AUG-Schutz.
2. **Gegenkante/`tp2` lokalisieren.** Der Restverlust (−0,0206 USD/Tr) sitzt
   nachweislich im Zielsystem: `tp2` 28,4320 und POC-Niveaus 32,3–32,8 bei
   H2-Kursen 46–54. Soll `_gegenkante` ebenfalls auf `L960` lokalisiert werden
   — dieselbe Operation, die Q29 geheilt hat?
3. **`tp1_anteil_pct` / POC-Fenster.** `berechne_kausalen_histogramm_poc`
   arbeitet mit `poc_start = 0` (Box-Beginn) — das ist die dritte globale
   Referenz im System. Ueberpruefen, ob auch sie auf `L960` gehoert.
4. **Reihenfolge bestaetigen.** Nach F8.2/F8.3 (Zielsystem) kann die
   Hybrid-Schliessung auf `L960` und erst danach der Zustandsautomat folgen.
5. **D3-Gate `USD/Trade > 0`.** Es ist derzeit **von keiner Variante**
   erfuellt. Zu klaeren, ob das Gate als *Zulassungs*- oder als
   *Zielkriterium* gilt (d. h. ob eine mechanisch geheilte, aber noch
   negative Variante weiterverfolgt werden darf).

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache.**
"""

neu = vorher.decode("utf-8") + TEXT
P.write_text(neu, encoding="utf-8", newline="\n")
n_b = P.read_bytes()
assert n_b.count(b"\r\n") == 0, "CRLF nach Append!"
print(f"vorher  {len(vorher)} B  {ist}")
print(f"nachher {len(n_b)} B  {hashlib.sha256(n_b).hexdigest()}")
print(f"delta   {len(n_b) - len(vorher)} B")
