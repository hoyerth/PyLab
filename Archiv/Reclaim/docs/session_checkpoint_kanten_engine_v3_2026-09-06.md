# Session-Checkpoint: Kanten-Engine V3 (Setup B) — Stand 2026-09-06

> **⚠️ Zeitbasis-Erratum (2026-09-11):** Dieses Dokument verwendet den historisch
> überladenen Begriff „Wanduhr" und teils die `Europe/Berlin`-Projektion (+2 h).
> **Verbindlich ist seit 2026-09-11 `docs/ZEITBASIS_KANON.md`:** Rechenbasis ist
> ausschließlich die **Broker-Kerzen-Zeit (BKZ)** = `time AT TIME ZONE 'UTC'`;
> `Europe/Berlin`/`Europe/Budapest` sind reine Anzeige-Dubletten.
> Abschnitte, die bereits `time AT TIME ZONE 'UTC'` nutzen, sind
> kanonkonform; Zeitangaben aus der alten Berlin-Projektion sind um
> −2 h gegen die BKZ verschoben.


> Fortsetzung morgen. Verbindliche Regeln: Agents.md (Kern-Prinzipien §1, §3, §4;
> Prämisse: Entscheidungen/Annahmen als Textblock, KEINE UI-/Regressionstests;
> Tests nur in `test/`; Commit-Signatur mit Continue-Co-Author).
> Wanduhr-Invariante: DB-Zeit via `time AT TIME ZONE 'UTC'`, tz-naiv.

---

## 1. Unmittelbarer Anknüpfungspunkt (MORGEN ZUERST)

**3 offene V3-Design-Entscheidungen — vom User noch UNBEANTWORTET** (letzte
Nachricht der Session stellte diese Fragen an den User):

- **F1 — Doppel-Pivot:** Soll V3 eine Umkehrbar (H==L gleichzeitig, z. B.
  Bar 386 am 14.08. 04:30: low 63.663 tiefste + high 64.077 höchste der
  Umgebung) **beidseitig** als Touch registrieren — d. h. die P1-Regel
  „H gewinnt bei H==L" (Harness Z. 408) für V3 aufheben? → würde
  LOWER-MAIN 63.67 von 6/7 auf exakt 7/7 bringen.
- **F2 — Touch-Band-Semantik:** Optionen (a) Docht muss Linie erreichen/
  kreuzen, kleine Toleranz ±0,05; (b) symmetrisches ±0,15-Band (Status quo →
  LOWER-MINOR 64.20 = 7 statt 4, weil 130/162/368 mit Distanz 0,10–0,13
  oberhalb mitzählen); (c) asymmetrisch nach Marktseite. Users Soll-Zählung
  (Minor 4, Main 7) braucht seine Regel.
- **F3 — Re-Trigger-Semantik:** Nach einem V3-Trade an derselben Kante:
  sofort feuern (kein Cooldown, V3-E) vs. nur nach neuem bestätigten Touch
  vs. Mindestabstand (z. B. 12 Bars)? **Real aufgetreten:** UPPER 66.46
  feuert 4 SHORTs, davon 530/531 und 564/565 in aufeinanderfolgenden Bars.

---

## 2. Soll-Referenz (User-Vorlage, „Basic-Kanten", maßgeblich)

| Kante | Seite | Zeitraum | Level | Soll-Touches |
|---|---|---|---|---|
| Upper | OBEN | 11.08. 03:45 – 18.08. 03:00 | 66.46 | 5 |
| Lower-Main | UNTEN | 10.08. 07:30 – 18.08. 17:30 | 63.67 | 7 |
| Lower-Minor | UNTEN | 11.08. 08:30 – 14.08. 02:30 | 64.20 | 4 |

Menschliche Zählung (Pivot-Extrema im ±0,15-Band): Upper 5 = 107/237/249/
529/536; Main 7 = 30/52/57/60/63/380/386; Minor 4 = 126/316/320/361.
Prototyp-Box 10.08.–18.08. = Bars 0–551 (AUG-Fenster 08-10…08-28, 1288 Bars).
**Im ersten Prototyp-Box wurde kein einziger Vorlage-Trade von A/B getroffen
und die Kanten nicht korrekt gesetzt — das war die Kernkritik des Users an der
akademischen Matrix-Auswertung.**

---

## 3. Arretierte Audit-Befunde (in §7.1 verankert)

**Ebene 1 — Geometrie:** `basis_preis` im Harness schreib-only (nur Z. 202/533/
892 gesetzt, nie gelesen). Referenz war immer mutierend: VWAP-Drift (Modus A,
Z. 442/444/523), Ratchet + `_b_ratchet_erlaubt` (Modus B, Z. 954/956/935),
2-Body-Bruch gegen `_ref_preis` (Z. 564–569). → Kante konnte nie verharren.

**Ebene 2 — Trigger:** 96/97 bestätigte AUG-Reclaims scheiterten an
`spread_zu_eng` (Z. 742); 12-Bar-Cooldown (Z. 774) sperrte Mehrfach-Reclaims
(Bars 237 vs. 249); Gegenkante musste handelbare Typ-B sein (Z. 734); TP1 = POC/
Balance der Einstiegsseite dysfunktional (Z. 750/1133); Reaktivierungs-Lücke
(Z. 516–524): SCHLAFEND nur durch Pivot im Band der gedrifteten Balance.

---

## 4. V3-Konzept (§7.1, committed)

- **Commit 37a66b4**: `docs(reclaim-kanten-engine): §7.1 V3-Konzept ...`
  (153 Insertions; Spez jetzt 586 Zeilen, §7.1 = Z. 346–500).
- Vorherige Commits: `f75f6d0` (V2-Spez), `c66457b` (V1-Spez), `b197011`,
  `dc1e2b0`, `b6bcfc6`.
- Kern: statische Kante am **fixen `basis_preis`** (AKTIV/SCHLAFEND, kein
  Zeitverfall, Reaktivierung per Docht-Touch); Einstieg Typ B (≥ 3 Touches,
  in_bar primär, next_bar sekundär); Kursziel Typ A (≥ 2 Touches, auch
  SCHLAFEND, Distanz ≥ 1,5 %); **Zwei-Stufen-TP 50/50** (TP1 = nächste
  Gegenkante, TP2 = dahinter); **struktureller SL = Sweep-Extremum + 0,05 USD**;
  entfallene Gates: spread_zu_eng (ersetzt durch statische Distanz-Prüfung),
  Gegenkanten-Handelbarkeit, 12-Bar-Cooldown, poc_seite/crv.
- Datenverträge `StatischeKanteV3` + `ZweiStufenTradePlan` (py_compile-OK).
- Offene Restpunkte in §7.1: Zeitverfall-Entfall vs. H3-Scan, Re-Trigger, A/B-
  Katalog (Gegenkante ≥2/≥3, Split 50/50 vs. 25/75, SL-Puffer fest/kfg.).

---

## 5. V3-Soll-Kanten-Audit-Ergebnisse (Skript in `test/`)

Skript: `test/tmp_v3_soll_kanten_audit.py` (rein lesend, parametrisierbar).
Parameter: TOUCH_BAND 0.15, MIN_BAR_ABSTAND 3, SL_BUFFER 0.05, TP_MINDIST 1.5 %.
Annahmen: Kursziel-Universum = die 3 Soll-Ebenen; keine Cooldown-/Spread-Gates.

| Soll-Kante | Soll | V3-Ist | Befund |
|---|---|---|---|
| UPPER 66.46 | 5 | **5** ✓ | exakt 107/237/249/529/536 |
| LOWER-MAIN 63.67 | 7 | **6** | 386 fehlt = Doppel-Pivot H==L (P1-Regel verschluckt) |
| LOWER-MINOR 64.20 | 4 | **7** | +130/162/368 (weiche Kontakte 0,10–0,13 oberhalb) |

**9 V3-In-Bar-Signale** (6 in Box), R-Angaben mit strukturellem SL:
- UPPER: SHORT bar 530 (E 66.324, TP1 64.20 +8,2R / TP2 63.67 +10,3R), 531,
  564, 565 — je in Folge-Bars (Re-Trigger-Problem!)
- LOWER-MAIN: LONG bar 386 (E 64.002, TP1 66.46 +6,3R), 398, 622
- LOWER-MINOR: LONG bar 361 (E 64.390, TP1 66.46 +8,6R), 378

**Kernaussage:** V3 trifft die 66.46-Decke exakt; die 63.67-Stütze braucht die
Doppel-Pivot-Korrektur (F1); die Minor-Touch-Zählung braucht die Band-Definition
(F2); Re-Trigger braucht eine Regel (F3).

---

## 6. Dateien-Übersicht (Workspace-Status)

- `docs/reclaim_kanten_engine_spez.md` — Führungsdokument (V1/V2 arretiert,
  §7.1 V3-Entwurf, §8 Gate; getrackt)
- `test/tmp_kanten_engine_replay.py` (1976 Z.) — Harness mit A/B-Schalter
  (Modus A = V1, Modus B = V2); Modus C (V3) ist **noch NICHT gebaut** und soll
  eigenständig/getrennt von A/B-Altlasten entstehen
- `test/tmp_v3_soll_kanten_audit.py` — V3-Soll-Kanten-Audit (rein lesend)
- `test/tmp_kanten_engine_basickanten_abgleich.py` — Soll/Ist-Abgleich A/B
- `test/tmp_kanten_engine_b_smoke.py` — AUG-Smoke-Diagnose B
- `test/tmp_kanten_engine_aug_katalog.py` — Kanten-Katalog A+B in Report-TXT
- `test/stats_kanten_engine_replay.txt` — Log/Report (A-Referenz-Backup:
  `stats_kanten_engine_replay_A_referenz.txt`)
- **Wichtig:** `test/` ist KOMPLETT gitignored (`.gitignore:63`) — nur
  `docs/`-Arretierungen werden committet. Die Harness-Datei ist NICHT im Git.
- Git-Status zuletzt: `37a66b4` (V3-Konzept), working tree nur
  `M docs/...` (V3-Audit-Erkenntnisse noch NICHT eingearbeitet) + `?? reports/`
- Modus-A-Referenz-Matrix (§8.3, Regression 8/8 identisch): S1 mt1 −15,73R/PF
  0,44 … mt60 +37,49R/PF 1,13; S2 mt1 +0,22R/PF 1,01 … mt60 +1,28R/PF 1,01;
  AUG mt60 19 Sig +13,39R/PF 2,29. Modus-B-Matrix: 0/8 Zellen S1/S2 je Satz
  (4 Sätze R{0,05/0,10/0,15}×S{1,5/2,0}) — **Null-Befund V2, nicht arretiert**
  (User-Kritik: Matrix-Auswertung war verfrüht/akademisch, Ziel verfehlt).

---

## 7. Sonstige Session-Fakten (Kontext)

- Baseline `scripts/phasen_volumen_profil.py` v0.4.0 (+297,14R) bleibt
  byte-identisch (Siegel, Commit-Signatur mit Continue).
- Modus-B-Sensitivitätsmatrix lief vollständig durch (kein Früh-Abbruch, wie
  vom User bestätigt); Ergebnis Null-Befund, aber **nicht** als solcher
  arretiert worden — V3-Pfad hat Vorrang.
- Empirische Eckwerte A/B (AUG, Modus B): Body-Reclaims 219, Ratchet-Abgelehnt
  63, Cluster-Geburten 20, Swing-Geburten 31.
