# -*- coding: utf-8 -*-
"""Handoff-Checkpoint E-34n/15 (V019-Komplett-Audit) -- Append.

Vorbedingungs-gated (Datei-SHA, Binaer-I/O wegen CRLF).
Abschnitt ist ASCII-only (Umlaute ae/oe/ue, Paragraph erlaubt).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
VORBEDINGUNG = "57252892ce1308964c859bb9dc215e5b5c96fe9e407b018512dec7221f63be1d"

ABSCHNITT = """

## Phase 2 / E-34n/15 (2026-09-11, af) - V019-KOMPLETT-AUDIT: FUENF ANWENDERFRAGEN, KAUSALITAETS-MESSUNG, FALLEN FUER MORGEN

Auftrag (Anwender): kompletter Check der V019-Version in fuenf Punkten --
(1) wirklich generischer Ansatz (andere Kursverlaeufe, andere Marktregime)?
(2) etwas uebersehen? (3) irgendwo unnoetig abgebogen? (4) Ziele verfehlt?
(5) Lookahead oder feste Nutzereingaben, die nicht live-faehig sind?

**Rein lesend**: Engine, Renderer, Adapter und Handoff blieben waehrend der
Untersuchung byte-identisch; neu sind nur read-only Pruefskripte und dieser
Checkpoint. Kein Paragraph 75, kein S1, keine S2-Laeufe, keine UI-/
Regressionstests, kein `git add -f`.

### D1 - Vorbedingung und Anker

Vorbedingung: Handoff-SHA
`57252892ce1308964c859bb9dc215e5b5c96fe9e407b018512dec7221f63be1d`
(352.405 B / 6.246 Zeilen, aus E-34n/14) - vor dem Append binaer verglichen.

| Anker | Bytes | SHA256 |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` | 196.649 | `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` |
| `backtest_lab/phasen_regime_adapter.py` | 30.663 | `4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83` |
| `test/tmp_png_aug_sichttest.py` | 109.022 | `7dab7a300e69c4ffae230b1cb547da508dae8a3801cb6a2fed2f63c5bc6d7a28` |

### D2 - Methode: renderer-treuer Harness (keine Nachbildung)

`test/_chk_v019_kausal_vergleich.py` laedt die Pruefbausteine per AST
**direkt aus den arretierten Dateien**:
* die 13 Bestands-Paare (`A_KANTEN` .. `A_KBASIS`) aus `tmp_png_aug_sichttest.py`,
* das Patchset aus der Renderer-Funktion `_wende_zielzonen_patches_v019`
  (5 Paare, per `ast.literal_eval` der `paare`-Liste gelesen),
* `_se_trades` aus der Engine,
* Laufzeit-Injektion `_zv` / `_ueb` / `_reclaim_stufe_lok` wie im Renderer.

**Kontrolle:** der Lauf mit `ADAPTER_V019` ergibt **24 Setups / +88.116626 R**
(H2 16 / +49.197042) - exakt die Arretierung. Damit ist belegt: der Harness
ist nicht nur aehnlich, sondern der Renderer-Pfad selbst (Assert im Skript).

### D3 - Frage 1: generischer Ansatz? - Regel ja, Arretierung nein

**Tragfaehig (zielfrei, marktabgeleitet):** aeusserste lebende Linie
(`b + 2 <= k`, `wall_live_bars = 96`), `_nah`-Band `touch_band_pct = 0.12 %`,
ZP-4 (A_UEB1 / A_VC / A_M6L / A_SB) und ZP-5 (A_KL_DOCHT). Im Automatik-Teil
steht kein Bar- oder Kanten-Literal aus der Vorgabe.

**Plateau unabhaengig nachgerechnet** (Reihenuntersuchung der vorhandenen
`_tmp_e34_auto_MIN*_out.txt`):

| MIN_BARS | Setups | R | Segmente ab 1021 |
|---|---|---|---|
| 0 .. 40 | 23 | +74.054425 | Klippe 1 |
| **41 .. 48** | 23 | **+82.614385** | **3**: 1033..1123 K67/K82, 1124..1173 K73/K85, 1174..1287 K73/K82 |
| **49 .. 114** | 23 | **+82.614385** | **2**: 1033..1173 K67/K82, 1174..1287 K73/K82 |
| 115 .. 260 | 20 | +79.318499 | Klippe 2 |

H1 bleibt in **allen** Varianten **8 / +38.919584** (Invariante haelt).
Zwei Praezisierungen zu E-34b:
1. Das Plateau **[41,114]** gilt fuer das **Ergebnis**, nicht fuer die
   **Struktur**: bei MIN 41..48 sind es drei Segmente (A2 = 1124..1173 mit
   Boden K85), ab 49 zwei. Ursache der Klippe bei 49 ist exakt
   `1124..1171 = 48 Bars`: bei MIN 48 ist das Teilsegment 48 nicht mehr
   zu kurz (`48 < 48` falsch) -> eigener Zweig; bei MIN 49 wird es
   verschluckt (`48 < 49`) -> Kette in A1. Das **Etikett** ist also
   parameterabhaengig, nur der **R-Wert auf AUG** ist unempfindlich.
2. Traegt man die Regel rein kausal (RAW / MIN 0, ohne Hysterese) aus, sind
   es **23 / +74.054425** - d. h. **+8,56 R** des V019-Zugewinns gegenueber
   MIN 0 stammen aus der Zusammenfassungs-Hysterese, nicht aus dem Markt.

**Nicht generisch (drei Klammern):**
* **Kalenderkante hart:** Engine Z. 2200
  `box_end_bar = int(np.searchsorted(ts_arr, np.datetime64("2026-08-19")))`;
  Renderer-Guard Z. 557-560 `if KONF.mode == "V019" and box_end != 644:
  raise SystemExit(...)`. V019 ist damit auf **AUG gepinnt**; jeder andere
  Monat faellt fail-loud aus. `box_end` ist nicht konfigurierbar.
* **Adapter-Fenster sind ein Snapshot** einer datenabhaengigen Rekursion;
  `A2_AUTO_77.end_bar = 1287 = n - 1` ist das **Datenende**, keine
  Marktkante (gleiche Semantik wie der `ENDE`-Exit aus E-34n/14 C2).
* **Hysterese** (`zusammenfassen`) mit Laufzeit entscheidender
  Laengenbedingung - siehe D6.

### D4 - Frage 2: etwas uebersehen? - fuenf Nachtraege, kein Blocker

1. **`verifiziere_gegen_scan` laeuft produktiv NICHT.** Aufrufer im gesamten
   Arbeitsbaum: `test/tmp_dryrun_p12.py` und drei `_tmp_e34*`-Pruefer.
   Der Renderer ruft ausschliesslich `verifiziere_niveau_overrides` und
   `verifiziere_boden_literale` (Import-Zeit, beide bestanden). Die schaerfste
   Adapterpruefung (Kanten gegen den Scan-Katalog) ist **kalt**.
2. **`PhasenReifeKonfiguration` hat keinen Produktionskonsumenten**
   (Kl. Z. 614). Genutzt nur in `_tmp_e34g_syntaxprobe.py`,
   `_tmp_e34g_toleranz.py` und `_tmp_e34h_einbrand_verify.py`. Die
   Plateau-Grenzen `PLATEAU_MIN_BARS=41` / `PLATEAU_MAX_BARS=114` /
   `PLATEAU_REFERENZ_BARS=77` sind damit **dokumentiert, aber nicht
   verdrahtet** - der Adapter `ADAPTER_V019` konsumiert sie nicht.
3. **ZP-4 ist unversehrt - der E-34m/X3-Hash ist nur ein ueberholter Anker.**
   `test/_chk_v019_zp45_probe.py` nimmt genau das fuenfte Paar
   (`A_KL_DOCHT`) zurueck und erhaelt **21.956 Zeichen / SHA256
   `8a3b7070582b620d997c2adfc0bcf3f20e016a94ab97faa84e5143410ee63778`** =
   das ZP-4-Soll. ZP-5 ist mit **+2.029 Zeichen** die einzige Zutat
   (23.985 Zeichen gesamt). **Kein Defekt.**
4. **Signal-Loop `range(2, box_end - 3)`** (Engine Z. 2564); der Renderer
   setzt Z. 562 `scan["box_end_bar"] = n` (Voll-Lauf). Mit `n = 1288` laeuft
   der Loop bis `k = 1284` - die Bars **1285..1287 sind nie Signalbar**
   (3-Bar-Strukturlag zusaetzlich zu Pivot + 2). Ohne den Renderer-Override
   waeren es die Bars 641..1287 (E-33/M0).
5. **Sollkatalog konsistent:** `ziel_r_gesamt=88.116626` und
   `ziel_delta_rb=40.300929  # = 88.116626 - 47.815697 (ZP-5(D))` (Z. 399,
   414) - kein veralteter Assert. Nebenbei: `_hit`/`stats` fuehren weiterhin
   nur die Engine-Zaehler; `HOOK2_BLOCKIERT`/`kein_gegner`/`f3`/`v_s` sind
   nicht im Protokoll ausgewiesen (E-34n P5 bleibt unbelegt).

### D5 - Frage 3: unnoetig abgebogen? - zwei echte Abkuerzungen

1. **ZP-5 als State-Mutation im Scanner.** `A_KL_DOCHT` schreibt direkt in
   den Kantenzustand (`_ek.wicks.append((_kb, _ext))`, `_ek.schlaf_windows =
   [...]`, `_ek.status = "AKTIV"`) - fuer die gesamte Restlaufzeit und ohne
   Idempotenzschutz. Ein vorgelagerter, reiner **Scan-Schritt** (Parameter:
   Segmentwaende + `_ueb`-Schranke) waere das gleiche Ergebnis ohne
   Reihenfolge-Kopplung an die Kinder-/Schlafphasen-Logik. Dass es
   funktioniert, ist gemessen (H1 8 / +38.919584), aber es ist kein Prinzip.
   *Wick-Reihenfolge bleibt harmlos:* `basis_bei` nutzt nur Extrema
   (`min`/`max`), `touch_conf` und `letzter_touch_conf` sind ordnungsfrei;
   nur der Pre-Birth-Fallback liest `wicks[0]`, und ZP-5 haengt nur hinten an.
2. **V-D-Kontrakt v0.24 ist ratifiziert, aber nicht verdrahtet** (Paragraph
   74: `KantenSicht`, `GegenkantenWahl.PHASE_EIGEN`,
   `OeffnungsTrigger.ignoriere_schlafstatus`, `RECLAIM_AT_OPENING`).
   Lebt nur in `test/_tmp_vd_vertrag_entwurf.py` -> zweite Spur ohne
   Produktionspfad. **Kandidat fuer: verdrahten oder ruhen lassen.**
3. **Kein Rueckbau noetig:** `--poolalok` (E-34e S3 verworfen) und
   `--poolhart` (35 Trades, ZIEL 18, `Q_stop` 0.457, USD/Trade +0.086) sind
   belegt verworfen; die Flags existieren nur in der read-only
   Variantenmatrix `_tmp_e34_auto.py`, nicht im Renderer.
4. **Drei Schwellen im selben Lauf** (0.60 `cfg.max_sweep_ueberdehnung_pct`,
   0.80 ZP-4/ZP-5 segment-lokal, 0.12 `touch_band_pct`) - gewollt, aber
   nirgends als Toleranz-Kanon zusammengefasst.

### D6 - Frage 4: Ziele verfehlt? - Zielzone nein, Live-Faehigkeit ja (gemessen)

Gefahren wird ein zweiter Lauf mit **kausal verzoegerten Etiketten**
(Variante B: ein Segmentetikett gilt erst ab `start + MIN_BARS - 1`,
`_nah`-Regel weiterhin am Start entscheidbar) sowie eine Kontrollvariante C
(kausale Etiketten, aber ZP-5-Injektionsfenster der zweiten Wand wie
arretiert):

| Lauf | Setups | R | H2 (entry >= 644) |
|---|---|---|---|
| **A arretiert (Kontrolle)** | **24** | **+88.116626** | 16 / +49.197042 |
| B kausal (Etikett verzoegert) | 23 | **+85.577150** | 15 / +46.657566 |
| C kausal + ZP-5-Fenster alt | 23 | +85.577150 | 15 / +46.657566 |

**Delta A -> B = -1 Trade / -2.539476 R** (= 2,88 % des Gesamt-R).
**B und C sind bit-identisch** -> die Ursache ist **allein das Etikett**,
nicht das Injektionsfenster. Rejektionszaehler: `v_s 24 -> 23`,
`zyklus_blockiert 34 -> 33`, `zyklus_liste 34 -> 33`.
Betroffen: **Bar 1211 SHORT K76 (+2.539476 R)**; alle uebrigen
Zielzonen-Trades (1075, 1122, 1172, 1268, 1272, 1280) sind **bit-identisch**.
Insbesondere ist die ZP-5-Zutat **K82@1172 (+5.5022 R) kausal sauber**
(1172 < 1174 = Beginn der zweiten Wand).

**Struktureller Kern (nicht ausgleichbar):** Der Bar 1211 liegt 38 Bars nach
Beginn der Wand A2 (1174). Jede Plateau-Regel verlangt mindestens MIN Bars
Bestaetigung; mit MIN >= 41 ist das Etikett fruehestens ab Bar **1214**
verfuegbar. Der Trade ist damit **fuer alle MIN in [41, 114] kausal
unerreichbar** - die Hysterese ist hindsight-validiert. Die Ursache im Code
ist `zusammenfassen` (`_tmp_e34_auto.py`): die Bedingung
`(s[1] - s[0] + 1) < min_bars` entscheidet erst am **Ende** des Teilsegments
und faellt die Entscheidung dann **rueckwaerts** (das Etikett des Vorgaengers
wird auf die gemeinsamen Bars ausgedehnt). Konkret fuer A2:
* Das 48-Bar-Stueck `1124..1171` (K73/K85) wird wegen `48 < 77` in A1
  gezogen - entscheidbar bei Bar **1172** (erster Bar des Folgestuecks).
* Das 2-Bar-Stueck `1172..1173` (K73/K60) wird ebenfalls gezogen -
  entscheidbar bei Bar **1174**.
* Dass Bar 1174 wirklich eine **neue** Wand eroeffnet (und nicht
  rueckwirkend in A1 verschmilzt), steht erst fest, wenn `1174..1287` die
  Mindestlaenge erreicht hat: **Bar 1250** (= 1174 + 77 - 1).
Bis dahin gilt kausal das **alte** Etikett A1 (K67/K82, `_q0 = 1033`); mit
diesem Etikett wird Bar 1211 abgelehnt (`zyklus_blockiert`). Die
Rohwechselpunkte (rein kausal, ohne jede Hysterese) sind:

| Rohabschnitt | Bars | kausales Paar |
|---|---|---|
| 1033..1076 | 44 | K67 / K82 |
| 1077..1116 | 40 | K67 / K85 |
| 1117..1119 | 3 | K73 / K85 |
| 1120..1123 | 4 | K78 / K85 |
| 1124..1171 | 48 | K73 / K85 |
| 1172..1173 | 2 | K73 / K60 |
| 1174..1287 | 114 | K73 / K82 |

Die arretierten Fenster werden von der **Batch-Regel exakt reproduziert**
(Assert im Skript), die reine Kausalregel liegt bei **23 / +74.054425**.

### D7 - Frage 5: Lookahead / nicht-live-faehige Eingaben

| # | Punkt | Fundstelle | Wirkung |
|---|---|---|---|
| 1 | Segmentetiketten hindsight-validiert | `_tmp_e34_auto.py::zusammenfassen` | **-2.539476 R gemessen** (D6) |
| 2 | Bestaetigung der Wand A2 (1174) erst ab Bar 1250; bis dahin gilt A1 | ebd. | Ursache von #1 |
| 3 | `A2.end_bar = 1287` ist Datenende, keine Marktkante | `ADAPTER_V019` | Snapshot-Artefakt |
| 4 | ZP-5-Fenster = dieselben Fenster | `A_KL_DOCHT` | in AUG neutral (Lauf C), strukturell abhaengig |
| 5 | `box_end` hart `"2026-08-19"` + Guard `!= 644` | Engine Z. 2200 / Renderer Z. 557 | V019 nur AUG |
| 6 | `A_VC`: `ex_hi = np.max(hi[_q0:k+1])` - segment-lokal gekappt (`_q0 = seg.start_bar`) | Renderer ZP-4 (2) | Design-Entscheidung, Stuetzbereich nicht deklariert |
| 7 | Pre-Birth-Fallback `wicks[0][1]` | `_SEEdgeH.basis_bei` | durch Loop-Untergrenze `erster_pivot + 2` maskiert (E-17-dokumentiert) |
| 8 | Signal-Loop schliesst Bars 1285..1287 aus | Engine Z. 2564 + Renderer Z. 562 | 3-Bar-Strukturlag |
| 9 | Entry `k + 1`, keine Kosten/Slippage/Funding | Engine | nicht live-faehig (bekannt) |
| 10 | Alle Strategie-Parameter aus `cfg`/KONF | - | **erfuellt**, kein Hardcoding |

### D8 - ENTSCHEIDUNGSFRAGEN FUER MORGEN (Klaerung, Textantwort)

**(1) Kausalitaets-Arretierung.** Soll V019 um eine zweite, kausal reine
Kennzahl ergaenzt werden (Basis: **23 / +85.577150**, H1 weiterhin
8 / +38.919584) - als *additiver* Sollwert **neben** 24 / +88.116626 -,
oder bleibt 24 / +88.116626 die alleinige Referenz mit dokumentiertem
Hindsight-Vorbehalt?

**(2) Reichweite der Kalenderkante.** Soll die Engine-Kante
`np.datetime64("2026-08-19")` parametrisiert (z. B. `box_end_datum` in
`cfg`) und der V019-Guard von `!= 644` auf "gleicher Scan wie ADAPTER_V019"
gelockert werden, damit ueberhaupt ein zweites Fenster pruefbar wird?

**(3) ZP-5-Form.** Soll der Kantenlaeufer-Durchstich als vorgelagerter,
idempotenter Scan-Schritt neu gefasst werden (Parameter: Segmentwaende +
`_ueb`-Schranke), oder bleibt die State-Mutation im `_se_trades`-Kopf als
arretiert gelten?

**(4) Kaltes Fail-Loud.** Soll `verifiziere_gegen_scan` in den
V019-Rendererpfad aufgenommen werden - und wird `PhasenReifeKonfiguration`
dabei **verdrahtet** oder als tot markiert/entfernt?

**(5) Wiedervorlage aus E-34n/14.** Unveraendert offen: **Q1** Bilanzierung
(a) +78.127525 vs. (b) +78.216484 und **Q2** Schranke (A) global-2 /
(B) global-2 + Kanten-Cooldown / (C) Cap >= 3.

**(6) Handoff-Nachtrag.** Dieser Audit ist **Arbeitstand, nicht Arretierung** -
er aendert keine der drei Dateien. Soll der Befund als eigener Paragraph
in die Adapter-Spez (v0.24, Paragraph 74) uebernommen werden?

### D9 - Artefakt-Anker E-34n/15 (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/_chk_v019_causal.py` | 3.897 | `6036b88a877c484301f7d560ae86d0e74a5ae362ab35482d8bef2850b1080401` |
| `test/_chk_v019_kausal_vergleich.py` | 13.638 | `dc9d332133766f580b447879ad2577f9ac1f38d8e3f00610a5ebfb64f776494e` |
| `test/_chk_v019_kausal_vergleich_out.txt` | 5.432 | `c5d44e175d0b151038055ec5cb4b12a75b53c5c8ce2e41012839c00a8c950a33` |
| `test/_chk_v019_zp45_probe.py` | 3.286 | `b417d4493a1b422b7d5da0079235046b84cc199d2eccb9a3d2d7215ab48bae6c` |
| `test/_chk_v019_zp45_probe_out.txt` | 1.056 | `14d934dc482b4d521346a12e868d8675c99278ecb9edfe1242259306603dcbde` |
| `test/_tmp_e34m_zp4_soll.txt` | 66 | `7236ec5f79159c2c7030394fd387c34c1132a52ed41c355c0a4fb7fc7eaa124c` |

Unveraendert bleiben die Engine-/Adapter-/Renderer-Anker aus D1;
**kein** Paragraph 75, **kein** S1, **keine** S2-Laeufe, **keine** UI-/
Regressionstests, **kein** `git add -f`.
"""


def main() -> None:
    # Binaer-I/O: der Anker-SHA ist der Datei-SHA (CRLF bleibt erhalten);
    # read_text() wuerde CRLF -> LF normalisieren und den Vergleich brechen.
    vorher = HANDOFF.read_bytes()
    ist = hashlib.sha256(vorher).hexdigest()
    assert ist == VORBEDINGUNG, (
        "Vorbedingung verletzt: Handoff-SHA", ist, "!=", VORBEDINGUNG)
    assert vorher.count(b"\r\n") == vorher.count(b"\n"), "gemischte Zeilenenden"
    anhang = ABSCHNITT.replace("\n", "\r\n").encode("utf-8")
    HANDOFF.write_bytes(vorher + anhang)
    neu = HANDOFF.read_bytes()
    print("OK  bytes", len(neu), "CRLF", neu.count(b"\r\n"),
          "LF", neu.count(b"\n"))
    print("neuer SHA256", hashlib.sha256(neu).hexdigest())
    print("replacement-zeichen", neu.decode("utf-8").count("\ufffd"))
    print("nicht-ASCII im Abschnitt",
          sorted({c for c in ABSCHNITT if ord(c) > 127}))


if __name__ == "__main__":
    main()
