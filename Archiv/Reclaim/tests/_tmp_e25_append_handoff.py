# -*- coding: utf-8 -*-
"""LF-Append: Phase 2 / E-25 an test/SESSION_HANDOFF.md (Blob-SHA-schonend)."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"F:\Python\PyLab\test\SESSION_HANDOFF.md")
SOLL = "4dd5091b48a0f7297475f7449964c73808b2f49b1f0bf4864ef67e5332d34feb"

vorher = P.read_bytes()
ist = hashlib.sha256(vorher).hexdigest()
assert ist == SOLL, f"Vorbedingung verletzt: {ist} != {SOLL}"
assert vorher.count(b"\r\n") == 0, "Datei ist nicht LF-clean"

TEXT = """
---

## Phase 2 / E-25 (2026-09-11, i) — Regime-Zustandsautomat: **das Gate ist anti-selektiv**

Der in E-24 (`F2`) geforderte Zustandsautomat wurde als read-only
Vorwärts-Simulation implementiert und gegen die 54 H2-Trades (LEGACY-Basis,
`tp2` = 45,7890) gemessen. **Ergebnis vorweg: jede untersuchte
Deklarationsquelle erzeugt `Q_stop` = 1,000 und tötet den einzigen Trade mit
positivem USD.**

### F1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e25_state_machine.py` | `ac00748ed82646e2f4cd08d4a7056bb887b8f30b386957e2a85de1f1176406e0` | 17.923 |
| `test/_tmp_e25_state_machine_out.txt` | `ffad99061b0d306304df96d48dbeac923c6eaae9cc9a42c6e227b25294016164` | 7.029 |
| `test/_tmp_e25_probe.py` | `{P1}` | {S1} |
| `test/_tmp_show_tail.py` | `{P2}` | {S2} |
| `test/_tmp_grep.py` | `{P3}` | {S3} |

### F2 · Q3 — ATR-Ordnungen (USD)

| Bar | Datum (BKZ) | ATR14 | ATR480 | ATR960 | 1,5 · ATR960 |
|---|---|---|---|---|---|
| 17.692 | 2025-10-01T00:00 | 0,0759 | 0,1206 | 0,1073 | 0,1609 |
| 18.172 | 2025-10-08T05:00 | 0,1539 | 0,1359 | 0,1282 | 0,1924 |
| 18.824 | 2025-10-17T08:00 | 0,1272 | 0,2312 | 0,1933 | 0,2899 |
| 20.000 | 2025-11-05T03:15 | 0,1504 | 0,1495 | 0,1656 | 0,2484 |
| 21.552 | 2025-11-28T02:45 | 0,1107 | 0,1687 | 0,1885 | 0,2827 |

Vergleichsgrößen: Split-Konsolidierung K408/K409 = **1,3331 USD** · §12-Kette
1,19–2,98 USD · typische 96-Bar-Range 0,7–0,9 USD · H2-Spanne 10,9950 USD.
⇒ Die Spec-Schwelle `Spanne < 1,5 · ATR960` (0,161–0,290 USD) liegt um den
Faktor **≈ 7–10 zu niedrig** für die Objekte, die sie finden soll.

### F3 · Q1 — Pfad A ist nicht diskriminierend

- **Erstbruch** (2 Closes > 47,1221): Bar **17.708** (2025-10-01T04:00).
- **Pfad A** (2 konsekutive Closes zurück unter das Dach) feuert bei Bar
  **17.713** — 5 Bars nach dem Bruch und **1 Bar vor dem ersten Entry**
  (17.713). Danach **202 Bars** mit erfüllter Bedingung (erste fünf
  17.713…17.717, letzte fünf 19.988…19.994).
- Varianten: 3 Closes < Decke → 193 Treffer (erster 17.714) · 2 Closes <
  Mittelband 46,4556 → 27 (erster 17.851) · 1 Close < Mittelband → 34 (17.850) ·
  2 Closes < Boden 45,7890 → 3 (erster 19.478).

⇒ Pfad A öffnet sofort wieder und bleibt nahezu durchgehend offen. Als
Rückkehr-Bedingung **untauglich**; allein Pfad B könnte diskriminieren.

### F4 · Q2 — Pfad B in der ratifizierten Form findet **nichts**

`≥ 3 Pivots (touch_conf ≥ 3)` im 480er-Fenster, **beidseitig**, mit
`Spanne < 1,5 · ATR960`: **0 Deklarationen** über ganz H2.
Kalibrierung `Spanne < m · ATR960`:

| m | 1,5 | 3,0 | 5,0 | 10,0 | 20,0 |
|---|---|---|---|---|---|
| Deklarationen | 0 | 0 | 0 | **2** | 15 |

Erste Niveaus bei m = 10: `K@18.326 49,0520/47,7200` · `K@20.761
51,2840/50,3900`. Sensitivität (m = 10): `min_touch` 2 → 1–2,
3 → 2–4, 4 → 2–5 Deklarationen; `min_pivots` 4 setzt m=10/touch=2 auf 0.

### F5 · Erratum E-25 — die §12-Kette ist **kein** Pfad-B-Objekt

Die §12-Auflösung (äußerste **lebende** Kante im 960er-Fenster) ist ein anderes
Objekt als eine Pivot-Balance: sie liegt konstruktionsbedingt am Fensterrand
(40-Tage-Hoch/Tief) und ist damit **nicht durchbrechbar**; der Pivot-Ansatz
liefert dagegen **innere** Bänder (49,05/47,72). Beide sind nicht ineinander
überführbar. ⇒ Das Kalibrierungsziel „m reproduziert die §12-Kette" ist
**falsifiziert**.

### F6 · Q2e — das `L960`-Verfahren reproduziert §12 **exakt** (validiert)

| Bar | §12-Soll (Decke/Boden) | `_paar_l960` (Ist) | Status |
|---|---|---|---|
| 17.692 | K408 47,1221 / K409 45,7890 | 47,1221 / 45,7890 | **identisch** |
| 18.172 | K436 48,6289 / K424 47,3247 | 48,6289 / 47,3247 | **identisch** |
| 18.652 | K494 52,4444 / K493 50,4759 | 52,4444 / 50,4759 | **identisch** |
| 19.612 | K429 48,3972 / K404 46,7691 | 48,3972 / 46,7691 | **identisch** |
| 20.572 | K547 54,2750 / K484 51,4427 | 54,2750 / 51,4427 | **identisch** |

Zwischenwerte (Schritt 480): 19.132 → 49,3040/47,6879 · 20.092 →
48,2710/47,0418 · 21.052 → 52,3420/50,2749 · 21.532 → 53,8797/52,6873.
⇒ Der Neu-Deklarations-Primitiv ist **reproduzierbar**; Pfad B muss auf ihm
aufsetzen, nicht auf Pivot-Touch-Zählung.

### F7 · Q2d — Entscheidend: alle Gates sind anti-selektiv

| Quelle | Neu-Dekl. | Zustände BAL/EXO/EXU | erlaubt | verboten | R (erlaubt) | R_adj | USD/Tr | ATR/Tr | Q_stop | getötete Gewinner |
|---|---|---|---|---|---|---|---|---|---|---|
| **OHNE GATE (54)** | – | 3932/0/0 | 54 | 0 | −19,065650 | −53,000000 | −0,0328 | −0,0463 | 0,981 | – |
| PIVOT m=10 | 2 | 1259/2161/512 | 17 | 37 | −17,000000 | −17,000000 | −0,1581 | −1,2133 | **1,000** | 1 |
| PIVOT m=20 | 18 | 1282/1098/1552 | 30 | 24 | −30,000000 | −30,000000 | −0,1679 | −1,2129 | **1,000** | 1 |
| L960-SEG | 228 | 3396/467/69 | 46 | 8 | −46,000000 | −46,000000 | −0,1915 | −1,2526 | **1,000** | 1 |
| STATIC K408 (E-24) | – | – | 2 | 52 | −2,000000 | −2,000000 | −0,2050 | – | **1,000** | 1 |

Die OHNE-GATE-Zeile reproduziert E-23/`LEGACY` **bit-identisch** (R
−19,065650 · R_adj −53,000000 · USD/Tr −0,0328 · ATR/Tr −0,0463 · Q_stop
0,981) — die Risikobasis `|sl − open[entry_bar]|` ist damit gegen E-23
abgeglichen (Avg-Risiko 0,1919 USD, Summen-USD −1,7711).

Entscheidende Zahlen:

- Der **einzige** Trade mit `R > 0` ist `k` 18.824 mit **R +33,934350**. Er wird
  von **allen** Gate-Varianten verboten.
- **Summen-USD:** OHNE GATE **−1,7711** · PIVOT m=10 −2,6877 · PIVOT m=20
  −5,0370 · L960-SEG −8,8090. **Jedes Gate verschlechtert den Gesamt-USD.**
- `R_adj` erscheint bei allen Varianten besser (−17 / −30 / −46 ≫ −53), aber nur,
  weil der Wegfall des Gewinners `R_max` vernichtet: `R_adj = R` **ohne jeden
  positiven Beitrag**. Nach `D2` wären alle drei zulässig — **`D1`
  (`Q_stop` > 0,75) schließt sie alle kategorisch aus.**

### F8 · Interpretation (kein Auswahlmenü)

1. Ein Regime-Gate, das nach dem Bruch **Short verbietet**, verbietet in H2 den
   Regelfall: alle 54 Trades sind SHORT, und laut E-24 `F0` war die Handelszone
   bereits beim ersten Signal ungültig.
2. Das Gate ist **kein Filter, sondern eine Auswahl der Verlierer**. Die Ursache
   liegt nicht in der Güte des Zustandsautomaten, sondern darin, dass der
   einzige Gewinner **im** Expansionsbereich liegt — das Gate entfernt genau die
   Prämie, die die Strategie trägt.
3. Der einzige Gewinner ist zudem ein **Artefakt der `tp2`-Umstellung**
   (`VD_K408_409`, E-20): unter der Baseline (`tp2` 28,4320) ist derselbe Trade
   ein Stop. Was das Gate tötet, ist die V-D-Zielwahl — kein Edge.

### F9 · Offene Entscheidungen (Textblock)

1. **Pfad B neu definieren.** Der Pivot-Ansatz ist widerlegt (E-25); das
   validierte Verfahren ist `L960` (§12, reproduzierbar nach F6). Offen ist die
   **Breitenbedingung**: §12-Bänder sind 1,19–2,98 USD breit (≈ 6–16 · ATR960).
   Soll Pfad B **ohne** Spannen-Kriterium arbeiten — jede `L960`-Neuauflösung
   ist eine neue Balance — oder mit `Spanne < m · ATR960`, m ∈ [10, 16]?
2. **Neu-Deklarations-Takt.** `L960` wechselt in H2 **228×** (≈ alle 17 Bars)
   und setzt jedes Mal auf `BALANCE` zurück; der Automat wird dadurch weitgehend
   inert (3396/3932 Bars `BALANCE`). Ist die Hybrid-Schließung (Neu-Deklaration
   **nur** aus `EXPANSION_*` heraus) verbindlich?
3. **Gate-Richtung prüfen.** Da alle H2-Trades SHORT sind und der Automat nur
   SHORT verbietet, ist „Gate aktiv" derzeit deckungsgleich mit „Handel
   eingestellt". Ist das der Zweck — oder soll das Gate **LONG freigeben**?
4. **`R` / `R_adj` als führende Metrik.** `R_adj` erweist sich hier als
   **irreführend** (besser, obwohl der USD schlechter wird). Bleibt Beschluss 4
   (USD/ATR führend, R sekundär) bestehen — und wird `R_adj` künftig **neben**
   `USD/Tr` ausgewiesen, statt als Zulassungskriterium zu dienen?

Bis zu diesen Entscheidungen unverändert: **kein Einbrand in
`backtest_lab/phasen_regime_adapter.py`, kein §75, kein S1-Cache.**
"""


def sha(p: str) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def groesse(p: str) -> str:
    return f"{pathlib.Path(p).stat().st_size:,}".replace(",", ".")


TEXT = TEXT.replace("{P1}", sha("test/_tmp_e25_probe.py"))
TEXT = TEXT.replace("{S1}", groesse("test/_tmp_e25_probe.py"))
TEXT = TEXT.replace("{P2}", sha("test/_tmp_show_tail.py"))
TEXT = TEXT.replace("{S2}", groesse("test/_tmp_show_tail.py"))
TEXT = TEXT.replace("{P3}", sha("test/_tmp_grep.py"))
TEXT = TEXT.replace("{S3}", groesse("test/_tmp_grep.py"))

neu = vorher.decode("utf-8") + TEXT
P.write_text(neu, encoding="utf-8", newline="\n")

n_b = P.read_bytes()
assert n_b.count(b"\r\n") == 0, "CRLF nach Append!"
print(f"vorher {len(vorher)} B  {ist}")
print(f"nachher {len(n_b)} B  {hashlib.sha256(n_b).hexdigest()}")
print(f"delta {len(n_b) - len(vorher)} B  CRLF {n_b.count(b'\\r\\n')}  "
      f"LF {n_b.count(b'\\n')}")
