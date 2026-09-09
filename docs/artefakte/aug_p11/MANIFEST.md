# MANIFEST — Revisions-Snapshot `aug_p11` (Baseline +40,45 R)

> **Zweck:** Unveraenderliche, git-versionierte Fixierung desjenigen Code- und
> Report-Stands, der den August-Benchmark traegt. Dieser Ordner ist ein
> **Beweisstueck** (Audit-Anker), **kein Werkzeug** — siehe Abschnitt 5.
>
> **Status: GESPERRT.** Aenderungen an den Dateien in diesem Ordner sind
> unzulaessig. Neue Staende erhalten einen neuen Ordner (`aug_p12`, ...).

Erstellt: 2026-09-09 · Stand des Codes: Patch `_p11` · Sprache: Deutsch

---

## 1. Artefakte und Pruefsummen

| # | Datei | Original | Bytes | SHA256 (vollstaendig) |
|---|---|---|---|---|
| 1 | `kanten_engine_replay_v40r.py.snapshot` | `test/tmp_kanten_engine_replay.py` | 191.814 | `3ba15c723958161fffc28a106a5758bd3e27a6152f0e0235969594a5255cb006` |
| 2 | `harness_AUG_v40r.txt.snapshot` | `test/tmp_v3_straight_edge_harness_AUG.txt` | 12.579 | `cd032d17004be8b9c469c9a69f7dbe3ec0c907b9fdbc88595fe11e5f1617b254` |
| 3 | `trades_AUG_mC_v40r.png` | `test/kanten_engine_trades_AUG_mC.png` | 556.793 | `2758dd62126874239ec7673e1007dfe5c0f124daae0dc8b7f1e88a19a93f60dd` |

**Kopierverifikation:** Alle drei Dateien wurden nach dem Kopieren
byte-identisch (`a == b`) gegen ihre Quelle geprueft — **3/3 OK**.

**EOL-Invariante:** Die Dateien sind CRLF-kodiert (Snapshot 1: 4.500 CRLF;
Snapshot 2: 164 CRLF; PNG: 9 zufaellige `\r\n`-Bytefolgen im Binaerstrom).
Die Regel `docs/artefakte/aug_p11/** -text` in `.gitattributes` verhindert
eine Zeilenenden-Normalisierung durch Git (`core.autocrlf = true`). Ohne diese
Regel waeren die obigen Hashes auf Linux/macOS **ungueltig**.

---

## 2. Datenbank-Fingerprint (zweistufig)

Quelle: `data/market_data.duckdb` (read-only abgefragt am 2026-09-09).
Die Datenbank selbst ist **nicht versioniert** (`.gitignore: *.duckdb`,
3.319 MB) — der Fingerprint ist die einzige Bruecke zur Reproduzierbarkeit.

### 2.1 Partitions-Ebene (Rohdaten-Quelle)

| Feld | Wert |
|---|---|
| Tabelle | `ohlcv_bars` (einzige Tabelle im Schema; **keine** View `silver_m15`) |
| Symbol | `SILVER` |
| Timeframe | `M15` |
| Zeilen | **222.944** |
| MIN `time` | `2013-06-05 02:00:00+02:00` |
| MAX `time` | `2026-09-05 00:45:00+02:00` |

### 2.2 Fenster-Ebene (Engine-Schnitt AUG)

Engine-WHERE (`_lade_fenster`): `time AT TIME ZONE 'UTC' >= DATE '2026-08-10'`
und `< DATE '2026-08-28'`.

| Feld | Wert |
|---|---|
| Fenster-ID | `AUG` |
| Bars | **1.288** |
| MIN `time` | `2026-08-10 02:00:00+02:00` |
| MAX `time` | `2026-08-28 00:45:00+02:00` |

> **Abgrenzung:** `222.944` ist der Partitions-Anker, `1.288` die abgeleitete
> Fenstergroesse. Eine Verwechslung beider Zahlen wurde im Vorfeld dieses
> Manifests aufgedeckt und ist hiermit ausgeschlossen.

---

## 3. Lauf-Trennung: Lauf A und Lauf B

Der Snapshot ist **nicht** in der Lage, den Benchmark selbst zu erzeugen.
`box_end_bar` ist im Code hart verdrahtet
(`box_end_bar = int(np.searchsorted(ts_arr, np.datetime64("2026-08-19")))`,
Zeile 2185) und **nicht** per CLI steuerbar. Verfuegbare Optionen:
`--fenster`, `--max-tage`, `--modus`, `--dpi`, `--matrix`, `--png`.

### 3.1 Lauf A — Deterministischer CLI-Lauf (`box_end_bar = 640`)

Befehl: `.venv\Scripts\python.exe test\tmp_kanten_engine_replay.py --fenster AUG --modus C`

| Kennzahl | Wert |
|---|---|
| Trades | **8** |
| Netto-R (Floats, arretiert) | **+38,9643 R** |
| Netto-R (Summe der Display-Rundungen) | **+38,97 R** |
| Rundungsdelta | **+0,0057 R** |
| Stacking-Sperren | 0 |

Einzel-R (Display, aus `harness_AUG_v40r.txt.snapshot`):
`+6,92 +3,95 −0,40 +5,66 −0,48 +8,39 +15,93 −1,00 = +38,97 R`

> **Rundungsdelta deklariert:** Der TXT-Report enthaelt **keine Aggregat-Zeile**;
> er listet nur Einzeltrades in 2-Nachkommastellen-Darstellung. Die Summe dieser
> Anzeigewerte (+38,97) weicht von der intern akkumulierten Float-Summe
> (+38,9643) um **+0,0057 R** ab. **Massgeblich ist der Float-Wert.**

### 3.2 Lauf B — Voll-Fenster (`box_end_bar = n = 1288`, programmatisch)

Erzeugung: **nicht** per CLI, sondern durch In-Memory-Oeffnung der Box-Grenze
(`sc["box_end_bar"] = sc["n"]`), dokumentiert in
`test/tmp_p9_gegenueberstellung.py` und `test/tmp_p9_boxend_diag.py`.

| Kennzahl | Wert |
|---|---|
| Trades | **14** |
| Netto-R (Floats, arretiert) | **+40,4451 R** |
| Netto-R (Display) | **+40,45 R** |
| Stacking-Sperren | 0 |
| H1-Anteil (semantisch, Signal-Bar < 640) | 9 / +37,9700 R |
| Nicht-Box-Anteil (Lauf-Definition, 6 Trades ab Bar 639) | 6 / +1,4808 R |

**Zerlegung (arithmetisch geschlossen):**
`37,9643 (Lauf A) + 1,4808 (Nicht-Box-Anteil) = 40,4451 R`

> **Feldnamen-Konvention:** Lauf-A-Groessen tragen das Praefix
> `lauf_a_cli_box_*`, Lauf-B-Groessen `lauf_b_programmatisch_voll_*`, damit
> die beiden Laeufe nicht verwechselt werden koennen.

### 3.3 Bekannte Kennzahl-Konstellation (transparent)

| Quelle | Box | Post/restlich | Summe |
|---|---|---|---|
| Semantische Lesart (Signal-Bar < 640) | 9 / +37,9700 | 5 / +2,4800 | 14 / +40,4500 |
| Lauf-Definition (`range(2, box_end−3)`) | 8 / +38,9643 | 6 / +1,4808 | 14 / +40,4500 |

Beide Lesarten sind arithmetisch korrekt; sie unterscheiden sich nur in der
Zuordnung des Trades **Bar 639 (Entry 640, −1,00 R)**. Grund: Mit
`box_end_bar = 640` laeuft die Trade-Schleife `range(2, box_end − 3)` nur bis
Bar 636, sodass der Signal-Bar 639 nicht mehr im Box-Lauf erscheint. Bar 639
ist Wanduhr **18.08. 21:45** und liegt damit **innerhalb** der Box-Grenze 640;
er rutscht ausschliesslich durch die Lookahead-Marge hinaus.

---

## 4. Header-Hinweis zum TXT-Snapshot

Zeile 2 von `harness_AUG_v40r.txt.snapshot` lautet:

```
V3-STRAIGHT-EDGE-HARNESS AUG | SE_BAND 0.120% | Box < 19.08 (bars < 640) | arretiert a771e04
```

Der Verweis `arretiert a771e04` ist ein **historischer Artefakt-Header** aus
einem frueheren Commit. Er wurde bewusst **nicht** angepasst, weil der Snapshot
den Stand unveraendert abbilden muss (Revisionsprinzip). Der tatsaechliche
Code-Stand dieses Snapshots ist **Patch `_p11`** (SHA256 siehe Abschnitt 1).
Der Header ist als offener kosmetischer Punkt in der Spezifikation gefuehrt.

---

## 5. Deklaration: Nicht-Ausfuehrbarkeit am Zielort

Der Snapshot ist **am Archivort nicht lauffaehig**. Grund sind relative Pfade,
die gegen den Dateistandort aufgeloest werden:

| Konstante | Zeile | Aufloesung am Zielort | Folge |
|---|---|---|---|
| `ROOT = Path(__file__).resolve().parent.parent` | 104 | `docs/artefakte` | falsches Wurzelverzeichnis |
| `DB_PATH = ROOT / "data" / "market_data.duckdb"` | 107 | `docs/artefakte/data/...` | Datenbank nicht gefunden |
| `REPORT_TXT = ROOT / "test" / "stats_kanten_engine_replay.txt"` | 108 | `docs/artefakte/test/...` | Zielordner existiert nicht |
| `_png_pfad_c` / `_kantenliste_c_txt` | 3974 / 3980 | `docs/artefakte/test/...` | Zielordner existiert nicht |

**Konsequenz:** Wer den Benchmark reproduzieren will, muss die Originaldatei
`test/tmp_kanten_engine_replay.py` mit identischem SHA256 verwenden (siehe
Abschnitt 1) und die DB unter `data/` vorfinden (Fingerprint Abschnitt 2).
Der Snapshot dient ausschliesslich der **Beweissicherung**.

Der Snapshot ist selbststaendig im Sinne der Abhaengigkeiten: Er importiert
ausschliesslich `argparse`, `os`, `sys`, `time`, `dataclasses`, `pathlib`,
`typing`, `duckdb`, `numpy`, `pandas` — **keine** `tmp_*`-Module.

---

## 6. Externe Abhaengigkeiten (nicht versioniert)

| Abhaengigkeit | Pfad | Status | Genutzt von |
|---|---|---|---|
| DuckDB-Marktdaten | `data/market_data.duckdb` | gitignored (`*.duckdb`), 3.319 MB | Engine, Fingerprint Abschnitt 2 |
| SILVER-M15-CSV | `test/archiv/silver_m15_ohlc_2026-08-10_2026-08-28.csv` | gitignored (`test/`), 64.976 B | 7 H1-Auditskripte |
| Engine-Vorstaende | `test/tmp_kanten_engine_replay_pre_p9/_p10/_p11.py` | gitignored (`test/`) | Gegenueberstellung/Audit-Kette |

---

## 7. Was dieser Snapshot **nicht** leistet

1. **Kein Runtime-Gate.** Es existiert bewusst **kein** `sys.exit(3)`-Waechter
   im Code. Die Arretierung erfolgt durch Versionierung, nicht durch starre
   Laufzeitschranken.
2. **Keine H1-Sperre.** Nach Fixierung dieses Stands duerfen Folgeaenderungen
   (Transition Zone, H2) H1 beeinflussen. Jede Abweichung wird gegen diesen
   Snapshot gemessen und dokumentiert.
3. **Keine Live-Portierung.** Die Straight-Edge-Revision ist Backtest-only;
   `scripts/reclaim_live_kernel.py` fuehrt `_se_*`, `touch_conf`, `basis_bei`
   nicht.
4. **Kein Beleg des Voll-Laufs durch Ausfuehrung** — Lauf B entsteht nur
   programmatisch (Abschnitt 3.2).
