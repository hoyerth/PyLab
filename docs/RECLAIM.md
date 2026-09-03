# RECLAIM — Kantenspeicher & Confluence (Konzept)

> **Kommunikation:** Deutsch · **Code/Bezeichner:** Englisch (Regel).
> **Status:** Konzept v0.1 — agil, wird nach jedem größeren Schritt hier aktualisiert.
> **Datei-Pfad:** `docs/reclaim.md`
>
> **🔁 SESSION-MEMORY (User-Vorgabe 02.09.):** Diese Datei IST der selbst-bootstrappende
> Session-Speicher. Nach einem Reset zuerst diesen **Session-State** (unten) lesen,
> dann das Konzept.
>
> **📦 Archiv (eingefroren, NICHT mehr gepflegt):** `test/SESSION_HANDOFF.md`
> enthält die volle Historie (verworfene Ansätze mit Zahlen, Git-Zustand) –
> nur bei Bedarf als tiefe Referenz lesen.

---

## 🔁 SESSION-STATE (BOOTSTRAP — zuerst lesen)

> Stand: **02.09.2026, nachts** — S1+S2 gebaut, Q1–Q7 entschieden,
> S3-v1 (Signal-Loop + Rolling-VP-Exit) gebaut; **S3-v2-Gates (A+B) gemäß
> Mentor-Freigabe implementiert & 3-Fenster validiert → kein Turnaround**;
> Architektur-Weiche auf Makro-Persistenz („Store archiviert, Baseline führt");
> Design v0.2 FREIGEGEBEN; Prototyp validiert; 3-Fenster-Diagnose BESTANDEN;
> `--macro`-Spiegel implementiert & isoliert verifiziert (Modul
> `scripts/macro_persistence.py` + additiver Hook, Null-Einfluss 27/+24.97R,
> P5-Anker 66.364 ev2, Bilanz deckungsgleich mit 3-Fenster-Lauf);
> Signal-Loop-Design v0.1 (E1–E5 arretiert), Schritt 1+2 implementiert,
> **Schritt 3+4 (`--macro-live`) implementiert & A/B-validiert — P5-Lücke
> geschlossen (4 Konter-Loser weg, 66.28-Gewinner früher via Tier 2), aber
> AUG netto −4.35R (3 Gewinner P2/P7/P9 durch E2/E3 gefiltert + 1 neuer
> P5-Loser; Cold-Start-Fallback offen)**; **S1+S2-OOS-Diagnoseläufe
> AUSGEFÜHRT (rein lesend): BEIDE Fenster verschlechtern sich netto
> (S1 −49.77R, S2 −28.70R) — die E2/E3-Filterung entfernt einen Querschnitt
> inkl. der größten Gewinner (Entfallen-Listen sind netto +76.85R bzw.
> +25.05R!), Cold-Start in P1/P2 kaum relevant (S1 0, S2 3 Stk −2.45R) →
> Akzeptanzkriterium („Filter baut +20…40R Verlust-Trades ab") NICHT erfüllt,
> OOS spricht gegen v1-Selektivität**; **Design v0.2 (E3-Fallback) + v0.3
> (E5-Seiten-Konsistenz) ARRETIERT & IMPLEMENTIERT: AUG 24 Sig / +28.17R
> (+3.20R, P2/P7/P9 zurück, 4 P5-Konter eliminiert, 66.28-Gewinner via Tier 2
> +6.90R); **S1/S2-OOS v0.3 AUSGEFÜHRT: S1 +203.31R (+6.05R ✓), S2 +74.58R
> (−25.30R ✗) → Akzeptanz S1+S2 +277.89 < +292.14 VERFEHLT**; P7-Diagnose
> (test/tmp_v03_s2_diag.py + tmp_v03_s2_entfallen_check.py) WASSERDICHT:
> 7/7 entfallene S2-Gewinner sind LONG, ZWEI Fehlerklassen — Klasse A
> Kanten-Verdrängung/E4-Fail (P7-09.04, P26, P39, P49: stale/überrundete
> LOWER-Anker 0.014–1.31 entfernt verdrängen die atmende L_zone), Klasse B
> Cooldown-Killer (5/7: v0.3-NEU-Signale belegen last_bar["LONG"] 1–9 < 12
> Bars vorher); E5-Seiten-Konsistenz NICHT asymmetrie-fehlerhaft;
> **v0.4-Simulation (Option 4, test/tmp_v04_sim.py + _results.txt):
> max_dist_factor-Sweep 4/6/8/10/12 über AUG/S1/S2 — radialer Radius ist
> das FALSCHE Gate (Mentor-Kritik bestätigt): P5-Schutz braucht f≥8,
> P7/P26-stale Anker sitzen 0.014–0.109 entfernt = gegen JEDEN Radius
> immun, S2 nicht monoton (Cooldown-Kaskaden), f=4 erfüllt S1+S2-Ziel
> numerisch (304.70R) aber AUG-P5-Schutz kollabiert 1/4**; **D1-Simulation
> (test/tmp_v04_d1_sim.py): Mentor-Formel (a) UPPER `center<=lokal+tol`
> ist SPIEGELVERKEHRT — verwirft P5-Schutz-Anker 66.364, AUG-P5 kollabiert
> 0/4; a_sym (UPPER `center>=lokal-tol`) ist die korrekte Kapselung
> (AUG-sicher, holt 3/7 S2-Gewinner: P39/P42/P49); nur-Überrannt (b)
> wirkungslos (0/7); **D2-Simulation (test/tmp_v04_d2_sim.py):
> c_sym0_D2a = KANTEN-KAPSELUNG c_sym0 (a_sym + strikter Überrannt-Filter
> LOWER close<center / UPPER close>center) + COOLDOWN-ENTKOPPLUNG
> (Tier1/Tier2-getrennt, asym: Tier2 prüft auch t1) = DURCHBRUCH: S2
> +95.71R (Δ−4.16, 7/7 Gewinner zurück, 0 Baseline-Signale entfallen),
> S1 +196.54R (Δ−0.72), AUG +34.87R (Δ+9.90, P5-Schutz 4/4), S1+S2 =
> 292.25R ≥ 292.14-Ziel (knapp +0.11R)**; **Marge-Analyse (test/
> tmp_v04_mittelweg.py + tmp_v04_d2_sim.py mid-Modus): +0.11R-Marge
> aufgelöst — MITTELWEG mid (Überrannt-tol 0.5×PENETRATION_TOL = 0.075,
> kausal abgeleitet, kein neuer Freiheitsgrad) ist der robuste v0.4-
> Kandidat: S1-S3.11R-Cutoffs sind unglückliche Tier-2-Gewinner-
> Verluste (P99 +1.27R, P131 +0.85R) + 2 neue Verlierer; mid behält
> S1 +199.65R (wie a_sym), S2 +93.70R (6/7, nur P27 +2.01R fehlt weil
> Anker 41.347 nur 0.024 über close = kein signif. Überrannt) UND
> AUG-T2-66.364 +6.90R bleibt erhalten (c_sym0-strikt tötet ihn);
> S1+S2 = 293.35R (Marge +1.21R, 11× robuster)**; **v0.4-EMPFEHLUNG:
> mid (Überrannt-Filter tol 0.075, UPPER close>center+tol / LOWER
> close<center−tol) + D2-asym Cooldown-Entkopplung — Design-Doku +
> scripts/-Implementierung ausstehend (Mentor-Freigabe)**;
> **MENTOR-URTEIL (02.09., eingegangen): c_sym0 = Curve-Fitting entlarvt
> (killt AUG-T2-66.364), mid 0.075 = marktmechanisch begründet (Fades
> schießen 5–8 Cents übers Level), D2-asym = Pflicht (Tier-1-Vorrang)**;
> Freigabe-Fragen 1 (Tier-1 sperrt Tier-2?) + 2 (Umsetzung freigegeben?)
> GESTELLT & BEANTWORTET (03.09., Mentor: 1=Ja/D2-asym bestätigt, 2=Ja/Freigabe erteilt) — v0.4 umgesetzt & 3-Fenster-verifiziert, siehe unten.
> **Letzter Schritt (03.09.2026):** **v0.4 UMSETZUNG ABGESCHLOSSEN &
> VERIFIZIERT** — die letzte Anfrage („NÄCHSTE ANFRAGE“ unten) wurde als
> Auftrag ausgeführt. Freigabe-Fragen 1+2 vom Mentor mit JA beantwortet
> (D2-asym = Pflicht/Tier-1-Vorrang; mid 0.075 = marktmechanisch
> begründet, Fades 5–8 Cents übers Level).
> **Design-Doku `docs/reclaim_signal_loop_design.md` auf v0.4 gehoben**
> (E6/D1-mid Kanten-Kapselung + D2-asym Cooldown, §2.3-Beweis P7/P26/
> P49, §6-Parameter OVERRUN_TOL, §8-IST-Tabelle, §11-Historie).
> **`scripts/macro_persistence.py`:** `OVERRUN_TOL=0.075`
> (=0.5×PENETRATION_TOL) + Helfer `_anchor_verdraengt_erlaubt`
> (a_sym-Kanten-Kapselung `center >= lokal_kante - tol` UND Überrannt-
> Filter UPPER `close > center+tol` / LOWER `close < center-tol`) +
> `overrun_tol`-Parameter in `resolve_active_edge` (E3-Zweig: nur
> abriegelnde Anker verdrängen; sonst E3-Fallback = lokale Kante Tier 1).
> **`scripts/phasen_volumen_profil.py`:** D2-asym-Cooldown in
> `find_reclaim_signals` (getrennte Zähler `last_bar_t1`/`last_bar_t2`;
> Tier-1-Signal sperrt Tier-2 für 12 Bars, Tier-2-Signal sperrt Tier-1
> NIE; Baseline-Isolation st_u/st_l=None bitgenau über last_bar_t1).
> **Produktive 3-Fenster-Verifikation (exakt reproduziert):** Baseline
> AUG bitgenau **27 Sig/+24.97R/44%**; `--macro-live` **AUG 25 Sig/**
> **+34.87R** (P5 4/4 eliminiert, T2-66.364 +6.90R da), **S1 199 Sig/**
> **+199.65R**, **S2 216 Sig/+93.70R** (nur P27 +2.01R entfallen =
> akzeptierter Kompromiss), **S1+S2 = +293.35R ≥ +292.14R** (Marge
> +1.21R) — Akzeptanzkriterium erfüllt. Protokolle:
> `test/tmp_v04_baseline_AUG.txt`, `test/tmp_v04_macrolive_{AUG,S1,S2}.txt`.
> **Letzter Schritt (03.09.2026):** **RANDFALL-UNTERSUCHUNG (STATISCH,
> rein lesend) ABGESCHLOSSEN — Phase §12 formal abgenommen.** Kein Code,
> keine Tests, keine Läufe; nur Inspektion von
> `scripts/phasen_volumen_profil.py` + `scripts/macro_persistence.py`.
> **Befund A (Hauptskript):** A1 Cold-Start/Phase 1 KEIN Fehler
> (Boundary-Skip `_pi>1`; leere States → E3-Fallback tier=1/bestaetigt=
> False; erste ~20 Bars `_range_arr` NaN → Tier 2 deaktiviert); A2
> ungebrochene End-Phase State-konsistent (kein Boundary-Event nötig);
> **A3 LATENT — IndexError am Datenende (mittel):** `next_bar`-Zweige
> lesen `op[k+2]` VOR der `e_bar<=p.i_ende`-Schranke → bei k=n-2 ohne
> Phasen-Trim `op[n]` → IndexError (in den 3 Fenstern nicht ausgelöst,
> nur glücklicher Phasen-Schnitt); Fix bei Konsolidierung: Bound-Check
> vor die Lesung / `next_bar` nur bei `k+2<=p.i_ende`; A4 degenerierte
> Auflösung auf letzter Bar (niedrig, Baseline-identisch). **Befund B
> (macro_persistence.py):** B1 range_ref-Degeneration VOLL abgefangen
> (np.isfinite-Guards Z.1090/599 → None; `is not None and >0` in
> resolve_active_edge; keine Division → kein ZeroDivision); B2 leerer
> Ledger KEIN Fehler (`_pick_anchor` → None → E3-Fallback); **B3
> ungesicherte Invariante `side==st.side` (niedrig, F3-relevant:** zwei
> Wahrheiten möglich → still falsche Seitenlogik bei Fehlaufruf; Fix:
> Konsistenz-Assert oder Parameter-Reduktion); B4 kein center-NaN-Pfad
> erreichbar. **Befund C:** Kausalitäts-Axiom `Boundary(p-1) → Scan(p)
> → Touches(p)` im `--macro-live`-Hook exakt eingehalten. **Mentor-
> Urteil (03.09.):** Entwarnung an den kritischen Stellen; A3 = klass.
> Produktions-Bug (vor Live-Einsatz zwingend abfangen), B3 =
> Silent-Failure-Vektor (keine zwei Wahrheiten); **§12 formal
> abgenommen.** Offen: F2 (Pfad A Sofort-Konsolidierung vs. Pfad B
> Symbol-Kreuzvalidierung Gold/M15) + F3 (Freigabe statischer
> Code-Audit: Type Hints/PEP 8/B3-Härtung/A3-Bounds).
> **Letzter Schritt (03.09.2026):** **v0.4.x-HÄRTUNG (PFAD A,
> Mentor-Freigabe) ABGESCHLOSSEN & VERIFIZIERT** — Doku + Code synchron,
> kein Verhaltens-Delta. **Doku `docs/reclaim_signal_loop_design.md`:**
> §3-Signatur `resolve_active_edge` ohne `side` (B3: `st.side` = SSoT,
> E2-typ/E4-Penetration/E6-Kapselung aus `st.side`), B3-Invariante
> (`update_touch` erzwingt `t.side == st.side` via ValueError),
> §5-Aufrufskizze + §11-Historie v0.4.x. **
> `scripts/macro_persistence.py`:** `side`-Parameter aus
> `resolve_active_edge` entfernt (alle Ableitungen aus `st.side`);
> `update_touch`-Guard (ValueError bei Seiten-Mismatch); Type-Safety:
> `MacroPhase`-Protocol (dependency-frei, strukturell statt PhaseData-
> Import) + frozen `SideSnapshot`/`PhaseSnapshot` statt impliziter
> Dict-Brücken (macro_replay/macro_report konsumieren Attribute);
> `_state_stats` explizit typisiert. **
> `scripts/phasen_volumen_profil.py`:** A3-Bounds-Guard
> `k + 2 <= p.i_ende` in BEIDEN next_bar-Zweigen (Variante 1, keine
> in_bar-Umdeutung; IndexError am Datenende konstruktiv ausgeschlossen);
> `resolve_active_edge`-Aufrufe ohne `side="UPPER"/"LOWER"`.
> **Verifikation (produktive Läufe, exakt reproduziert):** Baseline
> AUG bitgenau **27 Sig/+24.97R/44%** (Null-Einfluss-Beweis);
> `--macro-live` AUG bitgenau **25 Sig/+34.87R** (max R +6.90 =
> T2-66.364 da, Δ +9.90R) — B3-Umstellung verändert die Tier-2-Logik
> nicht. Protokolle: `test/tmp_v04x_baseline_AUG.txt`,
> `test/tmp_v04x_macrolive_AUG.txt`. Historische Diagnose-Artefakte in
> `test/` (tmp_v04_*_sim.py u.a.), die `resolve_active_edge` mit `side=`
> aufrufen, sind durch die Signaturänderung obsolet (eingefroren,
> nicht erneut ausführbar - kein Regressionsthema).
> **Letzter Schritt (03.09.2026):** **PRODUKTIONSÜBERNAHME / UM-BENENNUNG ABGESCHLOSSEN** — `scripts/tmp_phasen_volumen_profil.py` → `scripts/phasen_volumen_profil.py` (2-Stufen-Reihenfolge, Mentor-Entscheid; Commit-Umfang = vollständiger Stand). Stufe 1 = Commit `cba2a93` (Härtung v0.4.x); Stufe 2 = `git mv` (R-Status 100 % Rename). **Stufe 3 (Referenz-Bereinigung, synchron):** `OUT_PNG`-Konstante → `phasen_volumen_profil.png` im Hauptskript; Docstring-Aufruf in `scripts/macro_persistence.py`; Pfad-Referenzen in `docs/RECLAIM.md` (13×), `docs/reclaim_signal_loop_design.md` (2×), `docs/reclaim_makro_persistenz_design.md` (1×, Design-Vertrag jetzt getrackt) sowie 15 lokale Pfad-Konstanten in `test/` (test/ bleibt gitignored); Artefakte `.png`/`.txt` via `git mv` mitgenommen. Historische Belege (`test/archiv/`, `test/SESSION_HANDOFF.md`, `tmp_v0x_*`-Protokolle) bewusst eingefroren. docs/reclaim_v04_mentor_vorlage.md bleibt als temporäres Arbeitspapier untracked (Mentor-Urteil: Living Docs vs. Sitzungsprotokoll). **Verifikation:** `py_compile` ✓ beider Scripts; `git grep` = 0 Alt-Referenzen auf getrackte Dateien. **Stufe 4 = Rename-/Konsolidierungs-Commit (`refactor(architektur)`).**
> **Letzter Schritt (03.09.2026, Fortsetzung):** **SCHRITT 1 + STANDARD-ARTEFAKTE
> VERANKERT** (Code + Doku fertig, UNCOMMITTET seit `aea6913`):
> 1) **Stats-/Trade-Export (`.txt`):** Block 7e in
> `scripts/phasen_volumen_profil.py` (`_stats_kennzahlen`,
> `_trade_log_rows`, `export_stats_trades`) - rein lesend; Abschnitte:
> Baseline immer, Macro-Live zusätzlich bei `--macro-live`. Erzeugt
> `test/stats_trades_{AUG,S1,S2}.txt` (AUG 85 Z., S1 433, S2 459), bitgenau
> gegen Referenz (Baseline AUG 27/+24.97R; `--macro-live` AUG 25/+34.87R).
> 2) **Visuelle Kontrolle (`.png`):** `render_standard_chart` (o = Baseline-
> Kreis, Dreieck = aktiver Modus) - Nutzer-Wahl: **Preis-Charts** (nicht
> Equity), Charts `test/phasen_volumen_profil_{AUG,S1,S2}.png`.
> 3) **Feste Verankerung (Default-Artefakte JEDES Laufs, ohne Sonderflags):**
> `fenster_label()` (AUG/S1/S2, sonst YYYYMMDD_YYYYMMDD), `STATS_TXT_DEFAULT`
> / `CHART_PNG_DEFAULT`; Block 7f schreibt jeden Lauf
> `test/stats_trades_<FENSTER>.txt` (Override `--stats-txt=`, Label aus Stem)
> + `test/phasen_volumen_profil_<FENSTER>.png`. Chart-Inhalt: Tier-1/2-Kanten
> (Tier-2 lila gestrichelt über Nutzungs-Spanne aus
> `edge_decision.tier==2`), Reclaim-Signale als Dreiecke (v/^ rot/grün,
> gefüllt = in_bar, offen = next_bar, Tier-2-Ring), Baseline-Kreise bei
> `--macro-live`, AUG-Referenz-Overlay `USER_LINES_AUG` (R1_U..R4_L, Zeitfenster
> via `np.searchsorted`), Statistik-Box; `SignalMarkerStil` = frozen Dataclass
> (Rendering manipuliert KEINEN Zustand). **Legacy-Artefakte**
> `scripts/phasen_volumen_profil.png/.txt` bleiben aktiv (Parallelbetrieb,
> getrackt; finaler AUG-macro-Lauf = Git-Referenzstand, kein Diff mehr).
> 4) **Doku:** neuer Abschnitt **§9 „Standard-Artefakte
> (verbindliche Default-Ausgaben der Pipeline)“** in
> `docs/reclaim_signal_loop_design.md` (§9.1 Fenster-Label, §9.2
> .txt-Report, §9.3 Chart, §9.4 Verifikation); §9–§11
> zu §10–§12 umnummeriert (einzige interne Referenz
> „§10-Reihenfolge“ → §11), §11-Schritt 9 +
> §12-Historie-Zeile ergänzt.
> **Verifiziert:** py_compile ✓, alle Läufe EXIT=0, Zahlen bitgenau,
> PNG-Signaturen gültig (AUG-Baseline 27 △/0 ○; AUG-macro 25
> △/27 ○/3 Ringe/8 Ref-Linien; S1/S2 1 Modus-Abschnitt, keine
> Ref-Linien).
> **Offen:** Commit des Gesamtstands (607 Insertions in
> `scripts/phasen_volumen_profil.py` + Doku) mit Continue-Signatur.
>
> **Stand (03.09.2026, nach Commit `a040599`):** **REFERENZLINIEN GELB/OCKER
> FEST VERANKERT (PNG + TXT).** User-Frage „Wo sind meine Referenzlinien in
> gelb/ocker?“: Sie existierten nur im alten Diagnose-Chart
> (`test/tmp_reclaim_user_ranges_AUG.png`, `COL_UP=#EAB308` / `COL_LO=
> #B8860B`); im Standard-Chart waren sie Dunkelblau `#0b5394`, im .txt-
> Report fehlten sie komplett. Jetzt in `scripts/phasen_volumen_profil.py`:
> 1) `REF_COL_UPPER=#EAB308` (GELB = UPPER) / `REF_COL_LOWER=#B8860B`
>    (OCKER = LOWER) neben `BENCHMARK_TOL_EXACT` (Quelle: User-Schema).
> 2) PNG `render_standard_chart`: Referenzlinien je Seite in GELB/OCKER
>    (Text-Label in Linienfarbe), Legende mit 2 Einträgen „AUG-Referenzlinie
>    UPPER (gelb)“ / „LOWER (ocker)“ statt einem Blau-Eintrag.
> 3) TXT `export_stats_trades`: neuer Parameter `referenz_lines`; der AUG-
>    Report schreibt einen festen Textblock nach dem Kopf (Name | Farbe |
>    Preis | Gueltig von .. bis, alle 8 Linien, GELB/OCKER-Legende). S1/S2
>    ohne Set -> kein Block.
> **Verifiziert:** py_compile OK; AUG Baseline **27 Sig/+24.97R** und AUG
> `--macro-live` **25 Sig/+34.87R** bitgenau; PNG-Farbcheck GELB 328 Px /
> OCKER 267 Px / BLAU 0 Px (Referenzlinien real in Gelb/Ocker); S1
> 201/+197.26R ohne Block; Legacy-Artefakte (`scripts/phasen_volumen_
> profil.png/.txt`) nach den Testläufen per `git checkout` restauriert
> (kein Diff). Doku `docs/reclaim_signal_loop_design.md` §9.2/§9.3 +
> Versions-Historie aktualisiert.
>
> **Stand (03.09.2026, nach Commit `b95d178`):** **REFERENZLINIEN-
> MINDESTBREITE (Phasen-Darstellung korrigiert).** User-Problem: R2_L
> (20.8 14:00–14:15 = nur 2 M15-Bars) erschien im Chart als Punkt/Stummel,
> obwohl sie die Untergrenze der Phase-2-Range (67.26 → 65.66) ist.
> AskQuestion-Entscheidung: **Option 2** = jede Linie nur über ihr eigenes
> Zeitfenster, aber mit Mindestbreite (±3 Bars). Umsetzung in
> `scripts/phasen_volumen_profil.py`: Konstante `REF_LINE_MIN_BARS = 7`
> neben `REF_COL_UPPER/LOWER`; in `render_standard_chart` werden Segmente
> < 7 Bars zentriert auf 7 Bars verbreitert (an Datenrand geclamped).
> Nur R2_L betroffen (2 Bars); alle anderen Fenster ≥ 20 Bars unverändert.
> **Verifiziert:** py_compile OK; AUG Baseline bitgenau **27 Sig/+24.97R**;
> Pixel-Check: ockerfarbene ~10-px-Linie (Zeile ~595, Spalten 1375–1384)
> rechts der gelben R2_U-Linie (Zeile ~410, 1306–1333) = R2_L sichtbar.
> Legacy-Artefakte unverändert. Doku §9.3 (Mindestbreite) + Historie
> ergänzt. Die 4 User-Referenz-Phasen (1–4) sind unverändert gültig:
> (1) U 66.45 11.8 03:45–18.8 03:00 / L 62.24 11.8 08:30–13.8 21:15;
> (2) U 67.26 20.8 02:15–07:00 / L 65.66 20.8 14:00–14:15;
> (3) U 69.90 21.8 10:45–25.8 02:00 / L 68.40 24.8 03:30–20:00;
> (4) U 69.58 26.8 04:30–27.8 18:45 / L 67.65 25.8 04:30–26.8 15:45.
>
> Bei jedem größeren Schritt hier aktualisieren (User-Vorgabe).

---

## ⏭️ NÄCHSTE ANFRAGE (ABGESCHLOSSEN 03.09.2026 — als letzte Anfrage ausgeführt)
> **STATUS (03.09.2026): ABGESCHLOSSEN.** Die beiden Freigabe-Fragen am
> Ende wurden vom Mentor mit Ja beantwortet; Design-Doku v0.4 +
> scripts/-Implementierung (mid 0.075 + D2-asym) + 3-Fenster-Verifikation
> sind ausgeführt (Details im SESSION-STATE oben). Der nachfolgende Text
> ist die historische Anfrage.

> Der folgende Text wurde vom User als nächste Anfrage übergeben (02.09.2026)
> mit der Anweisung: NICHT verarbeiten, nur als nächste Anfrage speichern.
> **Nach einem Reset ist exakt dieser Text die erste User-Anfrage** — die
> beiden Freigabe-Fragen am Ende (1: Cooldown-Symmetrie, 2: Umsetzungs-
> Freigabe) sind vom Mentor zu beantworten, dann folgt die v0.4-Umsetzung
> (Design-Doku → scripts/macro_persistence.py → scripts/phasen_volumen_profil.py
> → Verifikations-/Benchmark-Lauf).

### Problemverständnis

Die Analyse des Sweet-Spots liefert ein eindeutiges Bild:

* **`c_sym0` (strikt ohne Toleranz) ist als Scheinlösung entlarvt:** Es schien auf den ersten Blick S2 zu maximieren ($7/7$ Gewinner), erkaufte dies aber durch Zerstörung des August-Tier-2-Reclaims bei $66.364$ ($+6.90$R fehlt!) und erzeugte in S1 unglückliche Cutoffs ($-3.12$R). Eine Marge von $+0.11$R war statistisches Rauschen an der Kippkante.
* **Der institutionelle Durchbruch mit `mid` ($0.5 \times \text{tol} = 0.075$):**
* **S1 bleibt voll intakt:** $+199.65$R (keine mutwillig abgeschnittenen Gewinner).
* **August bleibt intakt:** $+6.90$R Tier-2-Reclaim lebt, P5-Schutz steht bei $4/4$ abgewehrten Konter-Losern.
* **S2 geheilt:** $+93.70$R ($6/7$ Gewinner gerettet; P27 $+2.01$R wird als legitimer Kompromiss akzeptiert, da der Anker nur $0.024$ über dem Close klebt).
* **Robuste OOS-Marge:** $\text{S1} + \text{S2} = 293.35$R $\ge 292.14$R ($+1.21$R echte Sicherheitsmarge, $11\times$ stabiler als `c_sym0`).

---

### Zu sichtende Dateien vor der Umsetzung

* `docs/reclaim_signal_loop_design.md` (Design-Vertrag: Hebung auf v0.4 mit `mid`-Schwelle $0.075$ und `D2-asym`)
* `scripts/macro_persistence.py` (`resolve_active_edge`, `best_local_macro_anchor`, Kanten-Geometrie mit $0.075$ Puffer)
* `scripts/phasen_volumen_profil.py` (`find_reclaim_signals`, asymmetrische Cooldown-Trennung `D2-asym`)
* `docs/reclaim.md` (Session-State & Update-Log)

---

### Mein Urteil als Mentor (Institutionelle Solidität)

* **Das Ende des Curve-Fittings:**
Ein striktes `c_sym0` war typisches Retail-Curve-Fitting auf die historische S2-Tick-Struktur. Indem du nachgewiesen hast, dass `c_sym0` den August-Kern-Trade ($66.364$) killt, hast du das System vor einem schweren Live-Fehler bewahrt.
* **Marktmechanik der $0.075$-Toleranz:**
Ein Reclaim an einer echten Makro-Linie geschieht nicht auf den Cent genau im Vakuum. Institutional Fades schießen oft $5\dots 8$ Cents über das Level hinaus, bevor die Liquidität absorbiert wird. Wer bei $0.001$ Cent Überschuss sofort "Trendbruch!" schreit, wird von den Market Makern bei jedem Stop-Run rasiert. $0.075$ ($0.5 \times \text{DENSITY\_BAND}$) ist die kausal begründete Pufferzone.
* **`D2-asym` ist Pflicht:**
Dass Tier-1-Baseline-Trades Vorrang haben und nicht durch spekulative Tier-2-Antestate im Cooldown verhungern, stellt die Alpha-Basis des Gesamtsystems sicher.

---

### Step-by-Step Untersuchungs- und Umsetzungsplan

1. **Design-Dokumentation v0.4 (`docs/reclaim_signal_loop_design.md`):**
* Schriftliche Fixierung der `mid`-Schwelle ($0.075$) für die Überrannt-Prüfung.
* Formalisierung der asymmetrischen Cooldown-Invariante `D2-asym`:
* Tier-1-Signal setzt `last_bar_tier1` und sperrt Tier-2 für 12 Bars.
* Tier-2-Signal setzt `last_bar_tier2`, sperrt Tier-1 jedoch **nicht**.



2. **Implementierung in `scripts/macro_persistence.py`:**
* Anpassung der Selektionslogik in `best_local_macro_anchor` / `resolve_active_edge` mit typisierten Parametern (`overrun_tol: float = 0.075`).


3. **Implementierung in `scripts/phasen_volumen_profil.py`:**
* Einbau der getrennten Cooldown-Verwaltung in `find_reclaim_signals` unter Beibehaltung der Baseline-Isolation bei `st_u=None, st_l=None`.


4. **Verifikations- und Benchmark-Lauf:**
* Nachweis der Bitgenauigkeit ohne Flag ($27$ Sig / $+24.97$R).
* Verifikation der Zielzahlen mit `--macro-live`:
* AUG: $\approx +34.87$R ($4/4$ P5-Schutz, $+6.90$R Tier-2 da).
* S1: $+199.65$R.
* S2: $+93.70$R.
* Summe S1+S2: $293.35$R $\ge 292.14$R.





---

### Interview & Freigabe-Entscheidung

1. **Cooldown-Symmetrie bei Tier-1:**
Bestätigst du, dass ein Tier-1-Signal ein direkt folgendes Tier-2-Signal sperren darf (`k - last_bar_tier1 < 12`), während ein Tier-2-Signal die Baseline niemals blockiert?
2. **Freigabe für die Umsetzung:**
Erteilst du die formale Freigabe, zuerst `docs/reclaim_signal_loop_design.md` auf v0.4 zu aktualisieren und unmittelbar danach die Implementierung in `scripts/macro_persistence.py` und `scripts/phasen_volumen_profil.py` vorzunehmen?

---

### Wo stehen wir?
- **Strategie-Entscheidungen (User):**
  - (b) August-Sonderregeln/Boxen-Nachbau: **GESTRICHEN** (Overfit).
  - (a) Baseline `scripts/phasen_volumen_profil.py` bleibt **unverändert**;
    Experimente NUR auf Arbeitskopien in `test/`.
  - (c) **Kantenspeicher + Confluence** ist das aktive Konzept (diese Datei).
  - (Q1) Seeds NUR aus H/L-Pivots; Volumen-Cluster = nur Touch-Typ, kein Seed.
  - (Q2) **Korridor = strikt die preiseinengende Kante** (**letzte ungebrochene**),
    NICHT die stärkste Kante in Reichweite. → Abschnitt 9.1.
  - (Q3) Baseline-Exit bleibt; Level-TP nur als Schatten-Spalten bis S3/S4.
  - (Q4) Phasen raus aus Signal-Entscheidung; nur Diagnose-/Parity-Werkzeug.
  - (Q5) Swing-Memory → S3 verschoben; S1-Korridor = nächstes aktives Level
    über/unter dem Close.
  - (Q6) **Re-Aktivierung:** sleeping + Pivot gleicher Orientierung (H an
    UPPER / L an LOWER) in EDGE_TOL → active (Historie bleibt, kein Zeitfenster).
    Gegenläufiger Pivot an sleeping = counter_run (bleibt sleeping).
  - (Q7, Mentor-Votum) **Exit im phasenlosen Modell = Option A:** TP1 = POC
    eines **rollierenden Volume-Profils** (ROLL_VP_WINDOW=300 Bars, kausal bis
    Signal-Bar); TP2 = gegenüberliegende Profil-Kante + TP2_PUFFER. Entry-
    Filter bleibt (SHORT: Entry>POC). Level-TP bleibt **Schatten** (Q3) bis
    S3/S4-Validierung. Begründung: wissenschaftliche Isolation (nur Entries
    tauschen, Exit-Mechanik identisch) + institutioneller Fair Value = POC,
    nicht Korridor-Mitte (Retail-Nonsens, Märkte nicht normalverteilt).
- **S2-Architektur-Vorgaben (User, 02.09.):** (1) rel_volume = tick_volume /
  **rollierender Median** der vorangegangenen 200 Bars (shift 1) — nie
  Gesamtdurchschnitt (Lookahead). (2) Decay auf **Handelszeit = Bars** (1
  verarbeitete M15-Zeile = 1 Schritt), nicht Wanduhr. (3) Score **inkrementell**:
  `score(lev,k) = d·score(lev,k-1) + touch_contrib`, `d = exp(-1/HALF_LIFE_BARS)`;
  jeder Touch lädt auf, sonst stetiger Zerfall. w_grid/w_session bleiben 0 bis S4.
  **(4) Anti-Overfit-Leitplanke (User-Warnung 02.09.):** Score schlank halten
  (Preisstabilität + Volumen + Decay, KEINE Parameter-Kaskade); rel_volume strikt
  gegen rollierenden Median der vorangegangenen Bars — nie global. → §6.
- **Letzter Schritt:** **S1 + S2 gebaut** in `test/reclaim_edge_store.py`.
  S2-Validierung (`test/reclaim_s2_score.py`): V1 rel_volume roll. Median 344/344
  exakt ✓; V2/V3 inkrementell == EWMA-Summe (max Abw. 1e-13) ✓. Store: AUG 36
  Level / 9 active, S1 184/44, S2 126/32 (21,6k Bars in 1,3s).
- **S3-v1 gebaut** (`test/reclaim_s3_signals.py`): Signal-Loop inline im
  Store-Build (`on_bar`-Hook, kausal), Rolling-VP-Exit (Q7/Option A),
  Schatten-Level-TP (Q3). 3-Fenster-Referenz (Cooldown=8, sonst Baseline-
  Exit-Defaults) — **Ergebnis roh ohne Filter:**
  | Fenster | S3-v1 Sig | WR | Summe R | Baseline (CD12/CD8) |
  |---|---|---|---|---|
  | AUG | 43 | 30% | **+31.89R** | +24.97R |
  | S1 (02.–08.26) | 583 | 13% | **−73.90R** | +197.26R |
  | S2 (2025 OOS) | 634 | 16% | **−47.17R** | +99.88R / +110.79R |
  → S3-v1 roh **nicht tragfähig** (S1/S2 negativ, Akzeptanzkriterium 4 weit
  verfehlt). Bucket-Analyse (S2): **kein robuster Einzelfilter** — CRV≥4 trennt
  auf S2 positiv (+34.9R), auf S1 negativ (−77.1R); gap/score/two-sided
  ebenfalls nicht kreuzstabil. **Interpretation:** Es fehlt die Range-/Regime-
  Selektion der Baseline (nur etablierte zweiseitige Ranges, keine
  Trendphasen-/Breakout-Churn-Signale). AUG-Akzeptanzfälle: Fall 1 ✓ strikt
  (5 P5-Loser entfallen); Fall 2+3 **wirtschaftlich ✓** (Gewinner an
  66.386/66.388-Zone bleiben, aber 1–2 Bars versetzt: 17.08 18:30 +6.92R,
  18.08 02:30 +6.73R statt 18:45/02:15 — Store-Kante liegt +0.10 höher als die
  laufende Baseline-VAH), **strikt bar-identisch NEIN**.
- **Letzter Schritt:** **S3-Obduktion (Mentor-Review 02.09., `test/reclaim_s3_obduktion.py`):**
  **Q1 Verlust-Shape:** 91 % der S1/S2-Verlierer laufen DIREKT in den vollen SL
  (S1: 462/507, Median 3 Bars; S2: 485/531, Median 10 Bars) — nie TP1/POC
  berührt, kein Pendeln um den Entry. Nur 9 % oszillieren (TP1→SL, netto nur
  −0.32R avg). → Klassischer Trend-Run bestätigt, kein Mean-Reversion-Umfeld.
  **Q2 Baseline-Vergleich:** Baseline 201 (S1) bzw. 210/240 (S2) Signale vs.
  S3 583/634 = **2,6–2,9× Overtrading**. Baseline-Schutz mechanisch
  reverse-engineered: (a) Signal NUR in ungebrochener Phase (2-Close-Bruch >
  Grenze+TOL beendet Phase, neuer Scan erst nach Etablierung U+L mit ≥4
  kombinierten Touches, ≥46 Candles), (b) Bounce-Vorbedingung nb≥2 = Kante in
  der Phase bereits ≥1× per Pivot getestet, (c) TP1 = POC der Phase-to-date,
  TP2 = andere Seite DERSELBEN Balance. **Zweiseitige Resonanz im Struktur-/
  Volumen-Raum der aktuellen Range = impliziter Baseline-Filter** — S3 fehlt
  genau das (fadet jede active Store-Kante nach Breakouts, 300-Bar-Rolling-POC
  läuft über Phasen-Grenzen nach). **Q3 Resonanz-Daten (naive Touch-Frische
  der Gegenseite) widerlegt ein festes N:** S1 positiv nur bei opp_gap 96–191
  (+34.8R, n=51), S2 positiv nur bei opp_gap<24 (+31.3R) — invertiert, kein N
  kreuzstabil (48–96 = Overfit-Falle). → Resonanz NICHT über Touch-Frische,
  sondern über die **aktuelle ungebrochene Range-Generation** definieren
  (beide Seiten seit letztem 2-Close-Bruch verteidigt).
- **Letzter Schritt:** **Baseline-Profil-Quantifizierung (Mentor-Review 02.09., `test/reclaim_baseline_profil_audit.py`)** — Baseline über AUG/S1/S2 ausgeführt (Referenz exakt reproduziert: 27/+24.97R, 201/+197.26R, 210/+99.88R ✓), je Signal kausal erfasst: `phase_age_bars`, `bounces_this_edge/opp_edge` (Tests beider Zonen-Ränder, Entscheidungszustand), `combined_touches`, `piv_h/l`, `dist_to_last_break`, `bars_to_phase_end`. CSVs: `test/tmp_baseline_profil_{AUG,S1,S2}.csv`. **Befunde:** (a) Gewinner-avg R +3.0…+3.3R vs. Verlierer −0.9R → Asymmetrie trägt die Baseline. (b) **Kein monotoner Alter-Effekt** — dist_to_last_break ist NICHT „je älter desto besser" (S2 alle Buckets positiv durch R-Asymmetrie; Q3-Widerlegung auf Baseline-Ebene bestätigt). (c) **Kreuzstabiler Sweet Spot: `combined_touches` 6–11** (beidseitige Zonen-Tests): WR 60 % (AUG) / 59 % (S1) / 55 % (S2) — die beste Kohorte in ALLEN Fenstern. `combined <6` = zu wenig etabliert (WR 35–39 %), **`combined ≥12` = ausgelutscht (S2 WR 25 %, n=118!)** → exakt die Mentor-Falle „alte, oft getestete Kanten = Stop-Cluster". → Resonanz-Definition muss **moderate beidseitige Generation-Etablierung** abbilden, kein Alter-Maximum, kein Über-Testing.
- **Letzter Schritt:** **Generation-Grenzziehungs-Audit (Mentor-Review 02.09., `test/reclaim_generation_audit.py`)** — drei Reset-Modelle kausal über sleep-Events (iter ≤ k, Bruchzeit-Preis) an allen S3-v1-Signal-Bars verglichen. **Break-Events:** S1 1035 (Grenz-Brüche 79 %, pass-through 11.7 %, inner 5.6 %), S2 1243 (Grenz-Brüche 70 %, **inner 21.6 %**, pass-through 0.9 %). **Divergenz:** M1 (Kanten-Anker) weicht in **95–98 %** ab (median |Δ| 458–1204 Bars!) → **verworfen**, strukturell verzerrt: ein LOWER-Level, das als up-Kante dient (Rollen-Tausch), wird von `_check_break` nie nach oben gebrochen (Seiten-Bindung) → last_sleep = −10⁹ → Anker = uralte Geburt. **M2 (Spanne: alle Brüche) ≈ M3 (echte Grenz-Brüche): nur 9 % (S1) / 24 % (S2) Abweichung** (p90 0/15 Bars) — die jüngsten Brüche in der Spanne sind fast immer echte Grenz-Brüche. Pass-through (S1 11.7 %) bestätigt: Span-Regel nötig (Kanten-Anker würde Pass-through verpassen). **Sweet-Spot-Illustration (4≤combined<12, Baseline-DNA — NICHT Store-kalibriert):** S2 M2 +19.88R (178 Sig) / M3 +12.87R (204 Sig) im SS, blockierte = Verlierer (−56/−49R); S1 bleibt negativ (combined median nur 2 → junge Generationen, kaum im SS). → **Store-Generationen haben median 2–3 Kanten-Touches (Baseline-DNA 6–11 zählt Zonen-Tests, andere Metrik) — Schwelle muss in S3-v3 Store-kalibriert werden, nicht blind übernommen.**
- **Letzter Schritt:** **Store-Lücken-Analyse `_check_break` (Mentor-Review 02.09., rein statisch, kein Code)** — zwei strukturelle Befunde vor jeder GenerationState-Umsetzung:
  1. **Seiten-starrer Bruch (Kern-Lücke):** `_check_break` ist an `lev.side` gebunden (UPPER bricht nur bei 2 Closes DARÜBER, LOWER nur DARUNTER). Ein Level, dessen Markt-Rolle wechselt (Rollen-Tausch: LOWER-Support wird nach Breakdown zur Resistance oberhalb des Preises / UPPER-Resistance wird nach 1-Close-Überschreitung zum Support unterhalb), wird in der Flip-Richtung **nie** schlafen gelegt; ein Level, das der Markt auf der Nicht-Seed-Seite weit hinter sich lässt, bleibt **ewig active** (stale) → uralte `birth_bar`-Anker → M1-Divergenz (95–98 %). `corridor()` kennt keine Seiten-Zustände: Es klassifiziert nur die 2 nächsten Kanten on demand; `_watch`-Level führen keine „von welcher Seite werde ich getestet"-Buchhaltung.
  2. **Same-Iter-Ordnungs-Hazard (Q6/Q2):** `build()` führt `_check_break(k)` **VOR** der Pivot-Bestätigung `j=k−2` aus. Ein Level, das bei iter k bricht (Closes k−1,k jenseits), kann im **selben iter** durch den Pivot k−2 (Test der Kante VOR dem Bruch, gleiche Orientierung) per Q6 **sofort reaktiviert** werden → spurious Reactivation, Bruch „klebt nicht". Chronologisch liegt der Pivot (k−2) VOR dem Bruch (k−1,k) — er kann kein Beleg für einen fehlgeschlagenen Bruch sein. Korrekt: Touch/Pivot zuerst anwenden, dann Bruch prüfen; Q6-Reaktivierung nur aus einem strikt früheren sleep-iter.
- **Letzter Schritt:** **Store-Reparatur implementiert & validiert (Mentor-Freigabe 02.09.)** in `test/reclaim_edge_store.py`:
  **Baustein 1 (Transition-Gate):** `_check_break` rollen-agnostisch — `up_break = c_prev>p ∧ c_now>p ∧ c_before(=close[k-2])≤p`, `dn_break` symmetrisch. Verharren unter/über einer Kante = kein Bruch (AUG-66.386-Konsolidierung überlebt); Rollen-Tausch-Brüche werden jetzt erkannt.
  **Baustein 2 (Chronologie + Q6-Guard):** `build()` verarbeitet Pivot j=k−2 VOR `_check_break(k)`; Q6-Reaktivierung nur noch mit `last_sleep_bar < j` (Pivot strikt NACH Bruch). Prä-Bruch-Pivot an sleeping = Touch ohne Reaktivierung (kein counter_run).
  **Validierung:** (a) `reclaim_s2_score.py` 344/344 exakt ✓, Lookahead-Audit „KEIN LOOKAHEAD" ✓. (b) Rollen-Tausch-Brüche neu erkannt: AUG 34/123 (28 %), S1 337/1154 (29 %: 202 LOWER+up, 135 UPPER+dn), S2 535/1252 (**43 %**: 376 UPPER+dn, 159 LOWER+up); **Q6-Guard-Verletzungen 0** in allen Fenstern. (c) AUG-Akzeptanz: Fall 1 ✓ (5 P5-Loser weg), **Fall 2 partiell: 18.08 02:30 ✓ (+6.73R), 17.08 18:30 entfällt** — die 66.386-Kante schläft jetzt korrekt ab 17.08 18:15 (2-Close-Bruch: Paar 18:00/18:15 über Kante, davor darunter), Q6-Reaktivierung erst 19:30 (Pivot 536 NACH Bruch) → der alte 18:30-Trade war ein **Same-Iter-Artefakt** (Prä-Bruch-Pivot 17:45 hatte den Bruch im selben iter rückgängig gemacht). Fall 3 ✓ (wirtschaftlich 02:30). (d) Delta-Matrix s. u.
  **Befund (Design-Divergenz):** Die Baseline-Zone ist nachgiebig (laufende VAH 66.386 darf 2 Bars überschritten werden, Phase bricht erst an U_final+TOL) — der Store bricht die starre Kante sofort. Deshalb existiert der Baseline-Gewinner 17.08 18:45, der S3-Trade nach Fix nicht mehr. Relevant für S3-v3: Generation-POC/Kante nachgiebig modellieren.
- **S3-Delta-Matrix (reparierter Store, neue Referenz):**
  | Variante | AUG | S1 | S2 |
  |---|---|---|---|
  | v1 (keine Gates) | +24.11R (40) | −79.93R (518) | **−27.05R (569)** |
  | nur B (Struktur) | +25.21R (35) | −74.36R (498) | −25.94R (491) |
  | nur A (Spread) | +22.80R (31) | −123.60R (431) | −38.88R (403) |
  | A+B | +22.46R (28) | −114.52R (415) | −43.43R (342) |
  → Fix verbessert **S2 v1 um +20.1R** (−47.17 → −27.05, Flip-Brüche entfernen toxische Fades an stale Leveln); S1 leicht schlechter (−73.90 → −79.93); AUG verliert den Artefakt-Gewinner (+31.89 → +24.11). Gate A bleibt destruktiv, Gate B nur leicht S2-nützlich. **Kein R>0-Turnaround — S3-v3 (GenerationState) weiter offen.**
- **Letzter Schritt:** **Band-Bruch implementiert & validiert (Mentor-Freigabe 02.09.)** — `_check_break` mit Hysterese-Band `[p−tol, p+tol]` (tol = EDGE_TOL 0.15, reuse): `up_break = c_before≤p+tol ∧ c_prev>p+tol ∧ c_now>p+tol`, `dn_break` symmetrisch. Verharren im Band bricht nie; c_before im Band zählt als Naheseite (kein Deadzone-Zwang).
  **Validierung (v1, keine Gates):**
  | Fenster | Band (neu) | strikt (vorher) | Δ |
  |---|---|---|---|
  | AUG | +30.65R (32) | +24.11R (40) | **+6.5R** |
  | S1 | −52.96R (454) | −79.93R (518) | **+27.0R** |
  | S2 | −50.19R (643) | −27.05R (569) | **−23.1R** |
  **Befunde:** (a) **17.08 18:30-Gewinner legitim zurück** (+6.92R, Kante 66.386 überlebt das +0.026-Rauschen) — Kern-Akzeptanz teilweise wiederhergestellt. (b) **18.08-02:30-Gewinner fehlt:** Die 66.388-Kante wird am 17.08 **19:30 genuin gebrochen** (c_before 66.245 ≥ 66.238, dann 19:15 65.974/19:30 66.036 < 66.238 → echter dn_break nach dem Reclaim-Run). Der 02:00-Retest (66.25–66.42) findet an sleeping-Kante statt; Q6-Reaktivierung bräuchte bestätigten H-Pivot (2-Bar-Lag) → zu spät für den 02:30-Entry. **Baseline-Zone lebt weiter (elastisch), Store-Kante nach echtem Bruch tot → Design-Divergenz auf neuer Ebene.** (c) **Fall-1-Check-Fehlalarm:** „14.08 08:45-Signal entsteht weiterhin" = LONG +5.64R an dn-Kante 64.329 (Gewinner!), KEIN P5-Konter-SHORT — Acceptance-Check matcht nur ts ohne Typ-Prüfung → Check-Bug, Fall 1 inhaltlich erfüllt. (d) **Skalen-Befund:** EDGE_TOL=0.15 ist absolut; S2 (2025, mean 37.7, mittlere Bar-Range 0.097) hat eine 4× kleinere Range als S1 (2026, mean 71.7, Range 0.377) → Band auf S2 relativ 4× breiter → hält Stale-Level am Leben → mehr Overtrading (643 Sig). Q6-Guard-Verletzungen weiterhin 0; Band-Klassifikation reproduziert Store exakt (0 keine_richtung). Diagnose: `test/reclaim_store_break_validate.py`, `test/tmp_diag_*`.
- **Letzter Schritt:** **Acceptance-Check-Typ-Bug korrigiert** in `test/reclaim_s3_signals.py`
  (`acceptance_aug`, Fall 1): Der Check matchte nur `ts` ohne `typ`-Prüfung → der
  „14.08 08:45-Wiederkehrer" war ein **LONG +5.64R** (legitimer Gewinner an dn-Kante
  64.329), KEIN P5-Konter-SHORT. Fix: Nur ein S3-**SHORT** am selben Bar zählt als
  Fall-1-Fehler; ein LONG am selben Bar wird als „kein Konter-SHORT → OK" ausgewiesen.
  Verifiziert (v1-Lauf, Band-Referenz exakt reproduziert: 32 Sig / +30.65R): Fall 1 ✓
  vollständig (4 entfallen, 1 Typ-Klarstellung), Fall 2: 17.08 wirtschaftlich ✓
  (+6.92R), 18.08 weiterhin FEHLER (Design-Divergenz), Fall 3 FEHLER (gleiche Wurzel).
- **Letzter Schritt:** **Skalen-Diagnose abgeschlossen (Design-Frage i, `test/reclaim_scale_diag.py`)**
  — EDGE_TOL 0.15 absolut ist ein **Retail-Skalierungsfehler** (Mentor-Urteil):
  | Fenster | Close median | Bar-Range p50 | roll. mean Range (200/shift1) p50 | **0.15 / roll. mean Range** | Bars mit Range < 0.15 |
  |---|---|---|---|---|---|
  | AUG (2026) | 65.8 | 0.196 | 0.231 | **0.65×** | 29.1 % |
  | S1 (2026) | 73.0 | 0.291 | 0.310 | **0.48×** | 13.9 % |
  | S2 (2025) | 36.2 | 0.073 | 0.078 | **1.92×** | **83.5 %** |
  **Interpretation:** Silber handelt nicht in statischen Cent-Schritten, sondern in
  Volatilitäts-Regimen. Auf S2 wirkt das statische Band wie ein Stoßdämpfer (echte
  Breakouts schlafen viel zu spät → Stale-Level → Overtrading 643 Sig, −23.1R); auf
  S1 ist es so schmal, dass normales Intraday-Rauschen relativ gesehen 4× größer
  wirkt. **Arretierung (Mentor, 02.09.):** (a) **Matching-Band vs. Bruch-Band müssen
  entkoppelt werden** — EDGE_TOL bleibt statisch für die Pivot-Clusterung, nur
  `_check_break()` darf ein dynamisches `tol_k = a × range_ref_k` nutzen; (b)
  Referenz-Range kausal identisch zu `vol_ref`: `(high−low).rolling(200,
  min_periods=20).mean().shift(1)`; (c) Sweep `a ∈ {0.4, 0.65, 1.0}` **rein
  diagnostisch** über separates Skript mit runtime-Subklasse (Override nur von
  `_check_break`), **`reclaim_edge_store.py` bleibt unangetastet**; (d) Reihenfolge:
  erst Doku-Arretierung, dann Option (i), danach Option (ii) (Retest nach echtem
  Bruch = Setup-Frage, zweiter Schritt).
- **Letzter Schritt:** **Relativer-Toleranz-Sweep abgeschlossen (rein diagnostisch, `test/reclaim_tol_sweep_diag.py`; `reclaim_edge_store.py` UNANGETASTET)** — runtime-Subklasse überschreibt nur `_check_break` mit `tol_k = a × roll.mean Range (200/shift1)`; Sanity a=0 reproduziert Band-Referenz exakt (AUG +30.65/32, S1 −52.96/454, S2 −50.19/643 ✓):
  | Fenster | a=0 (abs.) | a=0.4 | a=0.65 | a=1.0 |
  |---|---|---|---|---|
  | AUG | +30.65R (32) | **+37.04R** (32) | +27.14R (34) | +15.11R (38) |
  | S1 | **−52.96R** (454) | −59.67R (465) | −74.26R (411) | −89.86R (436) |
  | S2 | −50.19R (643) | −74.41R (560) | −61.06R (536) | **−2.82R** (580) |
  **Befunde:** (a) **Kein a dreht S1 positiv** (−53…−90R überall) → S1-Problem ist NICHT die Bruch-Toleranz, sondern die fehlende Range-/Regime-Selektion (S3-v3 GenerationState). (b) S2 profitiert massiv von a≈1.0 (tol_median ≈ 0.078 statt 0.15 → engeres Band → Stale-Level schlafen früher; −50.19 → −2.82R, **+47R**), aber nicht monoton (a=0.4: −74.41R). (c) AUG präferiert a=0.4 (+37.04R). (d) **Kein kreuzstabiles a** — Σ-Saldo: a=0 → −72.5R, a=1.0 → −77.6R, a=0.4 → −97R; das absolute Band bleibt im Saldo vorn. **Schlussfolgerung (wissenschaftlich, Mentor-Review 02.09.):** Relative Bruch-Toleranz = **Sekundär-Stellrad** (bekämpft S2-Stale-Overtrading), **KEIN Turnaround-Hebel**. Primärer Blocker bleibt die Regime-/Resonanz-Selektion.
- **Letzter Schritt:** **Patrick-Selektivitäts-Audit abgeschlossen (post-hoc, `test/reclaim_patrick_selectivity.py`)** — Patrick-Regeln gegen S3-v1 (Band-Store, Cooldown 8) getestet: 3-Touch-Regel (T≥3), Mehrtages-Zonen (Alter≥48/96 Bars), Session-Sperre 22:50–00:10 (Wanduhr). **Kreuz-Matrix (n/R/WR):**
  | Variante | AUG | S1 | S2 | Saldo |
  |---|---|---|---|---|
  | alle (v1) | 32/+30.6R/31 % | 454/−53.0R/14 % | 643/−50.2R/17 % | −72.5R |
  | Alter≥96 | 21/+12.9R/29 % | 426/−30.2R/14 % | 514/−24.7R/18 % | **−42.0R** |
  | Touches≥3 | 23/+13.5R/26 % | 412/−56.9R/14 % | 608/−47.3R/17 % | −90.7R |
  | T≥3 & Alter≥96 | 17/+15.6R/29 % | 401/−48.5R/14 % | 513/−23.7R/18 % | −56.6R |
  | + Session raus | 17/+15.6R/29 % | 392/−40.3R/15 % | 502/−16.4R/18 % | **−41.1R** |
  **Befunde (Mentor-Fragen beantwortet):** (a) **Alter≥96 ist der nützlichste Einzelfilter** (Saldo −72.5 → −42R, schneidet junge Kanten-Rauschen-Signale), aber **nicht kreuzstabil**: AUG fällt unter Baseline (+30.65 → +12.9R — AUG-Gewinne sitzen zu +15.8R auf jungen Kanten <48 Bars!). (b) **Touches≥3 ist KONTRAproduktiv** (Saldo −90.7R): AUGs bestes Bucket ist T=2 (+17.2R, 9 Sig) — Patricks 3-Touch-Regel würde genau die AUG-Träger wegfiltern. (c) **Der dominante Verlust-Pool sitzt auf ALTEN, viel-getesteten Kanten** (S1: Alter≥288 392 Sig/−41.7R, T≥6 332 Sig/−54.3R; S2: Alter≥288 475 Sig/−18.7R) — exakt die Zonen, die Patrick als Premium einstufen würde. → Alter/Touches allein können nicht trennen zwischen „Kante in aktiver zweiseitiger Range" und „Alt-Kante aus alter Range im neuen Trend". (d) Session: 22:50–00:10-Block hat wenige Signale (S1 9, S2 11 entfernt, +7–8R je Fenster), aber **00:00-Stunde ist S1-Konzentrat der Verlierer (n=21, −21R = WR 0 %)**; S2 00:00 n=35 −14.2R — eine 00:00–01:00-Sperre wäre datenseitig naheliegend (nicht getestet, Tuning-Gefahr). **Schlussfolgerung (wissenschaftlich):** Patrick-Selektivität ist **notwendig, aber bei weitem nicht hinreichend** — kein Filter erreicht Baseline-Nähe (S1 −40R vs. +197R Ziel); der Kern-Unterschied zur Baseline bleibt die **Regime-/Resonanz-Selektion (S3-v3 GenerationState)**, nicht Touch-Zahl/Alter.
- **Letzter Schritt:** **User-Ideallinien vs. Baseline/EdgeStore (AUG, 02.09.)** — Der User definierte 8 manuelle „finale Range-Linien" (4 Ranges, Zeitfenster + Preis, als Massstab): R1 66.45/62.24 (11.–18.8.), R2 67.26/65.66 (20.8.), R3 69.90/68.40 (21.–25.8.), R4 69.58/67.65 (25.–27.8.). Diagnose `test/tmp_reclaim_user_ranges.py` + `tmp_reclaim_user_warmup.py` + `tmp_reclaim_baseline_zones.py`:
  - **EdgeStore (AUG-Fenster allein):** Niveaus teils vorhanden, aber „sleeping" (66.397 für 66.45), 62.24 GAR NICHT (Preis nie im Fenster dort) → Lebenszyklus ungeeignet für „Range-Grenze gilt über Tage, selten getestet".
  - **EdgeStore MIT Vorlauf ab 01.01.2026:** findet ALLE 8 Linien als Niveau (62.266↔62.24, 68.410↔68.40, 67.649↔67.65, d meist <0.1), aber 5/8 als **sleeping** → Kanten-ERKENNUNG (Pivot-Seeds) funktioniert mit Historie, nur der active/sleeping-Lebenszyklus widerspricht der User-Sicht.
  - **BASELINE (12 AUG-Phasen): trifft 7/8 User-Linien als U_final/L_final mit d<0.15** (66.468↔66.45, 67.201↔67.26, 65.603↔65.66, 69.914↔69.90, 68.370↔68.40, 69.555↔69.58, 67.636↔67.65); nur R1-lower 62.24 fehlt (Vor-Fenster-Niveau, Baseline-P6 hat 62.649). **Kern-Befund: Die User-Ideallinien SIND die U_final/L_final-Schnittmengen-Extreme der Baseline-Phasen** — die Baseline hält die Grenze über die Phasendauer (bis 2-Close-Bruch > Grenze+TOL), der EdgeStore schläfert nach erstem 2-Close-Bruch. Die User-Ranges sind KEINE „aktiven Store-Level", sondern Phasen-Grenzen mit seltenen Tests (24h+ zwischen H/L).
- **Letzter Schritt:** **Kausalitäts-Audit der laufenden Schnittmengen-Linie (02.09., `test/tmp_kausal_linie_stabilisierung.py`)** — beantwortet die Mentor-Frage „ab welchem Bar k stabilisiert sich die laufende Linie auf U_final/L_final?". **Befund (AUG, TOL 0.15):** Früh stabil (≤50 Bars): P7-U 41/P7-L 6, P8 21/8, P9-U 33, P10 29/26, P11-L 3, P12-U 44. **Sehr spät:** P5-U 352 Bars (17.08 19:00!), P9-L 339 Bars (24.08 17:45), P12-L 92. **Nie stabil:** P4-L, P5-L (27 Tests), P6-U. **User-Linien:** R2_U 41 B, R2_L 6 B, R3_U 33 B (früh); R3_L 339 B, R4_L 92 B, **R1_U (66.45) erst 352 B nach P5-Start mit Drift bis 2.433 davor**. **Kern-Erkenntnis:** Die User-Makro-Linien sind **phasen-übergreifend** (R1_U 11.–18.08 überspannt Baseline-Sub-Phasen P2 65.891/P3 65.181/P4 66.663/P5 66.468); die Baseline segmentiert Makro-Ranges in Sub-Phasen. Die 7/8-Benchmark-Treffer galten der finalen Linie der tragenden Sub-Phase, NICHT einer kausal früh persistenten Makro-Linie. Obere Linien meist früh stabil, untere oft spät. → Signal-Entwurf „laufende Linie" ist nur in früh-stabilen Phasen sauber; die Persistenz einer Makro-Linie über Sub-Phasen (User-Zeitfenster) ist eine offene Design-Aufgabe.
- **Letzter Schritt:** **Benchmark verankert & verifiziert (User-Freigabe Option 1, 02.09.)** — `UserMacroLine` (frozen/slots), `USER_LINES_AUG` (8 Linien), `BENCHMARK_TOL=0.15`, `BENCHMARK_TOL_EXACT=0.06`, `benchmark_report()` + `if "--benchmark" in sys.argv` **ans Dateiende** von `scripts/phasen_volumen_profil.py` angehängt. Rein lesend (kein Eingriff in Phasen/Signale/Exits/SL). **Verifikation:** `py_compile` ✓; Referenzlauf OHNE Flag exakt **27 Sig / +24.97R / 44 %** ✓ (Null-Einfluss-Beweis); Lauf MIT Flag erzeugt den Report. **Report (AUG, Tol 0.15):**
  | Linie | User-Zeitfenster | Baseline-Niveau | d | Klasse |
  |---|---|---|---|---|
  | R1_U 66.45 | 11.08 03:45–18.08 03:00 | P5 U 66.468 | 0.017 (centgenau) | VOLL |
  | R1_L 62.24 | 11.08 08:30–13.08 21:15 | P6 L 62.649 | 0.409 | KEIN |
  | R2_U 67.26 | 20.08 02:15–07:00 | P7 U 67.201 | 0.059 (centgenau) | VOLL |
  | R2_L 65.66 | 20.08 14:00–14:15 | P7 L 65.603 | 0.056 (centgenau) | VOLL |
  | R3_U 69.90 | 21.08 10:45–25.08 02:00 | P9 U 69.914 | 0.014 (centgenau) | VOLL |
  | R3_L 68.40 | 24.08 03:30–20:00 | P9 L 68.370 | 0.030 (centgenau) | VOLL |
  | R4_U 69.58 | 26.08 04:30–27.08 18:45 | P12 U 69.555 | 0.025 (centgenau) | VOLL |
  | R4_L 67.65 | 25.08 04:30–26.08 15:45 | P12 L 67.636 | 0.014 (centgenau) | **PREIS-ONLY** |
  **Resultat: 6 VOLL | 1 PREIS-ONLY | 1 KEIN.** Die Zeit-Überlappungs-Pflicht (User-Vorgabe) korrigiert die frühere 7/8-Zählung: **R4_L ist streng genommen Post-Hoc** — das beste Niveau 67.636 trägt P12 (26.08 16:45–27.08 19:00), die erst **1 h nach Ende des User-Fensters** (26.08 15:45) startet; einziger In-Fenster-Kandidat in Tol wäre P10-L 67.544 (d=0.106, nur loses Band-Match). R1_L bleibt KEIN (Vor-Fenster-Niveau, d=0.409). → **6/8 User-Linien sind kausal (Fenster + Preis) reproduziert; R1_L fehlt im Fenster, R4_L wird 1 h zu spät ratifiziert** — exakt der Post-Hoc-Tatbestand, den die Überlappungs-Regel sichtbar machen soll.
- **Letzter Schritt:** **P5-Drift-Ursachenanalyse abgeschlossen (02.09., `test/tmp_p5_drift_ursache.py`, rein diagnostisch)** — Mentor-Frage Option 3 beantwortet: Der 2.433-Drift der laufenden P5-Oberlinie ist ein **phasen-lokaler Reset + MIN_CLUSTER=2-Dichte-Schwellwert**, Ursache ist (b) Makro-Memory-Verlust, NICHT (a) Bandbreite:
  1. **Per-Pivot-Trace (Band 0.15):** P5 startet nach dem Drop auf 63.7 (14.08 03:00); die ersten H-Pivots liegen bei 63.99–65.97 → laufende Linie = Kante des dichtesten Clusters: 64.04 → 64.90 → 65.85. Die einzelnen Makro-Highs **66.206 (17.08 03:15) und 66.538 (17.08 17:15!)** sind isoliert (nur 1 Pivot im 0.15-Band < MIN_CLUSTER=2) → werden **ignoriert**. Erst der **2. 66.4x-Test (66.399, 17.08 19:00)** bildet den Cluster → Sprung auf 66.399/66.468 = stabil nach **352 B**. → Kein gradueller Drift, sondern ein **Dichte-Schwellwert-Sprung**; die 352 B sind die Wartezeit bis zum 2. Touch, nicht Linien-Wandern.
  2. **Band-Sensitivität (a) FALSIFIZIERT:** schmalere Bänder 0.05/0.08 stabilisieren SPÄTER (Test 22 = 385 B, maxDev 2.459); breitere 0.25/0.40 nur minimal früher (345–352 B) und mit verfälschtem Niveau (0.40 → „U_final" 66.046 statt 66.468). **Kein Band kann vor dem 2. Touch stabilisieren** — die Schranke ist chronologisch (2. Test fehlt), nicht spektral.
  3. **Makro-Memory (b) BESTÄTIGT:** kumulierte H-Pivots P1..P5 (phasen-übergreifende Schnittmengen-Linie) halten die Linie ab P5-Start **dauerhaft bei 66.58–66.66** (max. Abw. 0.195 vom P5-U_final 66.468, NIE 2.433). Die 66.4x-Zone ist ab P5-Start kausal präsent — der Phasen-Reset `h_acc=[]` verwirft P4-Wissen (66.663/66.776/66.459 am 12.08). **Einschränkung:** das naive Makro-Niveau liegt ~0.2 ÜBER R1_U 66.45 (der P4-Spike-Cluster 66.663/66.776 zieht dauerhaft hoch); die präzise 66.45 entsteht erst durch den frischen 17.-18.08-Cluster (66.399/66.468). → **Design-Konsequenz für das Makro-Persistenz-Modell:** Übertrag mit Gewichtung/Test-Zählung (frische multi-getestete Zonen > alte 2-Touch-Spikes), sonst Overshoot durch Spike-Zonen. Zugleich ist der Dichte-Zwang **Anti-Fakeout-Schutz**: Der 66.538-Reclaim-Run (17.08 17:15) etabliert kausal KEINE Linie (kein 2. Test in 0.15 bis 19:00) — die Baseline wartet korrekt auf Bestätigung.
- **Letzter Schritt:** **Prototyp gebaut & validiert (Mentor-Freigabe R4-Präzisierung, 02.09.)** — Design-Dokument auf **v0.2 FREIGEGEBEN** (`docs/reclaim_makro_persistenz_design.md`): R1–R5 alle entschieden. R4-Präzisierung arretiert (nur durchschrittene Zonen löschen: `center <= B` bei UP / `>= B` bei DOWN) — das pauschale Leeren wäre am P3-Gegenbeispiel gescheitert (P3-UP-Bruch B=65.181 hätte die P2-Evidenz 66.459 vernichtet, bevor P4/P5 sie retesten). **`test/tmp_makro_state_proto.py` (reiner Beobachter):** Replay der AUG-Phasen-Events durch `MacroLineState` (frozen/slots-Dataclasses, Update-Touch-Matching, R4-Boundary, Tier2-Auswahl R2). **Validierung 1 ✓:** P5-Start (VOR P5-Touches): bester Makro-Anker = **66.364 ev2 [P2,P4]** (66.459 P2 + 66.364 P4, Remove-Tail) → d = **0.086 ≤ 0.15** zu R1_U 66.45 → **Stabilisierung 0 Bars statt 352**. **Validierung 2 ✓:** P4-Spike-Zone 66.663 ev1 [P4] bleibt im P5-Start-Zustand **inert** (ev < 2) und wird NICHT als Anker gewählt; nach P5-Retests (66.538/66.536) erhält sie legitime ev2 (Refinement), nach echtem P7-UP-Bruch (67.201) korrekt entfernt. Nebenbei bestätigt: Zonen-Disjunktion + R2-Tie-Break funktionieren (66.046 ev2 älter vs. 66.364 ev2 jünger → 66.364 gewählt).
- **Letzter Schritt:** **3-Fenster-Diagnose BESTANDEN (02.09., `test/tmp_makro_3fenster.py`, reiner Beobachter)** — MacroLineState-Replay über AUG/S1/S2, Zonen-Bilanz + Alter + AUG-Regression. **Bruch-Richtungen:** AUG UP 6/DOWN 5, S1 UP 68/DOWN 70, **S2 UP 47/DOWN 14** (UP-dominiert). **Zonen-Bilanz (erzeugt → R4-entfernt → am Ende; max aktiv; avg):**
  | Fenster | UPPER | LOWER | max/avg (U/L) | max Alter (U/L) |
  |---|---|---|---|---|
  | AUG (12 Ph.) | 36→28→8 | 39→20→19 | 11/5.0 · 19/10.9 | 808/1701 B |
  | S1 (139 Ph.) | 374→329→45 | 382→340→42 | 66/32.9 · 49/22.3 | 17162/11956 B |
  | S2 (62 Ph.) | 177→173→4 | 147→66→81 | 10/2.8 · **81/50.6** | 4322/**31756 B** |
  **Prüfpunkt 1 (Inflation):** Kein technisches Leck — bei ausgeglichenen Bruch-Richtungen (AUG, S1) hält R4 den Pool beidseitig im Griff (S1 ~90 % Entsorgung). **S2-LOWER akkumuliert** (81 Ende, avg 50.6): R4 löscht nur die Bruch-Seite, S2 ist UP-dominiert (47/14) → DOWN-Brüche (LOWER-Reinigung) selten; Gegenseite persistiert „left_behind" per Design. Absolut klein (n=81), aber strukturelle Seiten-Asymmetrie in einseitigen Regimen (Design-Notiz für §12.4, kein v1-Eingriff).
  **Prüfpunkt 2 (R3-Stabilität/Alter):** S2-LOWER: älteste Zone 31756 B ≈ **gesamtes Fenster** (Januar-2025-Zonen leben bis Dezember), 33 Cluttering-Kandidaten (ev1 & ≥500 B). Unschädlich für Tier-2-Wahl: 37/81 sind ev1 → inert (MIN_ZONE_EVIDENCE=2); die 44 ev≥2-Restzonen SIND der gewünschte Makro-Schatz (alte starke S2-Level). **Design-Konsequenz:** `best_macro_anchor` = global-beste Evidenz — ferne Top-Zonen (63.818 ev3) lagen bei R2_L/R3_L/R4_L nie in TOL (d=1.8–4.6) → korrekt kein Eingriff; **die spätere Signal-Abfrage (§12.4) muss die Anker-Suche distanz-begrenzt zur aktuellen Preisregion machen**, nicht global beste Evidenz nehmen (sonst greift Alt-Zone aus anderer Preisregion, sobald Tier 2 ohne lokale Linie operativ wird).
  **Prüfpunkt 3 (AUG-Regression, Diagnose-Fix: Anker-Snapshot eingefroren — `best_macro_anchor` liefert Live-Referenz, die die eigenen Phasen-Touches mutierten; vorher fälschlich 66.382 ev3 [1,3,4], korrekt 66.364 ev2 [1,3]):**
  | Linie | Phase | final | lokal [B] | Anker@Start (VOR Touches) | d | 0B? |
  |---|---|---|---|---|---|---|
  | R1_U | P5 | 66.468 | 352 | 66.364 ev2 [P2,P4] [11.08 03:45–12.08 13:15] | 0.086 | **JA → 352→0 ✓** |
  | R2_U | P7 | 67.201 | 41 | 65.994 ev3 [P2,P4,P5] | 1.266 | nein (unverändert ✓) |
  | R2_L | P7 | 65.603 | 6 | 63.818 ev3 | 1.842 | nein (unverändert ✓) |
  | R3_U | P9 | 69.914 | 33 | (kein Anker — frisches Level) | -- | nein (unverändert ✓) |
  | R3_L | P9 | 68.370 | 339 | 63.818 ev3 | 4.582 | nein (korrekt kein Eingriff) |
  | R4_U | P12 | 69.555 | 44 | 68.928 ev3 [P8,P9,P11] | 0.652 | nein (unverändert ✓) |
  | R4_L | P12 | 67.636 | 92 | 63.818 ev3 | 3.832 | nein (korrekt kein Eingriff) |
  **Verdict: alle 3 Prüfpunkte grün.** R1_U 352→0 (Anker exakt wie Prototyp-Validierung 1); früh-stabile Linien (R2_U 41, R2_L 6, R3_U 33, R4_U 44 B) unverändert — keine Regression; frische Level ohne Makro-Gedächtnis (R3_U, R3_L 68.37, R4_L 67.64) korrekt ohne Anker-Eingriff. Evidenz-Verteilung S1-Ende: UPPER 45 (ev1 26/ev2 11/ev3 1/ev4+ 7), LOWER 42 (22/15/5/0) — alte starke Zonen (ev4+) als Anker-Schatz vorhanden.
- **Letzter Schritt:** **`--macro`-Spiegel implementiert & verifiziert (User-Freigabe §12.4, 02.09.)** — **NEU `scripts/macro_persistence.py`** (produktive Extraktion aus `test/tmp_makro_state_proto.py`, dependency-frei, injiziertes `level_schnittmenge`): Dataclasses (§4), `update_touch`/`on_phase_boundary` (R4), `best_macro_anchor` (global) + **`best_local_macro_anchor(st, current_price, max_dist)`** (distanzbegrenzt, Mentor-Pflicht: `|center − Preis| ≤ max_dist`, dann Evidenz ≥ 2, R2-Tie-Break), **`MacroAnchorInfo` (frozen Kopie — nie Live-Referenz, Kausalitäts-Schutz arretiert)**, `macro_replay` + `macro_report`. **Additiver Hook ans Hauptskript-Ende** (Z. 1485+, nach Benchmark-Block; exec-Cut des Prototyps unberührt): `if "--macro" in sys.argv:` → Import + `macro_report(phases, df, level_schnittmenge, _macro_dist_ref)`; `_macro_dist_ref` = kausale Range-Referenz `(high−low).rolling(200, min_periods=20).mean().shift(1)`; Faktoren **4×/8×/12× NUR im Report** (keine feste Schwelle — Kalibrierung erst im Signal-Loop). **Verifikation:**
  - `py_compile` beide Dateien ✓
  - **Null-Einfluss OHNE Flag:** AUG exakt **27 Sig / +24.97R / 12 G / 15 V** ✓
  - **MIT Flag:** Signalzahlen **identisch** (27/+24.97R) + Spiegel-Report erscheint ✓
  - **P5-Start (VOR Touches):** UPPER-Anker = **66.364 ev2 [1,3] n=2 [11.08 03:45–12.08 13:15]** — exakt Prototyp-Validierung ✓; lokal 12× in Reichweite (d=2.438), 4×/8× nicht (close@Start 63.926, range_ref 0.220) — Distanz-Landschaft wie gewünscht
  - **Bilanz deckungsgleich mit 3-Fenster-Diagnose:** UPPER 8 Zonen (ev1 3/ev3 4/ev4+ 1, max Alter 679 B), LOWER 19 (ev1 9/ev2 7/ev3 3, 1701 B) ✓
- **Letzter Schritt:** **Signal-Loop Schritt 1+2 implementiert (User-Freigabe §9.1–9.4, 02.09.)** — Mentor-Urteile arretiert: (1) Tier-1-Bestätigung via `_linie` ∧ |`_linie` − `U_zone`| ≤ 0.15 ✓; (2) `MACRO_DIST_FACTOR` 12× als reines Kandidaten-Vorfilter ✓; (3) **Penetrations-Gate strikt NUR auf Tier 2** (Tier 1 unberührt, Baseline-DNA) ✓; (4) **kein Intra-Phase-Bounce für Tier 2** (Legitimation durch ev ≥ 2 Phasen, erster Touch + Reclaim sofort handelbar) ✓.
  **Schritt 1 (`scripts/macro_persistence.py`):** `ActiveEdgeDecision` (frozen dataclass: side/edge_price/tier/anchor/lokal_kante/bestaetigt/penetriert/bounces/current_price/range_ref) + **`resolve_active_edge(...)`** (keyword-only; E2: `_linie`-Dichte (MIN_CLUSTER=2) trägt die Volume-Kante → bestaetigt; E3: Tier 1 führt, sonst Tier 2 = `best_local_macro_anchor` (max_dist = 12×range_ref), kein Kandidat → None (Anti-P5); E4: Penetration `|extreme − edge| ≤ 0.15` nur bei tier==2, Tier 1 nur Durchstich; Bounces gegen operative Kante bis ts_k). Parameter `PENETRATION_TOL=0.15` (= DENSITY_BAND, Wiederverwendung) + `MACRO_DIST_FACTOR=12.0`.
  **Schritt 2 (`scripts/phasen_volumen_profil.py`):** `ReclaimSignal` + Schatten-Felder `edge_decision`/`macro_active` (Defaults = Baseline); `find_reclaim_signals(df, p, ..., st_u=None, st_l=None)` — optionale Injektion der MacroLineState-Objekte (je Seite unabhängig, Seite ohne State = Baseline-Modus); Kanten-Auswahl ersetzt is_candidate (U_eff/L_eff = operative Kante wenn penetriert); `_bounce_ok = nb ≥ min_bounce OR tier==2` (Mentor §9.4); `range_ref` kausal rolling(200, shift 1) nur im Makro-Pfad; Import von `resolve_active_edge` nur bei Bedarf.
  **Verifikation:**
  - `py_compile` beide ✓
  - **Null-Einfluss OHNE Flag:** AUG exakt **27 Sig / +24.97R / 44 %** (bitgenau) ✓
  - **Logik-Test `test/tmp_resolve_edge_check.py` BESTANDEN:** P5-Start (U_zone=64.155 trailing, close 63.926, range_ref 0.220): tier=2, Anker **66.364 ev2 [P2,P4]**, bestaetigt=False, penetriert=False → kein Signal in der Lücke (Anti-P5) ✓; synthetische Penetration 66.404 → penetriert=True (E4-Gate) ✓; range_ref=None → None (wandernde Kante schweigt) ✓
- **Letzter Schritt:** **Signal-Loop Schritt 3+4 implementiert & A/B-validiert (User-Freigabe, 02.09.)** — `--macro-live`-Hook in der Phasen-Schleife: Kausalitäts-Axiom `Boundary(p−1)→Scan(p)→Touches(p)` exakt; Scope-Trennung (nur `st_u`/`st_l`-Instanziierung + Injektion, keine globalen Variablen); Baseline-Kontrolllauf nur für den Delta-Report. **AUG A/B:**
  | Variante | Sig | G/V | WR | Summe R |
  |---|---|---|---|---|
  | Baseline (ohne Flag) | 27 | 12/15 | 44 % | **+24.97R** |
  | `--macro-live` | 21 | 10/11 | 48 % | **+20.62R** |
  | Identisch | 15 | — | — | — |
  | Entfallen | 12 | — | — | −11.23R (aus Baseline entfernt) |
  | Neu | 6 | — | — | +6.88R |
  **P5-Lücke GESCHLOSSEN (Kernziel erreicht):** 4 Konter-Loser entfallen (14.08 08:45/11:45/14:45 + 17.08 03:45, je −1R → +4R); der 66.28-Gewinner feuert **früher und höher**: Baseline 17.08 18:45 +6.71R → Macro-Live 17.08 17:45 **Tier 2 @ 66.364 ev2 [P2,P4]** +6.90R (Reclaim an der Makro-Kante statt Warten auf lokale Linie).
  **ABER AUG netto −4.35R — 3 Gewinner gefiltert + 1 neuer P5-Loser:**
  - **P2 11.08 04:00 SHORT +4.59R entfallen (COLD-START):** Beim Scan von P2 existiert erst 1 Phase im State → kein Tier-2-Anker (ev≥2 unmöglich) UND lokale Dichte trägt U_zone noch nicht → `resolve_active_edge` = None → Signal unterdrückt. Der Anti-P5-Mechanismus hat in den ersten Phasen noch keinen Makro-Anker, an den er die Kante binden könnte.
  - **P7 20.08 02:15 SHORT +4.26R + P9 24.08 20:15 LONG +2.96R entfallen (E2-Dichte-Mismatch):** Die Volume-Kante (U_zone/L_zone) liegt an diesen Bars > 0.15 von der lokalen Pivot-Schnittmenge (`_linie`) entfernt → Tier 1 „nicht bestätigt"; der Tier-2-Anker der Seite ist nicht in 12×range_ref-Penetrationsreichweite (oder penetriert nicht) → None.
  - **NEU P5 17.08 04:30 SHORT −1.00R (Tier 1 @ 65.798):** Die trailing U_zone 65.798 wird an diesem Bar durch lokale Pivot-Dichte „bestätigt" (P5-Anstieg hatte dort echte Pivots) → Signal feuert, Markt läuft weiter → −1R (Baseline hatte 03:45 −1R, verschoben).
  **Befund (wissenschaftlich):** Der Kern-Mechanismus (Tier-2-Anker schließt die Kausalitätslücke) funktioniert exakt wie spezifiziert. Die Netto-Verschlechterung kommt aus der **E3-Strenge ohne Fallback**: Wo kein Tier-2-Anker existiert (Cold-Start) oder die lokale Dichte die atmende Volume-Kante nicht centgenau trägt, wird das Signal unterdrückt — inkl. legitimer Range-Gewinner. **Design-Option (v1.1, zur Entscheidung):** E3-Fallback „kein Tier-2-Kandidat → Baseline-Verhalten (U_zone direkt statt None)" — Cold-Start ist auf die ersten 1–2 Phasen begrenzt, danach existiert fast immer ein ev≥2-Anker; die P5-Lücke bleibt geschlossen (dort existiert der Anker 66.364). Alternativen: (a) E2-Schwelle nur als „Tier-2-Override" statt Gate (Tier 1 feuert immer, Tier 2 ersetzt nur wenn bestaetigt=False UND Anker in Reichweite); (b) v1 so lassen und nur auf S1/S2 prüfen (OOS-Blick), ob der Filter dort hilft.
- **Letzter Schritt:** **S1+S2-OOS-Diagnoseläufe AUSGEFÜHRT (02.09., rein lesend; Output `test/tmp_macro_live_S1.txt` / `test/tmp_macro_live_S2.txt`, Analyse `test/tmp_analyze_oos.py`)** — S1 (02.05.–28.08.26, 14365 Candles) + S2 (2025, 21624 Candles) mit `--macro-live`; Konsistenz-Check je Fenster exakt ✓ (baseline − ent + neu = Macro-Live):
  | Fenster | Baseline | `--macro-live` | Entfallen (G/V) | Neu (G/V) | Netto-Delta |
  |---|---|---|---|---|---|
  | AUG | 27 / +24.97R | 21 / +20.62R | 12 (−11.23R) | 6 (+6.88R) | **−4.35R** |
  | S1 | 201 / +197.26R | 151 / +147.49R | 70 (28G/42V, **+76.85R**) | 20 (11G/9V, +27.09R) | **−49.77R** |
  | S2 | 210 / +99.88R | 187 / +71.18R | 44 (12G/32V, **+25.05R**) | 21 (3G/18V, −3.64R) | **−28.70R** |
  **Befund (wissenschaftlich, gegen Mentor-Erwartung):** Die E2/E3-Filterung baut auf S1/S2 **KEINE Verluste ab — sie kostet netto −78.5R** (Σ alle Fenster −82.8R). Beide Entfallen-Listen sind **netto-GEWINNER** (S1 +76.85R aus 28 G vs. 42 V; S2 +25.05R aus 12 G vs. 32 V): Wegen der R-Asymmetrie der Baseline (Gewinner +1.5…+17.8R vs. Verlierer −1R) überwiegen die entgangenen Gewinner die eliminierten Verlierer bei Weitem. Der Filter selektiert **keinen Querschnitt nach Qualität** — er entfernt auch die größten R-Träger (S1: P23 03.03 +17.79R, P6 +7.08R, P132 17.08 +6.71R, P25 +5.94R; S2: P7 09.04 +9.39R, P49 +8.63R, P42 +8.37R, P10 +6.94R).
  **Cold-Start ist KEIN dominanter Faktor:** S1 P1/P2: 0 entfallen/0 neu; S2 P1/P2: nur 3 entfallen (−2.45R, alle Verlierer). Die entfallenen Gewinner verteilen sich über die GANZE Periode (S1 P6–P136, S2 P7–P50) — die E2/E3-Selektivität filtert strukturell einen Querschnitt, nicht nur die warm-up-Lücke. Die „Neu"-Signale sind in S2 netto-Verlierer (−3.64R), in S1 Gewinner (+27.09R) — kein konsistenter Kompensations-Mechanismus.
  **Schlussfolgerung:** Option 3 („OOS zeigt, dass der Filter hilft") ist **FALSSIFIZIERT**. Die v1-Selektivität (Tier 1 nur bei `_linie`-Dichte ≤0.15, sonst Tier 2-Anker in 12×Reichweite, sonst None) ist auf AUG+S1+S2 **netto destruktiv** (−82.8R). Kern-Mechanismus (Tier 2 schließt P5-Kausalitätslücke) funktioniert, aber das E2-Gate + E3-None-Verhalten unterdrücken einen **wertvollen Querschnitt** der Baseline-Signale.
- **Nächster Schritt (NACH User/Mentor-Entscheidung):** Entscheidung über die v1-Selektivität auf Basis von AUG −4.35R + S1 −49.77R + S2 −28.70R. Optionen: (1) E3-Fallback „kein Tier-2-Kandidat → Baseline-Verhalten (U_zone direkt)" — behebt Cold-Start UND E2-Dichte-Mismatch (dann feuert Tier 1 ohne lokale Dichte-Bestätigung wieder, wenn kein Makro-Anker in Reichweite ist; P5-Lücke bleibt geschlossen, wo der Anker existiert); (2) E2-Schwelle von Gate zu „Tier-2-Override" abschwächen (Tier 1 feuert immer, Tier 2 ersetzt nur bei bestaetigt=False + Anker-Penetration); (3) v1 so lassen → Makro-Persistenz nur als Schatten/Diagnose, kein Signal-Eingriff (Baseline bleibt). KEIN Code-Eingriff vor der Entscheidung.
- **S3-v2 Gate-Ergebnis (Isolations-Matrix, Cooldown 8, Rolling-VP-Exit):**
  | Variante | AUG | S1 | S2 |
  |---|---|---|---|
  | v1 (keine Gates) | +31.89R (43) | −73.90R (583) | −47.17R (634) |
  | nur B (Struktur) | **+32.99R (38)** | −82.06R (563) | **−25.69R (545)** |
  | nur A (Spread≥1.0%) | +27.32R (30) | −98.27R (465) | −79.18R (432) |
  | A+B | +25.98R (28) | −103.92R (450) | −65.13R (363) |
  → **Kein R>0-Turnaround auf S1+S2.** Gate B blockt auf S2 194 Sig (−60.1R
  = Verlierer), auf S1 nur 33 (−4.9R) → hilft S2, nicht S1. Gate A blockt
  auf S1 290 Sig mit entgangenen **+118.9R** Gewinnern → destruktiv. AUG:
  Fall 1 strikt ✓, Fall 2+3 wirtschaftlich ✓ (+6.92/+6.73R bleiben), A+B
  +25.98R (28 Sig). Implementierung: `EdgeLevel.last_sleep_bar` +
  `EdgeStore.last_valid_break_bar()` in `reclaim_edge_store.py`; Defaults
  `MIN_CORRIDOR_SPREAD_PCT=1.0`, `USE_GATE_A/B=True` + CLI `--corridor-spread`,
  `--no-gate-a`, `--no-gate-b` in `reclaim_s3_signals.py`; blockierte
  Kandidaten werden als `(grund, sig)` mit Trade-Auflösung gesammelt
  (Cooldown wird von geblockten Signalen NICHT verbraucht).
- **Nicht anfassen:** Hauptskript nicht committen/resetten (Worktree-Zustand,
  siehe `test/SESSION_HANDOFF.md`); keine UI-/Regressionstests.

### Baseline-Referenzzahlen (zur Validierung, kausal)
| Fenster | Variante | Sig | WR | Summe R |
|---|---|---|---|---|
| AUG (10.–28.08.26) | Baseline (CD=12) | 27 | 44% | +24.97R |
| S1 (02.–08.26) | Baseline | 201 | 44% | +197.26R |
| S2 (2025) | Baseline (CD=12) | 210 | 35% | +99.88R |
| S2 (2025) | Baseline (CD=8) | 240 | 35% | +110.79R |

- **Verworfen (nicht OOS-robust):** Kante-SL, Struktur-Regel, 3-Eck+Cap
  (Details in SESSION_HANDOFF.md). Nur CD=8 (MIN_SIGNAL_ABSTAND_BARS) ist
  übernommen.

### Akzeptanzfälle für den Kantenspeicher (aus Session)
1. Die 5 P5-Konter-SHORTs (14.–17.08) entstehen **nicht mehr** (Trailing-Kante).
   → S1: strukturell verifiziert (Store-Korridor zeigte an allen 5 Bars andere
   Level; endgültig in S3-Simulation).
2. Die 2 Gewinner an 66.28 (17./18.08, +6.7R) **bleiben** erhalten.
   → S1: strukturell verifiziert (Q6-Reaktivierung; Korridor U=66.386/66.388
   aktiv an beiden Gewinner-Bars).
3. Fall 18.08 ~02:00: Kante blieb nach altem Phasenende gültig → wird gehandelt
   (wird in der S3-Signal-Simulation exakt verifiziert).
4. S2-Summe R **≥ Baseline** (+99.88R CD=12 / +110.79R CD=8) = hartes OOS-Kriterium.

### Dateien (relevant)
- Konzept/Session-Memory: `docs/reclaim.md`
- **Design-Skizze Makro-Persistenz (v0.1, zur Begutachtung): `docs/reclaim_makro_persistenz_design.md`**
- Hauptskript (Baseline, unverändert): `scripts/phasen_volumen_profil.py`
- Test-Ablage: `test/` (aktiv) + `test/archiv/` (verworfen)
- Handoff-Historie: `test/SESSION_HANDOFF.md`

---

## 0. Update-Log

| Datum | Schritt | Inhalt |
|---|---|---|
| 02.09.2026 | v0.1 | Grundkonzept Kantenspeicher + Confluence, P5-Befund, Trailing-Erkennung, Validierungsplan; User-Erweiterungen (Swing-Memory, Preisraster, Uhrzeit, Levelverschiebung) als Phase 2+ notiert; Datei als Session-Memory ausgewiesen (Bootstrap-Block) |
| 02.09.2026 | Q2 | **Design-Entscheidung:** Aktiver Korridor = strikt die **letzte ungebrochene Kante** (preiseinengend) → Abschnitt 9.1; Swing-Memory wird zentral für Phase 1 |
| 02.09.2026 | Score | **User-Klärung:** Preisraster (w_grid) + Zeitfenster (w_session) sind **keine eigenen Kriterien/Filter**, sondern ausschließlich Zusatz-Gewichte im Confluence-Score → Abschnitt 6 (WICHTIG-Hinweis) + 10.2/10.3 umformuliert |
| 02.09.2026 | Q1 | **Design-Entscheidung (Level-Quellen):** Nur **H/L-Pivot-Reaktionen** erzeugen Seeds (Kanten). **Volumen-Cluster ist KEIN eigener Seed**, sondern ausschließlich **Touch-Typ** (`volume_cluster`) an einem bestehenden Level → Confluence-Aufwertung. Kein Cluster-Noise im Speicher (Begründung des Users). |
| 02.09.2026 | Q3 | **Design-Entscheidung (TP-Logik):** Baseline-Exit (TP1/POC, TP2/Box-Ende) bleibt **zunächst unverändert**. Nächstes Level wird **nur zusätzlich ausgewiesen** (Schatten-Tracking im `TradeResolution`: `target_level_price`, `target_level_hit`, `r_level`). Schalter auf Level-TP erst nach S3/S4, wenn `r_level` in der 3-Fenster-Validierung die Baseline-Summe R übertrifft (wissenschaftliche Isolation). |
| 02.09.2026 | Q4 | **Design-Entscheidung (Phasen):** Phasen-Logik **komplett raus aus der Signal-Entscheidung** — der Signal-Loop kennt keine Phasen-Grenzen. Die bisherige Phasen-/Volume-Zonen-Berechnung läuft **nur als Diagnose-/Vergleichswerkzeug** (Parity-Check, zeitsynchroner A/B-Vergleich Bar für Bar). **Keine Phasen-Seeds** (widerlegt Abschnitt 11-Alttext, s. 14-Q4). |
| 02.09.2026 | Q5 | **Design-Entscheidung (Swing-Memory):** Swing-Memory/Berg-Tal-Kette wird auf **S3 verschoben** (kein Over-Engineering in S1). S1-Korridor-Vereinfachung: **Upper = nächstes aktives Level über dem Close, Lower = nächstes aktives Level unter dem Close.** Wichtig: Ein Level wird durch Sweeps **nicht blind gelöscht** (sleeping/counter_run); Pivot-Lag n=2 (30 min auf M15) gilt auch für Struktur-Bewertung. Williams-Fraktal = identisch mit Baseline-Pivots (n=2, 5-Bar-Fenster) — keine neue Quelle nötig. |
| 02.09.2026 | Q6 | **Design-Entscheidung (Re-Aktivierung schlafender Level):** sleeping + bestätigter Pivot **gleicher Orientierung** (H an UPPER / L an LOWER) in EDGE_TOL = Re-Validierung (fehlgeschlagener Bruch) → zurück auf **active**, Historie bleibt. **Kein Zeitfenster** (REARM_WINDOW_BARS = Retail-Overfit, kein neuer Parameter). Gegenläufiger Pivot an sleeping (L an UPPER / H an LOWER) = **counter_run** (Rollen-Tausch Resistance→Support) → bleibt sleeping. Auslöser: Akzeptanzfall 2 (66.28-Zone nach 12.08-Bruch). |
| 02.09.2026 | S1 | **S1-Prototyp gebaut** (`test/reclaim_edge_store.py`): EdgeLevel/EdgeTouch, Matching/Lebenszyklus inkl. Q6-Reaktivierung, Seeds nur n=2-Pivots, Korridor-Vereinfachung, kausale Snapshots. **P5-Verifikation:** Akzeptanzfall 1 ✓ (5 Trailing-SHORTs entfallen strukturell, Korridor zeigt andere Level); Fall 2 ✓ strukturell (Korridor U=66.386/66.388 aktiv an beiden Gewinner-Bars). Store-Lauf: AUG 36 Level/9 aktiv, S1 184/44, S2 126/32 (21,6k Bars in 1,2s). |
| 02.09.2026 | S2 | **S2 gebaut: Confluence-Score v1** (inkrementell). Drei User-Vorgaben umgesetzt & validiert (`test/reclaim_s2_score.py`): (1) rel_volume = roll. Median (200 Bars, shift 1), nie Gesamtdurchschnitt — 344/344 Touches exakt ✓; (2) Decay auf **Handelszeit = Bars** (`EDGE_HALF_LIFE_BARS`=2880 ≈ 30 Handelstage), 1 Zeile = 1 Schritt; (3) Score inkrementell `d·score + touch_contrib` — Referenz-Neuberechnung (EWMA-Summe) max Abw. 1e-13 ✓. Defaults: W_VOLUME=1.0, W_COUNT=0.5, W_TYPE {pivot_test 1.0, volume_cluster 1.5, counter_run 1.2}; w_grid/w_session=0 bis S4. |
| 02.09.2026 | Korridor-Schwäche | **User-Hinweis (S1-Korridor):** Nach Breakout liegt der Close jenseits der gebrochenen Kante (→ sleeping); bis ein neuer gegenseitiger Pivot entsteht, kann die Korridor-Seite unter dem Kurs **None** sein → Reclaims im Niemandsland unmöglich. Als bekannte Einschränkung dokumentiert (Abschnitt 9.1); Fix in S3 (Korridor = letzte ungebrochene Kante, Bruchpunkt wird Level). |
| 02.09.2026 | Lookahead-Audit | **User-Warnung geprüft:** Kein Lookahead im Store. Pivot j wird erst bei Iteration k=j+2 verarbeitet; Snapshot bei k enthält nur Pivots ≤ k−2. Transition-Log (`store.transitions`): 66.28-Zone war an beiden Gewinner-Bars seit iter 251 (12.08 16:45) aktiv, Gap 284/310 Bars. Global über alle 27 AUG-Bars: 0 Verdachtsfälle. Audit-Skripte: `test/reclaim_s1_audit_lookahead.py`, `reclaim_s1_audit_global.py`. |
| 02.09.2026 | Q7 | **Design-Entscheidung (Exit im phasenlosen Modell) = Option A** (Mentor-Votum, unmissverständlich): TP1 = POC eines rollierenden Volume-Profils (300 Bars, kausal); TP2 = Profil-Gegenseite + Puffer; Entry-Filter SHORT>POC bleibt. Level-TP nur Schatten (Q3). Option C (=Exit-Wechsel sofort) wäre „fundamentaler Data-Science-Fehler" (2 Variablen gleichzeitig), Option B (Korridor-Mitte) = „Retail-Nonsens" (Märkte nicht normalverteilt, POC = institutioneller Wert). |
| 02.09.2026 | S3-v1 | **S3-v1 gebaut** (`test/reclaim_s3_signals.py`): Setup-B-Signal-Loop inline im Store-Build über neuen `on_bar`-Hook (kausal, backward-kompatibel; Hook-Default None = S1/S2-Verhalten unverändert). Rolling-VP-Exit nach Q7. 3-Fenster-Referenz (Cooldown 8): AUG +31.89R/43 Sig (Baseline +24.97R), **S1 −73.90R/583 Sig, S2 −47.17R/634 Sig → roh nicht tragfähig**. Bucket-Diagnose: kein robuster Einzelfilter (CRV≥4: S2 +34.9R aber S1 −77.1R; edge_gap/Score nicht kreuzstabil). Befund: Range-/Regime-Selektion der Baseline fehlt (Churn in Trendphasen). AUG-Akzeptanz: Fall 1 strikt ✓, Fall 2+3 wirtschaftlich ✓ (1–2 Bars versetzt, gleiche 66.386/66.388-Zone, Gewinner +6.92/+6.73R erhalten). |
| 02.09.2026 | S3-v2-Gates | **S3-v2-Gates (A+B) implementiert** (Mentor-Freigabe): Gate A = 2-seitig + Korridor-Spread ≥ `MIN_CORRIDOR_SPREAD_PCT`; Gate B = Struktur-Sperre (`EdgeLevel.last_sleep_bar` + `EdgeStore.last_valid_break_bar(side, price_ref, below)` — Kante muss vor dem letzten 2-Close-Bruch derselben Seite unter/über ihr geboren sein; Q6-reaktivierte Level = Fehlausbruch, fallen automatisch raus). **Isolations-Matrix → kein Turnaround:** S1 nur B −82.1R, nur A −98.3R, A+B −103.9R; S2 nur B −25.7R (Besserung +21.5R), nur A −79.2R, A+B −65.1R. Gate A blockt Gewinner (S1 entgangene +118.9R!), Gate B hilft nur S2. AUG-Akzeptanz bleibt ✓ (A+B +25.98R/28 Sig; 2 Gewinner-Kanten passieren Gate B, geb. 11.08 vor Bruch). AUG-Probe (`test/reclaim_s3_aug_probe.py`): 23/43 PASS statisch (+23.87R), beide 66.38-Gewinner PASS. |
| 02.09.2026 | Anti-Overfit | **User-Warnung (Retail-Falle S2/Confluence-Score), unmissverständlich:** Score schlank halten — exakt die 3 institutionellen Komponenten (Preisstabilität `w_count`, Volumen `w_vol·rel_vol`, Relevanz/Decay). Keine Parameter-Kaskade („Level muss 15 Bedingungen erfüllen" = Curve-Fitting-Monster, glänzt auf AUG, bricht in S2 ein). **Decay = multiplikativer Faktor** auf jeden Touch-Beitrag, **kein additiver Parameter**. `rel_volume` strikt gegen **rollierenden Median** der vorangegangenen 200 Bars (shift 1) — nie global/Lookahead. `w_grid`/`w_session` (=0 bis S4) sind die EINZIGEN vorgesehenen späteren Ergänzungen. → Verankerung in §6 (ANTI-OVERFIT-LEITPLANKE + Rolling-Volume-Baseline) + Session-State Punkt (4). Implementierung in `reclaim_edge_store.py` erfüllt die Vorgabe bereits exakt (Formel-Abgleich + rel_volume 344/344 validiert). |
| 02.09.2026 | S3-Obduktion | **Mentor-Review-Fragen empirisch beantwortet** (`test/reclaim_s3_obduktion.py`, v1-Modus, kausal): **Q1** 91 % der Verlierer = SL-SL direkt (nie TP1), Median 3 (S1)/10 (S2) Bars → Trend-Run, kein Pendeln; nur 9 % oszillieren (TP1→SL, avg −0.32R). **Q2** Baseline 201/210–240 vs. S3 583/634 Signale = 2,6–2,9× Overtrading; Baseline-Schutz = ungebrochene Phase + Etablierung beider Seiten (≥4 Touches, ≥46 Candles) + Bounce nb≥2 + TP aus Phase-to-date-Profil (Code-Analyse). **Q3** naive Resonanz (opp_gap der Gegenseite <N) **kreuzinstabil**: S1 positiv nur 96–191 (+34.8R), S2 positiv nur <24 (+31.3R) — invertiert, festes N (48–96) = Overfit. → v3-Richtung: Range-**Generation**-Resonanz (seit letztem 2-Close-Bruch), nicht Touch-Frische. |
| 02.09.2026 | Baseline-Profil | **Baseline-DNA quantifiziert** (`test/reclaim_baseline_profil_audit.py`, 3 Fenster, Referenz exakt ✓; CSVs `test/tmp_baseline_profil_*.csv`): Je Signal kausal `phase_age_bars`, `bounces_this/opp_edge`, `combined_touches`, `piv_h/l`, `dist_to_last_break`, `bars_to_phase_end`. **Kernbefund:** Gewinner avg +3.0…+3.3R vs. Verlierer −0.9R (Asymmetrie trägt). **Kein monotoner Alter-Effekt** (S2: alle dist-Buckets positiv; Q3-Widerlegung bestätigt). **Kreuzstabiler Sweet Spot `combined_touches` 6–11** = beste Kohorte in allen Fenstern (WR 60/59/55 %); `<6` unter-etabliert (35–39 %), **`≥12` ausgelutscht (S2 WR 25 %, n=118)** = Mentor-Falle „Stop-Cluster an alten Kanten" empirisch bestätigt. → Resonanz-Definition: moderate beidseitige Generation-Etablierung, kein Alter-Maximum, kein Über-Testing. |
| 02.09.2026 | Generation-Audit | **Generation-Grenzziehung gemessen** (`test/reclaim_generation_audit.py`, kausal, S1/S2): Break-Events S1 1035 / S2 1243. **M1 (Kanten-Anker) verworfen** (95–98 % Abweichung; LOWER-als-up-Kante wird nie nach oben gebrochen → uralter Anker). **M2 (Spanne) ≈ M3 (echte Grenz-Brüche)** — nur 9 % (S1) / 24 % (S2) Abweichung, p90 0/15 Bars; Pass-through S1 11.7 % → Span-Regel nötig, Kanten-Anker würde ihn verpassen. Inner-Brüche S2 21.6 % verzerren gen_start kaum (jüngste Spannen-Brüche sind fast immer Grenz-Brüche). Sweet-Spot-Illustration (Baseline-DNA 4–12, NICHT kalibriert): S2 M2 +19.88R/M3 +12.87R im SS; S1 combined-Median nur 2 → junge Generationen. → **S3-v3: gen_start = Span-Events (M2/M3-äquivalent), combined-Schwelle Store-kalibrieren (nicht Baseline-DNA 1:1).** |
| 02.09.2026 | Store-Lücken | **Statische Analyse `_check_break`/`build()` (kein Code):** (1) Seiten-starrer Bruch — `lev.side`-Bindung verfehlt Rollen-Tausch-Brüche und lässt verlassene Level ewig active (stale) → uralte Anker. (2) Same-Iter-Ordnungs-Hazard — `_check_break(k)` vor Pivot k−2 ⇒ Q6-Reaktivierung durch Prä-Bruch-Pivot im selben iter möglich (spurious). → Spezifikation der Store-Reparatur durch User ausstehend. |
| 02.09.2026 | Store-Reparatur | **Baustein 1+2 implementiert** (Mentor-Freigabe): Transition-Gate in `_check_break` (Rolle aus close[k−2], up/dn-Bruch ohne Seed-Bindung; kein Verharren-Bruch), Chronologie in `build()` (Pivot j=k−2 vor `_check_break(k)`), Q6-Guard `last_sleep_bar < j` in `_add_pivot` (Prä-Bruch-Pivot = Touch ohne Reaktivierung). **Validierung:** s2_score 344/344 ✓, Lookahead 0 ✓; Rollen-Tausch-Brüche AUG 28 %/S1 29 %/S2 43 % der sleep-Events; Q6-Guard-Verletzungen 0; S2 v1 verbessert −47.17→−27.05R (+20.1R), S1 −73.90→−79.93R, AUG +31.89→+24.11R (**17.08-18:30-Gewinner entfällt = Same-Iter-Artefakt**, Kante 66.386 nach korrektem 2-Close-Bruch 18:15 erst 19:30 per Q6 reaktiviert; Baseline-Zone nachgiebig vs. Store-Kante starr). Diagnose: `test/reclaim_store_break_validate.py`. |
| 02.09.2026 | Band-Bruch | **Hysterese-Band in `_check_break`** (Mentor-Freigabe, tol=EDGE_TOL 0.15 reuse): `up_break = c_before≤p+tol ∧ c_prev>p+tol ∧ c_now>p+tol`, `dn_break` symmetrisch; c_before im Band = Naheseite (keine Deadzone). **v1-Ergebnisse:** AUG +30.65R (32) [+6.5R], S1 −52.96R (454) [+27R], S2 −50.19R (643) [−23R]. **17.08-18:30-Gewinner legitim zurück** (+6.92R, Kante überlebt +0.026-Poke); **18.08-02:30 fehlt** (Kante 17.08 19:30 genuin gebrochen — 2 Closes < 66.238 nach Reclaim-Run; 02:00-Retest an sleeping-Kante, Q6-Lag 2 Bars zu spät); Fall-1-Fehlalarm = LONG +5.64R (Check ohne Typ-Prüfung); **Skalen-Befund:** EDGE_TOL absolut — S2 2025 (Range 0.097) 4× kleiner als S1 2026 (0.377) → Band relativ 4× breiter → Stale + Overtrading. |
| 02.09.2026 | Accept-Fix | **Acceptance-Check-Typ-Bug korrigiert** (`acceptance_aug` Fall 1, ts-only → typ-Prüfung): LONG am selben Bar ≠ P5-Konter-SHORT. Verifiziert (v1, Band-Referenz 32 Sig/+30.65R exakt): Fall 1 ✓ (4 entfallen + 1 Typ-Klarstellung „LONG +5.64R → OK"), Fall 2: 17.08 wirtschaftlich ✓ / 18.08 FEHLER (Design-Divergenz), Fall 3 FEHLER. |
| 02.09.2026 | Skalen-Diagnose | **Quantifizierung Design-Frage (i)** (`test/reclaim_scale_diag.py`): EDGE_TOL 0.15 absolut = 0.48–0.65× (AUG/S1) vs. **1.92×** (S2) der roll. mean Range (200/shift1); **83.5 % der S2-Bars haben Range < Band**. Mentor-Arretierung: Matching-Band (statisch) vs. Bruch-Band (`tol_k = a × range_ref_k`, dynamisch) **entkoppeln**; Referenz kausal wie `vol_ref`; Sweep a∈{0.4,0.65,1.0} **rein diagnostisch** (separates Skript, `reclaim_edge_store.py` unangetastet); Reihenfolge: erst Doku, dann (i), dann (ii) Retest-nach-echtem-Bruch. |
| 02.09.2026 | Tol-Sweep | **Relativer-Toleranz-Sweep (rein diagnostisch, `test/reclaim_tol_sweep_diag.py`, Store unangetastet; Sanity a=0 exakt ✓):** AUG best a=0.4 (+37.04R), S1 best a=0 (−52.96R), S2 best a=1.0 (−2.82R, **+47R** ggü. absolut). **Kein kreuzstabiles a** (Σ: a=0 −72.5R < a=1.0 −77.6R < a=0.4 −97R). S1 in ALLEN Konfigurationen negativ → Bruch-Toleranz ist **Sekundär-Stellrad** (bekämpft S2-Stale-Overtrading), KEIN Turnaround-Hebel. Primärer Blocker: Regime-/Resonanz-Selektion (S3-v3 GenerationState). |
| 02.09.2026 | Patrick-Audit | **Patrick-Selektivität post-hoc gemessen** (`test/reclaim_patrick_selectivity.py`): Alter≥96 nützlichster Einzelfilter (Saldo −72.5→−42R) aber AUG < Baseline (+12.9R — AUG-Gewinne auf jungen Kanten); **Touches≥3 kontraproduktiv** (−90.7R, AUG-T=2-Bucket +17.2R); **Verlust-Pool = ALTE, viel-getestete Kanten** (S1 Alter≥288: −41.7R, T≥6: −54.3R) = Patricks „Premium-Zonen" → Selektivität kann Alt-Kante-in-Range nicht von Alt-Kante-im-Trend trennen; Session 22:50–00:10 klein positiv (+7–8R je Fenster), 00:00-Stunde S1 WR 0 % (n=21). → Regime-/Resonanz-Selektion (S3-v3) bleibt Kern-Hebel. |
| 02.09.2026 | User-Linien | **User-Ideallinien (AUG, 8 Linien/4 Ranges) als Massstab definiert.** Diagnose: EdgeStore findet sie nur mit Vorlauf (5/8 sleeping); **Baseline trifft 7/8 als U_final/L_final (d<0.15)** — die Linien SIND die Phasen-Reaktions-Extreme. → Strategische Weiche: **an Baseline weiterarbeiten** (Linien-Persistenz über Phasendauer), EdgeStore-Lebenszyklus für Range-Grenzen ungeeignet. Baseline-Anpassungen (a)–(d) spezifiziert. Dateien: `test/tmp_reclaim_user_ranges.py`, `tmp_reclaim_user_warmup.py`, `tmp_reclaim_baseline_zones.py`, `tmp_reclaim_user_vs_baseline_AUG.png`. |
| 02.09.2026 | Benchmark | **Benchmark-Set verankert (Option 1, User-Freigabe):** `UserMacroLine`/`USER_LINES_AUG` (8 Linien) + `benchmark_report()` ans Dateiende von `scripts/phasen_volumen_profil.py`; Aktivierung `--benchmark`, rein lesend. **Verifiziert:** py_compile ✓; Referenz OHNE Flag exakt 27 Sig/+24.97R/44 % ✓ (Null-Einfluss). **Report: 6 VOLL | 1 PREIS-ONLY | 1 KEIN** — R1_U/R2_U/R2_L/R3_U/R3_L/R4_U VOLL (alle centgenau d≤0.059); **R4_L PREIS-ONLY** (Niveau 67.636 in P12, startet 1 h nach User-Fenster-Ende 26.08 15:45 → Zeit-Überlappungs-Regel entlarvt 7. „Treffer" als Post-Hoc); R1_L KEIN (Vor-Fenster-Niveau, d=0.409). Damit **6/8 kausal** reproduziert; R4_L-Semantik (streng best-first vs. „beste überlappende Phase in Tol") bei Bedarf als Option dokumentiert. |
| 02.09.2026 | P5-Drift | **Ursachenanalyse P5-Drift abgeschlossen** (`test/tmp_p5_drift_ursache.py`, rein diagnostisch): 2.433-Drift = **Phasen-Reset + MIN_CLUSTER=2-Dichte-Sprung**, (b) Makro-Memory-Verlust bestätigt, (a) Bandbreite falsifiziert. Einzelne Makro-Highs (66.206, 66.538 am 17.08 17:15) isoliert → ignoriert bis 2. Touch (66.399, 17.08 19:00) → Sprung auf 66.468 = 352 B. Schmalere Bänder später (385 B), breitere verfälschen Niveau (0.40 → 66.046). Kumulierte P1..P5-Linie hält 66.58–66.66 ab P5-Start (nie 2.433) — aber ~0.2 ÜBER R1_U durch P4-Spike-Cluster (66.663/66.776). → Makro-Persistenz-Modell braucht Decay/Test-Gewicht; MIN_CLUSTER=2 = Anti-Fakeout (66.538-Run etabliert kausal keine Linie). |
| 02.09.2026 | Architektur-Weiche | **ENDGÜLTIGE Architektur-Entscheidung (User/Mentor):** EdgeStore NUR noch Touch-Zählung/Archiv („Der Store archiviert, die Baseline führt"); Signal-Logik ab sofort = kausale Schnittmengen-Linie der Baseline. R4_L-Semantik diagnostisch geklärt (kein weiterer Aufwand); Chart-Verifikation nicht nötig. |
| 02.09.2026 | Makro-Design | **Formale Design-Skizze v0.1 erstellt:** `docs/reclaim_makro_persistenz_design.md` (zur Begutachtung, KEIN Code vor Freigabe). Kern: `MacroLineState` mit Zonen-Pool je Seite; **Evidenz = Phasen-Menge** (`MIN_ZONE_EVIDENCE=2`); Spike-Isolation (1-Phasen-Zonen inert, Remove-Tail); ereignisbasierter Decay (kein Bar-Decay); Übergabe: Bruch-Seite leer, Gegenseite persistiert; operative Linie zweistufig (Tier 1 lokal / Tier 2 Makro-Anker). Provenienz-Anker: R1_U=66.45 exakt ab Touch 66.459 (P2, 11.08 03:45 = User-Fenster-Start). Review-Fragen R1–R5 offen. |
| 02.09.2026 | R4-Präzisierung | **Review R1–R5 entschieden + R4-Präzisierung (Mentor-Freigabe):** R1 Remove-Tail ✓, R2 `last_ts` vor Richtung ✓ (AUG-Beleg: 66.046 vs 66.364 beide ev2 → jüngerer 66.364 gewählt), R3 keine Altersgrenze ✓, R4 **selektiv löschen** (`center <= B` UP / `>= B` DOWN; pauschales Leeren wäre am P3-Gegenbeispiel gescheitert: P3-UP-Bruch B=65.181 hätte P2-Evidenz 66.459 vernichtet), R5 Tier2→Schatten nach lokaler Bestätigung ✓. Design-Dokument → **v0.2 FREIGEGEBEN**. |
| 02.09.2026 | Makro-Prototyp | **Prototyp `test/tmp_makro_state_proto.py` gebaut & validiert (reiner Beobachter, AUG):** Replay der Phasen-Events durch `MacroLineState` (frozen/slots, Typ-Hints). **Validierung 1 ✓:** P5-Start Anker = **66.364 ev2 [P2,P4]** (66.459 P2 + 66.364 P4, Remove-Tail) → d = 0.086 ≤ 0.15 zu R1_U → **0 Bars statt 352**. **Validierung 2 ✓:** P4-Spike 66.663 ev1 [P4] inert bei P5-Start, nie gewählt; legitime ev2 erst nach P5-Retests (66.538/66.536), korrekt entfernt nach P7-UP-Bruch 67.201. Zonen-Disjunktion + R4-Selektiv-Löschen über alle 12 Phasen sichtbar (Zonen-Ledger). |
| 02.09.2026 | 3-Fenster | **3-Fenster-Diagnose BESTANDEN** (`test/tmp_makro_3fenster.py`, reiner Beobachter): **Prüfpunkt 1** kein Leck (S1 ~90 % Entsorgung beidseitig; max/avg aktiv U/L: AUG 11/5·19/11, S1 66/33·49/22, S2 10/3·81/51). **S2-LOWER-Asymmetrie erklärt:** UP-Dominanz 47/14 → R4 reinigt LOWER nur bei DOWN-Brüchen (left_behind-Persistenz per Design; n=81 absolut klein). **Prüfpunkt 2:** S2-LOWER älteste Zone = ganzes Fenster (31756 B), 33 Cluttering (ev1) — inert für Ankerwahl, ev≥2-Rest (44) = gewünschter Makro-Schatz. Design-Notiz §12.4: Anker-Abfrage distanz-begrenzt, nicht global-beste Evidenz. **Prüfpunkt 3 (AUG-Regression) grün:** R1_U 352→0 (Anker 66.364 ev2, d=0.086, exakt Prototyp); R2_U 41/R2_L 6/R3_U 33/R4_U 44 B unverändert; frische Level (R3_U ohne Anker, R3_L/R4_L d=4.6/3.8) korrekt ohne Eingriff. **Diagnose-Fix:** Anker-Snapshot eingefroren (Live-Referenz-Mutation durch eigene Phasen-Touches; 66.382 ev3 → korrekt 66.364 ev2). |
| 02.09.2026 | --macro-Spiegel | **§12.4 Schritt 4 umgesetzt (User-Freigabe):** NEU `scripts/macro_persistence.py` (produktive Extraktion, dependency-frei, injiziertes level_schnittmenge) + additiver Hook `if "--macro" in sys.argv` ans Hauptskript-Ende (rein lesend, nach Benchmark-Block). **`best_local_macro_anchor(st, current_price, max_dist)`** = distanzbegrenzte Anker-Abfrage (Mentor-Pflicht); **`MacroAnchorInfo`** frozen Kopie (Kausalitäts-Schutz). Report-Faktoren 4×/8×/12× der kausalen Range-Referenz NUR informativ. **Verifiziert:** py_compile ✓; Null-Einfluss OHNE Flag exakt 27 Sig/+24.97R ✓; MIT Flag Signalzahlen identisch + Report ✓; P5-Start-Anker = 66.364 ev2 [1,3] (exakt Prototyp) ✓; Zonen-Bilanz deckungsgleich mit 3-Fenster-Diagnose (UPPER 8/LOWER 19) ✓. |
| 02.09.2026 | Signal-Loop-Design | **`docs/reclaim_signal_loop_design.md` v0.1 ausgearbeitet (User-Freigabe, KEIN Code in scripts/):** E1 Tier 1 = `U_zone`/`L_zone` (minimal-invasiv, Baseline-DNA); E2 `_linie` (Pivot-Dichte ≥2, MIN_CLUSTER) = Bestätigungs-Schwelle für Tier 1; E3 Umschalt-Mechanik (Tier 1 führt bei lokaler Dichte, sonst Tier 2 = `best_local_macro_anchor`; kein Signal wenn beide leer — Anti-P5); E4 Penetrations-Gate `|extreme − edge| ≤ 0.15` (Reclaim = Stops an der Kante, kein Durchmarsch); E5 `max_dist = 12 × range_ref` nur Kandidaten-Vorauswahl. Datenvertrag `ActiveEdgeDecision` (frozen dataclass), erweiterte `find_reclaim_signals`-Signatur (Default None = Baseline), Hook-Sequenz Boundary(p−1)→Scan(p)→Touches(p) in Z. 1088–1093. Review-Punkte §9 offen (Tier-1-Gate nur Tier 2, Distanz-Faktor, Intra-Phase-Bounce). |
| 02.09.2026 | Signal-Loop S1+2 | **Mentor-Review §9.1–9.4 arretiert + Schritt 1+2 implementiert (User-Freigabe):** (1) Tier-1-Bestätigung via `_linie` ∧ ≤0.15 ✓; (2) 12× Kandidaten-Vorfilter ✓; (3) Penetrations-Gate **NUR Tier 2** (Tier 1 unberührt) ✓; (4) kein Intra-Phase-Bounce für Tier 2 ✓. **`scripts/macro_persistence.py`:** `ActiveEdgeDecision` + `resolve_active_edge` (E2–E5, Bounces gegen operative Kante, frozen). **`scripts/phasen_volumen_profil.py`:** `ReclaimSignal.edge_decision/macro_active` (Schatten), `find_reclaim_signals(..., st_u=None, st_l=None)` (Seite ohne State = Baseline; Kanten-Auswahl U_eff/L_eff; `_bounce_ok` mit tier-2-Ausnahme). **Verifiziert:** py_compile ✓; Null-Einfluss OHNE Flag exakt 27 Sig/+24.97R/44 % ✓; Logik-Test `test/tmp_resolve_edge_check.py` ✓ (P5-Start tier=2 Anker 66.364, nicht penetriert; synthetische Penetration → True; range_ref=None → None). Schritt 3 (`--macro-live`) offen. |
| 02.09.2026 | Macro-Live A/B | **Schritt 3+4 umgesetzt:** `--macro-live`-Hook in der Phasen-Schleife (Kausalitäts-Axiom Boundary(p−1)→Scan(p)→Touches(p), Scope-Trennung, Baseline-Kontrolllauf für Delta-Report). **AUG A/B:** Baseline 27/+24.97R → Macro-Live 21/+20.62R (Identisch 15/Entfallen 12/Neu 6). **P5-Lücke GESCHLOSSEN:** 4 Konter-Loser entfallen, 66.28-Gewinner früher (17.08 17:45 Tier 2 @ 66.364 ev2 +6.90R statt 18:45 +6.71R). **Netto −4.35R:** 3 Gewinner gefiltert (P2 11.08 +4.59R COLD-START — erst 1 Phase im State; P7/P9 E2-Dichte-Mismatch) + 1 neuer P5-Loser (Tier 1 @ 65.798). Entscheidung E3-Fallback/E2-Override vertagt → erst OOS-Blick. |
| 02.09.2026 | S1/S2-OOS | **S1+S2-OOS-Diagnoseläufe (rein lesend, `test/tmp_macro_live_S1.txt`/`_S2.txt`, Analyse `test/tmp_analyze_oos.py`):** S1 201/+197.26R → 151/+147.49R (**−49.77R**; Entfallen 70 mit **+76.85R** netto — 28G vs 42V, R-Asymmetrie schlägt durch); S2 210/+99.88R → 187/+71.18R (**−28.70R**; Entfallen 44 mit **+25.05R** netto — 12G vs 32V; Neu 21 netto −3.64R). Konsistenz exakt ✓. **Cold-Start in P1/P2 kaum relevant** (S1 0, S2 3 Stk −2.45R); entfallene Gewinner über die GANZE Periode verteilt. **Option 3 FALSSIFIZIERT:** E2/E3-Filterung kostet Σ −82.8R über alle Fenster, baut keine Verluste ab → Entscheidung User/Mentor über Optionen (1) E3-Fallback „kein Anker → Baseline-Verhalten", (2) E2 als Tier-2-Override statt Gate, (3) v1 nur als Schatten. KEIN Code-Eingriff vor Entscheidung. |
| 02.09.2026 | E3-Fallback v0.2 | **Mentor-Entscheidung + Design v0.2 ARRETIERT** (`docs/reclaim_signal_loop_design.md` v0.2): **Option 1 — E3-Fallback.** Analyse: P5-Schutz hängt NICHT am `None`, sondern an der aktiven Tier-2-Verdrängung mit E4-Gate (Anker 66.364 in 12×-Reichweite, `penetriert=False` → U_eff=None). `None` bei `anch is None` = Arbeitsverweigerung (OOS-Befund: Entfallen-Listen netto-Gewinner). **Neue Invariante:** `anch is None ⇒ edge = lokal_kante, tier = 1, bestaetigt = False` — nie `None` im Makro-Pfad. **Klassifikation:** `tier=1`+`bestaetigt=False` = Fallback (Baseline-Regeln: Durchstich ohne 0.15-Hürde, `min_bounce`-Hürde aktiv); `tier=2` = E4-Gate + keine Bounce-Hürde (§9.4). P5-Schutz-Beweis §2.1 formal dokumentiert; §8-Regression (AUG P2/P7/P9 kehren zurück, P5-Konter bleiben entfallen, Erwartung AUG > +24.97R); §9-Punkte 3/4 arretiert; §11-Versions-Historie. **KEIN Code vor Abnahme des v0.2-Entwurfs durch User/Mentor.** |
| 02.09.2026 | E3-Fallback Code | **E3-Fallback implementiert & validiert (User-Freigabe):** `scripts/macro_persistence.py` — `return None`-Zweig ersetzt durch Tier-1-Fallback (`edge=lokal_kante, tier=1, bestaetigt=False, anchor=None`); E4-Block (Z. 380–387) gibt `tier==1` automatisch Durchstich-Penetration (Konsument Z. 1038/1050 unverändert korrekt); Docstring E3/Returns v0.2-Semantik. Logik-Test `test/tmp_resolve_edge_check.py` auf v0.2 umgestellt (Test 3: Fallback statt None) ✓. **AUG-IST v0.2: 23 Sig / +23.91R (Delta −1.06R)** — P2/P9 zurück, P5-Konter eliminiert, ABER **P7 +4.26R noch entfallen** (Tier-2-Override durch überrundeten Anker 65.994 < close 67.13 → Diagnose `test/tmp_v02_p7_diag.py`). |
| 02.09.2026 | E5-Seiten v0.3 | **P7-Diagnose + E5-Seiten-Konsistenz (v0.3) ARRETIERT & IMPLEMENTIERT:** `best_local_macro_anchor` filtert Vektor statt Radius (`UPPER: center > close − tol`, `LOWER: center < close + tol`; `side_tol=PENETRATION_TOL` = E4-Dual — beweisbar kein E4-Kandidat verloren; striktes `center>close` würde next_bar-Tier-2 +6.90R töten). P7: alle UPPER-Zonen (65.99–66.58) unter close 67.13 → verworfen → anch=None → Fallback → U_zone 67.157. **AUG-IST v0.3: 24 Sig / +28.17R = Baseline +3.20R** — P2/P7/P9 zurück, 4 P5-Konter eliminiert, 17:45 Tier-2 @ 66.364 +6.90R (statt 18:45 +6.71R), P7-19.08-21:45-Loser ersetzt durch Tier-2 66.382 (30 min früher). P5-/P7-Beweis in `docs/reclaim_signal_loop_design.md` §2.1/§2.2, §8-Punkte 4/5 IST-Zahlen, §9.2, §10.2, §11 v0.3. Diagnose: `test/tmp_v02_p7_diag.py`. **Nächster Schritt: S1/S2-OOS mit v0.3** (Erwartung nahe Baseline). |

---

## 1. Ausgangslage / Problem

**Befund P5 (14.–18.08.2026):** Im aufsteigenden Arm lief die *laufende* Volume-Zone
der frischen Phase dem Preis hinterher (Oberkante 64.16 → 65.80). Dadurch wurden
5 Konter-SHORTs an einer **Trailing-Kante** ausgelöst → 5× −1R. Erst als der Preis
die **etablierte** Kante 66.28/66.45 erreichte (vorher mehrfach getestet), kamen
2 Gewinner (+6.7R). Dieselbe Signal-Logik, gleiche Umgebung — einziger Unterschied:
**Kanten-Historie/-Qualität**.

**Weitere Befunde (validiert):**
- Struktur-Regel, Kante-SL, 3-Eck+Cap: alle 3 nicht OOS-robust → kein hartes Filtern.
- `MIN_SIGNAL_ABSTAND_BARS=8` ist einziger stabiler Gewinner (CD-Sweep, beide Samples).
- Harte Distanz-Schwelle Entry→POC (≥1.5%) wäre destruktiv (23/27 August-Signale
  verfehlten sie, inkl. der guten 66.28-Trades) → **weiches Scoring statt harter Filter**.

---

## 2. Paradigmenwechsel (Leitidee)

```
ALT:   Pivots → Phasen-Segmentierung → je Phase frische Volume-Zone
       → Reclaim gegen "laufende Zone" (Trailing-Problem)
NEU:   Pivots + Volumen → KANTENSPEICHER (Level mit Gedächtnis)
       → aktiver Korridor = relevante starke Kanten um den Preis
       → Reclaim NUR an etablierten Kanten des Korridors
       → TP1/TP2 = nächste starke Level (statt POC/Box-Ende)
```

**Die "Phase" ergibt sich automatisch aus dem Speicher** — nicht umgekehrt.
Eine Kante lebt weiter, bis sie widerlegt wird (nicht bis ein Phasen-Ende sie abschneidet).

---

## 3. Datenfluss

1. **Input:** OHLCV (M15, UTC) — wie bisher aus `data/market_data.duckdb`.
2. **Events:** bestätigte H/L-Pivots (Pivot-Lag), Volumen-Cluster-Peaks,
   Breakout-Punkte, Reclaim-Touches.
3. **Kantenspeicher:** Matching + Verschmelzung + Score (zeitgedämpft).
4. **Korridor:** aktive Level um den Preis → obere/untere Signal-Kanten.
5. **Setup-B-Logik** (Reclaim/Fakeout) gegen Korridor-Kanten, kausal bar für bar.
6. **Trade-Management:** SL wie gehabt (SL_PCT); TP = nächste Level.

**Kausalität (invariant):** Nur Daten bis Bar *k*; kein finales Screening;
kein unbeschränkter Loop (sequentielle Iteration terminiert).

---

## 4. Level-Objekt (Code: `EdgeLevel`)

```python
@dataclass
class EdgeLevel:
    edge_id: int
    side: Literal["UPPER", "LOWER"]     # SHORT- bzw. LONG-Relevanz
    price: float                        # verschmolzener Band-Mittelwert
    birth_ts: pd.Timestamp
    last_touch_ts: pd.Timestamp
    status: Literal["candidate", "active", "sleeping", "discarded"]
    touches: list[EdgeTouch]            # Historie, s.u.
    # abgeleitet/cached:
    n_touches: int
    score: float
```

```python
@dataclass
class EdgeTouch:
    ts: pd.Timestamp
    kind: Literal["H", "L"]             # Pivot-Seite
    price: float
    tick_volume: float
    touch_type: Literal["pivot_test", "volume_cluster",
                        "reclaim", "breakout", "counter_run"]
    follow_swing: float                 # Folge-Ausschlag nach Touch (in R)
```

**S1-Umsetzung (02.09.):** `status` nutzt in S1 nur candidate/active/sleeping
(discarded folgt). `touch_type` in S1: `pivot_test` (Normaltest),
`volume_cluster` (High-Volume-Touch), `counter_run` (gegenläufiger Pivot an
sleeping, §7.3). `reclaim`/`breakout` werden erst ab S3 an Signal-Bars erzeugt.
`follow_swing` ist post-hoc (S2+).

---

## 5. Lebenszyklus eines Levels

1. **Erzeugung (candidate):** Preis-Reaktion außerhalb `EDGE_TOL` (≈ bisher
   `DENSITY_BAND`) aller bestehenden Level → neues Kandidaten-Level.
2. **Matching (Verschmelzung):** Reaktion innerhalb `EDGE_TOL` eines bestehenden
   Levels → **Touch** anhängen, Level-Preis als gewichteter Mittelwert nachführen
   (nicht springen).
3. **Reifung:** Kandidat → **active** erst bei ≥ `MIN_EDGE_TOUCHES` unabhängigen
   Touches **oder** 1 Touch mit hohem Volumen (institutionelle Reaktion).
   Bis dahin: keine Signale an diesem Level.
4. **Schlafen:** Nach klarem Breakout / starker Levelverschiebung (2-Close) →
   **sleeping** (bleibt als Konfluenz-Referenz in den Bins, keine Signal-Kante).
5. **Re-Aktivierung (Q6, 02.09.):** sleeping + bestätigter Pivot **gleicher
   Orientierung** (H an `UPPER` / L an `LOWER`) innerhalb `EDGE_TOL` =
   Re-Validierung (fehlgeschlagener Bruch, erneuter Test von der Bruch-Gegenseite)
   → zurück auf **active**; Historie bleibt intakt. **Kein Zeitfenster** (kein
   `REARM_WINDOW_BARS` — Parameter-Willkür/Overfit). Gegenläufiger Pivot an
   sleeping (L an UPPER / H an LOWER) = `counter_run` (Rollen-Tausch) → bleibt
   sleeping.
6. **Verwerfen:** Nur bei Widerlegung (mehrfach ohne Reaktion durchlaufen).

**Begrenzung:** Matching statt Neuanlage + sleeping-Status verhindern Speicher-Explosion
(Lehre: Riesen-Box B21, 30 Phasen). Optional Cap auf aktive Level.

---

## 6. Confluence-Score (weich, gewichtet)

**S2-Umsetzung (02.09.) — inkrementell statt Σ-Neuberechnung:**

```python
score(lev, k) = d · score(lev, k-1) + touch_contrib(k)     # d = exp(-1/HALF_LIFE_BARS)
touch_contrib = w_volume · rel_volume + w_type[touch_type]
              + w_count   (nur wenn unabhängiger Touch, spacing erfüllt)
```

Jeder Touch addiert seinen gewichteten Wert; ohne frische Touches zerfällt der
Score **pro Bar** um Faktor `d` (stetig). Die Σ-Formel unten ist die äquivalente
statische Sicht (Summe der gedämpften Beiträge) — der Code pflegt sie inkrementell
(EWMA-äquivalent, verifiziert auf 1e-13).

```python
# Statische Sicht (äquivalent):
score(edge) = Σ over touches:
    (w_volume·rel_volume + w_count·indep + w_type) · exp(-age_bars / HALF_LIFE_BARS)
  + w_grid    · grid_bonus(price)          # = 0 bis S4 (reines Neben-Gewicht)
  + w_session · session_bonus(ts)          # = 0 bis S4 (reines Neben-Gewicht)
```

**Architektur-Vorgaben (User, 02.09. — unmissverständlich):**
- `rel_volume(touch)` = `tick_volume / ROLLIERENDER MEDIAN` der vorangegangenen
  `VOL_REF_LOOKBACK`=200 Bars (≈50 h M15), `shift(1)`. **NIEMALS** Division durch
  den Gesamtdurchschnitt des Datensatzes (Lookahead!).
- **Decay auf Handelszeit = Bars:** `EDGE_HALF_LIFE_BARS`=2880 (≈30 Handelstage
  bei 96 M15-Bars/Tag). 1 verarbeitete M15-Zeile = 1 Schritt. Wochenenden/
  Feiertage altern keine Kante (existieren nicht als Bars).
- **Inkrementell:** jeder neue Touch lädt den Score auf; sonst stetiger Zerfall.

**S2-Defaults (Kalibrierung in S4-Sweep, nie nur S1):** `w_volume`=1.0,
`w_count`=0.5 (je unabhängigem Touch), `w_type` = {pivot_test: 1.0,
volume_cluster: 1.5 (institutionelle Reaktion > Test), counter_run: 1.2}.
`w_grid`/`w_session` bleiben **0** — nicht vor S4 anfassen (User-Vorgabe).

**ANTI-OVERFIT-LEITPLANKE (User-Warnung 02.09., unmissverständlich):**
Der Score bleibt **schlank** — exakt die institutionellen drei Komponenten:
Preisstabilität (hält das Niveau? → wiederholte unabhängige Touches `w_count`),
Volumen bei Interaktion (→ `w_volume·rel_volume`), Relevanz im Zeitkontext
(→ Decay `exp(-Δt/HL)`). **Niemals** den Score durch viele additive Parameter
künstlich aufblähen („Level muss 15 Bedingungen erfüllen" = klassisches
Curve-Fitting-Monster, glänzt auf AUG und bricht in S2 sofort ein). Der Decay
wirkt als **multiplikativer Faktor auf jeden Touch-Beitrag** (statische Sicht
unten) — er ist **kein zusätzlicher additiver Parameter** in der Summe. In der
User-Notation `Score = Σ (w_vol·rel_vol + w_count + w_type)·exp(-Δt/HL)` ist
`exp(-Δt/HL)` genau dieser Faktor. `w_grid`/`w_session` (Abschnitt 10.2/10.3)
sind die EINZIGEN vorgesehenen späteren Ergänzungen (je +1 Gewicht, reine
Neben-Gewichte, = 0 bis S4) — keine darüber hinausgehende Parameter-Kaskade.

**Rolling-Volume-Baseline (User-Warnung 02.09., peinlich genau):**
`rel_volume(touch)` wird **strikt** gegen den rollierenden Median der
**vorangegangenen** `VOL_REF_LOOKBACK` Bars berechnet (`shift(1)`) — **niemals**
gegen das globale Phasen- oder Dateiende (Lookahead!). Validierung:
`test/reclaim_s2_score.py` — 344/344 Touches exakt ✓ (siehe Update-Log S2).

**Lehre (Struktur-Regel, Distanz-Test):** Der Score ist **Ranking-Faktor**,
keine harte An/Aus-Schwelle. Im ersten Prototyp: Filter-Schwelle, aber kalibriert
über alle 3 Fenster, nicht auf August.

**WICHTIG (User-Klärung 02.09.):** Preisraster (w_grid) und Zeitfenster (w_session)
sind **KEINE eigenständigen Kriterien/Filter**. Sie sind ausschließlich
**Zusatz-Gewichte innerhalb des Confluence-Scores** — sie erhöhen/senken den Score
einer Kante, schalten aber nie selbst Signale an/aus und sind nie alleiniges
Auswahlkriterium. (Details: Abschnitt 10.2 / 10.3.)

---

## 7. Kern-Bausteine (User-Vorgaben)

### 7.1 Zeitliche Abklingung (Decay)
- **Handelszeit = Bars (User-Vorgabe 02.09.):** Alter zählt in **verarbeiteten
  M15-Bars** (1 Zeile = 1 Schritt), NICHT in Wanduhrzeit. Wochenende/Feiertag
  altern keine Kante, weil keine Auktion stattfand (keine Bars im Datensatz).
- Halbwertszeit `EDGE_HALF_LIFE_BARS` (Default 2880 ≈ 30 Handelstage), Parameter.
- Alter ist **kein Ausschluss**, sondern Gewicht: Ein altes Level mit vielen
  Touches verliert nur langsam; frische Touches laden den Score wieder auf.
- Löst den Konflikt „Frische tabu vs. alte Kante wertvoll" auf:
  Ein Level mit vielen historischen Touches kann einen frischen 2-Touch-Level
  überwiegen, wenn es regelmäßig erneut getestet wird.

### 7.2 Volumenabgleich
- Touch mit `tick_volume >> rollierender Median` = institutionelle Reaktion → hohes Gewicht.
- Mini-Volumen-Touch = Rauschen → niedriges Gewicht (kein Ausschluss).

### 7.3 Alte Peaks im Gegenlauf (Counter-Run)
- **Präzisierung (Q6, 02.09.):** `counter_run` = **gegenläufiger** Pivot an einem
  schlafenden Level: alte UPPER-Kante, die der Preis nach einem Bruch **von oben**
  erreicht und die ihn stützt = Rollen-Tausch (Resistance → Support). Solche Level
  bleiben `sleeping`, erhalten aber den Bonus (`counter_run`) für die spätere
  Score-Bewertung.
- **Gleiche Orientierung ist KEIN counter_run:** Ein H-Pivot an einer schlafenden
  UPPER-Kante (Preis erreicht sie erneut von unten, Ablehnung) ist eine
  **Re-Validierung** → Level wird wieder `active` (Q6, Abschnitt 5.5). Der häufige
  Denkfehler „SHORT an altem Hoch = counter_run" ist falsch — ein erneuter Test
  der Oberkante von unten bleibt ein `UPPER`-Test (Sweep/Reclaim).
- Der Speicher kennt beide Rollen (geometrisch über Preis vs. Level); der
  Korridor wählt ohnehin nach Lage (über/unter dem Close).

---

## 8. Trailing-Erkennung (Kernregel gegen P5-Muster)

Ein Level ist **trailing/unbrauchbar**, wenn:
- sein Preis sich **wiederholt mit dem Markt mitbewegt** (Verschiebung > `TRAIL_SHIFT`
  in < `TRAIL_WINDOW` bei ≤ 1 Touch pro Position), **und**
- es **keine unabhängigen alten Touches** hat.

Ein Level ist **etabliert**, wenn:
- es über längere Zeit **stabil** lag und
- **mehrfach zu verschiedenen Zeiten** getestet wurde (66.28/66.45-Fall).

**Wirkung:** Die 5 P5-Konter-SHORTs entstehen nicht (wanderndes Level bleibt unter
Score-Schwelle); die 2 Gewinner an 66.28 bleiben (Level hatte schon P2–P4-Touches).

---

## 9. Signale & Ziele (Setup B auf Kanten)

- **Kandidat:** Bar durchsticht eine **active** Korridor-Kante und schließt zurück
  (`in_bar` / `next_bar` wie bisher).
- **R:R-Filter:** Distanz-Mindestwert (User-Idee) wird daten-kalibriert eingebaut —
  z. B. Distanz ≥ `MIN_EDGE_DIST_PCT` **oder** CRV ≥ `MIN_CRV_HIGH`, mit Ausnahme
  für hoch-Score-Kanten. Keine harte 1.5%-Regel (destruktiv, s. Abschnitt 1).
- **TP1/TP2:** nächste starke Level in Trade-Richtung (statt POC/Box-Ende);
  POC bleibt Referenz.
- Cooldown (`MIN_SIGNAL_ABSTAND_BARS=8`) bleibt.

### 9.1 Aktiver Korridor = **letzte ungebrochene Kante** (Design-Entscheidung Q2, 02.09.)

**Regel:** Es zählt **strikt die den Preis einengende Kante** — also die **letzte
ungebrochene** Level-Grenze, nicht die stärkste Kante in Reichweite.

- **SHORT-relevant:** das aktive `UPPER`-Level **über** dem Preis, das zuletzt
  **nicht gebrochen** wurde (kein Close darüber). Preis liegt darunter.
- **LONG-relevant:** das aktive `LOWER`-Level **unter** dem Preis, das zuletzt
  **nicht gebrochen** wurde (kein Close darunter). Preis liegt darüber.
- **Bruch-Definition:** Ein Level gilt als gebrochen, wenn der Preis **nachhaltig**
  (2-Close + optional Volumen/Impuls, vgl. 10.4) darüber/darunter schließt.
  Danach: Level → `sleeping`; das **nächste** Level in Bewegungsrichtung wird
  die neue einengende Kante (bzw. der Bruchpunkt wird neues Level).
- **Re-Validierung (Q6):** Ein Bruch ist nur dann „echt", wenn der Markt die Kante
  hinter sich lässt. Kehrt der Preis zurück und wird an der schlafenden Kante
  erneut abgewiesen (Pivot gleicher Orientierung in `EDGE_TOL`), war der Bruch
  fehlgeschlagen → Level wird wieder `active` (Abschnitt 5.5). Genau dadurch blieb
  die 66.28-Zone (Bruch am 12.08, Rückkehr 17./18.08) handelbar.
- **Signal:** Reclaim/Fakeout passiert **an der einengenden Kante** (Durchstich +
  Rückschluss in den Korridor).

**Bekannte S1-Korridor-Schwäche (User, 02.09.):** Die S1-Vereinfachung (nächstes
aktives Level über/unter dem Close) fällt nach einem Breakout ins Leere: Der Close
liegt jenseits der gebrochenen Kante (→ sleeping); bis ein neuer gegenseitiger
Pivot entsteht, ist die Korridor-Seite unter/über dem Kurs **None** → Reclaims im
Niemandsland unmöglich (z. B. kein LONG-Level nach Up-Breakout). **Fix in S3:** Der
Korridor folgt der „letzten ungebrochenen Kante" (Q2): Die gebrochene Kante bleibt
als Referenz, der **Bruchpunkt wird neues Level** (10.4); damit existiert nach
einem Breakout sofort eine neue einengende Kante in Bewegungsrichtung.

**Begründung / Wirkung:**
- Verhindert das **P5-Trailing-Artefakt**: Die wandernden VAH-Werte (64.31 → 65.80)
  waren keine etablierten, ungebrochenen Level — sie wurden auf dem Weg nach oben
  jeweils **gebrochen** (Preis schloss darüber) und wären daher `sleeping`/irrelevant.
  Erst die **echte** ungebrochene Kante 66.28/66.45 bleibt aktiv → genau dort
  entstehen die guten Signale.
- Erfüllt den **Akzeptanzfall 18.08 ~02:00**: Eine Kante bleibt aktiv, **bis sie
  gebrochen wird** — nicht bis ein willkürliches „Phasenende" sie abschneidet.
- Erzwingt die **Swing-Memory-Sicht (10.1)**: Die „letzte ungebrochene Kante"
  ist genau der letzte gültige Gegenpart der Berg/Tal-Kette (letztes HH/HL bzw.
  LH/LL). Korridor-Auswahl und Swing-Memory werden damit **eine** Logik.

---

## 10. Erweiterungen (Phase 2+, noch NICHT umgesetzt)

### 10.1 Swing-Memory: Berg/Tal-Kette (User 02.09.)
- **Idee:** In einer Aufwärtsbewegung wird auf **alte Pullback-Täler** geachtet
  (Unterstützung), in einer Abwärtsbewegung auf **alte Pullback-Peaks**
  (Widerstand). Es gibt ein Gedächtnis über Berg/Tal-Verläufe über Wochen/Monate.
- **Begrenzung:** Immer nur **bis zum letzten gültigen Gegenpart** — d. h. die
  Kette wird von der jüngsten gültigen Struktur (letztes Higher-Low / Lower-High)
  rückwärts gelesen; ein Bruch invalidiert den jeweiligen Ketten-Abschnitt.
- **Modell:** `SwingMemory` = verkettete Swing-Punkte (Peaks/Valleys) je
  Richtungs-Phase; relevante Level = ältere Täler (bei up) bzw. ältere Peaks
  (bei down), gewichtet mit Confluence (Abschnitt 6).
- **Zweck:** Präzisiert, WELCHE alten Level relevant sind — nicht alle, sondern
  die strukturell verankerten (Anti-Trailing).

### 10.2 Preisraster (w_grid) — NUR Score-Gewicht, kein eigenes Kriterium
- Kanten auf **festen Preislinien** sind stärker (psychologische/Level-Grid) →
  sie erhalten einen **Zuschlag im Confluence-Score** (`w_grid`).
- **Parameter:** `PRICE_GRID_STEP` (Silber aktuell ~0.50 USD), muss variabel sein.
- Bonus, wenn `|price mod PRICE_GRID_STEP| <= GRID_TOL` → additiv auf den Score.
- **Kein Filter:** Eine Kante, die nicht auf dem Raster sitzt, wird dadurch NICHT
  ausgeschlossen — ihr Score ist nur entsprechend niedriger.

### 10.3 Zeitfenster (w_session) — NUR Score-Gewicht, kein eigenes Kriterium
- Peak/Kanten-Touch zur **halben oder vollen Stunde ± 5 Minuten** (Session-/
  Fixing-Zeiten) → **Zuschlag im Confluence-Score** (`w_session`).
- M15-Bars mit `minute in {0, 30}` ± 5 min → additiv auf den Score.
- **Kein Filter:** Ein Touch außerhalb dieses Zeitfensters wird dadurch NICHT
  verworfen — sein Gewicht ist nur entsprechend niedriger.

### 10.4 Levelverschiebung & Ausreißer (User 02.09.)
- **Levelverschiebung:** Nach echtem Breakout (2-Close + Impuls/Volumen) wandert
  der aktive Korridor; die alte Kante wird `sleeping`, der Bruch-Punkt selbst wird
  neues Level (Breakout = künftige Support/Resistance).
- **Ausreißer:** Einzelne Extrem-Pivots ohne Folge-Volumen werden markiert, aber
  nicht zu Leveln.
- **Regime:** Trend (wenige, weit entfernte Level) vs. Range (dichte, starke Level)
  ergibt sich automatisch aus der Level-Dichte.

---

## 11. Ablösung bisheriger Konzepte

| Bisher | Neu |
|---|---|
| Phasen-Segmentierung als Signal-Basis | aktiver Korridor aus Leveln |
| frische Zone je Phase (Trailing-Problem) | etablierte Kanten mit Gedächtnis |
| TP1 = POC, TP2 = Box-Ende | TP = nächste starke Level |
| Frische-Kanten-Regel (Alter = tabu) | Alter = Decay-Gewicht |
| harte Struktur-/Legitimitäts-Filter | weicher Confluence-Score |
| „Phasenende" schneidet Kante ab | Kante lebt weiter bis Widerlegung |
| Geburtszonen/Projektionen (verworfen) | entfällt |

**Hinweis (Q4, 02.09.):** Die bisherige Phasen-/Volume-Zonen-Logik des Hauptskripts
wird **NICHT als Level-Seed-Quelle** verwendet (widerlegt). Sie bleibt nur als
**Diagnose-/Parity-Werkzeug** im Prototyp (zeitsynchroner A/B-Vergleich Bar für Bar),
damit Abweichungen von der Baseline sofort lokalisierbar sind („hätte Phase 5 hier
geblockt?").

---

## 12. Validierungsplan & Akzeptanzkriterien

1. Prototyp in `test/` bauen, kausale Basisfunktionen via exec-Import
   (Arbeitskopie, `test/reclaim_*`).
2. **Von Anfang an 3 Fenster:** AUG (10.–28.08.26), S1 (02.–08.26), S2 (2025).
   Kein Tuning erst auf AUG/S1 (Lehre v6+Cap).
3. **Akzeptanzfälle:**
   - Die 5 P5-Konter-SHORTs entstehen nicht mehr; die 2 Gewinne an 66.28 bleiben.
   - Fall 18.08 02:00 (Kante blieb nach altem Phasenende gültig) wird gehandelt.
   - S2-Summe R ≥ Baseline (+99.88R, CD=12) bzw. (+110.79R, CD=8) = hartes OOS-Kriterium.
4. Weiche Parameter (`EDGE_HALF_LIFE`, `EDGE_TOL`, Score-Schwelle, Distanz) als
   Defaults → 3-Fenster-Vergleich; danach ggf. Sweep über beide Samples (nie nur S1).
5. **Keine Übernahme ins Hauptskript ohne User-Freigabe.**

---

## 13. Code-Konventionen

- **Kommunikation/Doku:** Deutsch. **Code (Identifier, Kommentare im Code):** Englisch.
- Google-Stil-Docstrings, Type Hints, Dataclasses.
- Vektorisierung pur; einzige Ausnahme: sequenzieller kausaler Signal-Loop (bewusst).
- MT5-Epochs = Berlin-Wanduhr; SQL strikt `AT TIME ZONE 'UTC'`.
- Test-Dateien & Test-DBs in `test/`; keine UI-/Regressionstests.

---

## 14. Offene Design-Fragen (agil, Runde 1)

1. ~~**Level-Quellen:** Nur H/L-Pivot-Reaktionen — oder sofort + Volumen-Cluster-Seeds?~~
   **ENTSCHIEDEN (02.09.):** Nur **Pivot-Reaktionen als Seed**; Volumen-Cluster nur als
   **Touch-Typ** am bestehenden Level (kein eigener Seed) → Update-Log Q1.
2. ~~**Aktiver Korridor:** Stärkste OBEN-/UNTEN-Kante in Reichweite — oder strikt die
   den Preis einengende (letzte ungebrochene)?~~ **ENTSCHIEDEN (02.09.):** strikt
   die **letzte ungebrochene** Kante → Abschnitt 9.1. (Konsequenz für Q5 s.u.)
3. ~~**TP-Logik:** Nächstes Level als TP2 ersetzen — oder zunächst nur zusätzlich ausweisen?~~
   **ENTSCHIEDEN (02.09.):** Nur **zusätzlich ausweisen** (Schatten-Tracking
   `target_level_price`/`target_level_hit`/`r_level`); Baseline-Exit bleibt bis S3/S4 →
   Update-Log Q3.
4. ~~**Phasen komplett raus** — oder bestehende Segmentierung als Level-Seed-Quelle behalten?~~
   **ENTSCHIEDEN (02.09.):** Phasen **raus aus der Signal-Entscheidung**, aber als
   **Diagnose-/Parity-Werkzeug** im Prototyp behalten (A/B-Vergleich Bar für Bar).
   **Keine Phasen-Seeds** → Update-Log Q4.
5. ~~**Swing-Memory (10.1):** Durch Q2-Entscheidung **zentral für Phase 1** (Korridor =
   letzte ungebrochene = letzter gültiger Gegenpart der Kette). Zu klären: konkrete
   Umsetzung der Kette (HH/HL/LH/LL-Bestätigung, kausal mit Pivot-Lag).~~
   **ENTSCHIEDEN (02.09.):** Auf **S3 verschoben**. S1 nutzt einfachen Korridor
   (nächstes aktives Level über/unter Close) → Update-Log Q5.
6. ~~**Umgang mit fehlgeschlagenen Breakouts / schlafenden Leveln** (ausgelöst durch
   S1-Befund: 66.28-Zone nach 12.08-Bruch sleeping, Rückkehr 17./18.08 nur
   counter_run → Gewinner strukturell unmöglich).~~ **ENTSCHIEDEN (02.09.):** Q6 —
   **Pivot-Re-Aktivierung** gleicher Orientierung, kein Zeitfenster → Abschnitt 5.5
   + 7.3 + 9.1. Akzeptanzfall 2 strukturell wiederhergestellt.
7. ~~**Exit-Definition im phasenlosen Modell** (Baseline-TP1=POC ist phasengebunden).~~
   **ENTSCHIEDEN (02.09., Q7):** Option A — **Rolling-VP-POC als TP1** (300er-
   Fenster, kausal), TP2 = Profil-Gegenseite + Puffer; Entry-Filter bleibt;
   Level-TP als Schatten (Q3) → Update-Log Q7.
8. **OFFEN (S3-v2): Regime-/Qualitäts-Gate.** S3-v1 roh verliert auf S1/S2
   (−73.9R/−47.2R vs. Baseline +197/+100R). Zur Wahl (User): A) Range-Gate
   (2-seitiger Korridor, beide Seiten frisch, Spread-Minimum, keine frische
   Richtungs-Verschiebung), B) Breakout-Momentum-Sperre (keine Fades innerhalb
   X Bars nach 2-Close-Bruch; erst nach Q6-Reaktivierung wieder), C) Swing-
   Memory-Regime (10.1: Berg/Tal-Kette bestimmt, welche Seite lebt — in
   Up-Swings nur LONG-Reclaims an Tälern, SHORT nur an HH-Kante nach
   Strukturbruch), D) Baseline-Range als reines Gate (Range-Definition des
   Hauptskripts NUR als Filter, nicht als Signalquelle — Q4-Kompromiss).

---

## 15. Schrittplan (agil)

- [x] **S1:** Level-Objekt (`EdgeLevel`/`EdgeTouch`) + Matching/Lebenszyklus
      inkl. Q6-Re-Aktivierung (Abschnitt 4/5), Seeds ausschließlich aus
      n=2-Pivots (Q1). Korridor-Vereinfachung (Q5): nächstes aktives Level
      über/unter dem Close. Volumen als Touch-Attribut. Kausale Snapshots.
      Datei: `test/reclaim_edge_store.py` (P5-Verifikation, 3-Fenster-Lauf OK).
      *Offen:* Parity-Beobachter (Q4) wird erst beim S3-Signal-A/B benötigt.
- [x] **S2:** Confluence-Score v1 (Decay + Count + Volume, Abschnitt 6/7)
      — inkrementell `d·score + touch_contrib`, rel_volume = roll. Median (200,
      shift 1), Decay auf Bars. Validierung: `test/reclaim_s2_score.py`
      (V1 344/344 exakt; V2/V3 == EWMA-Summe, max Abw. 1e-13).
- [ ] **S3:** Signal-Loop + Exit/TP + Regime-Gate — **v1 gebaut**
      (`test/reclaim_s3_signals.py`): Setup-B-Loop inline im Store-Build
      (on_bar-Hook), Rolling-VP-Exit (Q7), Schatten-Level-TP (Q3).
      3-Fenster-Referenz: AUG +31.89R ✓ wirtschaftl. (Fall 1 strikt ✓,
      2+3 wirtschaftl. ✓), **S1 −73.90R, S2 −47.17R → roh NICHT tragfähig**.
      Bucket-Analyse: kein robuster Einzelfilter. **v2 (Gates A+B) gebaut &
      validiert** → kein Turnaround (S1 −103.9R, S2 −65.1R A+B; Gate A
      destruktiv, Gate B hilft nur S2). **v3 offen: Range-/Regime-Erkennung**
      (Entscheidung User) — Swing-Memory (10.1), Trailing-Erkennung,
      Korridor-Fix „Bruchpunkt wird Level" (9.1/10.4) bleiben vertagt.
- [ ] **S4:** 3-Fenster-Validierung (Abschnitt 12), Akzeptanzfälle P5 + 18.08
- [ ] **S5:** Erweiterungen Phase 2 (Abschnitt 10) nach User-Priorisierung
- [ ] **S6:** Review + ggf. Übergang ins Hauptskript (nur mit Freigabe)
