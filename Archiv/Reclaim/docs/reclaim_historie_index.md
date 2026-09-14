# Reclaim-Historie — Master-Index (Setup B, SILVER M15)

Status: **AKTIV / NAVIGATIONS-DOKUMENT**
Datum: 2026-09-06
Zweck: Vollständige chronologische Landkarte der Reclaim-Engine-Entwicklung —
vom Lookahead-Code über die kausale Bereinigung und alle Optimierungsstufen bis
zur arretierten Baseline (+297,14R) und den heutigen Null-Befunden.
Dieses Dokument ersetzt keine der referenzierten Quellen — es verweist.

> **Wichtig:** `docs/Archiv/` wird laut Agents.md ignoriert (Archiv-Doktrin).
> Dieser Index ist die Ausnahme-Regel: Er ist der einzige Lese-Einstieg, der die
> Archiv-Dateien mit Zeilennummern referenziert. Kein Rückverweis von Archiv-
> Dateien auf diesen Index.

---

## 1. Die Erzähllinie in 7 Phasen

| Phase | Zeitraum | Ereignis | Edge-Entwicklung | Quelle (Doku, Z.) |
|---|---|---|---|---|
| **0. Lookahead-Ära** | vor 31.08.2026 | Setup B mit finalem Zonen-Screening (Lookahead) | 2026: 125 Sig / 65 % / **+250,80R**; 2025: 84 Sig / 63 % / **+144,14R** | SESSION_HANDOFF Z. 41–42 |
| **1. Kausale Bereinigung** | 31.08.2026 | `find_reclaim_signals` umgebaut: sequenzielle Schleife, laufende Zone nur bis Bar k; L4-Finalize nur post-hoc/Grafik | 2026: 201 Sig / 44 % / **+197,26R** (CD=12); 2025: 210 Sig / 35 % / **+99,88R** (CD=12) — *Edge blieb gut* | SESSION_HANDOFF Z. 37–43 |
| **2. Re-Optimierung (kausal)** | 31.08.2026 | Sweep candles/bounce/crv/cooldown → Optima **robust**; CD 12→8 als Knie-Punkt | CD=8: S1 **+219,14R** / 226 Sig; S2 **+110,79R** / 240 Sig | SESSION_HANDOFF Z. 45–53 |
| **3. Baseline-Verfeinerung** | 01.09.2026 | Kante-SL, Struktur-Regel, 3-Eck+Cap: alle verworfen (nicht OOS-robust); nur CD übernommen | Baseline bleibt kausal | SESSION_HANDOFF Z. 55–127, 184–365 |
| **4. Kantenspeicher-/Makro-Ära** | 02.–03.09.2026 | Q1–Q7, S1-Prototyp, S2-Score, S3-Loop; v0.1→v0.4 (E1–E5, D2-asym, mid 0.075) | v0.2: AUG +28,17R; v0.3: S1+S2 = 277,89R (**verfehlt** 292,14); v0.4-mid: S1+S2 = **293,35R** — *Strang verworfen, Baseline führt* | RECLAIM.md Z. 19–80, 627–673 |
| **5. Arretierung & Weiche** | 03.–04.09.2026 | Baseline v0.4.0 eingefroren (CD=12); RECLAIM.md → `docs/Archiv/` (47b5c89); Weiche zu Makro-Swings/Setup C | **Baseline: S1+S2 = +297,14R** (CD=12); AUG 27 Sig / +24,97R | RECLAIM.md Z. 595–605 |
| **6. Reclaim-Neuzeit (Null-Befunde)** | 06.09.2026 | AVWAP-Roadmap → AVWAP-Pfad-A-Null; Live-Kernel + L1; Lateriz-Befund (Stopp); Snapshot-Spez + Replay | AVWAP AUG +0,78R (PF 1,19); Replay: S1 PF 1,07 / S2 PF 0,45 → **Snapshot-Null offen** | docs/ im Root, siehe §2 |

---

## 2. Dokumenten-Verzeichnis (vollständig)

### 2.1 Aktive Reclaim-Dokus (docs/-Root, getrackt)

| Datei | Commit | Inhalt |
|---|---|---|
| `docs/reclaim_avwap_roadmap.md` | `691bf56` | AVWAP-Reclaim-Schatten-Spezifikation (F1–F5, K1–K5); CD=12-Benchmark-Tabelle korrigiert (CD=8-Irrtum als S3-Strang-Fußnote) |
| `docs/reclaim_live_lateriz_befund.md` | `b6bcfc6` | Null-Live-Befund: Rechtsrand-Lateriz (0 frische Signale; min. Lag 2, Median 46,5 Bars); Pfad-A-Stopp des Live-Runners |
| `docs/reclaim_snapshot_spez.md` | `dc1e2b0` | Snapshot-Spezifikation Pfad B (Post-Phase-Kanten, N_MAX=192, Cooldown 12, Gate S1/S2 je PF ≥ 1,30) |

### 2.2 Archiv-Dokus (docs/Archiv/, getrackt — eingefroren, nicht gepflegt)

| Datei | Umfang | Inhalt / Zeilennavigator |
|---|---|---|
| `docs/Archiv/RECLAIM.md` | 119 KB / 1114 Z. | **Haupt-Konzeptdoku v0.1–v0.4** (Kantenspeicher/Confluence/Signal-Loop). Session-State Z. 17–80; Baseline-Referenztabelle Z. 595–605; Update-Log Z. 627–673; P5-Befund Z. 677–692; Akzeptanzfälle Z. 607–616 |
| `docs/Archiv/reclaim_signal_loop_design.md` | 46 KB / 787 Z. | Signal-Loop-Design v0.1→v0.4.x: E1–E5, Tier-1/2, Penetrations-Gate, D2-asym-Cooldown; Versions-Tabelle Z. 779–787; Lookahead-Audit Z. 594 |
| `docs/Archiv/reclaim_makro_persistenz_design.md` | 22 KB / 416 Z. | Makro-Persistenz/Kanten-Speicher-Design; Lookahead-Regel Z. 174 |
| `docs/Archiv/reclaim_v04_mentor_vorlage.md` | 8 KB / 171 Z. | **Nur lokal** (explizit gitignored, .gitignore Z. 247): v0.4-Mentor-Simulation, P7/P26-stale-Anker-Radius-Analyse |

### 2.3 Historische Protokolle (test/, nur lokal — gitignored)

| Datei | Umfang | Inhalt |
|---|---|---|
| `test/SESSION_HANDOFF.md` | 28 KB / 413 Z. | **Kern der Lookahead-Geschichte** (eingefroren 02.09.): Lookahead-Bereinigung Z. 37–43, Re-Optimierung Z. 45–53, Reihentests (historisch) Z. 162–165, kausale 3-Eck v6+Cap Z. 184–365, Kantenspeicher-Idee Z. 174–183 |
| `test/SESSION_START_2026-09-04.md` | 7 KB / 114 Z. | Bootstrap 04.09.: State-of-Truth-Landkarte (Makro-Swings-Weiche) |

---

## 3. Commit-Linie (chronologisch, Reclaim-relevant)

| Commit | Datum | Inhalt |
|---|---|---|
| `7337bfc` | 01.09. | „Setup B abgeschlossen" — CD=12 + **Lookahead** (finales Zonen-Screening) |
| `9b6b28a` | 02.09. | „Lookahead tests" — kausale CD=8-Version (Bereinigung) |
| `7ef8c39` | 03.09. | „Optimierung Baseline Konzept" — erstellt `docs/RECLAIM.md` |
| `cba2a93` | 03.09. | Härtung v0.4.x: A3-Bounds-Check, B3 st.side-SSoT, Type-Safety |
| `aea6913` | 03.09. | Rename `tmp_phasen_volumen_profil` → `phasen_volumen_profil` |
| `a040599`/`b95d178`/`a2cc7ec`/`3c21faa` | 03.09. | Standard-Artefakte + Referenzlinien; R1_L-Korrektur 62.24→64.24 |
| `47b5c89` | 04.09. | **Tabula Rasa**: `docs/RECLAIM.md` + signal_loop + makro_persistenz → `docs/Archiv/` (R100) |
| `691bf56` | 06.09. | `docs/reclaim_avwap_roadmap.md` |
| `7e76b8f` | 06.09. | AVWAP Pfad A (`scripts/anchored_vwap.py`) + §5.6-Null-Befund |
| `12658a1` | 06.09. | `scripts/reclaim_live_kernel.py` (L1-bitgenau) + L1-Tests |
| `b6bcfc6` | 06.09. | Lateriz-Befund (Pfad A) |
| `dc1e2b0` | 06.09. | Snapshot-Spezifikation (Pfad B) |

---

## 4. Kennzahlen-Referenz (Entwicklung der Edge)

| Stand | Fenster | Sig | WR | Summe R |
|---|---|---|---|---|
| Lookahead | 2026 (Feb–Aug) | 125 | 65 % | +250,80R |
| Lookahead | 2025 (Jan–Nov) | 84 | 63 % | +144,14R |
| **Kausal** | S1 (2026) | 201 | 44 % | **+197,26R** (CD=12) |
| **Kausal** | S2 (2025) | 210 | 35 % | **+99,88R** (CD=12) |
| Kausal + Re-Opt | S1 | 226 | 43 % | +219,14R (CD=8) |
| Kausal + Re-Opt | S2 | 240 | 35 % | +110,79R (CD=8) |
| **Arretierte Baseline v0.4.0** | AUG | 27 | 44 % | **+24,97R** |
| **Arretierte Baseline v0.4.0** | S1+S2 (CD=12) | — | — | **+297,14R** |
| (nicht arretiert) | S1+S2 (CD=8) | — | — | +308,05R |

Quellen: SESSION_HANDOFF Z. 41–53; RECLAIM.md Z. 595–605.
Hinweis: CD = `MIN_SIGNAL_ABSTAND_BARS`. Die arretierte Produktions-Baseline
nutzt **CD=12** (argv-überschreibbar im frozen Skript); CD=8 war der historische
Re-Optimierungs-Default und ist keine arretierte Baseline.

---

## 5. Null-Befunde & offene Punkte (Stand 06.09.2026)

1. **AVWAP Pfad A** (§5.6, Commit `7e76b8f`): AUG 9 Trades +0,78R, PF 1,19 < 1,50 → Null.
2. **Live-Runner Pfad A** (Commit `b6bcfc6`): Rechtsrand-Lateriz → Live-Betrieb gestoppt.
3. **Snapshot Pfad B** (Spez `dc1e2b0`, Schritt-0-Replay ausgeführt, Arretierung **OFFEN**):
   AUG +19,82R (PF 2,08, Referenz) · S1 +7,79R (PF 1,07, **verfehlt**) ·
   S2 −14,95R (PF 0,45, **verfehlt**) → Null-Befund-Doku angefordert, durch
   Recherche-Auftrag pausiert. Replay-Protokoll: `test/stats_reclaim_snapshot_replay.txt`.
4. Backlog: AVWAP Pfad B (U-Sweep-Expansion, §5.4), Setup-C-Crash-Sicherung 2026.

---

## 6. Skript- & Test-Landschaft (Reclaim)

**Getrackt (scripts/):**
- `scripts/phasen_volumen_profil.py` — **Frozen Baseline v0.4.0** (CD=12, byte-identisch, kein `__main__`-Guard)
- `scripts/reclaim_live_kernel.py` — zustandsloser L1-verifizierter Kernel (Commit `12658a1`)
- `scripts/macro_persistence.py` — Tier-2/Kanten-Speicher (eingefroren)
- `scripts/anchored_vwap.py` — AVWAP Pfad A (Setup-C-Anbindung, §5.6)
- `scripts/archiv/phasen_makro_swings.py`, `tmp_phasen_move_m15.py` — archivierte Arbeitskopien

**Nur lokal (test/, gitignored):**
- `test/tmp_reclaim_live_l1.py`, `test/tmp_reclaim_live_frozen_runner.py` — L1 bitgenau (27 Sig/+24,97R)
- `test/tmp_reclaim_snapshot_replay.py` — Schritt-0-Replay-Harness
- `test/stats_reclaim_snapshot_replay.txt` — Replay-Protokoll (AUG/S1/S2)
- `test/SESSION_HANDOFF.md`, `test/SESSION_START_2026-09-04.md` — historische Protokolle
- `test/stats_trades_S1.txt`, `stats_trades_S2.txt` (+ PNG) — Baseline-Artefakte

**Historisch (gelöscht 02.09., dokumentiert in SESSION_HANDOFF Z. 23–28, 198–207):**
`test/archiv/` — `test_kausal_box_reife.py`, `test_sweep_cap.py`, `test_diag_3eck_v6(_chart/_v7_vmove).py`,
`test_diag_box_persistenz.py`, `tmp_diag_sl_kante(_rel).py`, `tmp_diag_struktur_regel.py`,
`tmp_diag_check_0700.py`, `tmp_diag_trade_p7.py`, `tmp_diag_p7p8.py`, `test_diag_volumen_zone.py`,
`tmp_phasen_volumen_profil_v2.py`; ferner (RECLAIM.md-Kontext): `reclaim_edge_store.py`,
`reclaim_s2_score.py`, `reclaim_s3_signals.py`, `reclaim_tol_sweep_diag.py`,
`reclaim_patrick_selectivity.py`, `reclaim_baseline_profil_audit.py`, `reclaim_generation_audit.py`,
`tmp_makro_state_proto.py`, `tmp_makro_3fenster.py`, `tmp_v03_s2_diag.py`, `tmp_v04_sim.py`,
`tmp_v04_d1_sim.py`, `tmp_v04_d2_sim.py`, `tmp_v04_mittelweg.py`, `tmp_p5_drift_ursache.py`.
