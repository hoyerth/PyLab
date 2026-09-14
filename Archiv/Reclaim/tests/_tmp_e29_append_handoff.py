# -*- coding: utf-8 -*-
"""LF-Append: E-29 (Binning-Audit + H2-Stop-Out-Anatomie) an SESSION_HANDOFF.md."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"F:\Python\PyLab\test\SESSION_HANDOFF.md")
SOLL = "86e65764d5e25667b88de0213f00f49d3a3050b543963f1be42f22706b93ba17"

vorher = P.read_bytes()
ist = hashlib.sha256(vorher).hexdigest()
assert ist == SOLL, f"Vorbedingung verletzt: {ist} != {SOLL}"
assert vorher.count(b"\r\n") == 0, "Datei ist nicht LF-clean"

TEXT = """
---

## Phase 2 / E-29 (2026-09-11, m) — Binning-Audit & H2-Stop-Out-Anatomie: **die Rausch- und die Stop-Hypothese sind falsifiziert**

Auftrag (Anwender-Freigabe): (1) `geg960poc` als Kernstandard arretieren,
(2) `num_bins = 60` bei 960 Bars rein datenseitig pruefen, (3) Ursachen der
H2-Stop-Outs lokalisieren, (4) Hybrid-Schliessung auf `L960` vorbereiten.
Alle Messungen read-only; **keine** Aenderung an Engine oder Adapter.

### H0 · Reproduktions-Fidelity

Der E-29-Harness reproduziert `geg960poc` aus E-28 **bit-identisch**:
271 Setups · R +55,871446 · USD +14,2466 · USD/Tr +0,0526 · ATR/Tr +0,3890 ·
Q_stop 0,742 · H1 232 / H2 39. Die POC-Diagnose-Replikation ist gegen den
Engine-Rueckgabewert per `assert` abgesichert (Abweichung < 1e-9).

### H1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e29_audit.py` | `7a51c1fa74f047ed0e02b2d32ffd757d1112471db028ece82fc666b630016e1b` | 16.962 |
| `test/_tmp_e29_run_all.py` | `ea56621aa73b9942c55fcf9c94ac33d554f482901eb0a0b7674837077efc09ac` | 1.159 |
| `test/_tmp_e29_sammel.py` | `0ec406e0d46669a0ad46e2a0eceb5102c0d7a699d4e3b7e4e66c426121884d28` | 2.592 |
| `test/_tmp_e29_h2.py` | `e7fcc3fdcdcd2c65fcae41cbfce770e44b1aa2d410c4c5b198c2f897a1bf14f3` | 1.837 |
| `test/_tmp_e29_be.py` | `9208bac371f6ac5fd98f224c262015a2da3de8a02bfd944752e7c4559329caff` | 5.911 |
| `test/_tmp_e29_risk.py` | `2a25882723423ec5cb918d1955b8338fefb374f7708cb32c5dcc6ff703a9840d` | 2.459 |
| `test/_tmp_e29_diag.py` | `20e73d125853bacf78222f8f3df964ab68b4862ffb94d61e6fc6d89598f70466` | 1.068 |
| `test/_tmp_e29_setups_s2_b60.pkl` | `17865f660bae248e8d7b173af084ed8c09bf4eb713de53c0448f7abb6910724c` | 37.384 |
| `test/_tmp_e29_setups_aug_b60.pkl` | `35ad8b0c70ea53c47b2d037b0633bbc79127c6d90aa8bc55e192844d65d1f017` | 1.270 |
| `test/_tmp_e29_audit_s2_b60_out.txt` | `ed359babb90f24be971e97b213ae91a50e61b0073297f4ad9353c90caabede25` | 28.388 |
| `test/_tmp_e29_audit_aug_b60_out.txt` | `d60b6739cda5088ad7251201b657dca6bd7167e5c5aa5da08215e62f45505372` | 3.080 |

**Kernmechanik (Engine Z. 1586-1647, unveraendert):** `rm = 0,5·r1 + 0,5·r2`,
`r1 = -1` bei SL, `tp1 = POC`, `tp2 = Gegenkante`. Daraus folgt **exakt**:
`rm <= -1` ist nur moeglich, wenn **beide** Haelften am Stop enden. Q_stop
ist also **keine Glaettungs- oder Ausreisserfrage**, sondern die Aussage:

> Q_stop = Anteil der Trades, bei denen der Preis **den POC nie vor dem Stop
> beruehrt hat**.

Diese Identitaet ist der Schluessel zu allen weiteren Lesarten.

### H2 · T1 — Binning-Oekonomie: **keine ungefuellten Bins, keine Rauschsorge**

| `num_bins` | Fenster-Bars median | Preisspanne median | Bin-Breite median | leere Bins |
|---|---|---|---|---|
| 10 | 961 | 2,0355 | 0,203550 | **0** (0,0 %) |
| 15 | 961 | 2,0355 | 0,135700 | **0** (0,0 %) |
| 20 | 961 | 2,0250 | 0,101250 | **0** (0,0 %) |
| 30 | 961 | 2,0150 | 0,067167 | **0** (0,0 %) |
| 40 | 961 | 1,9660 | 0,049150 | **0** (0,0 %) |
| 60 | 961 | 1,9015 | 0,031692 | **0** (0,0 %) |

Die Sorge „960 Bars auf 60 Bins ⇒ jedes Bin zu schmal ⇒ zufaellige Docht-Peaks"
ist **empirisch falsifiziert**: bei **jeder** Aufloesung von 10 bis 60 Bins ist
**kein einziges Bin leer**. Ursache: die Binnung laeuft nicht ueber die Zeit,
sondern ueber den **Preisraum `[unter, ober]` = [Gegenkante, Einstiegskante]**
(Median ~2,0 USD) bei ~961 Bars — jedes Bin wird von vielen Bars getroffen.
Die POC-Aufrufe steigen von 284 (b10) auf 308 (b60), weil der POC selbst
ueber die Ordnungsbedingung `sl < entry < poc < tp2` auf die Annahme
zurueckwirkt.

### H3 · T2 — Binning-Sweep S2 (`box_end_bar = n`, Kernstandard `geg960poc`)

| `num_bins` | Setups | R ges. | USD/Tr | ATR/Tr | Q_stop | H1 n | H2 n | H2 R | H2 USD/Tr |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 284 | +38,280775 | +0,0395 | +0,3797 | 0,810 | 243 | 41 | +17,531395 | +0,1498 |
| 15 | 284 | +31,006989 | +0,0367 | +0,3359 | 0,806 | 243 | 41 | +16,859602 | +0,1478 |
| 20 | 283 | +31,610277 | +0,0384 | +0,3334 | 0,784 | 242 | 41 | +17,384518 | +0,1533 |
| 30 | 280 | +31,505286 | +0,0395 | +0,3439 | 0,761 | 239 | 41 | +16,901548 | +0,1513 |
| 40 | 279 | +56,479291 | +0,0509 | +0,4160 | 0,746 | 238 | 41 | +42,091396 | +0,2228 |
| **60** | **271** | **+55,871446** | **+0,0526** | **+0,3890** | **0,742** | 232 | 39 | **+43,745381** | **+0,2549** |

Kein Rausch-Muster, sondern ein **monotoner Effekt mit Plateau bei 40-60**:
mit groeberem Bin springt der POC auf ein groeberes Niveau (Bin-Mitte), was die
Zielwahl verschlechtert. Der Anteil des Max-Bins steigt von 4,50 % (b60) auf
17,27 % (b10) — der POC wird also **nicht verrauscht, sondern unspezifisch**.

**Die harte Grenze kommt jedoch von AUG** (Tabelle H4): `num_bins` ist ein
**globaler** Parameter und **nicht** lokalisiert. Schon `num_bins = 40`
veraendert die August-Baseline. Damit ist die Entscheidung nicht
Geschmackssache, sondern erzwungen.

### H4 · `num_bins` ist AUG-kritisch — 60 bleibt

| `num_bins` | AUG Setups | AUG R ges. | AUG USD/Tr | AUG Q_stop |
|---|---|---|---|---|
| 10 | **9** | +36,272980 | +1,0953 | 0,333 |
| 15 | **9** | +35,934863 | +1,0970 | 0,333 |
| 20 | **9** | +34,683981 | +1,0655 | 0,333 |
| 30 | **9** | +35,597659 | +1,0890 | 0,222 |
| 40 | 8 | +36,488272 | +1,2566 | 0,125 |
| **60** | **8** | **+38,919584** | **+1,4077** | **0,125** |

`num_bins = 40` verschiebt den V018-Anker (R +38,919584 → +36,488272), und
`<= 30` erzeugt **einen zusaetzlichen Trade** (9 statt 8). Es gibt hier —
anders als bei der Lokalisierung (`_W(k) = 0` ⇒ konstruktive Inertheit) —
**keine** Invarianz. **Verdikt: `num_bins = 60` bleibt arretiert.** Der
Binning-Audit ist damit abgeschlossen und *beendet*, nicht offen.

### H5 · H2-Stop-Out-Anatomie (Rekonstruktion aus gespeicherter Geometrie)

H2 (`n = 39`): **32 STOP** (r <= -1) · 3 Teil-SL · 4 ok.
Der Median-Abstand Entry -> TP1(POC) betraegt **13,29 R** (Maximum 74,32 R).

| Kenngroesse | Wert |
|---|---|
| Stop-Outs mit **MFE >= 1,0 R** (hat funktioniert, dann gedreht) | **18 von 32** |
| Stop-Outs mit MFE < 0,5 R (nie in Bewegung) | 10 von 32 |
| d_POC (Entry -> TP1) min / median / max | 0,15 / **13,29** / 74,32 |
| risk (USD) min / median / max | 0,0410 / 0,1670 / 0,4090 |

Die H2-Stop-Outs sind also **kein** gleichfoermiges Bild: 18 Trades waren
zwischenzeitlich im Gewinn (teils > 20 R), 10 waren sofort falsch. Das ist
genau die Signatur eines **fehlenden Verlust-Managements**, nicht einer
falschen Richtung.

### H6 · Risiko-Kalibrierung — die Stop-Hypothese ist **falsifiziert**

Meine Arbeitshypothese aus H5 ("der Stop ist degeneriert, E-22") haelt der
Messung **nicht** stand:

| Datensatz | Haelfte | risk/Entry % (med) | **risk/ATR14 (med)** | d_POC [R] (med) | ATR14 med |
|---|---|---|---|---|---|
| S2 | gesamt | 0,302 | 1,36 | 6,72 | 0,0868 |
| S2 | H1 | 0,301 | 1,40 | 5,86 | 0,0752 |
| **S2** | **H2** | 0,348 | **0,96** | **13,29** | 0,1664 |
| AUG | H1 | 0,385 | 1,27 | 4,43 | 0,1906 |

Der strukturelle Stop liegt bei **~1 ATR14** — das ist ein *normaler*, kein
degenerierter Stop. Das eigentliche Missverhaeltnis sitzt im **Ziel**: TP1
(= POC) liegt in H2 bei **~13 ATR14** Entfernung (Entry an der Aussenwand,
POC in der **Mitte der lokalen Spanne ~2,0 USD ≈ 4,2 % Kursweg**). Der Trade
muss also unmittelbar ~4 % gegen die Bewegung laufen, bevor die erste Haelfte
bezahlt wird — in einem **Trendabschnitt**.

**Kernsatz E-29:** Nicht der Stop ist zu eng, sondern **das Ziel ist zu weit** —
und zwar systematisch, weil Q29 den Einstieg an die *Aussenwand* legt,
waehrend der POC die *Mitte* der Spanne markiert.

### H7 · Break-Even-Studie: **Falsifikation** des naheliegenden Fixes

Pfadgenau, ohne Look-ahead (Stop-Wechsel wirkt ab dem Folgebar; bei Gleichstand
im selben Bar gewinnt der Stop, identisch zur Engine). Schwellwert `x` =
MFE-Schwelle fuer Stop auf Einstand.

S2 (`n = 271`):

| Variante | R ges. | **USD/Tr** | ATR/Tr | Q_stop | geaenderte Trades |
|---|---|---|---|---|---|
| **BASIS (arretiert, kein BE)** | +55,871446 | **+0,0526** | +0,3890 | 0,742 | 0 |
| BE-Stop ab +0,25 R | -17,140669 | +0,0010 | -0,0608 | **0,269** | 190 |
| BE-Stop ab +0,50 R | -8,149865 | +0,0024 | -0,0152 | 0,339 | 165 |
| BE-Stop ab +0,75 R | +13,778437 | +0,0181 | +0,0874 | 0,387 | 145 |
| BE-Stop ab +1,00 R | +27,425888 | +0,0218 | +0,2040 | 0,424 | 130 |
| BE-Stop ab +1,50 R | +63,010310 | +0,0457 | +0,3647 | 0,506 | 104 |
| BE-Stop ab +2,00 R | +61,897816 | +0,0497 | +0,4086 | 0,579 | 77 |
| BE-Stop ab +3,00 R | +45,473281 | +0,0434 | +0,3456 | 0,646 | 52 |
| BE +1,00 R + Trail 0,5 R | +19,006714 | +0,0114 | +0,0645 | 0,424 | 141 |
| BE +2,00 R + Trail 0,5 R | +1,904968 | -0,0018 | +0,0064 | 0,579 | 91 |

AUG (`n = 8`) bestaetigt: BE-Stop ab +0,25 R halbiert den Ertrag
(USD/Tr +1,4077 → +0,4960); erst ab +3,00 R ist er neutral
(+1,4135, eine einzige geaenderte Position = Rauschen).

**Zwei Schlussfolgerungen, beide unangenehm:**

1. **Kein Break-Even-Wert verbessert das führende Maß.** Q_stop faellt von
   0,742 auf 0,269 — und `USD/Trade` von +0,0526 auf +0,0010. Bei +1,50 R
   *steigt* `R` auf +63,01, waehrend `USD/Trade` auf +0,0457 **faellt**:
   die R-Summe und das USD-Maß laufen auseinander (erneut die D2/D3-Lehre —
   `R` ist ungewichtet, `USD/Trade` gewichtet mit dem Risiko).
2. **`Q_stop` ist als Optimierungsziel untauglich und spielfaehig.** Es laesst
   sich trivial auf 0,269 druecken, waehrend das System schlechter wird. Als
   *Ausschluss*-Kriterium (`D1`) bleibt es brauchbar; als *Ziel* ist es
   verboten. **H2/Q_stop = 0,821 ist damit nicht der eigentliche Defekt.**

### H8 · Hybrid-Schliessung: beide Schranken gemessen

Als Naetherung fuer den Strukturbruch dient die Einstiegskante (Basis); als
Bruch gilt der erste Close jenseits dieser Kante vor dem Stop.

| Sicht | Regel | R ges. | USD/Tr | Q_stop | Gewinner getoetet |
|---|---|---|---|---|---|
| Basis | – | +55,871446 | +0,0526 | 0,742 | – |
| **T4b (obere Schranke)** | Bruch-Exit **nur** auf Verlust-Trades (ex post) | **+115,099620** | **+0,0836** | **0,351** | 0 |
| **T4c (untere Schranke)** | Bruch-Exit mechanisch auf **alle** Trades | **-52,613531** | +0,0031 | 0,742 | **18 von 35** |

AUG analog: T4c toetet **4 von 5** Gewinnern (-26,835559 R;
USD/Tr +1,4077 → +0,1469).

Die Spanne zwischen +115,10 und -52,61 R ist **vollstaendig** eine Frage der
**Diskrimination** — nicht der Exit-Mechanik. Ein nackter Close-Bruch ist ein
Whipsaw-Generator; er braucht den Zustandsautomaten (Block A), der Rauschen
von echter Neu-Deklaration trennt. Das ist die **quantifizierte**
Arbeitsanweisung fuer Schritt 3: die Hybrid-Schliessung ist **genau dann**
wertvoll, wenn ihre Trennschaerfe nahe an T4b heranreicht.

### H9 · Ratifizierungen (Anwender-Freigabe, 2026-09-11 m)

1. **`geg960poc` ist der verbindliche Kernstandard fuer `L960`** — Q29 lokal
   960, Gegenkante lokal 960-Lebigkeit, POC-Anker lokal 960. Die Varianten
   `base`, `geg`, `poc`, `gegpoc` sind als **abgearbeitet** archiviert;
   `gegleb`/`geglebpoc` sind als **96-Bar-Artefakt** verworfen (E-28/G0).
2. **`D1` gilt fuer die Gesamtbilanz** (Q_stop = 0,742 <= 0,75). Die
   H2-Teilquote (0,821) ist bei `n = 39` statistisch nicht belastbar und wird
   **nicht** als Abbruchkriterium angewandt — sie bleibt aber als sekundaerer
   Beobachtungspunkt notiert.
3. **`tp1_anteil_pct = 50 %` bleibt unveraendert** (kein zweiter Hebel
   gleichzeitig).
4. **`num_bins = 60` bleibt arretiert** — nicht wegen S2, sondern wegen des
   AUG-Ankers (H4).
5. **Reihenfolge bestaetigt:** Zielsystem arretiert -> Binning geprueft
   (erledigt, geschlossen) -> **Hybrid-Schliessung auf `L960`** -> Zustandsautomat.

### H10 · Offene Entscheidungen (Textblock)

1. **Zielgeometrie statt Stop-Management.** Der Kernbefund (H6) ist ein
   **Ziel**-Problem: TP1 = POC liegt in H2 bei ~13 ATR. Zwei Wege sind
   denkbar: (a) eine **Obergrenze** fuer den Zielabstand einfuehren
   (`V3_TP_MINDIST_PCT = 1,5 %` ist eine *Unter*grenze — es gibt keine
   Obergrenze), oder (b) die **Einstiegsseite** relativieren (Q29 an der
   Aussenwand ist in einem Trendabschnitt strukturell benachteiligt). Zu
   entscheiden ist, welcher Weg zuerst gemessen wird.
2. **`H7` verlangt eine Zieldefinition.** Soll die Hybrid-Schliessung auf
   `USD/Trade` optimiert werden (Empfehlung) und `Q_stop` **nur** als
   Ausschlusskriterium gefuehrt werden? Das ist die direkte Konsequenz aus
   der Antagonie in H7.
3. **Whipsaw-Kontrolle als Pflichtmetrik.** T4c zeigt die Untergrenze. Fuer
   jede Hybrid-Variante ist kuenftig **mit** zu berichten, wie viele
   *Gewinner* sie toetet (Analogon zu E-25 „getoetete Gewinner").
4. **Fortfuehrung read-only** trotz unbefriedigender H2-Teilquote — bestaetigt;
   ein Einbrand bleibt ausgeschlossen.

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
