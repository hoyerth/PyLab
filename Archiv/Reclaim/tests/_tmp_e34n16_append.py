# -*- coding: utf-8 -*-
"""Append E-34n/16 (Stufen 1a/1b/2a/2b) an test/SESSION_HANDOFF.md.

ASCII-only, CRLF-erhaltend, mit Vorab-SHA-Assert auf den E-34n/15-Stand.
"""
import hashlib

P = r"F:\Python\PyLab\test\SESSION_HANDOFF.md"
PRE_SHA = "04886c5e042555ae2251eb3fe527f95caa5fe6610f00c7f0587aea9b6e189000"
PRE_BYTES = 367034

SECTION = """
## Phase 2 / E-34n/16 (2026-09-12, ag) - V019-KAUSALITAET ARRETIERT (STUFEN 1a/1b/2a/2b): DUALER LAUF, HINDSIGHT-MARKER, SPEC-BINDUNG

Auftrag (Anwender, Ausfuehrung der Entscheidungsfragen aus E-34n/15 D8):
Der kausale Satz wird die gesetzte Primaerwahrheit; der Batch-Satz
(24 / +88.116626) bleibt als dokumentierte, NICHT handelbare
Hindsight-Referenz sichtbar. Umgesetzt in vier Backend-Stufen (1a, 1b.1,
1b.2, 2a) und der sichtbaren Stufe 2b.

Bindender Kanon dieser Session (Anwender):

 1. Kausalitaet = primaerer harter Assert; 24 / +88.116626 bleibt
    dokumentierte Hindsight-Referenz.
 2. Fail-Loud `verifiziere_gegen_scan` ZUERST (getrennt von
    `PhasenReifeKonfiguration`).
 3. Paket (i): Stufe 2a laesst die PNGs byte-identisch; Stufe 2b separat.
 4. `_q0`-Absicherung NUR ueber `aktive_phase_bei()`-Asserts; die
    Injektionskette bleibt unangetastet.
 5. Marker Bar 1211: Ausnahme zu Paragraph 54 Regel 10, `mfc="none"`,
    `mec="#7f7f7f"`, `mew=1.4`, `ms=9.0`; `ls="--"` auf der Trade-Spanne
    `[t.tp2, t.sl]`.
 6. Legendentext: `Hindsight-Artefakt - K76@1211, +2.5395 R,
    Hysterese 77 (nicht handelbar)`.
 7. Urkunde DOPPELT: dieser Paragraph UND die Spiegelspez; `test/` ist
    gitignored, kein `git add -f`.
 8. Toleranz der dualen R-Asserts: strikt `< 1e-6`.
 9. ZP-5-Refaktor (Stufe 5) erst nach 1./2./4., nur bei Bit-Identitaet.
10. Zweites Fenster (S1/S2) erst nach Schritt 4.

Regeln durchgehend: keine UI-/Regressionstests, kein Paragraph 75,
read-only wo moeglich; `python -O`-Sicherheit (daher `raise` statt
`assert` im Adapter).

**Diese Urkunde ist eine ERST-Arretierung:** V019 besass bisher nur
Byte-Groessen, keine SHA256 der fuenf PNGs. Die Hashes in F16.8 sind die
ersten.

### F16.1 - Vorbedingung und Anker

Vorbedingung: Handoff-SHA
`04886c5e042555ae2251eb3fe527f95caa5fe6610f00c7f0587aea9b6e189000`
(367.034 B / 6.498 Zeilen CRLF, aus E-34n/15) - vor dem Append binaer
verglichen.

| Anker | Start (E-34n/15) | Ende (E-34n/16) |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` | 196.649 B / `4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a` | unveraendert |
| `backtest_lab/phasen_regime_adapter.py` | 30.663 B / `4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83` | 36.255 B / `983192b3d25a1a50dcd06aac3b9230fc31f7759e5297c933d286b4fa88033cfb` |
| `test/tmp_png_aug_sichttest.py` | 109.022 B / `7dab7a300e69c4ffae230b1cb547da508dae8a3801cb6a2fed2f63c5bc6d7a28` | 118.127 B / `cb302fc7ea80bdf5b30a0de829265587bcceb157cc855c3c776ac2722d15b416` |
| `reports/h2_phasenregime/H2_PHASENREGIME_ADAPTER_SPEZ.md` | 220.428 B | 222.795 B / `6ceddce01893d333722acb69b83e84ef4450ec8b15ead80f1e111d76733bdee9` |

Die Engine blieb in allen Stufen unangetastet (replay-identisch).

### F16.2 - Stufe 1a: Fail-Loud Scan-Abgleich im Renderer (erledigt)

`verifiziere_gegen_scan` in den V019-Rendererpfad aufgenommen, gated auf
`_V19`; die Referenzbars datengetrieben aus `adapter.segmente`
(848 / 1033 / 1174 statt Literale), kein `log()` - dadurch blieben die
Protokoll-Bytes identisch. Verifiziert: `py_compile`, AST, Positiv-
kontrolle (848/1033/1174/1287 OK) und vier Negativkontrollen fail-loud.
Pruefer: `test/_chk_v019_scanverify_ref.py`.

### F16.3 - Stufe 1b.1: Reife-Bindung im Adapter (erledigt)

`AUTO_VERSCHMELZUNG_SCHWELLE = PhasenReifeKonfiguration().verschmelzungs_schwelle`
(= 77) plus `_verifiziere_reife_bindung()` beim Modulimport. Zwei bewusste
Abweichungen von der woertlichen Vorgabe:

 * `raise ValueError` statt `assert` - nur so ist die Bindung unter
   `python -O` wirksam (Konvention wie `verifiziere_niveau_overrides`).
 * Guard (a) prueft
   `PhasenReifeKonfiguration(AUTO_VERSCHMELZUNG_SCHWELLE).ist_im_plateau()`;
   die woertliche Vorgabe `PhasenReifeKonfiguration().ist_im_plateau()`
   waere TAUTOLOGISCH (Default stets Referenz 77) und deckt keinen
   Fehlwert auf. Vom Stresstest aufgedeckt.

Pruefer: `test/_chk_v019_reife_bindung.py` - Schwelle 77 akzeptiert;
40/115/200 -> Plateaugrenze; 41/114/50 -> Mismatch.

### F16.4 - Stufe 1b.2: AST-Rekonstruktion (erledigt, Weg b)

`test/_chk_v019_reife_rekonstruktion.py` zieht die vier Funktionen
(`_lebt_kausal`, `ecken`, `_nah`, `zusammenfassen`) per
`ast.get_source_segment` WORTGLEICH aus `test/_tmp_e34_auto.py`.
Ergebnis: 7 Rohsegmente identisch zur D6-Tabelle;
`zusammenfassen(roh, 77)` == `(A1_AUTO_77, A2_AUTO_77)` bar- UND
kantenidentisch; Provenienz = kausale Basis am Segmentstart (0.000000 %
Abweichung); Klippen 40 -> 41 und 114 -> 115 mit Strukturwechsel; bei 41
entstehen 3 Segmente (`1124..1173 K73/K85`).

### F16.5 - Stufe 2a: Dualer kausaler Lauf (erledigt)

Adapter: reine, zustandsfreie Funktion
`kausale_segmentfenster(segmente, schwelle)` (Index 0 = Anker unberuehrt;
`wirksam_ab = start + schwelle - 1`; Vorgaenger-`end_bar = wirksam_ab - 1`)
plus `ADAPTER_V019_KAUSAL`. Fenster: P9 848..1020, A1 1033..**1249**,
A2 1174..1287. Der Renderer konsumiert nur, er rechnet nicht neu.

Renderer-Felder `neu_basis_soll_hindsight=()`, `ziel_trades_kausal`,
`ziel_r_kausal`, `ziel_r_h2_kausal`; in V019 23 / 85.577150 / 46.657566;
`neu_basis_soll` ohne (1211, 76); `neu_basis_soll_hindsight=((1211, 76),)`;
vierter Lauf `V1_kausal`; Scan-Abgleich fuer BEIDE Adapter; Protokoll dual.
Fehlerquelle/Hinweis: `renderer.phasen_id` fuer A1 ist `"A1_AUTO_77"`,
nicht `"A1"`.

Verifikation `test/_chk_v019_dual_kausal.py` (PNG-frei, Harness-Ausgabe
via `_Quiet`-stdout-Stub mit `reconfigure`): **GESAMT: OK**.
V1_kausal 23 / +85.57715036556571; H1 8 / +38.919584; H2 15 / +46.657566;
Menge == Harness-B; entfernt genau `[(1211, 76)]`; gemeinsame Trades
R-bit-identisch; H1 kausal == H1 Batch.

### F16.6 - Stufe 2b: Hindsight-Marker und Rollentausch (erledigt)

Spiegelspez vorab: neuer **Paragraph 54.4** (Regeln 15-20, Stil
`hindsight`, Strichlinie nur an der Spanne, Annotation, Legende nur
Panels 01/03/05, kein Zaehlwert, kausaler Primaersatz `_q0`) und
**Paragraph 55.1** (S11 Kausalitaet primaer, S12 Artefakt sichtbar-nicht-
gezaehlt, S13 Fail-Loud beidseitig), ASCII-only, LF erhalten.

Rollentausch im Renderer: `V1_batch = V1_aktiv`; `V1_kausal`
(Default-Copy fuer Nicht-V019); `V1 = V1_kausal`; `_AKTIV_KEYS`/`NEU` auf
kausal; `HINDSIGHT_TRADES` aus `neu_basis_soll_hindsight`; Sollwerte
kausal 23 / 85.577150 / 46.657566 / `ziel_delta_rb=37.761453`; neue Felder
`ziel_trades_hindsight=24` / `ziel_r_hindsight=88.116626` /
`ziel_r_h2_hindsight=49.197042`; duale `< 1e-6`-Asserts (kausal primaer,
Batch sekundaer); vier `_q0`-Vorbedingungs-Asserts; neuer Stil
`stil="hindsight"` in `mark_trades` samt `elif hin:`-Annotationszweig und
G4-Ausschluss; `LEG_HINDSIGHT`; Marker nur an Panels 01/03/05 (Panel 04
bewusst nicht); Protokoll dual. Insgesamt 20 Einzel- plus 2 Mehrfachanker
mit Count-Asserts (LF).

### F16.7 - Protokollzeilen (Lauf `--mode V019`, exit 0, 14+ Asserts bestanden)

```
V1_kausal (LIVE, primaer): 23 Trades / +85.577150 R  (H1 8/+38.919584 | H2 15/+46.657566)  <- PRIMAER (live-faehig)
V1_batch (HINDSIGHT)     : 24 Trades / +88.116626 R  (H1 8/+38.919584 | H2 16/+49.197042)  <- NICHT handelbar
  Hindsight-Delta: +2.539476 R aus 1 Artefakt-Trade(s) -- Hysterese 77, nicht handelbar
Delta V019-v0.1: +37.761453 R  (Soll +37.761453)
```

### F16.8 - Artefakt-Anker: Fuenf-PNG-Satz (SHA256; Erst-Arretierung)

| PNG | Bytes | SHA256 |
|---|---|---|
| `test/aug_sichttest_v019_01_gesamt.png` | 2.158.471 | `5881d8167386331df2626233a34184a196058c66e96b4a602fbf42e815f6c292` |
| `test/aug_sichttest_v019_02_h1_box.png` | 896.312 | `7189fa55f0c940855bc3bfa7c94e493f06652c5fd977869651ef4c38afa0ca2f` |
| `test/aug_sichttest_v019_03_h2_phasen.png` | 1.796.954 | `29e9d1babcbbea78d53252f9e9f50921c9e603cb5c9436310ade4f346c6a05e4` |
| `test/aug_sichttest_v019_04_p9_regime.png` | 1.195.846 | `49cbeec2bb1c801916938ae5986a1d64f7e0fce21fe937b7045889b23fe13259` |
| `test/aug_sichttest_v019_05_kantenkarte.png` | 2.152.133 | `6df089a2dae9f8206ce2ee98a4e9c620e081a53e9bed56b85a0a30c6895fbf42` |
| Protokoll `test/tmp_png_aug_sichttest_v019_out.txt` | 5.334 | `be93e559b630a8be5cd6866e440c1eea5d61a2a2001a38faadff8163e2b8536f` |

### F16.9 - Invariante Panels (Byte-Groessenidentitaet)

Die Panels **02 (896.312 B)** und **04 (1.195.846 B)** sind
byte-groessenidentisch zum Stand vor Stufe 2b. Panel 02 durch die
bestehende Paragraph-71.2-Ausnahme; Panel 04, weil dort kein
Hindsight-Marker gezeichnet wird (`LEG_HINDSIGHT` nur an 01/03/05).
Vorheriger Stand (E-34n/13, vor 2b): 01 2.133.327 / 03 1.772.173 /
05 2.129.083. Panel 01/03/05 aendern sich ausschliesslich durch den
zusaetzlichen Marker/Annotation/Legende.

### F16.10 - Artefakt-Anker: Pruef-/Patchskripte (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/_chk_v019_scanverify_ref.py` | 2.051 | `3112899f4b4d354d101fb9bc247d226eed075cd12270d1d378d5e0d5d58ea877` |
| `test/_chk_v019_reife_bindung.py` | 2.612 | `7901ed25d0784f741cbbaadd270fb722a379cbc44cbadce1860a5f4355dad6a6` |
| `test/_chk_v019_reife_rekonstruktion.py` | 9.332 | `afc32c347ac476c81ce97363d4b86c64d7f8894475d6df3f8ad75ba13d529899` |
| `test/_chk_v019_dual_kausal.py` | 5.230 | `10e63878919ad3264bb41f472965b954da4d5d327d786bef26677be76b50392e` |
| `test/_tmp_step1a_patch_scanverify.py` | 2.189 | `078e9e3f97c459dd47f9e4cd8d700fa38137cef1bca7f630df4511d61ac8a08e` |
| `test/_tmp_step2a_patch_dual_kausal.py` | 9.093 | `01e0dcb4336be87e7df420abf9005526a5c41660645185399407b7c0b55496c8` |
| `test/_tmp_step2b_patch.py` | 20.269 | `5c7086a04dfbe04165c17670843fcdb16d47081c276668dbc30a40b6cde25dfa` |
| `test/_tmp_step2b0_spec.py` | 3.437 | `43daeafd7f08473a1476cff7a23cadbf31cd1377df990fe4fb6f27c8d4ecbf78` |
| AST-Quelle `test/_tmp_e34_auto.py` | 22.826 | `edb7365e588ba78a1a3f82e6874ede80930603bdab7929409f68eb8420f15884` |

Unveraendert bleiben die Engine- und Adapterherkunft aus D1; **kein**
Paragraph 75, **kein** S1, **keine** S2-Laeufe, **keine** UI-/
Regressionstests, **kein** `git add -f`.

### F16.11 - Offene Schritte (Wiedervorlage)

 1. **Stufe 3:** `box_end_datum` in `cfg`; V019-Guard von Bar-Literal
    `!= 644` auf dynamischen Scan-Abgleich.
 2. **Stufe 4a/4b:** `R_realisiert` ((b) +78.216484 / Untergrenze (a)
    +78.127525); Cap >= 3/Richtung arretieren; kausale Kanten-Ereignis-
    Regel isoliert messen.
 3. **Stufe 5:** ZP-5-Refaktor (nur bei Bit-Identitaet, sonst arretiert)
    plus Paragraph 75.
 4. Spaeter: Zweitfenster S1/S2 als Generizitaetsnachweis.
Unveraendert offen aus E-34n/14: Q1 Bilanzierung (a)/(b) und Q2 Schranke.
"""


def main() -> None:
    b = open(P, "rb").read()
    assert len(b) == PRE_BYTES, ("Pre-Bytes", len(b))
    h = hashlib.sha256(b).hexdigest()
    assert h == PRE_SHA, ("Pre-SHA", h)

    txt = SECTION.replace("\r\n", "\n").replace("\n", "\r\n")
    assert txt.isascii(), "SECTION nicht ASCII"
    if not txt.endswith("\r\n"):
        txt += "\r\n"
    with open(P, "ab") as f:
        f.write(txt.encode("ascii"))

    nb = open(P, "rb").read()
    print("pre  bytes", len(b), "sha", h)
    print("post bytes", len(nb), "sha", hashlib.sha256(nb).hexdigest())
    print("delta", len(nb) - len(b))


if __name__ == "__main__":
    main()
