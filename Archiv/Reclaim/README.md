# Archiv: Reclaim

**Status: VERWORFEN am 2026-09-14.** Die Reclaim-Idee ist als Trading-Strategie
nicht nutzbar (Entscheid des Anwenders nach Sichtprüfung der Live-Charts).
Dieses Verzeichnis konserviert den vollständigen Bestand revisionssicher in Git.

## Drei Stränge unter einem Namen

| Strang | Was | Fundstelle |
|---|---|---|
| **Setup A — Counter-Engine (Ping-Pong)** | Antizipative Gegenposition am Kontakt mit VAH/VAL in Mean-Reversion-Richtung. Implementierung `scripts/counter_engine_profil.py`; Abgrenzung zu Setup B im Kopf von `docs/counter_engine_experiment.md`. | `tests/setup_a/` |
| **Setup B — Reclaim/Fakeout** (Patrick Nill, P1) | Der Monolith `scripts/phasen_volumen_profil.py` ist **zu 100 % Setup B** (`SETUP B: RECLAIM/FAKEOUT-SIGNALE`, Funktionen `find_reclaim_signals`, Konstanten `MIN_RECLAIM_*`). Kein Setup-A-/Setup-C-Anteil. | `tests/setup_b/` |
| **Kanten-Engine (SE-Harness v0.4 … v022)** | Aufsatz auf die Baseline `aug_p11`; Replays, Sichtprüfungen, Spez, Signal-Loop-Design. | `tests/`, `docs/`, `artefakte/` |

Alle drei Stränge sind verworfene Strategie und liegen hier gemeinsam.

## Inhalt

| Unterordner | Dateien | Inhalt |
|---|---|---|
| `docs/` | 12 | Spez, Roadmap, Historie, Signal-Loop- und Makro-Persistenz-Design, Live-Lateriz-Befund, Snapshot-Spez, 3 Session-Checkpoints, v0.4-Mentor-Vorlage, `RECLAIM.md` |
| `scripts/` | 10 | `reclaim_live_kernel.py` (Produktivkern) und die Archivierungswerkzeuge |
| `tests/` | 1096 | Replays, Audit-/Sonden-/Diagnoseskripte, Outputs, Sichtprüfungs-PNGs |
| `tests/setup_a/` | 55 | Counter-Engine-Ausgaben: Replays AUG/S1/S2, Prüfberichte, Schritte 1–4, F1–F9-Antworten, `stats_counter_*.txt` (lagen irrtümlich in `test/setup_c/`) |
| `tests/v019_aug_staging/` | 39 | Kanten-Engine-v019-Staging inkl. Altstände `phasen_regime_adapter.py`, `SESSION_HANDOFF.md` |
| `tests/setup_b/` | 25 | Setup-B-Diagnostik auf dem Monolithen: Segmentierung (`*_3eck_*`, `*_box_*`), Kanten-SL (`tmp_diag_sl_kante*`), Struktur-Regel, Parameter-Sweeps, Initialphasen-/Anker-Audits. Die neun Generator-Skripte (S1/S2-Monats- und Wirtschaftsauswertung, CSV-Export) wurden am 2026-09-14 nach Weisung entfernt — sie sind in Minuten neu geschrieben. |
| `artefakte/` | 4 | Beweisstücke der Baseline `aug_p11` (v40r): Engine-Snapshot, Renderer-Snapshot, Trade-Chart, `MANIFEST.md` |

## Herkunft

| Ursprung | Ziel | Dateien |
|---|---|---|
| `test/archiv/reclaim/` | `tests/` (1:1) | 1118 |
| `test/archiv/reclaim_*.py` | `tests/` | 21 |
| `test/archiv/v019_aug_staging/` | `tests/v019_aug_staging/` | 37 (+2 Altstände aus Phase 3) |
| `test/archiv/` (Setup-B-Diagnostik) | `tests/setup_b/` | 33 |
| `test/counter_engine/` + `test/setup_c/stats_counter_*.txt` | `tests/setup_a/` | 46 (+7) |
| `docs/Archiv/reclaim/` + `docs/Archiv/RECLAIM.md` + `docs/Archiv/reclaim_*.md` | `docs/` | 12 |
| `scripts/reclaim_live_kernel.py` | `scripts/` | 1 |
| `test/_tmp_archiviere_reclaim.py` | `scripts/` | 1 |
| `docs/artefakte/aug_p11/` | `artefakte/` | 4 |

### Nicht übernommen (bewusst)

* `test/archiv/H2_PHASENREGIME_ADAPTER_SPEZ.md` — **Dublette**, hash-identisch mit
  `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` (Thema H2-Phasenregime).
* `test/archiv/test.py` — Altstand der zentralen Testdatei, am 2026-09-14 gelöscht;
  `test/archiv/` ist damit aufgelöst.

## Nachgelagerte Aufräumung (2026-09-14, Weisung des Anwenders)

`test/silver_regime/` (94 Dateien) war die Ausgabesammlung der Setup-B-/Phasen-
profil-Linie und damit Reclaim-Alt; sie wurde **gelöscht**. Erhalten blieben:

| Datei | neuer Ort | Grund |
|---|---|---|
| 3× `silver_m15_ohlc_*.csv` | `data/` | Rohdaten-Exporte |
| 11× Stufe-5-Regime (`tmp_regime_*`, `tmp_test_regime.py`, `tmp_sanity_klassifikation.py`, `tmp_stufe5_db_scan.py`, `tmp_inspect_freezed.py`, `regime_schwellen_freezed.json`) | `test/setup_c/regime_stufe5/` | Validierung von `scripts/regime_filter.py`; `tmp_regime_validation.py` ist die 1:1-Vorlage der Portfolio-Assemblierung in `scripts/setup_c_profil.py` (Z1097) — gehört zu **Setup C**, nicht zu Reclaim |

Diese Ausnahme ist belegt: `scripts/setup_c_profil.py` (Z130-137) nutzt die
versiegelten `RegimeSchwellen`-Klassen-Defaults und greift **bewusst nicht** auf
`test/regime_schwellen_freezed.json` zu; trotzdem bleibt das Sigel als
Validierungsnachweis der Regimefilter-Stufe 5 erhalten.

## Manifeste

Stand 2026-09-14. Nach Weisung des Anwenders („es wird niemals einen Audit
geben") werden sie **nicht weiter gepflegt** — die unter `tests/setup_b/`
entfernten Generator-Dateien sind darin noch als vorhanden gelistet.

* `MANIFEST.sha256` — SHA256, Größe, neuer Pfad und Ursprungspfad je Datei (1158).
* `MANIFEST_ENTFERNT.sha256` — SHA256, Größe, Pfad und Grund der **338 entfernten**
  Dateien (80 ältere Sichtprüfungs-PNGs nach der Regel „nur der jeweils letzte
  Lauf", 257 Dateien aus `test/trash/`, 1 Dublette).
* `tests/MANIFEST.sha256` — historisches Phase-1-Manifest (1117 Einträge).
* `tests/setup_b/MANIFEST.sha256` — Phase-3-Manifest (33 Einträge).

## Zeilenenden-Schutz

`artefakte/**` ist in `.gitattributes` mit `-text` markiert (vormals
`docs/artefakte/aug_p11/**`). Ohne diese Regel normalisiert Git die Zeilenenden
und zerstört die SHA256-Anker der Beweisstücke.

## Aufräumregel PNG (Weisung 2026-09-14)

> nur den jeweils letzten lauf zu Aug und Mai-Juli, alles ältere kann weg

Umgesetzt als: AUG = höchste Versionsreihe `aug_sichttest_v019_*` (5 Dateien),
Mai/Juni/Juli = `render_{mai,jun,juli}_sichttest.png` (3 Dateien),
letzter erweiterter Lauf = `ext_sichttest_v2_*` (7 Dateien),
plus das Beweisstück `trades_AUG_mC_v40r.png`. Identische Dubletten (u. a. die
v019-Serie aus `v019_aug_staging/`) wurden auf eine Kopie reduziert.

## Entscheidungsgrundlage (Messwerte Juli/August 2026)

* Juli-Fenster 54,751–63,253 USD (8.502 USD); Median-Spanne 5,070 USD
  (8,80 %) gegen Median-Stop 0,276 USD (0,45 %) → CRV ≈ 18:1, Stop liegt im Rauschen.
* 14/21 = 67 % Vollstopps im Juli; über alle 98 Trades 64,3 % Vollstopps.
* Niveau-Entartung: mittlerer Linienabstand 0,0804 USD ≈ Touchband 0,0690 USD
  ≈ Docht-Streuung 0,0630 USD (Median) — die Kanten liegen in der Rauschbreite.
* Abprallquote 20,45 % gegen Null-Modell 17,98 % (p = 0,0000): statistisch
  schwach signifikant, aber **Bruchquote 79,55 %** — die Abweisungsprämisse ist invertiert.
* Ergebnis hängt an Einzelausreißern: Top-1 (+51,67 R) entfernt → +13,35 R,
  Top-2 entfernt → **−2,52 R**, Top-3 entfernt → **−12,67 R**.
* Kein Steuerhebel in den Parametern: `kein_raum` 6/8 tot, K7a/K7b strukturell inert.

## Wiederherstellung

Die entfernten Sichtprüfungs-PNGs sind aus den archivierten Replay-Skripten unter
`tests/` reproduzierbar; die entfernten `test/trash/`-Dateien sind in
`MANIFEST_ENTFERNT.sha256` namentlich und per Hash dokumentiert.
