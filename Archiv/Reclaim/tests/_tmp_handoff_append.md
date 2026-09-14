
---

## Einbrand 2026-09-11 — Engine-Generation V018 (Addendum v0.23 / §73) + Zeitbasis-Bereinigung S0–S4

> Antwort auf die **N5-Entscheidungsfragen** (Zeitbasis) aus der Exploration
> 2026-09-10: alle vier sind entschieden und umgesetzt.

### Was passiert ist

Stufenweise Bereinigung der Zeitbasis (SSoT `docs/ZEITBASIS_KANON.md`):

| Stufe | Inhalt | Commit |
|---|---|---|
| S0 | Read-only-Audit (703 Fundstellen / 130 Dateien) | — |
| S1 | Kanon als SSoT, Agents.md bereinigt, Kopf-Errata | `8826639` |
| S2 | Nomenklatur-Sweep „Wanduhr" → BKZ (AST-neutral) | `9b2e585` |
| S3.4 | Inline-Marker „historisch überholt" in 3 Alt-Protokollen | `64fc154` |
| S4 | Peripherie auf BKZ (tz_offset_hours entfernt) | `50912f2` |
| S3 | Engine/Renderer **V018** (Engine in `test/`, gitignored) | urkundlich |

**Antworten auf N5 (Zeitbasis):**
1. **Z. 600 → `'UTC'`** (Weg A) — neu arretiert als **V018**; `box_end` dynamisch
   **644**; der Grenztrade `K1@640` (r = −1,000000) kippt von H2 nach H1.
2. AGENTS.md entschärft — Kanon ist verbindlich.
3. `docs/reclaim.md`-Erratum korrigiert (Datei existiert nicht).
4. **PNG-Neuproduktion verworfen** — V01…V017 bleiben historische Zeitzeugen,
   nur der V018-Satz ist Produktionsreferenz.

### Sollwerte V018 (Adapter v0.1)

| Kennzahl | V017 | **V018** |
|---|---|---|
| V0 (Baseline) | 14 / +42,450970 | 14 / +42,450970 |
| V1_basis | 14 / +47,815697 | 14 / +47,815697 |
| **V1_aktiv** | 17 / +65,835576 | **17 / +65,835576** |
| H1 | 7 / +39,919584 | **8 / +38,919584** |
| H2 | 10 / +25,915992 | **9 / +26,915992** |
| n / box_end | 1288 / 640 | **1288 / 644** |

`K1@640` ist der **einzige** Trade, der die Box-Grenze wechselt (H2 → H1);
Gesamtsummen bit-identisch. **E-15:** H1/H2-Split ist ab V018
generationsgebunden — generationenübergreifende H1/H2-Vergleiche unzulässig.

### Artefakte (SHA-Anker, `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| Engine V018 `tmp_kanten_engine_replay.py` | `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` | 196.649 |
| Backup V017 `_tmp_backup_engine_pre_v018.py` | `4a3567659990586cb507f51e10575bdc9b64d82745523034c206b188e19f7298` | 196.083 |
| Renderer V018 `tmp_png_aug_sichttest.py` | `0d145ef4c5ea0aa9b9b158c00bd54d97bfb1abd68e4a2a32f4e496fcea1f6fc7` | 97.160 |
| Adapter (unverändert) `backtest_lab/phasen_regime_adapter.py` | `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` | 25.783 |
| Protokoll `tmp_png_aug_sichttest_v018_out.txt` | `d0e2ad537e55eed26a902690f95827fb2b5aa20bc82a12fe450bbc1cfa2c1d97` | 5.048 |

Produktionssatz `aug_sichttest_v018_01..05.png`: SHAs und Bytes in
`reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` **§73.7**.

### S4 — Peripherie auf BKZ

`tz_offset_hours` projektweit entfernt; SQL überall `AT TIME ZONE 'UTC'`:

- `algos/chart_engine.py`, `algos/chart_plugins.py` (neu `_EPOCH`/`_epoch_sec`,
  ersetzt 5× `int(...timestamp())`), `signal_lab/quick_look.py`,
  `signal_lab/run_definition.py` (`available_date_range`), `signal_lab/sweep_runner.py`.
- `Notebooks/00_DB_Service.py`, `01_Chart_Inspector.py`, `02_Signal_Lab.py`.
- `backtest_lab/db.py`: neue **öffentliche Anzeige-Dublette** `to_display_bp(series)`
  (delegiert an `_fmt_wallclock_series`); `_to_utc_naive()` als BKZ-Garantie.
- `backtest_lab/ui.py`: `_format_created_at` → `db.to_display_bp` (kein Zugriff
  auf modul-private Namen mehr).

**Verifikation (Hausregel: keine UI-/Regressionstests):**
`py_compile` 10/10 OK · `test/test.py` **48 OK / 0 FAIL** ·
`_epoch_sec(t) == int(t.timestamp())` für tz-naive (inkl. DST-Randfälle) ·
`available_date_range() ==` direkte BKZ-MIN/MAX-Abfrage ·
`ui._format_created_at == db.to_display_bp` (naive + tz-aware) ·
Engine/Renderer/Adapter-SHAs unverändert.

### Generationsbindung — Fail-Loud und Rückweg

Unverändertes Prinzip (§72.10), jetzt V017 ⇄ V018: `--mode V017` mit V018-Engine
bricht **vor dem ersten PNG** ab (`EXIT 1`); Rückweg explizit:

```text
python test/tmp_png_aug_sichttest.py --mode V017 ^
    --engine test/_tmp_backup_engine_pre_v018.py
```

Alle arretierten Sätze V01…V017 bleiben damit reproduzierbar
(V017-Protokoll numerisch unverändert).

### Offen

1. **Kein Renderer-Backup `pre_v018`** — der V017-Renderer (`3d6a4788…` /
   92.915 B) wurde in place überschrieben; nur urkundlich (SHA) erhalten.
   Wirkung nicht betroffen: V018-Renderer führt die V017-Literalzweige weiter.
2. `SWEEP_MARKER_P02` (deklariert, nicht referenziert) — unverändert.
3. E-12 (V014-P03) nicht neu arretiert.
4. **Nächster Auftrag unverändert:** H2-Marktanalyse (Phase P10 ab Bar 1021).
