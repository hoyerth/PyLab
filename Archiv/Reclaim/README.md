# Archiv: Reclaim (Kanten-Engine)

**Status: VERWORFEN am 2026-09-14.** Die Reclaim-Idee ist als Trading-Strategie
nicht nutzbar (Entscheid des Anwenders nach Sichtprüfung der Live-Charts).
Dieses Verzeichnis konserviert den vollständigen Bestand revisionssicher in Git.

## Inhalt

| Unterordner | Dateien | Inhalt |
|---|---|---|
| `docs/` | 12 | Spez, Roadmap, Historie, Signal-Loop- und Makro-Persistenz-Design, Live-Lateriz-Befund, Snapshot-Spez, 3 Session-Checkpoints, v0.4-Mentor-Vorlage, `RECLAIM.md` |
| `scripts/` | 2 | `reclaim_live_kernel.py` (Produktivkern), `_tmp_archiviere_reclaim.py` (Archivierungswerkzeug Phase 1) |
| `tests/` | 1096 | Replays, Audit-/Sonden-/Diagnoseskripte, Outputs, Sichtprüfungs-PNGs, `v019_aug_staging/` |
| `artefakte/` | 4 | Beweisstücke der Baseline `aug_p11` (v40r): Engine-Snapshot, Renderer-Snapshot, Trade-Chart, `MANIFEST.md` |

Gesamt: **1116 Dateien, 37.185.413 B (35,46 MB)**.

## Herkunft

| Ursprung | Ziel | Dateien |
|---|---|---|
| `test/archiv/reclaim/` | `tests/` (1:1) | 1118 |
| `test/archiv/reclaim_*.py` | `tests/` | 21 |
| `test/archiv/v019_aug_staging/` | `tests/v019_aug_staging/` | 37 |
| `docs/Archiv/reclaim/` + `docs/Archiv/RECLAIM.md` + `docs/Archiv/reclaim_*.md` | `docs/` | 12 |
| `scripts/reclaim_live_kernel.py` | `scripts/` | 1 |
| `test/_tmp_archiviere_reclaim.py` | `scripts/` | 1 |
| `docs/artefakte/aug_p11/` | `artefakte/` | 4 |

Drei Fremdbeigaben aus `test/archiv/v019_aug_staging/` wurden **nicht** übernommen
und liegen weiter unter `test/archiv/`: `H2_PHASENREGIME_ADAPTER_SPEZ.md`,
`phasen_regime_adapter.py`, `SESSION_HANDOFF.md` (Thema H2-Phasenregime / Handoff).

## Manifeste

* `MANIFEST.sha256` — SHA256, Größe, neuer Pfad und Ursprungspfad je übernommener Datei.
* `MANIFEST_ENTFERNT.sha256` — SHA256, Größe und Pfad der **337 entfernten** Dateien
  (80 ältere Sichtprüfungs-PNGs nach der Regel „nur der jeweils letzte Lauf",
  257 Dateien aus `test/trash/`). Damit bleibt jede Entfernung nachweisbar.

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
