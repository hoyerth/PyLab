
---

# Addendum v0.23 — Zeitbasis-Kanon: Engine-Generation V018 (BKZ statt Berlin-Projektion) (2026-09-11)

## 73.0 Geltung und Abgrenzung

Dieses Addendum setzt §72 fort. Es regelt **eine** Sache: den Einbrand der
Engine-Generation **V018** in `test/tmp_kanten_engine_replay.py` — die
Umstellung der Datenprojektion von `AT TIME ZONE 'Europe/Berlin'` auf die
**Broker-Kerzen-Zeit (BKZ)** `AT TIME ZONE 'UTC'`.

Verbindliche Grundlage ist der projektweite Kanon `docs/ZEITBASIS_KANON.md`
(SSoT, Stufe S1): BKZ ist die **einzige Rechenbasis**; `Europe/Berlin` und
`Europe/Budapest` sind **reine Anzeige-Dubletten** und duerfen in
Auswertungs-/Display-Logik **nicht** als Rechenbasis auftreten.

Rahmen (Stufen S0–S4 der Zeitbasis-Bereinigung): **S0** Read-only-Audit
(703 Fundstellen / 130 Dateien), **S1** Kanon + Agents.md + Kopf-Errata
(`8826639`), **S2** Nomenklatur-Sweep (`9b2e585`), **S3** Engine/Renderer
V018, **S4** Peripherie-Harmonisierung (Commit `50912f2`). Dieses Addendum
dokumentiert **S3**; S4 ist im Code gefuehrt (Nachweis `test/test.py`
48 OK / 0 FAIL).

**Nicht** Gegenstand: die H2-Marktanalyse (P10 ab Bar 1021); die
Renderer-Darstellungsnorm (§54/§66, unveraendert); eine Neu-Arretierung des
V014-Panel-03-Hashes (bleibt **E-12**).

## 73.1 Anlass: die Projektion war DST-abhaengig

`ohlcv_bars.time` ist `TIMESTAMPTZ` und traegt die rohe MT5-Broker-Zeit in
UTC-Verkleidung. Die Engine las sie ueber `time AT TIME ZONE 'Europe/Berlin'`;
weil die DuckDB-Session-Zeitzone `Europe/Budapest` ist und die
`WHERE`-Fenstergrenzen dagegen bereits **UTC-formuliert** waren, zerfielen
`SELECT` und `WHERE` in **zwei** Zeitbasen. Der Offset ist zudem
**DST-abhaengig** (+1 h Winter / +2 h Sommer) — das ist keine Verschiebung,
sondern eine **verzerrte Zeitachse**.

**Weg A (gewaehlt):** `SELECT ... AT TIME ZONE 'UTC'` — eine Zeitbasis fuer
`SELECT` **und** `WHERE`; bar-identisch zur DB-Spalte und zum M15-Chart.

**Weg B (verworfen):** Berlin-Projektion beibehalten und die
`WHERE`-Grenzen nachziehen — haette zwei Zeitbasen in einer Datei belassen
(Verstoss gegen den Kanon „eine Zeitbasis pro Datei").

## 73.2 Die Motoraenderung: ein einziger Bezeichner

Die funktionale Aenderung der Engine ist **ein** Bezeichner im `SELECT`
(Z. 600 der V017):

```diff
-        SELECT time AT TIME ZONE 'Europe/Berlin' AS ts, open, high,
+        SELECT time AT TIME ZONE 'UTC' AS ts, open, high,
```

Alles Uebrige im Hunk ist Kommentar/Docstring (Nomenklatur „Wanduhr" →
BKZ). Gesamtdiff V017 → V018: **21 Zeilen hinzu / 8 entfernt, 2 Hunks**.

| Groesse | V017 | V018 |
|---|---|---|
| SHA256 | `4a356765…` | `4a576a76…` |
| Bytes | 196.083 | 196.649 (**+566**) |
| Umbrueche (CRLF) | 4.574 | 4.587 |

**Die `WHERE`-Grenzen waren bereits UTC.** Der Zeilensatz bleibt daher
zahlenmaessig identisch (**n = 1288**); es aendert sich **allein** die
Ableitung der Kalenderkante.

`box_end_bar` wird **nicht** als Bar-Konstante gefuehrt, sondern dynamisch
abgeleitet (Kanon §K4):

```python
box_end_bar = int(np.searchsorted(ts_arr, np.datetime64("2026-08-19")))
```

## 73.3 Box-Grenze 640 → 644 und der Grenztrade K1@640

Weil `ts_arr` jetzt die BKZ traegt, liefert
`searchsorted(ts_bkz, "2026-08-19")` den Wert **644** (V017: **640**). Die
H1-Box umfasst damit die Bars `< 644` statt `< 640`.

Damit kippt **genau ein** Trade ueber die Grenze: `K1@640`
(Entry-Bar 640, R = −1,000000). Er lag in V017 in **H2** (Entry 640 >= 640)
und liegt in V018 in **H1** (Entry 640 < 644).

| Auswirkung | V017 | V018 |
|---|---|---|
| H1-Box (Bars) | 0 … < 640 | 0 … < 644 |
| `K1@640` (R = −1,000000) | H2 | **H1** |
| H1 Trades / R (V0) | 7 / +39,919584 | **8 / +38,919584** |
| H2 Trades / R (V0) | 7 / +2,531386 | **6 / +3,531386** |
| H1 Trades / R (V1_aktiv) | 7 / +39,919584 | **8 / +38,919584** |
| H2 Trades / R (V1_aktiv) | 10 / +25,915992 | **9 / +26,915992** |

Es ist ein **Populations-/Reporting-Effekt der Box-Grenze**, keine
Regelwirkung: Kante, Richtung, Entry und R des Trades bleiben unveraendert;
nur seine **Zuordnung** wechselt. Die Gesamtsummen bleiben daher
**bit-identisch** (H1 + H2 = 17 Trades / +65,835576 R).

## 73.4 Fail-Loud-Generationsbindung V017 ⇄ V018

Der Renderer laedt **eine** Engine. Nach dem Einbrand traegt sie die
BKZ-Projektion; ein V017-Lauf mit ihr wuerde still falsche Sollwerte
produzieren. Das wird **nicht** stillschweigend ausgehebelt (beide
Richtungen geprueft, jeweils `EXIT 1` **vor** dem ersten PNG):

```text
$ python test/tmp_png_aug_sichttest.py --mode V017           # V018-Engine
AssertionError ... (box_end / Sollwert)   -> EXIT 1, Rueckweg genannt

$ python test/tmp_png_aug_sichttest.py --mode V018 ^
      --engine test/_tmp_backup_engine_pre_v018.py           # V017-Engine
AssertionError ...                         -> EXIT 1
```

Der Rueckweg fuer die Alt-Generation ist explizit und erprobt:

```text
python test/tmp_png_aug_sichttest.py --mode V017 ^
    --engine test/_tmp_backup_engine_pre_v018.py
```

Damit bleiben alle arretierten Saetze V01 … V017 **vollstaendig
reproduzierbar** — gebunden an die jeweilige Vorgaenger-Engine. Das
V017-Protokoll ist nach dem Umbau **numerisch unveraendert**; es
differieren nur der geladene Engine-Dateiname und die PNG-Namen/-Groessen.

## 73.5 Neuarretierte Sollwerte (V017 → V018)

| Kennzahl | V017 | **V018 (neu)** |
|---|---|---|
| `V0` (Baseline) | 14 / +42,450970 | **14 / +42,450970** (gleich) |
| `V0` Aufteilung | H1 7/+39,919584 · H2 7/+2,531386 | **H1 8/+38,919584 · H2 6/+3,531386** |
| `V1_basis` | 14 / +47,815697 | **14 / +47,815697** |
| `V1_aktiv` | 17 / +65,835576 | **17 / +65,835576** |
| `V1_aktiv` Aufteilung | H1 7/+39,919584 · H2 10/+25,915992 | **H1 8/+38,919584 · H2 9/+26,915992** |
| Quartett-R | +19,806095 | **+19,806095** |
| Delta `R1 − R_B` | +18,019879 | **+18,019879** |
| G4 `K77@1002` | +3,629016 | **+3,629016** (bit-identisch) |
| Niveauwechsel (sichtbar) | 66 | **66** |
| Linien mit Netto-Preiswechsel | 41 | **41** |
| Sperr-Marker Q29 | 69 | **69** |
| Sperr-Marker M6 | 24 | **24** |
| Lebende Kanten | 59 edges + 14 seeds = 73 | **59 + 14 = 73** |
| `n` | 1288 | **1288** |
| `box_end_bar` | 640 | **644** |

**E-15 (neuartig, deutlich).** Ab der Generation V018 ist der
**H1/H2-Split** an die Engine-Generation gebunden: die Aufteilung
`H1 8 | H2 6` (V0) bzw. `H1 8 | H2 9` (V1_aktiv) gilt **nur** fuer V018.
Die V017-Aufteilung (`H1 7 | H2 7` / `H1 7 | H2 10`) ist **nicht** mehr
reproduzierbar ohne die Vorgaenger-Engine. Ein H1/H2-Vergleich ueber
Generationen hinweg ist **unzulaessig**, ohne die Grenztrade-Migration
(§73.3) zu beruecksichtigen.

Der V018-H2-Sollwert **`9 / +26,915992 R` ist bestaetigt** (Adapter-Lauf,
`V1_aktiv`). Die Zahl `6 / +3,531386` ist der **ungepatchte V0-Motorlauf
ohne Adapter** und **kein** Adapter-Sollwert — die beiden Zahlen gehoeren
zu verschiedenen Gegenstaenden.

## 73.6 Renderer V018

Der Renderer `test/tmp_png_aug_sichttest.py` bekam einen **eigenen** Modus
`V018` + `KONFIGURATION_V018` + `AdapterMode`-Zweig, ohne den
V01…V017-Literaltext anzutasten (Diskriminatoren `_V18` / `_NEU` /
`_VTAG`). Die V017-Zweige behalten ihren Wortlaut.

| Groesse | V017 | V018 |
|---|---|---|
| SHA256 | `3d6a4788…` | `0d145ef4…` |
| Bytes | 92.915 | 97.160 (**+4.245**) |

Neu/erzwungen: `box_end`-Fail-Loud-Guards, BKZ-Nomenklatur (0 „Wanduhr",
0 `Europe/Berlin`), `_VER_TEXT`-V018-Zweig.

## 73.7 Artefakte und Arretierung

**Engine**

| Datei | SHA256 | Bytes |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` (V018) | `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` | 196.649 |
| `test/_tmp_backup_engine_pre_v018.py` (V017) | `4a3567659990586cb507f51e10575bdc9b64d82745523034c206b188e19f7298` | 196.083 |

**Renderer**

| Datei | SHA256 | Bytes |
|---|---|---|
| `test/tmp_png_aug_sichttest.py` (V018) | `0d145ef4c5ea0aa9b9b158c00bd54d97bfb1abd68e4a2a32f4e496fcea1f6fc7` | 97.160 |

**Adapter (unveraendert)**

| Datei | SHA256 | Bytes |
|---|---|---|
| `backtest_lab/phasen_regime_adapter.py` | `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` | 25.783 |

**Produktionssatz V018** (`aug_sichttest_v018_01..05.png`)

| Panel | SHA256 | Bytes |
|---|---|---|
| `01_gesamt` | `479dc86e8abf6e77cbcad8f18624edf5808f82e124d5e6bc8586455276b10746` | 2.072.366 |
| `02_h1_box` | `d5dc0516452b317e2f3e79491e2b5b403320bfb32ba4e482afa5391d36e5c6f1` | 895.851 |
| `03_h2_phasen` | `cd1214c44216770547fdd333027c7316057b829fc2d4b5f4aa23f6e097d6565d` | 1.703.141 |
| `04_p9_regime` | `d757db10fd21e08fefc1bf83cc76529b8dbdcedaaa1ab6886c2335e1d3468140` | 1.192.412 |
| `05_kantenkarte` | `2aef6011aa1f790c6d65a59423909783163c4b8e1f7d5adf5453127d9826067c` | 2.071.523 |
| **Protokoll** `test/tmp_png_aug_sichttest_v018_out.txt` | `d0e2ad537e55eed26a902690f95827fb2b5aa20bc82a12fe450bbc1cfa2c1d97` | 5.048 |

**Arretierungswechsel.** Ab V018 ist der **V018-Satz** die gueltige
Produktionsreferenz. Die Saetze V01 … V017 bleiben als **historische
Zeitzeugen** unveraendert liegen (keine kosmetische Neu-Erzeugung,
Anwenderentscheid).

## 73.8 Integritaet und Neutralitaetsnachweise

Alle Nachweise wurden als **gezielte Einzelpruefungen** gefahren (keine
Regressionstests).

| # | Pruefung | Ergebnis |
|---|---|---|
| 1 | `py_compile` Engine und Renderer | OK |
| 2 | Enginediff V017 → V018 | 21 +/8 −, 2 Hunks; **nur** Kommentar/Docstring + 1 Bezeichner |
| 3 | `WHERE`-Zeilensatz | n = 1288 **unveraendert** |
| 4 | V01 … V016-Saetze + Protokolle | **byte-identisch** reproduzierbar (Renderer `0d145ef4…`, Engine `4a356765…`) |
| 5 | V017-Satz + Protokoll | **byte-identisch** reproduzierbar (Engine `4a356765…`); numerisch unveraendert |
| 6 | Fail-Loud beide Richtungen | **EXIT 1** vor dem ersten PNG (§73.4) |
| 7 | G4 `K77@1002` | **+3,629016 R bit-identisch** |
| 8 | Kanten-IDs | **alle 73 stabil** |
| 9 | Summenkonsistenz H1 + H2 | V018: 8 + 9 = 17 Trades / +65,835576 R |
| 10 | S4 Peripherie | `py_compile` 10/10; `test/test.py` **48 OK / 0 FAIL**; Commit `50912f2` |

## 73.9 Status und offene Punkte

| Kennzahl | Wert |
|---|---|
| **V018 (eingebrannt)** | **17 Trades / +65,835576 R** |
| davon H1 | 8 / +38,919584 R |
| davon H2 | 9 / +26,915992 R |
| Engine-Generation | `4a576a76…` (V018, BKZ) |
| Regelbestand | §54 + §66 + §67 + §68 + §69 + §70 + §71 + §72 + **§73** |
| Renderer | `0d145ef4…` (V018) |
| Adapter | `0f3f8765…` (unveraendert) |
| Errata | E-5 · E-11 · E-12 · E-13 · E-14 · **E-15** (H1/H2 generationsgebunden) |

**Offen:**

1. **`test/` ist gitignored.** Engine, Renderer, Backups, PNG und
   Protokolle sind **untracked**; die Arretierung erfolgt urkundlich per
   SHA256 in diesem Dokument und im Handoff — **kein** `git add -f`.
2. **Kein Renderer-Backup `pre_v018`.** Der V017-Renderer
   (`3d6a4788…` / 92.915 B) wurde **in place** ueberschrieben und liegt
   nur noch urkundlich (SHA) vor — anders als bei der Engine (§73.7) und
   beim Renderer `pre_v017` (§72.8). Ein byte-genauer *Renderer*-Rollback
   ist damit nicht mehr moeglich. Die **Wirkung** ist davon nicht
   betroffen: der V018-Renderer fuehrt die V017-Literalzweige weiter, der
   V017-Satz bleibt ueber `--engine _tmp_backup_engine_pre_v018.py`
   reproduzierbar (§73.4).
3. **`SWEEP_MARKER_P02`** unveraendert (§71.7 / §72.11 Punkt 2).
4. **E-12** unveraendert (V014-P03 nicht neu arretiert).
5. **PNG-Neu-Erzeugung V01 … V017** nicht vorgesehen (historische
   Zeitzeugen).

**Naechster Auftrag:** H2-Marktanalyse (Phase P10 ab Bar 1021) — unveraendert.
