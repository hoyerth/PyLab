# CHECKPOINT 2026-09-09 — H2-Phasenregime-Adapter (Stand für morgen)

**Zweck:** Wiederaufsetzpunkt. Kein neuer Befund, keine neue Entscheidung —
reine Zustandssicherung. Alle Zahlen sind durch Skripte in `test/`
reproduzierbar (gitignored), die Dokumentation liegt in
`reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` (Addenda v0.1–v0.8).

---

## 1. Ein-Satz-Stand

Der H2-Phasen-Regime-Adapter v0.1 (P9 aktiv) ist implementiert, verifiziert und
committet; die H2-Exploration ist **abgeschlossen**; der neue **PNG-Satz für den
Sichttest über AUG komplett (5 Grafiken)** ist erzeugt, warnungsfrei und wartet
auf die **manuelle Sichtprüfung durch den Anwender**.

---

## 2. Git-Zustand

| Commit | Inhalt |
|---|---|
| `cd0e1b3` | Adapter v0.1 (`backtest_lab/phasen_regime_adapter.py`) |
| `63cdd2f` | P12-Trockenlauf + Konsolidierung (Doku) |
| `1aee0e4` | P12-Reserve-Struktur (Dreiteilung, gebundene Auditierung) |
| **`5ffc527`** | **Addendum v0.8 — PNG-Satz AUG-Sichttest** |

`git status --short`: nur `?? reports/setup_c/` (Fremdthema, unverändert).
Working Tree ansonsten clean.

---

## 3. Arretierte Baseline (GESPERRT — nicht antasten)

| Lauf | Definition | Trades | R |
|---|---|---|---|
| Lauf A (Box) | `entry_bar < 640` | 8 | **+38.964262** |
| Lauf B (Voll) | alle | 14 | **+40.445143** |

- Engine `test/tmp_kanten_engine_replay.py`: 4.500 Zeilen, 191.814 B,
  SHA256 `3ba15c723958161fffc28a106a5758bd3e27a6152f0e0235969594a5255cb006`
  — **byte-identisch** zu `docs/artefakte/aug_p11/kanten_engine_replay_v40r.py.snapshot`.
- `SL_BUFFER_USD = 0.05` bleibt.

---

## 4. Adapter v0.1 — Fakten

`backtest_lab/phasen_regime_adapter.py` (LF, kein BOM):

- `Hook2ZielModus` (MAKRO / PHASE / BLOCKIERT), `PhasenKanteInfo(kid: int,
  provenienz_basis, touch_bars)`, `PhasenSegmentEintrag`, `Hook2Ergebnis`
- `P9` = 848–1020, Decke K67 (69.9140), Boden K77 (68.3700),
  `ziel_preis_short = 68.3700`, `ziel_preis_long = 69.9140`,
  `touch_band_pct = 0.12`
- `AKTIVE_DEFAULT_SEGMENTE = (P9,)` · `P12_RESERVE` (1171–1272, K73/K82,
  67.6355) + `RESERVE_SEGMENTE` (dokumentarische Reserve, **nicht** aktiv)
- `start_scope_bar = 848`; Lücken = strikt **fail-closed** (BLOCKIERT,
  kein Makro-Fallback)
- Hook 1 = **Prädikat an zwei Stellen** (Pool-Filter in `_kandidat` + `continue`
  in `_blockiert_durch_aussenkante`), Freigabe nur im `dist < 0`-Zweig,
  nur die sweep-bildende Wand (Tie-Break `min |sweep−basis|`)

### Sollwerte (alle erfüllt)

| Prüfung | Soll | Ist |
|---|---|---|
| H1 bit-identisch | 8 / +38.964262 R | ✅ |
| H2 Adapter | 7 / +7.9021 R | ✅ +7.902085 |
| K73@980 | +2.4119 R | ✅ |
| K73@1020 | +3.0093 R | ✅ |
| Regime-Summe | +5.4212 R | ✅ |
| K59@853 | entfällt | ✅ |
| Gesamt V1 | 15 / +46.866348 R | ✅ |

---

## 5. Der neue PNG-Satz (Kern des offenen Auftrags)

Skript: `test/tmp_png_aug_sichttest.py` (703 Zeilen, 32.303 B, gitignored)
Protokoll: `test/tmp_png_aug_sichttest_out.txt` (warnungsfrei)

| # | Datei (in `test/`) | Fenster | Pixel | Bytes |
|---|---|---|---|---|
| 01 | `aug_sichttest_01_gesamt.png` | 0..1288 | 6600×3900 | 1.657.807 |
| 02 | `aug_sichttest_02_h1_box.png` | 0..660 | 6000×3600 | 652.507 |
| 03 | `aug_sichttest_03_h2_phasen.png` | 620..1288 | 6600×3600 | 1.168.856 |
| 04 | `aug_sichttest_04_p9_regime.png` | 820..1045 | 6300×3600 | 698.274 |
| 05 | `aug_sichttest_05_kantenkarte.png` | 0..1288 | 6600×3900 | 1.626.925 |

Eingebaute Asserts (Fail-Loud) im Skript: V0 14/≈40.45 · H1 8/+38.964262 ·
H2 7/+7.9021 · K73-Summe +5.4212.

Konventionen eingehalten: Statistik **mittig** im unteren Panel, Legende
**oben links**, `Agg`-Backend (kein GUI), H1/H2-Grenze aus
`scan["box_end_bar"]` (640) — **keine** Hardcode-Altlast mehr.

Reproduktion:

```
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe test\tmp_png_aug_sichttest.py
```

---

## 6. Nächster Schritt (morgen zuerst)

1. **Sichttest der 5 PNGs durch den Anwender** (manuell, Pflicht — keine
   UI-/Regressionstests durch die KI).
2. Danach ggf. Darstellungs-Nachbesserungen (Kandidaten):
   - (a) x-Achsen-Ticks in `png_04` (12 Ticks über 820..1045),
   - (b) Überlappung der Trade-Annotationsboxen in dichten Bereichen
     (`png_01` / `png_05`),
   - (c) Position der `P9 AKTIV` / `P12 RESERVE`-Labels am oberen Rand
     (`y1`) in `png_01` / `png_03` / `png_05`.

### Offene Entscheidungsfragen (Antwort als Text erwartet)

| # | Frage |
|---|---|
| F1 | PNGs zusätzlich nach `reports/h2_phasenregime/png_aug_sichttest/` kopieren (versionierbar) oder bewusst nur lokal in `test/` lassen? |
| F2 | Welche Darstellungs-Kandidaten (a/b/c) anpassen? |
| F3 | Adapter **v0.2** mit P12 als aktivem Segment, oder bleibt `segmente=(P9,)` bis zum empirischen P12-Nachweis arretiert? |

---

## 7. Mentor-Entscheidungen (fixiert, nicht neu verhandeln)

1. Kriterium **M** (Touch-Band 0,12 %) · 2. Start **Bar 848 / P9** ·
3. **striktes Fail-Closed** in Lücken · 4. **BLOCKIERT** ohne Makro-Fallback ·
5. Zielort `backtest_lab/phasen_regime_adapter.py` · 6. Freistellung **nur
sweep-bildende Wand** · 7. `kid: int` · 8. Freigabe **nur im `dist < 0`-Zweig**
(Prädikat-Gate) · 9. Vorzeichen **intern** abgeleitet · 10. Fail-Loud
(`ValueError`) für `boden.kid` · 11. `provenienz_basis(K67)=69,9140` ·
12. `boden.provenienz_basis` + `ziel_preis_short` beide behalten ·
13. `ziel_preis_long=69,9140` · 14. **P12 = RESERVE**, `segmente=(P9,)` ·
15. **Transition-Zone 640–847: FINGER WEG**, dauerhaft MAKRO ·
16. v0.1 **ohne Engine-Tagging**.

---

## 8. Umgebung / Kommandos (Windows PowerShell 5)

- Projekt `F:\Python\PyLab`; **kein `&&`** — `;` verwenden.
- Interpreter `.venv\Scripts\python.exe` (Python 3.12.10);
  `$env:PYTHONIOENCODING="utf-8"` voranstellen.
- `certutil -hashfile <datei> SHA256` (kein `Get-FileHash` verfügbar).
- DB `data/market_data.duckdb` (read_only), SILVER M15, Tabelle `ohlcv_bars`.
- Tests **nur** in `test/`; `test/` ist gitignored (`.gitignore` Z. 63).
- `reports/` und `backtest_lab/` sind **nicht** ignored.
- Keine UI-/Regressionstests; Verifikation nur Logik-/DB-Tests,
  `py_compile`, Code-Inspektion.
- Commit-Signatur Pflicht:
  `Generated with [Continue](https://continue.dev)` +
  `Co-Authored-By: Continue <noreply@continue.dev>`.

---

## 9. Bekannte Altlasten (nicht Teil des aktuellen Auftrags)

- `test/tmp_png_h1h2_full.py` hardcodiert Label `bars < 644` (muss 640) —
  das **neue** Sichttest-Skript hat diesen Fehler nicht.
- Veraltete `_p8` / `_p9`-Docstrings in `test/tmp_png_vollzeitraum.py`
  und `test/tmp_png_h2_zoom.py`.
- Chart-H1/H2-Konvention (semantisch 9/+37,97 vs. Lauf-Definition
  8/+38,96) — ungeklärt, aber für den Sichttest nicht relevant.
- `reports/setup_c/` untracked (Fremdthema).
- Aufräum-Ziel für alte `tmp_*`-Skripte: `test/archiv/p1_p9/` (noch offen).

---

## 10. Referenz-Artefakte (Wiederaufsetzen)

| Zweck | Datei |
|---|---|
| Spezifikation (alle Addenda) | `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` |
| Adapter (Produktivcode) | `backtest_lab/phasen_regime_adapter.py` |
| Adapter-Test (Sollwerte) | `test/tmp_test_phasen_regime_adapter.py` (+`_out.txt`) |
| Hook-Semantik-Beweis (V0–V7) | `test/tmp_hook_semantik_check.py` (+`_out.txt`) |
| P12-Trockenübung | `test/tmp_dryrun_p12.py` (+`_out.txt`) |
| **PNG-Sichttest (aktuell)** | `test/tmp_png_aug_sichttest.py` (+`_out.txt`) |
| Engine (gesperrt) | `test/tmp_kanten_engine_replay.py` |
