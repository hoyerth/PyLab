# Zeitbasis-Kanon (BKZ) — Single Source of Truth

Status: **VERBINDLICH / AKTIV** (kein historisches Protokoll)
Datum: 2026-09-11
Geltung: **alle aktiven Linien** — Code (`algos/`, `backtest_lab/`, `scripts/`,
`signal_lab/`, `test/`) und getrackte Doku (`docs/`-Root, `reports/`, `test/`).
Archiv-Ausnahme: **`docs/Archiv/` bleibt unberührt** (Archiv-Doktrin, Agents.md).
Grundlage: Audit **S0** (`test/_tmp_zeitkanon_audit.py`, read-only, 2026-09-11).

---

## 1. Wurzel des Problems (Befund S0)

Es gab nicht *eine* falsche Zeile, sondern **vier Konventionen** und **einen
überladenen Begriff**. „Wanduhr" bedeutete an einer Stelle *rohe Kerzenzeit*,
an einer anderen *+2 h-Berlin-Projektion* — und war nirgends als SSoT markiert.

| # | Faktum | Konsequenz |
|---|---|---|
| F1 | `ohlcv_bars.time` ist `TIMESTAMP WITH TIME ZONE` und hält die **rohe MT5-Broker-Wanduhr im UTC-Gewand** (Instant ≠ Marktzeit) | Jede Projektion ist eine *zweite* Verschiebung |
| F2 | DuckDB-Session-TZ = `Europe/Budapest` | Nacktes `SELECT time` ist **maschinenabhängig** |
| F3 | Engine Z. 600 projizierte zusätzlich auf `Europe/Berlin` | **DST-abhängiger** Offset: AUG +2 h konstant; **S1 9.895×+2 h / 3.394×+1 h**; **S2 13.658×+2 h / 7.966×+1 h** |
| F4 | `searchsorted(ts, "<datum>")` lag auf der Berlin-Achse | Kalendergrenzen wandern saisonal um **4 oder 8 Bars** |
| F5 | Der Begriff „Wanduhr" war doppelt belegt | Jede Session griff die zuletzt gelesene Lesart |

**Messbeweis F1/F3** (read-only, `test/_tmp_zeitkanon_semantik.py`, `…_dst.py`):

| Bar | `time AT TIME ZONE 'UTC'` (**BKZ**, = MT5-Kerze) | `Europe/Berlin` (Anzeige-Dublette) |
|---|---|---|
| 1122 | 26.08. **04:30** ✅ (K73-Docht H 69,7090) | 26.08. 06:30 |
| 1272 | 27.08. **19:00** ✅ (K73-Decke H 69,7140) | 27.08. 21:00 |
| 1075 | 25.08. **15:45** ✅ (K82 Monatstief L 67,4200) | 25.08. 17:45 |

7 von 7 Anwender-Marken treffen die UTC-Lesart, keine die Berlin-Lesart.

---

## 2. Der Kanon (verbindliche Regeln)

### K1 — BKZ ist die einzige Rechenbasis

> **Broker-Kerzen-Zeit (BKZ) := `time AT TIME ZONE 'UTC'`** (tz-naiv, nach
> `tz_localize(None)`).

Das ist die Zeit, die MT5 als Kerze anzeigt. Sie ist die **Leitwährung** für
Fenster, Kalendergrenzen, Achsen, Tabellen, Labels und Bar-Zuordnung.

### K2 — Regionale Projektionen sind reine Anzeige-Dubletten

`Europe/Berlin` und `Europe/Budapest` dürfen **ausschließlich** als zusätzliche,
klar benannte Anzeige-Spalte erscheinen (z. B. `bar_anzeige`). Sie sind:

* **nie** Rechenbasis,
* **nie** in `WHERE` / `searchsorted` / `floor` / `resample` / `groupby`-Schlüsseln,
* **nie** Grundlage einer Bar-Berechnung,
* **nie** alleinige Zeitachse einer Grafik.

### K3 — Terminologie-Verbot

| Verboten | Erlaubt / Pflicht |
|---|---|
| „Wanduhr" (doppeldeutig) | **„BKZ"** bzw. **„Broker-Kerzen-Zeit"** |
| „Berlin-Wanduhr" | **„Anzeige (+02:00)"** / `Europe/Berlin` (Dublette) |
| „Engine-Wanduhr", „Motor-Wanduhr" | **„BKZ"** |
| „Broker/UTC", „UTC-Wanduhr" | **„BKZ"** (UTC ist die Extraktions-**Projektion**, nicht die Zeit) |

Das Wort **„Wanduhr" wird projektweit eliminiert** (Code, Docstrings, Kommentare,
Doku). „UTC" bleibt zulässig als Bezeichnung der *SQL-Projektion* (`AT TIME
ZONE 'UTC'`), **nie** als Name der Zeitachse.

### K4 — Nacktes `SELECT time` ist verboten

Da die Session-TZ `Europe/Budapest` ist (F2), muss jede Zeit-Extraktion explizit
projizieren:

```sql
-- VERBINDLICH (BKZ)
SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
FROM ohlcv_bars
WHERE symbol = 'SILVER' AND timeframe = 'M15'
  AND time AT TIME ZONE 'UTC' >= DATE '{start}'   -- Fenstergrenzen in BKZ
  AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
ORDER BY time
```

Anschließend: `d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_localize(None)`.

### K5 — Spaltenkonvention (Dreispaltig)

| Bar | Broker-Kerzen-Zeit (BKZ) | Anzeige (+02:00) |
|---|---|---|
| 1122 | 26.08. 04:30 | 26.08. 06:30 |

**Der Bar-Index ist der Primärschlüssel** jeder Aussage; Zeitstempel sind
nachrangig und dienen der Lesbarkeit.

### K6 — Kalendergrenzen werden dynamisch abgeleitet

Kalendergrenzen werden **kausal aus dem Datumsstring auf der BKZ-Achse** gebildet
— **niemals** als statische Bar-Konstante hartcodiert:

```python
ts_arr = d["ts"].to_numpy().astype("datetime64[ns]")      # BKZ, tz-naiv
box_end_bar = int(np.searchsorted(ts_arr, np.datetime64("2026-08-19")))  # -> 644
```

Im Fenster AUG (M15) ergibt `"2026-08-19"` auf der BKZ-Achse exakt **Bar 644**
(= 19.08. 00:00 BKZ). `640` war das Artefakt der Berlin-Achse (18.08. 22:00 BKZ)
und ist **nicht** mehr gültig.

---

## 3. Migrationsmatrix V017 → V018

| Größe | V017 (Berlin-Achse) | **V018 (BKZ)** |
|---|---|---|
| `d["ts"]` Bar 1122 | 26.08. 06:30 | **26.08. 04:30** |
| `AXIS_TZ_OFFSET_H` | 0 (aber falsche Achse) | **0 (korrekt)** |
| `box_end_bar` | 640 (statisch, ~18.08. 22:00 BKZ) | **644** (dynamisch, 19.08. 00:00 BKZ) |
| H1-Partition | 7 Trades / +39,919584 R | **8 Trades / +38,919584 R** |
| H2-Partition | 10 Trades / +25,915992 R | **6 Trades / +3,531386 R** |
| **V1_aktiv (Gesamt)** | 17 / +65,835576 R | **17 / +65,835576 R (unverändert)** |
| Trades/Reclaims/Kanten | 17 / vollständig | **identisch** (nur Labels −2 h) |
| Panel-02-Anker `42427164…` (874.523 B) | gültig | **aufgehoben → Neu-Arretierung** |

**Der einzige kippende Trade:** `K1`, `entry_bar = 640`, `r = −1,000000` wandert
von H2 nach H1. Alle übrigen 16 Trades bleiben in ihrer Partition; die
Gesamt-Performance ist **bit-identisch**.

---

## 4. Prüfkriterien (Selbstkontrolle jeder Änderung)

1. `python test/_tmp_zeitkanon_audit.py` → **C im Code = 0** (außer arretierte
   Backups/`test/trash/`).
2. Kein Treffer für `AT TIME ZONE 'Europe/Berlin'` außerhalb von Anzeige-Spalten.
3. Kein Treffer für `SELECT time ` ohne `AT TIME ZONE`.
4. Kein Treffer für „Wanduhr" außerhalb von `docs/Archiv/` und historischen
   Protokollen.
5. `py_compile` der geänderten Dateien; Sollwert-Asserts fail-loud.

---

## 5. Bekannte, bewusst unveränderte Zeitzeugen

| Ort | Grund |
|---|---|
| `docs/Archiv/**` | Archiv-Doktrin (Agents.md) |
| `test/_tmp_backup_engine_pre_v017.py` | Zeitzeuge der alten Zeitbasis (pre-V018) |
| `test/_tmp_backup_renderer_pre_v015/16/17.py` | Zeitzeugen der Renderer-Generationen |
| `test/trash/**` | Aussonderungsbestand |
| `test/_tmp_zeitbasis_check*.py`, `…_kopplung.py` | Forensik-Nachweise (read-only) |

Diese Dateien werden **byte-unverändert** belassen und sind ausdrücklich als
„alte Zeitbasis (pre-V018)" gekennzeichnet.

---

## 6. Historie

| Datum | Ereignis |
|---|---|
| 2026-09-10 | Forensik: +2 h-Versatz in `d["ts"]` entdeckt (N3, `SESSION_HANDOFF.md`) |
| 2026-09-11 | Messung der **DST-Verzerrung** (S1/S2: +1 h bzw. +2 h) |
| 2026-09-11 | Audit **S0**: 703 Fundstellen / 130 Dateien (A=240, B=171, C=66) |
| 2026-09-11 | **S1**: Dieser Kanon in Kraft; `Agents.md` bereinigt |
