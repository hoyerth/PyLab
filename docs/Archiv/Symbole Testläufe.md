# Symbole Testläufe — Reclaim-Engine (Setup B) quer über Assets

> **Zweck:** Zentrales Archiv für Testläufe der SILVER-Reclaim-Baseline
> (`scripts/phasen_volumen_profil.py`, v0.4.x-baseline-frozen) auf weiteren
> Symbolen. Pro Symbol werden die Parameter an die Preisstruktur kalibriert
> (ATR-Skalierung + VA_PCT-Resonanz) und die Referenzfenster AUG / S1 / S2
> gelaufen (Equity-Statistik, txt + png Artefakte).
> **Produktions-Baseline bleibt exklusiv SILVER M15** (VA_PCT 0.93).
> **Stand:** 06.09.2026 — BRENT M15 (QS-4), COCOA M15 (QS-5), NGas M15
> (QS-6), EURUSD M15 (QS-7), Ger40 M15 (QS-8, grobe Orientierung) und
> COFFEE M15 (QS-9) abgeschlossen.

---

## 1. Protokoll (analog QS-3 GOLD, §8.27 `docs/makro_swings_experiment.md`)

1. **Inventur & ATR-Ratio:** USD-Schwellen (`TOL`, `TOL_TOUCH`, `DENSITY_BAND`,
   `SHIFT_TOL`) werden je Fenster über das Verhältnis der mittleren M15-Bar-Spanne
   (Asset/SILVER) skaliert — keine starren Preisratios.
2. **SL-Vola-Skalierung:** `SL_PCT` wird je Fenster auf ~0,87 ATR des Assets
   gesetzt (sonst ersticken zu weite %-Stops die R-Multiples).
3. **Reihenuntersuchung der wichtigsten Parameter** für den Sweet Spot:
   VA_PCT-Resonanz-Sweep (0,85–0,99), SL_PCT-Sensitivität (um den 0.87-ATR-
   Anker), MIN_SPREAD_PCT-Gate. Optimum = höchste kombinierte S1+S2-Summe R
   (analog GOLD-Protokoll; Kurs%/Trade als Vergleichsmetrik).
4. **Finale Testläufe** AUG/S1/S2 mit dem Sweet-Spot-VA_PCT + Fenster-Skalierung
   → `stats_trades_<Symbol>_<Fenster>.txt` + Phasen-Chart + Equity-Kurve.

**Ausführung:** Arbeitskopie `test/tmp_phasen_volumen_profil_symbol.py`
(bitgenau zur SILVER-Baseline, verifiziert AUG 27 Tr / +24.97R / PF 2.83),
`--symbol=...`, `--stats-txt=...`, Parameter-Overrides per CLI.
Sweeps: `test/tmp_symbol_sweep.py SYMBOL FENSTER PARAM WERTE [KEY=VAL]`.

---

## 2. Parameter-Kalibrierung je Symbol (M15)

### 2.1 SILVER (Produktions-Baseline, unverändert)
| Parameter | Wert | Bemerkung |
|---|---|---|
| VA_PCT | **0.93** | Resonanzkante SILVER (§8.23) |
| TOL / TOL_TOUCH / DENSITY_BAND / SHIFT_TOL | 0.34 / 0.15 / 0.15 / 0.05 USD | fensterunabhängig (Baseline-Default) |
| SL_PCT | 0.45 % | fensterunabhängig (Baseline-Default) |
| MIN_CANDLES / MIN_TOUCHES / MIN_SPREAD_PCT | 46 / 3 / 1.5 % | unverändert |

### 2.2 GOLD (QS-3, §8.27 — dokumentarisch)
| Fenster | TOL | TOL_TOUCH / DENSITY_BAND | SHIFT_TOL | SL_PCT | VA_PCT |
|---|---|---|---|---|---|
| S1 | 10.1 | 4.5 | 1.5 | 0.21 % | **0.95** |
| S2 | 19.2 | 8.5 | 2.8 | 0.29 % | **0.95** |

### 2.3 BRENT (QS-4, dieser Testlauf — ATR-Ratio BRENT/SILVER je Fenster)
Mittlere M15-Bar-Spanne (USD): BRENT AUG 0.301 / S1 0.473 / S2 0.172
— SILVER AUG 0.234 / S1 0.377 / S2 0.097 → Ratio 1.29 / 1.25 / 1.77.

| Fenster | TOL | TOL_TOUCH / DENSITY_BAND | SHIFT_TOL | SL_PCT (≈0.87 ATR) | VA_PCT |
|---|---|---|---|---|---|
| AUG | 0.4388 | 0.1936 | 0.0645 | 0.2968 % | **0.95** |
| S1  | 0.4265 | 0.1881 | 0.0627 | 0.4536 % | **0.95** |
| S2  | 0.6030 | 0.2660 | 0.0887 | 0.2190 % | **0.95** |

**Resonanz-Bestimmung:** VA_PCT-Sweep S1+S2 (0.85–0.99), Optimum bei
**VA_PCT = 0.95** (S1 +134.83R / S2 +212.85R → kombiniert +347.68R).
Damit liegt die BRENT-Resonanzkante identisch zu GOLD (+0.02 vs. SILVER 0.93).

### 2.4 COCOA (QS-5, dieser Testlauf — ATR-Ratio COCOA/SILVER je Fenster)
Mittlere M15-Bar-Spanne (USD): COCOA AUG 45.43 / S1 34.71 / S2 61.64
— SILVER AUG 0.234 / S1 0.377 / S2 0.097 → Ratio 194.5 / 92.0 / 635.4.
Cocoa-Preisniveau ~4–12.6k USD (Range-Jahr 2025 bis 12.6k); Sessions
(~8–12 h/Tag) deutlich kürzer als Metalle → geringere Bars (AUG 490, S1 4.852,
S2 7.893).

| Fenster | Bars | TOL | TOL_TOUCH / DENSITY_BAND | SHIFT_TOL | SL_PCT (≈0.87 ATR) | VA_PCT (Sweet Spot) |
|---|---|---|---|---|---|---|
| AUG | 490 | 66.1328 | 29.1763 | 9.7254 | 0.6718 % | **0.91** |
| S1  | 4.852 | 31.2673 | 13.7944 | 4.5981 | 0.7005 % | **0.91** |
| S2  | 7.893 | 216.0518 | 95.3170 | 31.7723 | 0.6133 % | **0.91** |

**Sweet-Spot-Bestimmung (Reihenuntersuchung):** VA_PCT-Sweep S1+S2 → Optimum
**0.91** (+176.01R kombiniert). Regime-Divergenz: S1 (2026, Abverkauf) Kuppe
bei 0.95, S2 (2025, Rally) Kuppe bei 0.91 → 0.91 als robuster Kompromiss
(dokumentiert in §11).

### 2.5 NGas (QS-6, dieser Testlauf — ATR-Ratio NGas/SILVER je Fenster)
Mittlere M15-Bar-Spanne (USD): NGas AUG 0.0095 / S1 0.0131 / S2 0.0163
— SILVER AUG 0.2336 / S1 0.3775 / S2 0.0970 → Ratio 0.041 / 0.035 / 0.168.
NGas-Preisniveau 2.77 / 2.93 / 3.58 USD (2025er-Range ~2.6–4.8 USD); nahezu
durchgehender 24-h-Handel → hohe Bars (AUG 1.286, S1 13.274, S2 21.569).

| Fenster | Bars | TOL | TOL_TOUCH / DENSITY_BAND | SHIFT_TOL | SL_PCT (≈0.87 ATR) | VA_PCT (Sweet Spot) |
|---|---|---|---|---|---|---|
| AUG | 1.286 | 0.0139 | 0.0061 | 0.0020 | 0.3001 % | **0.97** |
| S1  | 13.274 | 0.0118 | 0.0052 | 0.0017 | 0.3885 % | **0.97** |
| S2  | 21.569 | 0.0573 | 0.0253 | 0.0084 | 0.3972 % | **0.97** |

**Sweet-Spot-Bestimmung (Reihenuntersuchung):** VA_PCT-Sweep S1+S2 → Optimum
**0.97** (+285.59R kombiniert). S2 (2025, volatiles Trend-/Range-Jahr mit
Breitband-Ausschlägen 2.6→4.8 USD) verlangt klar weite Zonen **0.97**
(+170.40R / PF 1.72) — im breiten 0.85–0.95-Tal teils negativ; S1 (2026)
steigt monoton zu sehr breiten Zonen (0.99 +129.51R). Kombiniert dominiert
**0.97** (dokumentiert in §15). Resonanzverschiebung damit wie SILVER-Kante
(+0.04 vs. SILVER 0.93, aber stärker ausgeprägt).

### 2.6 EURUSD (QS-7, dieser Testlauf — ATR-Ratio EURUSD/SILVER je Fenster)
Mittlere M15-Bar-Spanne (USD): EURUSD AUG 0.0004 / S1 0.0006 / S2 0.0008
— SILVER AUG 0.2336 / S1 0.3775 / S2 0.0970 → Ratio 0.0018 / 0.0016 / 0.0081.
EURUSD-Preisniveau 1.1608 / 1.1603 / 1.1266 USD (2025er-Band ~1.03–1.17);
durchgehender 24/5-Handel → Bars AUG 1.344 / S1 14.016 / S2 22.756.
**Mikrostruktur-Warnung:** Die M15-Range beträgt nur 0.037–0.070 % vom Preis
(FX-Preisbasis ~1.16) — bei den Commodities waren es 0.3–0.8 %. Der
0.87-ATR-SL-Anker (0.032–0.061 %) wird dadurch extrem eng und muss für die
2026er-Fenster (AUG/S1) auf **~2,2× ATR (SL_PCT 0.10 %)** angehoben werden.

| Fenster | Bars | TOL | TOL_TOUCH / DENSITY_BAND | SHIFT_TOL | SL_PCT (final) | VA_PCT (Sweet Spot) |
|---|---|---|---|---|---|---|
| AUG | 1.344 | 0.0006 | 0.0003 | 0.0001 | **0.10 %** (≈2,2× ATR) | **0.99** |
| S1  | 14.016 | 0.0005 | 0.0002 | 0.0001 | **0.10 %** (≈2,2× ATR) | **0.99** |
| S2  | 22.756 | 0.0028 | 0.0012 | 0.0004 | 0.0608 % (0.87 ATR) | **0.91** |

**Sweet-Spot-Bestimmung (Reihenuntersuchung):** Der ATR-0.87-SL-Anker ergibt
für AUG/S1 (2026, Seitwärts-Chop) tief negative Ergebnisse (−53.52R AUG /
−67.10R S1 bei VA 0.93). Erst SL_PCT **0.10 %** (= ~2,2× ATR) macht S1
positiv (+20.86R bei VA 0.93, Kuppe 0.09–0.10 %), kombiniert mit VA **0.99**
→ +29.28R. S2 (2025, Trendjahr) bevorzugt dagegen den engen Anker
(0.0608 %) bei VA **0.91** → +73.46R (SL-Sweep S2: Anker klar besser als
0.05/0.08/0.10/0.135). MIN_SPREAD_PCT ist auf EURUSD **nicht bindend**
(identische Resultate 0.3–2.0 %, §21). Details in §§19–23.

### 2.7 Ger40 (QS-8, grobe Orientierung — ATR-Ratio Ger40/SILVER je Fenster)
Mittlere M15-Bar-Spanne (Punkte): Ger40 AUG 23.74 / S1 40.56 / S2 33.81
— SILVER AUG 0.234 / S1 0.378 / S2 0.097 USD → Ratio 101.6 / 107.5 / 348.5.
DAX-Preisniveau ~23.2–26.3k Punkte; Sessions ~09:00–22:00 → Bars
AUG 1.106 / S1 11.445 / S2 18.812. Range-Pct 0.09–0.16 % (FX-ähnliche
Mikrostruktur), dennoch funktioniert hier der 0.87-ATR-SL-Anker (anders als
EURUSD — keine SL-Anpassung nötig).

| Fenster | Bars | TOL | TOL_TOUCH / DENSITY_BAND | SHIFT_TOL | SL_PCT (0.87 ATR) | VA_PCT (Sweet Spot) |
|---|---|---|---|---|---|---|
| AUG | 1.106 | 34.5576 | 15.2460 | 5.0820 | 0.0786 % | **0.89** |
| S1  | 11.445 | 36.5340 | 16.1179 | 5.3726 | 0.1429 % | **0.89** |
| S2  | 18.812 | 118.4990 | 52.2790 | 17.4263 | 0.1270 % | **0.89** |

**Sweet-Spot-Bestimmung (grob, reduziertes Raster):** VA-PCT-Sweep
(0.85–0.99) → beide Fenster stimmig bei **0.89** (S1 +117.91R / PF 2.38,
S2 +153.16R / PF 1.83 → kombiniert +271.07R). Ger40-Resonanz liegt damit
knapp **unter** der SILVER-Kante (0.89 vs. 0.93) — Index bevorzugt etwas
engere Zonen als SILVER/GOLD/BRENT/NGas.

### 2.8 COFFEE (QS-9, dieser Testlauf — ATR-Ratio COFFEE/SILVER je Fenster)
Mittlere M15-Bar-Spanne (USD): COFFEE AUG 1.9886 / S1 1.5023 / S2 1.8788
— SILVER AUG 0.2336 / S1 0.3775 / S2 0.0970 → Ratio 8.51 / 3.98 / 19.37.
Coffee-Preisniveau AUG ~305–342 / S1 ~240–353 / S2 ~281–432 (Range je
Fenster); Sessions (~8–12 h/Tag, ICE Soft) → Barzahl identisch zu COCOA
(AUG 490, S1 4.852, S2 7.893), Range-Pct 0.52–0.62 % vom Preis (wie Cocoa
0.3–0.8 %). Der 0.87-ATR-SL-Anker liegt mit ~0.45–0.54 % nahe am
SILVER-Default (0.45 %) — keine Anpassung nötig.

| Fenster | Bars | TOL | TOL_TOUCH / DENSITY_BAND | SHIFT_TOL | SL_PCT (≈0.87 ATR) | VA_PCT (Sweet Spot) |
|---|---|---|---|---|---|---|
| AUG | 490 | 2.8946 | 1.2770 | 0.4257 | 0.5363 % | **0.93** |
| S1  | 4.852 | 1.3531 | 0.5970 | 0.1990 | 0.4481 % | **0.93** |
| S2  | 7.893 | 6.5852 | 2.9052 | 0.9684 | 0.4502 % | **0.93** |

**Sweet-Spot-Bestimmung (Reihenuntersuchung):** VA_PCT-Sweep S1+S2
(0.85–0.99, verfeinert um 0.90/0.92/0.94) → Optimum **0.93** (S1 +57.40R /
PF 2.63, S2 +133.52R / PF 2.54 → kombiniert +190.92R, PF 2.57). S1 (2026,
Abverkauf ~323→240 mit Erholungsrally bis ~353) zeigt ein breites Plateau
0.87–0.93 (Kuppe 0.92–0.93, +59.91R bei 0.92); S2 (2025, Rally-Jahr mit
432er-Hoch und volatiler Range 281–432) hat eine klare Kuppe bei **0.93**.
Damit sind **beide Regime stimmig bei 0.93** — die COFFEE-Resonanz liegt
**exakt auf der SILVER-Kante**, keine Verschiebung und keine Regime-Divergenz
(wie bei COCOA §2.4, dokumentiert in §26).

---

## 3. Ergebnisübersicht (kombinierter Benchmark)

| Symbol | Fenster | Bars | Ph (hb) | Trades | WR % | SumR | PF | AvgW | AvgL | Kurs%/Tr |
|---|---|---|---|---|---|---|---|---|---|---|
| SILVER | S1 | 13.289 | — | 201 | 44.3 | +197.26 | 3.01 | +3.32 | −0.88 | +0.441 |
| SILVER | S2 | 21.624 | — | 210 | 35.2 | +99.88 | 1.80 | +3.04 | −0.92 | +0.214 |
| **SILVER** | **S1+S2** | **34.913** | — | **411** | **39.7** | **+297.14** | **2.33** | — | — | **+0.325** |
| GOLD | S1 | 13.288 | 131 (38) | 198 | 40.4 | +115.75 | 2.08 | +2.78 | −0.91 | +0.123 |
| GOLD | S2 | 21.627 | 75 (28) | 222 | 32.0 | +80.31 | 1.58 | +3.09 | −0.92 | +0.105 |
| **GOLD** | **S1+S2** | **34.915** | 206 (66) | **420** | **36.5** | **+196.06** | **~1.80** | — | — | **+0.113** |
| BRENT | AUG | 1.200 | 11 (3) | 22 | 22.7 | −3.02 | 0.79 | +2.31 | −0.86 | −0.041 |
| BRENT | S1 | 12.351 | 134 (42) | 231 | 39.8 | +134.83 | 2.13 | +2.77 | −0.86 | +0.265 |
| BRENT | S2 | 20.087 | 54 (28) | 231 | 24.7 | +212.85 | 2.31 | +6.59 | −0.93 | +0.202 |
| **BRENT** | **S1+S2** | **32.438** | 188 (70) | **462** | **32.3** | **+347.68** | **2.23** | **+4.23** | **−0.90** | **+0.233** |
| COCOA | AUG | 0.490 | 4 (2) | 18 | 38.9 | +16.86 | 2.53 | +3.98 | −1.00 | +0.629 |
| COCOA | S1 | 4.852 | 54 (24) | 89 | 34.8 | +42.59 | 1.85 | +3.00 | −0.87 | +0.335 |
| COCOA | S2 | 7.893 | 28 (20) | 141 | 25.5 | +133.42 | 2.42 | +6.31 | −0.89 | +0.580 |
| **COCOA** | **S1+S2** | **12.745** | 82 (44) | **230** | **29.1** | **+176.01** | **2.22** | **+4.78** | **−0.88** | **+0.486** |
| NGas | AUG | 1.286 | 11 (4) | 25 | 36.0 | +17.25 | 2.08 | +3.69 | −1.00 | +0.207 |
| NGas | S1 | 13.274 | 105 (29) | 177 | 33.9 | +115.19 | 2.11 | +3.65 | −0.89 | +0.253 |
| NGas | S2 | 21.569 | 96 (48) | 345 | 25.5 | +170.40 | 1.72 | +4.63 | −0.92 | +0.196 |
| **NGas** | **S1+S2** | **34.843** | 201 (77) | **522** | **28.2** | **+285.59** | **1.84** | **+4.26** | **−0.91** | **+0.215** |
| EURUSD | AUG | 1.344 | 12 (0) | 7 | 71.4 | +3.71 | 3.71 | +1.02 | −0.69 | +0.053 |
| EURUSD | S1 | 14.016 | 147 (0) | 124 | 49.2 | +29.28 | 1.72 | +1.15 | −0.64 | +0.024 |
| EURUSD | S2 | 22.756 | 45 (8) | 313 | 24.3 | +73.46 | 1.34 | +3.80 | −0.91 | +0.014 |
| **EURUSD** | **S1+S2** | **36.772** | 192 (8) | **437** | **31.4** | **+102.74** | **1.40** | **+2.62** | **−0.85** | **+0.017** |
| Ger40 | AUG | 1.106 | 11 (0) | 23 | 43.5 | +4.41 | 1.51 | +1.31 | −0.66 | +0.015 |
| Ger40 | S1 | 11.445 | 102 (10) | 162 | 42.0 | +117.91 | 2.38 | +2.99 | −0.91 | +0.104 |
| Ger40 | S2 | 18.812 | 41 (15) | 262 | 26.3 | +153.16 | 1.83 | +4.89 | −0.96 | +0.074 |
| **Ger40** | **S1+S2** | **30.257** | 143 (25) | **424** | **32.3** | **+271.07** | **2.00** | **+3.95** | **−0.94** | **+0.087** |
| COFFEE | AUG | 0.490 | 6 (2) | 14 | 28.6 | −1.86 | 0.78 | +1.62 | −0.83 | −0.071 |
| COFFEE | S1 | 4.852 | 54 (17) | 82 | 48.8 | +57.40 | 2.63 | +2.31 | −0.84 | +0.314 |
| COFFEE | S2 | 7.893 | 37 (18) | 149 | 32.9 | +133.52 | 2.54 | +4.49 | −0.87 | +0.403 |
| **COFFEE** | **S1+S2** | **12.745** | 91 (35) | **231** | **38.5** | **+190.92** | **2.57** | **+3.51** | **−0.86** | **+0.372** |

> Kurs%/Tr = SumR × SL_PCT / Trades (SL-basierte Kursrendite je Trade).
> SILVER/GOLD-Werte dokumentarisch aus §8.27 bzw. Baseline-Referenz.
> COCOA-Endwerte mit Sweet-Spot VA_PCT 0.91 + ATR-SL je Fenster (§2.4);
> NGas-Endwerte mit Sweet-Spot VA_PCT 0.97 + ATR-SL je Fenster (§2.5);
> EURUSD-Endwerte mit fensterindividueller Kalibrierung (§2.6);
> Ger40-Endwerte mit VA_PCT 0.89 + ATR-SL je Fenster (§2.7);
> COFFEE-Endwerte mit Sweet-Spot VA_PCT 0.93 + ATR-SL je Fenster (§2.8).
> AUG + S1 + S2 NGas kombiniert: 547 Trades / +302.84R;
> AUG + S1 + S2 EURUSD kombiniert: 444 Trades / +106.44R;
> AUG + S1 + S2 Ger40 kombiniert: 447 Trades / +275.47R;
> AUG + S1 + S2 COFFEE kombiniert: 245 Trades / +189.06R.

---

## 4. BRENT M15 — Equity-Statistik (USD, 1R = 100 USD)

Konvention: Risiko 100 USD/Trade, Positionsgröße = 100/(Entry × SL_PCT),
keine Kosten, kein Zinseszinseffekt (Belege: `test/stats_trades_Brent_*_equity.txt`).

| Fenster | Trades | WR % | SumR (Log) | End-Equity | Max DD (USD) | PF (USD) | Kurs%/Tr |
|---|---|---|---|---|---|---|---|
| AUG | 22 | 22.7 | −3.02R | **−302 $** | −992 $ | 0.79 | −0.041 |
| S1 | 231 | 39.8 | +134.81R | **+13.481 $** | −1.423 $ | 2.13 | +0.265 |
| S2 | 231 | 24.7 | +212.84R | **+21.284 $** | −1.572 $ | 2.31 | +0.202 |
| S1+S2 | 462 | 32.3 | +347.65R | **+34.765 $** | — | 2.23 | +0.233 |

> Hinweis: SumR/Equity in dieser Tabelle summieren die im Trade-Log gerundeten
> R-Werte (2 Dezimalstellen) und weichen dadurch minimal von den offiziellen
> Engine-Werten ab (S1 +134.83R / S2 +212.85R). Da die Equity bei 0 startet
> (reiner P/L-Verlauf), sind Drawdown-Prozente vom laufenden Peak nicht
> aussagekräftig — angegeben ist der absolute Max DD in USD.

---

## 5. VA_PCT-Topologie BRENT (S1+S2, SL-skaliert)

| VA_PCT | S1 SumR | S2 SumR | S1+S2 SumR | Status |
|---|---|---|---|---|
| 0.85 | +119.43R | +132.22R | +251.65R | solide |
| 0.87 | +108.46R | +123.84R | +232.30R | S1-Tal |
| 0.89 | +118.27R | +160.12R | +278.39R | Transition |
| 0.91 | +126.15R | +147.27R | +273.42R | Zwischenwert |
| 0.93 | +117.50R | +145.53R | +263.03R | SILVER-Kante |
| **0.95** | **+134.83R** | **+212.85R** | **+347.68R** | **Globales Optimum** |
| 0.96 | +128.42R | +85.30R | +213.72R | S2-Abfall |
| 0.97 | +140.90R | +96.83R | +237.73R | S1 hoch, S2 schwach |
| 0.98 | +140.66R | +108.17R | +248.83R | — |
| 0.99 | +163.53R | +89.46R | +252.99R | S1 steigt weiter, S2 bricht ein |

Lesart: S2 (2025, Range-Jahr) verlangt klar VA 0.95; S1 (2026, Expansion)
tendiert zu sehr breiten Zonen (0.97–0.99). Kombiniert dominiert **0.95**
(+347.68R) — identische Resonanzverschiebung wie GOLD.

---

## 6. Artefakte (test/, gitignored)

| Fenster | txt (Engine) | png (Phasen-Chart) | txt (Equity) | png (Equity) | Engine-Log |
|---|---|---|---|---|---|
| AUG | `stats_trades_Brent_AUG.txt` | `phasen_volumen_profil_Brent_AUG.png` | `stats_trades_Brent_AUG_equity.txt` | `stats_trades_Brent_AUG.png` | `tmp_brent_AUG_engine.log` |
| S1 | `stats_trades_Brent_S1.txt` | `phasen_volumen_profil_Brent_S1.png` | `stats_trades_Brent_S1_equity.txt` | `stats_trades_Brent_S1.png` | `tmp_brent_S1_engine.log` |
| S2 | `stats_trades_Brent_S2.txt` | `phasen_volumen_profil_Brent_S2.png` | `stats_trades_Brent_S2_equity.txt` | `stats_trades_Brent_S2.png` | `tmp_brent_S2_engine.log` |

Weitere Belege: `tmp_brent_va_sweep_S1.txt`, `tmp_brent_va_sweep_S2.txt`,
`tmp_brent_params.py` (Preisstruktur-/ATR-Vorabermittlung),
`tmp_phasen_volumen_profil_symbol.py` (Arbeitskopie, unverändert zur Baseline
+ `--symbol=`/CLI-Overrides).

---

## 7. Befunde & Einordnung

1. **Generative Natur bestätigt (2. Asset):** BRENT trägt den Reclaim-Edge mit
   PF 2.23 über S1+S2 (+347.68R / 462 Trades) — nach GOLD der zweite
   erfolgreiche Cross-Asset-Beleg. Die VA_PCT-Resonanz liegt wie bei GOLD bei
   **0.95** (asset-spezifische Verschiebung +0.02 vs. SILVER).
2. **Effizienz-Relation:** BRENT erreicht ~72 % der SILVER-Kursrendite je
   Trade (+0.233 % vs. +0.325 %) — deutlich näher an SILVER als GOLD (35 %).
   S2 (2025) liefert mit +212.85R / PF 2.31 den größten R-Beitrag
   (Runner-Profil: AvgW +6.59R bei WR 24.7 %).
3. **AUG-Fenster negativ** (−3.02R / 22 Tr / PF 0.79): kleines Fenster,
   Rauschen; kein Akzeptanzkriterium für Einzelfenster-Aussagen (deckungsgleich
   mit der Vorgehensweise bei GOLD).
4. **Produktion bleibt exklusiv SILVER.** BRENT ist als eigenständiges
   Handelssymbol dokumentiert, ersetzt aber nichts.

---

## 8. COCOA M15 — Equity-Statistik (USD, 1R = 100 USD)

Konvention: Risiko 100 USD/Trade, Positionsgröße = 100/(Entry × SL_PCT),
keine Kosten, kein Zinseszinseffekt (Belege: `test/stats_trades_Cocoa_*_equity.txt`).
Finale Läufe mit VA_PCT 0.91 + ATR-SL je Fenster.

| Fenster | Trades | WR % | SumR (Log) | End-Equity | Max DD (USD) | PF (USD) | Kurs%/Tr |
|---|---|---|---|---|---|---|---|
| AUG | 18 | 38.9 | +16.86R | **+1.686 $** | −700 $ | 2.53 | +0.629 |
| S1 | 89 | 34.8 | +42.60R | **+4.260 $** | −2.077 $ | 1.85 | +0.335 |
| S2 | 141 | 25.5 | +133.40R | **+13.340 $** | −1.961 $ | 2.42 | +0.580 |
| S1+S2 | 230 | 29.1 | +176.00R | **+17.600 $** | — | 2.22 | +0.486 |

> Hinweis: SumR/Equity summieren die im Trade-Log gerundeten R-Werte (2 Dez.);
> Engine-STATS-EXPORT lautet S1 +42.59R / S2 +133.42R. Equity startet bei 0
> (reiner P/L-Verlauf) → DD-Prozente vom laufenden Peak nicht aussagekräftig,
> daher absoluter Max DD in USD.

---

## 9. COCOA M15 — VA_PCT-Reihenuntersuchung (ATR-SL je Fenster)

| VA_PCT | S1 SumR | S1 PF | S2 SumR | S2 PF | S1+S2 SumR | Status |
|---|---|---|---|---|---|---|
| 0.85 | +64.29R | 2.36 | +65.44R | 1.67 | +129.73R | solide |
| 0.87 | +45.36R | 1.92 | +77.65R | 1.79 | +123.01R | S1-Tal |
| 0.89 | +49.20R | 1.98 | +95.21R | 2.02 | +144.41R | Transition |
| 0.90 | +30.06R | 1.57 | +117.44R | 2.24 | +147.50R | Zwischenwert |
| **0.91** | **+42.59R** | 1.85 | **+133.42R** | 2.42 | **+176.01R** | **Kombiniertes Optimum** |
| 0.92 | +40.91R | 1.75 | +104.50R | 2.10 | +145.41R | S2-Abfall |
| 0.93 | +50.19R | 1.93 | +121.38R | 2.33 | +171.57R | SILVER-Kante |
| 0.94 | +62.03R | 2.14 | +93.94R | 2.02 | +155.97R | S2 fällt |
| 0.95 | +93.35R | 2.71 | +76.43R | 1.89 | +169.78R | S1-Kuppe |
| 0.97 | +73.36R | 2.48 | +67.51R | 1.80 | +140.87R | S1 hoch, S2 schwach |
| 0.99 | +63.25R | 2.74 | +41.32R | 1.68 | +104.57R | S1 hält, S2 bricht ein |

**Lesart:** S1 (2026, Abverkauf 6.5k→2.9k, volatile Expansion) verlangt weite
Zonen (**0.95**, +93.35R / PF 2.71); S2 (2025, Rally 5k→12.6k) bevorzugt enge
Zonen (**0.91**, +133.42R / PF 2.42). Die S1+S2-Kombination hat ihr Maximum
bei **0.91** (+176.01R). Im Gegensatz zu GOLD/BRENT (beide Fenster stimmig bei
0.95) ist die Cocoa-Resonanz **regime-abhängig** — kein einzelner VA_PCT
dominiert beide Fenster gleich stark. **Gewählt: 0.91** (kombiniertes SumR-
Optimum nach QS-3-Kriterium), 0.93 als SILVER-nahe Alternative nahezu gleichauf
(+171.57R).

---

## 10. COCOA M15 — SL_PCT-Reihenuntersuchung (bei VA_PCT 0.91)

Gleiche absolute SL_PCT-Werte auf beiden Fenstern (Preis-/ATR-Relation ist über
die Fenster ähnlich: Bar-Range ~0.7–0.8 % vom Preis). Der 0.87-ATR-Anker liegt
bei S1 ≈ 0.70 % und S2 ≈ 0.61 %.

| SL_PCT | S1 SumR | S1 Kurs%/Tr | S2 SumR | S2 Kurs%/Tr | S1+S2 SumR |
|---|---|---|---|---|---|
| 0.40 % | +37.13R | +0.138 | +169.10R | +0.467 | +206.23R |
| 0.50 % | +50.09R | +0.243 | +145.45R | +0.505 | +195.54R |
| 0.60 % | +57.42R | +0.371 | +129.02R | +0.549 | +186.44R |
| **0.70 % (≈Anker S1)** | +42.66R | +0.336 | +133.10R | +0.675 | +175.76R |
| 0.80 % | +33.44R | +0.315 | +125.73R | +0.734 | +159.17R |
| 0.90 % | +35.91R | +0.404 | +108.67R | +0.741 | +144.58R |
| 1.00 % | +24.71R | +0.330 | +89.17R | +0.719 | +113.88R |

**Lesart:** Engere Stops (0.4–0.6 %) maximieren die SumR (R-Skalierungseffekt),
weitere Stops (0.8–1.0 %) die Kursrendite je Trade. Der 0.87-ATR-Anker
(0.70/0.61 %) ist ein robuster Mittelweg. Für die finalen Läufe beibehalten
(Preisstruktur-Skalierung, GOLD-Protokoll-konform).

---

## 11. COCOA M15 — MIN_SPREAD_PCT-Reihe (bei VA_PCT 0.91, S1)

| MIN_SPREAD_PCT | Trades | SumR | PF |
|---|---|---|---|
| 1.0 / 1.5 / 2.0 / 2.5 / 3.0 | 89 (identisch) | +42.59R (identisch) | 1.85 |

**Lesart:** Das 1.5 %-Spread-Gate ist auf Cocoa **nicht bindend** — alle
handelbaren Phasen überschreiten 3 % Phasen-Breite (hohe prozentuale Volatilität).
Default 1.5 % bleibt unverändert.

---

## 12. COCOA M15 — Artefakte (test/, gitignored)

| Fenster | txt (Engine) | png (Phasen-Chart) | txt (Equity) | png (Equity) | Engine-Log |
|---|---|---|---|---|---|
| AUG | `stats_trades_Cocoa_AUG.txt` | `phasen_volumen_profil_Cocoa_AUG.png` | `stats_trades_Cocoa_AUG_equity.txt` | `stats_trades_Cocoa_AUG.png` | `tmp_cocoa_AUG_engine.log` |
| S1 | `stats_trades_Cocoa_S1.txt` | `phasen_volumen_profil_Cocoa_S1.png` | `stats_trades_Cocoa_S1_equity.txt` | `stats_trades_Cocoa_S1.png` | `tmp_cocoa_S1_engine.log` |
| S2 | `stats_trades_Cocoa_S2.txt` | `phasen_volumen_profil_Cocoa_S2.png` | `stats_trades_Cocoa_S2_equity.txt` | `stats_trades_Cocoa_S2.png` | `tmp_cocoa_S2_engine.log` |

Reihenuntersuchung (Protokolle): `tmp_Cocoa_va_pct_sweep_S1.txt`,
`tmp_Cocoa_va_pct_sweep_S2.txt`, `tmp_Cocoa_sl_pct_sweep_S1.txt`,
`tmp_Cocoa_sl_pct_sweep_S2.txt`, `tmp_Cocoa_min_spread_pct_sweep_S1.txt`.
Helper: `tmp_symbol_params.py` (Preisstruktur/ATR), `tmp_symbol_sweep.py`
(Sweep-Treiber), `tmp_symbol_equity.py`, `tmp_symbol_summary.py`,
`tmp_phasen_volumen_profil_symbol.py` (Engine-Arbeitskopie, unverändert zur
Baseline + `--symbol=`/CLI-Overrides).

---

## 13. COCOA M15 — Befunde & Einordnung

1. **Dritter Cross-Asset-Beleg, aber regime-abhängig:** COCOA trägt den
   Reclaim-Edge über S1+S2 mit +176.01R / 230 Trades (PF 2.22). Im Gegensatz
   zu GOLD/BRENT (VA-Kuppe 0.95 in beiden Fenstern) divergiert Cocoa:
   S2/2025-Rally bevorzugt 0.91, S1/2026-Abverkauf 0.95. VA_PCT 0.91 als
   kombiniertes Optimum gewählt.
2. **Effizienz:** Kursrendite je Trade S1+S2 +0.486 % — **über SILVER
   (+0.325 %)** und deutlich über BRENT/GOLD. S2 liefert mit +133.42R / PF 2.42
   den Hauptbeitrag (Runner-Profil: AvgW +6.31R bei WR 25.5 %).
3. **Kurze Sessions beachten:** Cocoa handelt nur ~8–12 h/Tag → AUG nur 490
   Bars (18 Tr). Die Engine skaliert (MIN_CANDLES unverändert 46), die
   Phasen-Segmentierung läuft fensterübergreifend; AUG bleibt kleine
   Stichprobe (positiv, +16.86R).
4. **SL-Sensitivität:** 0.4–0.6 % maximieren SumR (eng), 0.8–1.0 % die
   Kursrendite (weit). 0.87-ATR-Anker beibehalten (robuster Mittelweg).
   MIN_SPREAD_PCT-Gate nicht bindend (Default 1.5 % bestätigt).
5. **Produktion bleibt exklusiv SILVER.** COCOA als eigenständiges
   Handelssymbol dokumentiert (QS-5).

---

## 14. NGas M15 — Equity-Statistik (USD, 1R = 100 USD)

Konvention: Risiko 100 USD/Trade, Positionsgröße = 100/(Entry × SL_PCT),
keine Kosten, kein Zinseszinseffekt (Belege: `test/stats_trades_NGas_*_equity.txt`).
Finale Läufe mit VA_PCT 0.97 + ATR-SL je Fenster.

| Fenster | Trades | WR % | SumR (Log) | End-Equity | Max DD (USD) | PF (USD) | Kurs%/Tr |
|---|---|---|---|---|---|---|---|
| AUG | 25 | 36.0 | +17.26R | **+1.726 $** | −800 $ | 2.08 | +0.207 |
| S1 | 177 | 33.9 | +115.20R | **+11.520 $** | −1.778 $ | 2.11 | +0.253 |
| S2 | 345 | 25.5 | +170.43R | **+17.043 $** | −4.231 $ | 1.72 | +0.196 |
| S1+S2 | 522 | 28.2 | +285.63R | **+28.563 $** | — | 1.84 | +0.215 |

> Hinweis: SumR/Equity summieren die im Trade-Log gerundeten R-Werte (2 Dez.);
> Engine-STATS-EXPORT lautet AUG +17.25R / S1 +115.19R / S2 +170.40R. Equity
> startet bei 0 (reiner P/L-Verlauf) → DD-Prozente vom laufenden Peak nicht
> aussagekräftig, daher absoluter Max DD in USD (S2: Peak +17.292 $, längste
> DD-Serie 89 Trades).

---

## 15. NGas M15 — VA_PCT-Topologie (S1+S2, ATR-SL je Fenster)

| VA_PCT | S1 SumR | S1 PF | S2 SumR | S2 PF | S1+S2 SumR | Status |
|---|---|---|---|---|---|---|
| 0.85 | +26.87R | 1.23 | +77.88R | 1.26 | +104.75R | solide |
| 0.87 | +28.06R | 1.24 | −10.62R | 0.97 | +17.44R | S2-Tal |
| 0.89 | +43.92R | 1.41 | +7.17R | 1.02 | +51.09R | Transition |
| 0.91 | +60.84R | 1.54 | +11.70R | 1.04 | +72.54R | Zwischenwert |
| 0.93 | +68.11R | 1.60 | +24.83R | 1.09 | +92.94R | SILVER-Kante, S2 schwach |
| 0.95 | +84.88R | 1.78 | +34.21R | 1.13 | +119.09R | S2 steigt an |
| 0.96 | +75.96R | 1.67 | +85.72R | 1.33 | +161.68R | S2-Sprung |
| **0.97** | **+115.19R** | 2.11 | **+170.40R** | 1.72 | **+285.59R** | **Kombiniertes Optimum** |
| 0.98 | +111.64R | 2.04 | +87.83R | 1.39 | +199.47R | S2 bricht ein |
| 0.99 | +129.51R | 2.49 | +72.80R | 1.36 | +202.31R | S1 steigt weiter, S2 fällt |

**Lesart:** S2 (2025, volatiles Trend-/Range-Jahr mit Breitband-Ausschlägen
2.6→4.8 USD) verlangt klar **weite Zonen 0.97** (+170.40R / PF 1.72) — das
komplette Band 0.85–0.95 liegt teils im Negativen (breites S2-Tal bis 0.93:
nur +24.83R / PF 1.09). S1 (2026) steigt monoton zu sehr breiten Zonen
(0.99 +129.51R / PF 2.49). Kombiniert dominiert **0.97** (+285.59R) mit
starkem Abstand — die ausgeprägteste Resonanzverschiebung aller bisherigen
Symbole (SILVER 0.93 / GOLD+BRENT 0.95 / COCOA 0.91).

---

## 16. NGas M15 — SL_PCT-Reihenuntersuchung (bei VA_PCT 0.97)

Der 0.87-ATR-Anker liegt fensterabhängig bei AUG 0.30 %, S1 0.39 %,
S2 0.40 % (niedrige Preisbasis ~2.8–3.6 USD → kleine %-Stops).

| SL_PCT | S1 SumR | S1 Kurs%/Tr | S2 SumR | S2 Kurs%/Tr | S1+S2 SumR |
|---|---|---|---|---|---|
| 0.25 % | +106.41R | +0.131 | — | — | — |
| **0.30 % (≈Anker AUG/S2)** | +110.30R | +0.169 | **+186.31R** | +0.156 | +296.61R |
| 0.35 % | +123.34R | +0.235 | — | — | — |
| **0.40 % (≈Anker S1/S2)** | +105.03R | +0.240 | +167.36R | +0.194 | +272.39R |
| 0.50 % | +65.17R | +0.213 | +150.95R | +0.229 | +216.12R |
| 0.60 % | +32.06R | +0.146 | — | — | — |
| 0.80 % | +39.44R | +0.312 | +139.21R | +0.395 | +178.65R |

**Lesart:** Beide Fenster bevorzugen enge Stops für die SumR (S1-Kuppe 0.35 %,
S2-Kuppe 0.30 % — R-Skalierungseffekt, wie bei Cocoa §10). Der 0.87-ATR-Anker
(0.39/0.40 %) liegt bei S2 nahe der Kuppe, bei S1 knapp daneben; weite Stops
(0.80 %) maximieren erwartungsgemäß die Kursrendite je Trade. Für die finalen
Läufe bleibt der ATR-Anker beibehalten (Preisstruktur-Skalierung,
GOLD-Protokoll-konform) → S1 +115.19R / S2 +170.40R bei VA 0.97.

---

## 17. NGas M15 — Artefakte (test/, gitignored)

| Fenster | txt (Engine) | png (Phasen-Chart) | txt (Equity) | png (Equity) | Engine-Log |
|---|---|---|---|---|---|
| AUG | `stats_trades_NGas_AUG.txt` | `phasen_volumen_profil_NGas_AUG.png` | `stats_trades_NGas_AUG_equity.txt` | `stats_trades_NGas_AUG.png` | `tmp_ngas_AUG_engine.log` |
| S1 | `stats_trades_NGas_S1.txt` | `phasen_volumen_profil_NGas_S1.png` | `stats_trades_NGas_S1_equity.txt` | `stats_trades_NGas_S1.png` | `tmp_ngas_S1_engine.log` |
| S2 | `stats_trades_NGas_S2.txt` | `phasen_volumen_profil_NGas_S2.png` | `stats_trades_NGas_S2_equity.txt` | `stats_trades_NGas_S2.png` | `tmp_ngas_S2_engine.log` |

Reihenuntersuchung (Protokolle): `tmp_NGas_va_pct_sweep_S1.txt`,
`tmp_NGas_va_pct_sweep_S2.txt`, `tmp_NGas_sl_pct_sweep_S1.txt`,
`tmp_NGas_sl_pct_sweep_S2.txt`. Helper: `tmp_symbol_params.py`
(Preisstruktur/ATR-Ratio, CLI-Sets oben), `tmp_symbol_sweep.py`,
`tmp_symbol_equity.py`, `tmp_phasen_volumen_profil_symbol.py`
(Engine-Arbeitskopie, unverändert zur Baseline + `--symbol=`/CLI-Overrides).

---

## 18. NGas M15 — Befunde & Einordnung

1. **Vierter Cross-Asset-Beleg:** NGas trägt den Reclaim-Edge über S1+S2 mit
   +285.59R / 522 Trades (PF 1.84) — nach BRENT der zweitstärkste R-Beitrag
   und mit AUG zusammen +302.84R / 547 Trades. Die VA_PCT-Resonanz liegt mit
   **0.97** am weitesten von SILVER entfernt (stärkste Zonen-Verbreiterung
   aller getesteten Assets).
2. **Regime-Charakteristik:** S2 (2025, Range 2.6→4.8 USD mit scharfen
   Breitband-Ausschlägen) ist der dominante R-Beitrag (+170.40R), verlangt
   aber zwingend weite Zonen VA 0.97 — engere Zonen (0.87–0.95) kollabieren
   (S2-Tal bis PF 1.09). S1 trägt mit PF 2.11 (+115.19R) bei; AUG bleibt die
   kleine Stichprobe (+17.25R / PF 2.08, 25 Tr).
3. **Effizienz:** Kursrendite je Trade S1+S2 +0.215 % — unter SILVER
   (+0.325 %) und COCOA (+0.486 %), aber über GOLD (+0.113 %) und nahe BRENT
   (+0.233 %). Runner-Profil in S2: AvgW +4.63R bei WR 25.5 %, bester Trade
   +20.74R.
4. **Robustheit (Achtung):** S2-WR nur 25.5 % mit PF 1.72 und längster
   DD-Serie von 89 Trades (Max DD −4.231 $ vom Peak +17.292 $) — der schwächste
   PF aller S2-Fenster bisher. Das S2-Ergebnis hängt empfindlich an der
   VA 0.97-Resonanz (Absturz auf +24.83R bei 0.93). NGas ist damit das
   fragilste getestete Symbol; ATR-SL-Anker und weite Zonen sind kritisch.
5. **Produktion bleibt exklusiv SILVER.** NGas als eigenständiges
   Handelssymbol dokumentiert (QS-6).

---

## 19. EURUSD M15 — Equity-Statistik (USD, 1R = 100 USD)

Konvention: Risiko 100 USD/Trade, Positionsgröße = 100/(Entry × SL_PCT),
keine Kosten, kein Zinseszinseffekt (Belege: `test/stats_trades_EURUSD_*_equity.txt`).
Finale Läufe mit fensterindividueller Kalibrierung (§2.6): AUG/S1 VA 0.99 +
SL 0.10 %, S2 VA 0.91 + SL 0.0608 %.

| Fenster | Trades | WR % | SumR (Log) | End-Equity | Max DD (USD) | PF (USD) | Kurs%/Tr |
|---|---|---|---|---|---|---|---|
| AUG | 7 | 71.4 | +3.72R | **+372 $** | −100 $ | 3.72 | +0.053 |
| S1 | 124 | 49.2 | +29.23R | **+2.923 $** | −846 $ | 1.72 | +0.024 |
| S2 | 313 | 24.3 | +73.49R | **+7.349 $** | −2.268 $ | 1.34 | +0.014 |
| S1+S2 | 437 | 31.4 | +102.72R | **+10.272 $** | — | 1.40 | +0.017 |

> Hinweis: SumR/Equity summieren die im Trade-Log gerundeten R-Werte (2 Dez.);
> Engine-STATS-EXPORT lautet AUG +3.71R / S1 +29.28R / S2 +73.46R. Equity
> startet bei 0 (reiner P/L-Verlauf) → DD-Prozente vom laufenden Peak nicht
> aussagekräftig, daher absoluter Max DD in USD. S1-Bester T14 +4.02R
> (LONG); S2-Bester T71 +18.31R (SHORT); S2-längste DD-Serie 89 Trades,
> Max DD −2.268 $ (Tief T64).

---

## 20. EURUSD M15 — VA_PCT-Topologie (S1+S2, ATR-SL-Anker je Fenster)

| VA_PCT | S1 SumR | S1 PF | S2 SumR | S2 PF | S1+S2 SumR | Status |
|---|---|---|---|---|---|---|
| 0.85 | −97.02R | 0.39 | +71.73R | 1.32 | −25.29R | S1 tief negativ |
| 0.87 | −91.65R | 0.43 | +59.56R | 1.27 | −32.09R | S1 tief negativ |
| 0.89 | −74.74R | 0.51 | +14.32R | 1.06 | −60.42R | S2-Tal |
| 0.91 | −66.85R | 0.56 | **+73.46R** | 1.34 | +6.61R | S2-Optimum, S1 negativ |
| 0.93 | −67.10R | 0.57 | +55.42R | 1.26 | −11.68R | SILVER-Kante, S1 negativ |
| 0.95 | −68.15R | 0.59 | +29.54R | 1.14 | −38.61R | S2 fällt |
| 0.97 | −61.51R | 0.61 | +1.64R | 1.01 | −59.87R | S2 kollabiert |
| 0.99 | −19.10R | 0.87 | +38.41R | 1.23 | +19.31R | S1 besser, aber negativ |

**Lesart (Anker-SL):** Mit dem 0.87-ATR-Anker ist S2 (2025) über die gesamte
Kante positiv (Optimum **0.91** +73.46R), S1 (2026) über die gesamte Kante
negativ (bestenfalls −19.10R bei 0.99). Der Reclaim-Edge ist in der
2026er-FX-Regimehälfte mit Anker-SL **nicht vorhanden** — erst die SL-
Anpassung auf 0.10 % erschließt S1 (siehe §21: +29.28R bei VA 0.99).

---

## 21. EURUSD M15 — SL_PCT-Reihenuntersuchung & VA×SL-Interaktion

Der 0.87-ATR-Anker liegt bei AUG 0.0317 %, S1 0.0449 %, S2 0.0608 %
(FX-Preisbasis ~1.16 → sehr kleine %-Stops).

**SL_PCT-Sweep S1 (bei VA 0.93):**

| SL_PCT | Trades | WR % | SumR | PF | Kurs%/Tr |
|---|---|---|---|---|---|
| 0.0449 % (Anker) | 215 | 31.6 | −67.10R | 0.57 | −0.014 |
| 0.06 % | 172 | 42.4 | −3.34R | 0.96 | −0.001 |
| 0.08 % | 122 | 52.5 | +13.63R | 1.33 | +0.009 |
| **0.09 %** | 108 | 59.3 | **+20.86R** | 1.67 | +0.017 |
| **0.10 %** | 96 | 60.4 | **+20.86R** | **1.80** | +0.022 |
| 0.11 % | 87 | 58.6 | +14.16R | 1.58 | +0.018 |
| 0.12 % | 72 | 62.5 | +12.40R | 1.62 | +0.021 |
| 0.15 % | 53 | 60.4 | +5.97R | 1.34 | +0.017 |
| 0.20 % | 25 | 56.0 | −1.92R | 0.82 | −0.015 |
| 0.45 % (SILVER-Default) | 2 | 50.0 | −0.11R | 0.89 | −0.025 |

**VA-PCT-Sweep S1 (bei SL 0.10 %):**

| VA_PCT | Trades | WR % | SumR | PF |
|---|---|---|---|---|
| 0.89 | 85 | 63.5 | +23.07R | 2.06 |
| 0.91 | 89 | 60.7 | +19.72R | 1.83 |
| 0.93 | 96 | 60.4 | +20.86R | 1.80 |
| 0.95 | 103 | 52.4 | +16.44R | 1.55 |
| 0.97 | 121 | 50.4 | +21.95R | 1.65 |
| **0.99** | 124 | 49.2 | **+29.28R** | 1.72 |

**SL_PCT-Sweep S2 (bei VA 0.91):**

| SL_PCT | Trades | WR % | SumR | PF |
|---|---|---|---|---|
| 0.05 % | 328 | 21.6 | +40.28R | 1.17 |
| **0.0608 % (Anker)** | 313 | 24.3 | **+73.46R** | 1.34 |
| 0.08 % | 298 | 27.5 | +43.30R | 1.22 |
| 0.10 % | 278 | 31.7 | +49.07R | 1.28 |
| 0.135 % | 246 | 35.8 | +28.44R | 1.19 |

**Lesart:** Der enge Anker (0.0317/0.0449 %) choppt S1 in der 2026er-
Seitwärtsphase (−67R, WR 31 %, 215 Trades); weite Stops ~0.10 % (= ~2,2×
ATR) kippen das Ergebnis ins Positive (WR springt auf ~60 % — die Reclaim-
Trades bekommen Luft, AvgL sinkt auf −0.7R). Die Trade-Zahl halbiert sich
(~96–124). S2 (2025, trendig) bleibt beim Anker am besten (Runner-Profil).
Der Sweet-Spot **S1 = VA 0.99 + SL 0.10 %** (+29.28R / PF 1.72) und
**S2 = VA 0.91 + SL 0.0608 %** (+73.46R / PF 1.34) wird für die finalen Läufe
gewählt — bewusst fensterindividuell, weil kein gemeinsamer Satz beide
Regime trägt.

---

## 22. EURUSD M15 — MIN_SPREAD_PCT-Reihe (bei VA 0.93, S1) & Artefakte

| MIN_SPREAD_PCT | Trades | SumR | PF |
|---|---|---|---|
| 0.3 / 0.5 / 0.8 / 1.0 / 1.2 / 2.0 | 215 (identisch) | −67.10R (identisch) | 0.57 |

**Lesart:** Das Spread-Gate ist auf EURUSD **nicht bindend** — auch bei
0.3 % keine zusätzlichen Phasen (alle S1-Ranges > 2 % breit). Default 1.5 %
unverändert. Artefakte:

| Fenster | txt (Engine) | png (Phasen-Chart) | txt (Equity) | png (Equity) | Engine-Log |
|---|---|---|---|---|---|
| AUG | `stats_trades_EURUSD_AUG.txt` | `phasen_volumen_profil_EURUSD_AUG.png` | `stats_trades_EURUSD_AUG_equity.txt` | `stats_trades_EURUSD_AUG.png` | `tmp_eurusd_AUG_engine.log` |
| S1 | `stats_trades_EURUSD_S1.txt` | `phasen_volumen_profil_EURUSD_S1.png` | `stats_trades_EURUSD_S1_equity.txt` | `stats_trades_EURUSD_S1.png` | `tmp_eurusd_S1_engine.log` |
| S2 | `stats_trades_EURUSD_S2.txt` | `phasen_volumen_profil_EURUSD_S2.png` | `stats_trades_EURUSD_S2_equity.txt` | `stats_trades_EURUSD_S2.png` | `tmp_eurusd_S2_engine.log` |

Reihenuntersuchung (Protokolle): `tmp_EURUSD_va_pct_sweep_S1.txt`,
`tmp_EURUSD_va_pct_sweep_S2.txt`, `tmp_EURUSD_va_pct_sweep_S1_sl-pct0.10.txt`,
`tmp_EURUSD_va_pct_sweep_AUG_sl-pct0.10.txt`, `tmp_EURUSD_sl_pct_sweep_S1.txt`,
`tmp_EURUSD_sl_pct_sweep_S2_va-pct0.91.txt`, `tmp_EURUSD_sl_pct_sweep_AUG.txt`,
`tmp_EURUSD_min_spread_pct_sweep_S1.txt`. Helper: `tmp_symbol_params.py`
(Preisstruktur/ATR-Ratio), `tmp_symbol_sweep.py` (Sweep-Treiber, erweitert um
Fix-Parameter-Protokolle), `tmp_symbol_equity.py` (VA_FENSTER für
fensterindividuelle Anzeige), `tmp_phasen_volumen_profil_symbol.py`
(Engine-Arbeitskopie, unverändert zur Baseline + `--symbol=`/CLI-Overrides).

---

## 23. EURUSD M15 — Befunde & Einordnung

1. **Erster FX-Test, schwächster Cross-Asset-Beleg:** EURUSD trägt den
   Reclaim-Edge über S1+S2 mit +102.72R / 437 Trades (PF 1.40) — deutlich
   unter allen Commodities. Das Ergebnis ist **regime- und parameter-kritisch**:
   ohne die SL-Anpassung wäre S1 (2026) tief negativ (−67R bei Anker-SL).
2. **Mikrostruktur:** FX-M15-Bars sind prozentual ~10× kleiner als
   Commodity-Bars (Range 0.04–0.07 % vs. 0.3–0.8 %). Der 0.87-ATR-SL-Anker
   liegt dadurch bei 0.03–0.06 % — für die 2026er-Chop-Phase zu eng. Erst
   ~2,2× ATR (0.10 %) erzeugt den Sweet Spot (WR-Sprung auf ~60 %,
   PF ~1.8). In der 2025er-Trendphase bleibt der enge Anker überlegen
   (Runner: AvgW +3.80R, Bester +18.31R).
3. **Regime-Asymmetrie:** S2/2025 (FX-Trendjahr, EURUSD ~1.03→1.17) trägt mit
   +73.46R den Hauptbeitrag; S1/2026 (Seitwärts ~1.13–1.17) nur +29.28R nach
   Kalibrierung, AUG minimal (+3.71R / 7 Tr). Im Gegensatz zu den Commodities
   (S1/2026 meist stark) ist bei EURUSD das 2026er-Fenster strukturell
   schwächer — FX-Seitwärtsphasen ohne Richtung liefern dem Zonen-Reclaim
   wenig.
4. **Kursrendite je Trade minimal:** +0.017 % (S1+S2, gewichtet) — die
   niedrigste aller getesteten Assets (SILVER +0.325 %). Bei 1R = 100 USD
   ergibt sich dennoch +10.272 $ End-Equity über 437 Trades (keine Kosten).
   Für einen realen FX-Betrieb wären Spread/Slippage (nicht modelliert)
   kritisch zu prüfen.
5. **Produktion bleibt exklusiv SILVER.** EURUSD als eigenständiges
   Handelssymbol dokumentiert (QS-7), mit dem ausdrücklichen Befund, dass der
   Reclaim-Edge auf FX schwächer und fragiler ist als auf Commodities.

---

## 24. Ger40 M15 — Grobe Orientierung (QS-8)

**Equity-Statistik** (1R = 100 USD, keine Kosten; Belege:
`test/stats_trades_Ger40_*_equity.txt`), Finale Läufe mit VA_PCT 0.89 +
ATR-SL je Fenster (§2.7):

| Fenster | Trades | WR % | SumR | End-Equity | Max DD (USD) | PF (USD) | Kurs%/Tr |
|---|---|---|---|---|---|---|---|
| AUG | 23 | 43.5 | +4.41R | **+441 $** | −300 $ | 1.51 | +0.015 |
| S1 | 162 | 42.0 | +117.91R | **+11.792 $** | −1.100 $ | 2.38 | +0.104 |
| S2 | 262 | 26.3 | +153.16R | **+15.314 $** | −1.975 $ | 1.83 | +0.074 |
| S1+S2 | 424 | 32.3 | +271.06R | **+27.106 $** | — | 2.00 | +0.087 |

> Hinweis: SumR/Equity summieren gerundete Log-R-Werte; Engine-STATS-EXPORT
> lautet AUG +4.41R / S1 +117.91R / S2 +153.16R. S1-Bester T31 +26.97R
> (LONG), S2-Bester T204 +26.37R (SHORT); Max DD bei S1 −13.8 % vom Peak,
> S2 −36.6 % (längste DD-Serie 46 Trades).

**VA_PCT-Topologie (Sweep, ATR-SL-Anker):**

| VA_PCT | S1 SumR | S1 PF | S2 SumR | S2 PF | S1+S2 SumR |
|---|---|---|---|---|---|
| 0.85 | +90.08R | 2.15 | +107.83R | 1.56 | +197.91R |
| **0.89** | **+117.91R** | 2.38 | **+153.16R** | 1.83 | **+271.07R** |
| 0.93 | +93.70R | 2.17 | +116.09R | 1.70 | +209.79R |
| 0.95 | +88.06R | 1.93 | +123.24R | 1.77 | +211.30R |
| 0.97 | +98.09R | 2.02 | +43.32R | 1.26 | +141.41R |
| 0.99 | +66.23R | 1.76 | +46.61R | 1.32 | +112.84R |

**Artefakte (test/, gitignored):**

| Fenster | txt (Engine) | png (Phasen-Chart) | txt (Equity) | png (Equity) | Engine-Log |
|---|---|---|---|---|---|
| AUG | `stats_trades_Ger40_AUG.txt` | `phasen_volumen_profil_Ger40_AUG.png` | `stats_trades_Ger40_AUG_equity.txt` | `stats_trades_Ger40_AUG.png` | `tmp_ger40_AUG_engine.log` |
| S1 | `stats_trades_Ger40_S1.txt` | `phasen_volumen_profil_Ger40_S1.png` | `stats_trades_Ger40_S1_equity.txt` | `stats_trades_Ger40_S1.png` | `tmp_ger40_S1_engine.log` |
| S2 | `stats_trades_Ger40_S2.txt` | `phasen_volumen_profil_Ger40_S2.png` | `stats_trades_Ger40_S2_equity.txt` | `stats_trades_Ger40_S2.png` | `tmp_ger40_S2_engine.log` |

Reihenuntersuchung: `tmp_Ger40_va_pct_sweep_S1.txt`, `tmp_Ger40_va_pct_sweep_S2.txt`.
Helper: `tmp_symbol_params.py` (Preisstruktur/ATR-Ratio), `tmp_symbol_sweep.py`,
`tmp_symbol_equity.py` (+ Ger40), `tmp_phasen_volumen_profil_symbol.py`
(Engine-Arbeitskopie, unverändert zur Baseline + `--symbol=`/CLI-Overrides).

**Befunde (grob):**
1. **Erster Index-Test, starker Beleg:** Ger40 (DAX) trägt den Reclaim-Edge
   mit S1+S2 **+271.07R / 424 Trades / PF 2.00** — nach BRENT/NGas der
   drittstärkste R-Beitrag, klar über GOLD und weit über COCOA/EURUSD.
2. **Resonanz unter SILVER-Kante:** Beide Fenster stimmig bei **VA 0.89**
   (engere Zonen als SILVER 0.93 / GOLD+BRENT 0.95). Der 0.87-ATR-SL-Anker
   funktioniert ohne Anpassung (trotz FX-ähnlicher Range-Pct 0.09–0.16 %) —
   im Gegensatz zu EURUSD; AUG bleibt kleine Stichprobe (+4.41R / PF 1.51).
3. **Effizienz:** Kursrendite je Trade S1+S2 **+0.087 %** — über EURUSD
   (+0.017 %) und GOLD (+0.113 % nahe), aber deutlich unter SILVER/BRENT/
   COCOA. S1 trägt mit PF 2.38 und WR 42 % (Ausnahme unter den Symbolen),
   S2 mit Runner-Profil (AvgW +4.89R / WR 26.3 %).
4. **Produktion bleibt exklusiv SILVER.** Ger40 als eigenständiges
   Handelssymbol dokumentiert (QS-8).

---

## 25. COFFEE M15 — Equity-Statistik (USD, 1R = 100 USD)

Konvention: Risiko 100 USD/Trade, Positionsgröße = 100/(Entry × SL_PCT),
keine Kosten, kein Zinseszinseffekt (Belege: `test/stats_trades_Coffee_*_equity.txt`).
Finale Läufe mit VA_PCT 0.93 + ATR-SL je Fenster (§2.8).

| Fenster | Trades | WR % | SumR (Log) | End-Equity | Max DD (USD) | PF (USD) | Kurs%/Tr |
|---|---|---|---|---|---|---|---|
| AUG | 14 | 28.6 | −1.86R | **−186 $** | −409 $ | 0.78 | −0.071 |
| S1 | 82 | 48.8 | +57.40R | **+5.740 $** | −948 $ | 2.63 | +0.314 |
| S2 | 149 | 32.9 | +133.50R | **+13.350 $** | −984 $ | 2.54 | +0.403 |
| S1+S2 | 231 | 38.5 | +190.90R | **+19.090 $** | — | 2.57 | +0.372 |

> Hinweis: SumR/Equity summieren die im Trade-Log gerundeten R-Werte (2 Dez.);
> Engine-STATS-EXPORT lautet S1 +57.40R / S2 +133.52R. Equity startet bei 0
> (reiner P/L-Verlauf) → DD-Prozente vom laufenden Peak nicht aussagekräftig,
> daher absoluter Max DD in USD (S1 −29.3 % vom Peak, Tief T28; S2 −10.2 % vom
> Peak, Tief T105). S2-Bester T73 SHORT +20.36R; längste DD-Serie S1 22 Trades.

---

## 26. COFFEE M15 — VA_PCT-Topologie (S1+S2, ATR-SL je Fenster)

| VA_PCT | S1 SumR | S1 PF | S2 SumR | S2 PF | S1+S2 SumR | Status |
|---|---|---|---|---|---|---|
| 0.85 | +38.89R | 2.22 | +94.49R | 1.89 | +133.38R | solide |
| 0.87 | +52.70R | 2.50 | +104.71R | 2.04 | +157.41R | Aufbau |
| 0.89 | +53.66R | 2.46 | +66.89R | 1.68 | +120.55R | S2-Tal |
| 0.90 | +53.06R | 2.45 | +97.93R | 2.07 | +150.99R | Zwischenwert |
| 0.91 | +51.32R | 2.51 | +111.45R | 2.25 | +162.77R | steigend |
| 0.92 | +59.91R | 2.78 | +127.25R | 2.45 | +187.16R | nahe Optimum |
| **0.93** | **+57.40R** | 2.63 | **+133.52R** | 2.54 | **+190.92R** | **Globales Optimum (SILVER-Kante)** |
| 0.94 | +44.03R | 2.12 | +119.89R | 2.39 | +163.92R | S1-Abfall |
| 0.95 | +28.21R | 1.65 | +130.26R | 2.63 | +158.47R | S1 bricht ein |
| 0.96 | +22.85R | 1.50 | +111.95R | 2.44 | +134.80R | S1-Tal |
| 0.97 | +37.47R | 1.81 | +97.07R | 2.26 | +134.54R | S2 fällt |
| 0.98 | +42.76R | 1.91 | +89.41R | 2.24 | +132.17R | Plateau |
| 0.99 | +52.01R | 2.33 | +89.61R | 2.36 | +141.62R | S1-Anstieg, S2 schwach |

**Lesart:** S1 (2026, Abverkauf ~323→240 mit Erholungsrally bis ~353) zeigt
ein breites Plateau 0.87–0.93 (Kuppe 0.92–0.93, +59.91R / PF 2.78), ein Tal
bei 0.95–0.96 und einen erneuten Anstieg zu 0.99; S2 (2025, Rally-Jahr mit
432er-Hoch, volatile Range 281–432) hat eine klare Kuppe bei **0.93**
(+133.52R / PF 2.54) und fällt danach monoton. Kombiniert dominiert **0.93**
(+190.92R / PF 2.57). Im Gegensatz zu COCOA (§9) ist die COFFEE-Resonanz
**regime-unabhängig** — beide Fenster stimmig, die Kante liegt **exakt auf
SILVER 0.93** (erste Bestätigung ohne Resonanzverschiebung).

---

## 27. COFFEE M15 — SL_PCT-Reihenuntersuchung (bei VA_PCT 0.93)

Gleiche absolute SL_PCT-Werte auf beiden Fenstern (Preis-/ATR-Relation ist
über die Fenster ähnlich: Bar-Range ~0.5–0.62 % vom Preis). Der 0.87-ATR-
Anker liegt bei S1 ≈ 0.448 % und S2 ≈ 0.450 %.

| SL_PCT | S1 SumR | S1 Kurs%/Tr | S2 SumR | S2 Kurs%/Tr | S1+S2 SumR |
|---|---|---|---|---|---|
| 0.30 % | +76.41R | +0.249 | +180.55R | +0.332 | +256.96R |
| 0.35 % | +73.83R | +0.301 | +181.79R | +0.398 | +255.62R |
| 0.40 % | +58.40R | +0.281 | +164.84R | +0.417 | +223.24R |
| **0.45 % (≈Anker S1/S2)** | +55.79R | +0.310 | +133.62R | +0.404 | +189.41R |
| 0.50 % | +53.59R | +0.353 | +109.26R | +0.372 | +162.85R |
| 0.60 % | +32.04R | +0.310 | +92.19R | +0.401 | +124.23R |
| 0.70 % | +23.02R | +0.304 | +94.01R | +0.488 | +117.03R |

**Lesart:** Engere Stops (0.30–0.35 %) maximieren die SumR (R-Skalierungs-
effekt: S1 +76.41R / S2 +181.79R), weite Stops senken die SumR; die
Kursrendite je Trade bleibt über 0.30–0.60 % bemerkenswert stabil (S2-Max
~0.49 % erst bei 0.70 %). Der 0.87-ATR-Anker (0.448/0.450 %) ist ein robuster
Mittelweg — für die finalen Läufe beibehalten (Preisstruktur-Skalierung,
GOLD-Protokoll-konform).

---

## 28. COFFEE M15 — MIN_SPREAD_PCT-Reihe (bei VA_PCT 0.93, S1)

| MIN_SPREAD_PCT | Trades | SumR | PF |
|---|---|---|---|
| 1.0 / 1.5 / 2.0 / 2.5 / 3.0 | 82 (identisch) | +57.40R (identisch) | 2.63 |

**Lesart:** Das 1.5 %-Spread-Gate ist auf Coffee **nicht bindend** — alle
handelbaren Phasen überschreiten 3 % Phasen-Breite (hohe prozentuale
Volatilität wie bei Cocoa §11). Default 1.5 % bleibt unverändert.

---

## 29. COFFEE M15 — Artefakte (test/, gitignored)

| Fenster | txt (Engine) | png (Phasen-Chart) | txt (Equity) | png (Equity) | Engine-Log |
|---|---|---|---|---|---|
| AUG | `stats_trades_Coffee_AUG.txt` | `phasen_volumen_profil_Coffee_AUG.png` | `stats_trades_Coffee_AUG_equity.txt` | `stats_trades_Coffee_AUG.png` | `tmp_coffee_AUG_engine.log` |
| S1 | `stats_trades_Coffee_S1.txt` | `phasen_volumen_profil_Coffee_S1.png` | `stats_trades_Coffee_S1_equity.txt` | `stats_trades_Coffee_S1.png` | `tmp_coffee_S1_engine.log` |
| S2 | `stats_trades_Coffee_S2.txt` | `phasen_volumen_profil_Coffee_S2.png` | `stats_trades_Coffee_S2_equity.txt` | `stats_trades_Coffee_S2.png` | `tmp_coffee_S2_engine.log` |

Reihenuntersuchung (Protokolle): `tmp_Coffee_va_pct_sweep_S1.txt`,
`tmp_Coffee_va_pct_sweep_S2.txt`, `tmp_Coffee_sl_pct_sweep_S1_va-pct0.93.txt`,
`tmp_Coffee_sl_pct_sweep_S2_va-pct0.93.txt`,
`tmp_Coffee_min_spread_pct_sweep_S1_va-pct0.93.txt`.
Helper: `tmp_symbol_params.py` (Preisstruktur/ATR), `tmp_symbol_sweep.py`
(Sweep-Treiber), `tmp_symbol_equity.py`, `tmp_symbol_summary.py`,
`tmp_phasen_volumen_profil_symbol.py` (Engine-Arbeitskopie, unverändert zur
Baseline + `--symbol=`/CLI-Overrides).

---

## 30. COFFEE M15 — Befunde & Einordnung

1. **Fünfter Cross-Asset-Beleg, resonanzstabil:** COFFEE trägt den
   Reclaim-Edge über S1+S2 mit +190.92R / 231 Trades (PF 2.57). Im Gegensatz
   zu COCOA (Regime-Divergenz S1 0.95 / S2 0.91) liegen beide Fenster-Kuppen
   bei **0.93** — die VA-Resonanz fällt exakt mit der SILVER-Baseline
   zusammen. Coffee ist damit das erste Asset außer SILVER ohne
   Resonanzverschiebung (weder + wie GOLD/BRENT/NGas noch − wie COCOA/Ger40).
2. **Höchster PF über S1+S2 aller Assets (2.57)** und S1 (2026) mit
   PF 2.63 / WR 48.8 % das stärkste S1 aller Symbole (bisher Ger40 2.38) —
   ausgeglichenes Gewinnprofil (AvgW +2.31R / AvgL −0.84R) statt
   Runner-Abhängigkeit.
3. **Effizienz:** Kursrendite je Trade S1+S2 **+0.372 %** — über SILVER
   (+0.325 %), nur von COCOA (+0.486 %) übertroffen. S2 (2025) liefert mit
   +133.52R / PF 2.54 den Hauptbeitrag (Runner-Profil: AvgW +4.49R bei
   WR 32.9 %, Bester T73 +20.36R).
4. **Kurze Sessions beachten:** Coffee handelt (ICE) nur ~8–12 h/Tag → AUG
   nur 490 Bars (14 Tr, −1.86R / PF 0.78). Wie bei Cocoa bleibt AUG eine
   kleine, nicht aussagekräftige Stichprobe; die Engine skaliert
   (MIN_CANDLES unverändert 46).
5. **SL-Sensitivität:** 0.30–0.35 % maximieren SumR (eng), der 0.87-ATR-Anker
   (≈0.45 %) bleibt robuster Mittelweg. MIN_SPREAD_PCT-Gate nicht bindend
   (Default 1.5 % bestätigt).
6. **Produktion bleibt exklusiv SILVER.** COFFEE als eigenständiges
   Handelssymbol dokumentiert (QS-9).

---

## 31. Gesamtauswertung & Rangliste (alle Symbole, S1+S2)

Vergleichs-Basis: Referenzfenster S1+S2 (2025 + 2026 bis 28.08.), final
kalibrierte Parameter je Symbol (§2.2–2.8). SILVER/GOLD ohne Equity-Report
in diesem Archiv (dokumentarisch aus §8.27); Equity-Konvention 1R = 100 USD,
keine Kosten.

### 31.1 Haupttabelle (sortiert nach SumR S1+S2)

| Rang | Symbol | Klasse | VA_PCT | Trades | WR % | SumR | PF | AvgW | Kurs%/Tr | End-Equity S1+S2 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **BRENT** | Rohöl-Future | 0.95 | 462 | 32.3 | **+347.68R** | 2.23 | +4.23 | +0.233 | +34.765 $ |
| 2 | **SILVER** | Metall (Baseline) | 0.93 | 411 | 39.7 | **+297.14R** | 2.33 | +3.32 | +0.325 | ~29.7k $ (n. ber.) |
| 3 | **NGas** | Gas-Future | 0.97 | 522 | 28.2 | **+285.59R** | 1.84 | +4.26 | +0.215 | +28.563 $ |
| 4 | **Ger40** | Index (DAX) | 0.89 | 424 | 32.3 | **+271.07R** | 2.00 | +3.95 | +0.087 | +27.106 $ |
| 5 | **GOLD** | Metall | 0.95 | 420 | 36.5 | **+196.06R** | ~1.80 | +2.78 | +0.113 | ~19.6k $ (n. ber.) |
| 6 | **COFFEE** | Soft-Commodity | 0.93 | 231 | 38.5 | **+190.92R** | 2.57 | +3.51 | +0.372 | +19.090 $ |
| 7 | **COCOA** | Soft-Commodity | 0.91 | 230 | 29.1 | **+176.01R** | 2.22 | +4.78 | +0.486 | +17.600 $ |
| 8 | **EURUSD** | FX | 0.99/0.91* | 437 | 31.4 | **+102.74R** | 1.40 | +2.62 | +0.017 | +10.272 $ |

\* EURUSD fensterindividuell (AUG/S1 0.99, S2 0.91).

### 31.2 Rangliste Profit-Faktor (PF, S1+S2)

| Rang | Symbol | PF | Rang | Symbol | PF |
|---|---|---|---|---|---|
| 1 | COFFEE | **2.57** | 5 | Ger40 | **2.00** |
| 2 | SILVER | **2.33** | 6 | NGas | 1.84 |
| 3 | BRENT | **2.23** | 7 | GOLD | ~1.80 |
| 4 | COCOA | **2.22** | 8 | EURUSD | 1.40 |

### 31.3 Rangliste Kursrendite je Trade (S1+S2)

| Rang | Symbol | Kurs%/Tr | Rang | Symbol | Kurs%/Tr |
|---|---|---|---|---|---|
| 1 | COCOA | **+0.486** | 5 | NGas | +0.215 |
| 2 | COFFEE | **+0.372** | 6 | GOLD | +0.113 |
| 3 | SILVER | **+0.325** | 7 | Ger40 | +0.087 |
| 4 | BRENT | **+0.233** | 8 | EURUSD | +0.017 |

### 31.4 Rangliste End-Equity S1+S2 (1R = 100 USD, ohne SILVER/GOLD-Report)

| Rang | Symbol | End-Equity | Rang | Symbol | End-Equity |
|---|---|---|---|---|---|
| 1 | BRENT | **+34.765 $** | 4 | COFFEE | **+19.090 $** |
| 2 | NGas | **+28.563 $** | 5 | COCOA | +17.600 $ |
| 3 | Ger40 | **+27.106 $** | 6 | EURUSD | +10.272 $ |

### 31.5 VA_PCT-Resonanzübersicht (Sweet Spot je Symbol)

| Symbol | VA_PCT | Abstand zu SILVER (0.93) | Tendenz |
|---|---|---|---|
| Ger40 | **0.89** | −0.04 | engere Zonen |
| COCOA | **0.91** | −0.02 | engere Zonen |
| SILVER | **0.93** | 0 | Baseline |
| COFFEE | **0.93** | 0 | Baseline-identisch (beide Regime) |
| GOLD / BRENT | **0.95** | +0.02 | weitere Zonen |
| NGas | **0.97** | +0.04 | weitere Zonen |
| EURUSD | 0.99/0.91 | +0.06/−0.02 | regime-abhängig extrem |

### 31.6 Gesamt-Fazit (Rangfolge qualitativ)

1. **BRENT** — bester R-Beitrag (PF 2.23, +347.68R), beide Fenster stimmig bei
   VA 0.95; Runner-Profil in S2. Robustester Cross-Asset-Beleg (R-Beitrag).
2. **COFFEE** — höchster PF über S1+S2 aller Assets (2.57), beide Fenster
   stimmig **exakt auf der SILVER-Kante (VA 0.93)** — erste Bestätigung ohne
   Resonanzverschiebung; S1 (2026) mit PF 2.63/WR 48.8 % das beste S1 aller
   Assets; Kursrendite +0.372 %.
3. **SILVER (Baseline)** — Benchmark: PF 2.33, WR 39.7 %, Kurs%/Tr +0.325;
   über den 18-Monats-Stresstest (§32) bestätigt. Produktion bleibt exklusiv
   SILVER.
4. **NGas** — zweitstärkster R-Beitrag, aber fragil: S2 kollabiert ohne weite
   Zonen (VA 0.97 zwingend); PF 1.84, längste DD-Serien.
5. **Ger40 (DAX)** — erster Index-Beleg, solide: PF 2.00, S1 (2026) mit
   PF 2.38/WR 42 %; VA 0.89 (engste Zonen).
6. **GOLD** — dokumentarisch: PF ~1.80, moderater Beleg bei VA 0.95.
7. **COCOA** — regime-abhängig (S1 0.95 / S2 0.91), aber höchste
   Kursrendite je Trade (+0.486 %), PF 2.22; wenige Bars (kurze Sessions).
8. **EURUSD** — schwächster und fragilster Beleg (PF 1.40): nur S2/2025-Trend
   trägt; S1/2026 erst nach SL-Anhebung auf ~2,2× ATR positiv; geringste
   Kursrendite/Trade (+0.017 %).

**Asset-Klassen-Fazit:** Der Reclaim-Edge ist auf Commodities und Indizes
(je PF ≥ 1.8) robust, auf FX (EURUSD) deutlich schwächer/fragiler. Softs
(COCOA/COFFEE) liefern die höchste Kursrendite je Trade (+0.486 %/+0.372 %)
bei kurzen Sessions; COFFEE bestätigt die SILVER-Resonanz (VA 0.93) als
erste Asset ohne Verschiebung.

---

## 32. SILVER M15 — Langzeit-Stresstest (QS-8.1, 05.02.2025 – 29.08.2026)

**Fragestellung:** Hält die SILVER-Baseline (unveränderte Produktions-Defaults)
den vollen DB-Zeitraum von 05.02.2025 bis 29.08.2026 (37.015 M15-Bars,
255 Phasen) durch — inklusive Super-Squeeze Dez 2025 und Crash-Ende
2025/Anfang 2026? Lauf über die Arbeitskopie mit `--symbol=SILVER
--start=2025-02-05 --ende=2026-08-30` und unveränderten Defaults
(VA_PCT 0.93, TOL 0.34/0.15/0.15/0.05, SL_PCT 0.45 %).

### 32.1 Gesamtergebnis (18 Monate)

| Kennzahl | Wert |
|---|---|
| Bars / Phasen | 37.015 / 255 (68 handelbar) |
| Trades | 442 (Long 252 / Short 190) |
| Win-Rate | 37.6 % |
| SumR | **+307.02R** |
| Profit-Faktor | **2.23** |
| AvgW / AvgL | +3.35R / −0.90R |
| End-Equity (1R = 100 USD) | **+30.707 $** |
| Max Drawdown | −1.706 $ (Tief T80, früh Feb–März 2025) |
| Längste DD-Serie | 50 Trades |
| Bester Trade | T207 SHORT +19.58R |
| Kursrendite/Trade | +0.313 % |

### 32.2 Monatsübersicht (Trades aus Engine-Log aggregiert)

| Monat | n | SumR | WR % | PF | Bemerkung |
|---|---|---|---|---|---|
| 2025-02 | 23 | −2.76R | 17.4 | 0.84 | Startphase |
| 2025-03 | 17 | +32.26R | 41.2 | 4.94 | |
| 2025-04 | 13 | −1.60R | 15.4 | 0.85 | |
| 2025-05 | — | (0 Trades) | — | — | keine handelbaren Phasen |
| 2025-06 | 14 | +5.94R | 35.7 | 1.71 | |
| 2025-07 | 14 | −10.07R | 7.1 | 0.23 | schwächster 2025er-Monat |
| 2025-08 | 17 | +11.05R | 41.2 | 2.17 | |
| 2025-09 | 24 | +28.35R | 70.8 | 5.05 | |
| 2025-10 | 36 | +28.51R | 41.7 | 2.46 | |
| 2025-11 | 21 | +8.23R | 28.6 | 1.60 | |
| **2025-12** | 33 | **+27.40R** | 27.3 | 2.30 | **Super-Squeeze: profitiert (Runner, AvgW +5.39R)** |
| **2026-01** | 24 | **−7.83R** | 20.8 | 0.53 | **Crash-Monat: Verlust, aber begrenzt** |
| 2026-02 | 31 | +21.47R | 35.5 | 2.12 | sofortige Erholung |
| 2026-03 | 22 | +27.27R | 36.4 | 3.12 | |
| 2026-04 | 31 | +33.16R | 41.9 | 3.02 | |
| 2026-05 | 35 | +44.68R | 57.1 | 4.94 | bester Monat |
| 2026-06 | 30 | +0.55R | 26.7 | 1.03 | |
| 2026-07 | 29 | +24.50R | 48.3 | 3.00 | |
| 2026-08 | 28 | +35.96R | 50.0 | 3.69 | |

### 32.3 Befunde Stresstest

1. **Engine hält den vollen Zeitraum fehlerfrei durch** — keine Exceptions/
   Warnungen, 255 sauber segmentierte Phasen über den kompletten
   Squeeze-Crash-Übergang; der Phasen-Referenzabgleich funktioniert über die
   Jahresgrenze.
2. **Crash-Phase Dez 2025 + Jan 2026 insgesamt positiv (+19.57R, 57 Tr,
   PF 1.52):** Der Dezember-Squeeze wird sogar genutzt (+27.40R, AvgW +5.39R
   → Runner in der Beschleunigung); der Januar-Crash ist ein Verlustmonat
   (−7.83R / PF 0.53), aber **kein Zusammenbruch** — größter Monatsverlust
   überhaupt liegt bei −10.07R (Jul 2025). Februar 2026 erholt sofort
   (+21.47R).
3. **Gesamt-Performance stabil:** +307.02R / PF 2.23 über 18 Monate — die
   Kursrendite je Trade (+0.313 %) bleibt nahe der S1+S2-Referenz (+0.325 %).
   Der Max-Drawdown (−1.706 $) stammt aus der frühen Startphase 2025
   (T80), nicht aus dem Crash.
4. **Kein Monat mit katastrophalem Verlust** (> −11R) und kein
   „Phase-0/Chaos"-Verhalten in der Trendbeschleunigung — die VA-0.93-Zonen
   und der 0.45 %-SL bleiben auch unter Extrem-Volatilität funktional.

**Artefakte:** `test/stats_trades_SILVER_LONG.txt`, `test/stats_trades_SILVER_LONG_equity.txt`,
`test/stats_trades_SILVER_LONG.png` (Equity), `test/phasen_volumen_profil_SILVER_LONG.png`
(Phasen-Chart), `test/tmp_silver_long_engine.log`, `test/tmp_monthly_agg.py`
(Auswertung). Produktions-Baseline unverändert.

