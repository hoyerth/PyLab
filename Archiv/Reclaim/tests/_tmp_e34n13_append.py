# -*- coding: utf-8 -*-
"""Handoff-Append E-34n/13 (Einbrand ZP-5(D) + V018-Gegenprobe).

Idempotent geschuetzt: nur anhaengen, wenn der Vorbedingungs-SHA exakt passt.
Abschnitt ist ASCII-only (Umlaute als ae/oe/ue, Paragraph erlaubt).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HANDOFF = Path("test/SESSION_HANDOFF.md")
VORBEDINGUNG = "5355407c1bd796b3193cfb462636a444e1e359167709b9aa914348934ac1365f"

ABSCHNITT = """

## Phase 2 / E-34n/13 (2026-09-11, ae) - EINBRAND ZP-5(D) AUSGEFUEHRT + V018-GEGENPROBE

Auftrag (Anwender, nach E-34n/12): Der in Z5 vorgelegte Text-Diff (Form 14a) ist
autorisiert. Einbrand in den Renderer, Messlauf im Modus V019, V018-Gegenprobe
zur Regressionsfreiheit. Geaendert wurde ausschliesslich
`test/tmp_png_aug_sichttest.py` (gitignored; Arretierung ueber SHA-Anker
statt Versionierung). Engine `test/tmp_kanten_engine_replay.py` und Adapter
`backtest_lab/phasen_regime_adapter.py` blieben **byte-identisch**.

Vorbedingung: Handoff-SHA
`5355407c1bd796b3193cfb462636a444e1e359167709b9aa914348934ac1365f`
(334.982 B / 5.930 Zeilen) - vor dem Append per SHA-Vergleich bestaetigt.

### A1 - Einbrand: 4 inhaltliche Aenderungen (6 @@-Bloecke)

Diff-Paar: `test/_tmp_backup_renderer_pre_zp5.py` (104.221 B) ->
`test/tmp_png_aug_sichttest.py` (109.022 B); voller Text-Diff als Artefakt in
`test/_tmp_e34n13_diff.txt`. Hinweis zur Zaehlung: der Auftrag sprach von
"4 Hunks"; `difflib` zerlegt den zweizeiligen Docstring-Block in zwei separate
`@@`-Bloecke, sodass 6 `@@`-Bloecke bei 4 inhaltlichen Aenderungen entstehen.

1. **`KONFIGURATION_V019`** (Z. 394-424): `ziel_trades_gesamt` 23 -> 24,
   `ziel_r_gesamt` 82.614385 -> 88.116626, `ziel_r_h2` 43.694801 -> 49.197042
   (mit Kommentar `# ZP-5(D): +5.502241 (K82@1172, entry 1173)`),
   `ziel_delta_rb` 34.798688 -> 40.300929, `neu_basis_soll` um das Tupel
   `(1172, 82)` erweitert (9 -> 10 Tupel). Unveraendert: `ziel_r_h1=38.919584`,
   `ziel_p9_beitrag=23.435111`, Quartett, `referenz_soll` und
   `niveauwechsel_gesamt=66`.
2. **Docstring `_wende_zielzonen_patches_v019`**: Beschreibung auf
   "...Zielzonen-Engine-Regeln..." verallgemeinert und um
   "+ Kantenlaeufer-Durchstich (ZP-5, E-34n)" ergaenzt (2 @@-Bloecke).
3. **5. Paar `A_KL_DOCHT`** (Z. 766 ff.) in `_wende_zielzonen_patches_v019` (Anker =
   `seite_edges`-Block). Der Patchkopf traegt die `_b0`-Invariante als
   Kommentar (TRAGEND: `basis_bei(seg.start_bar)`; mit der statischen
   `.basis` (67.5455) kippt Bar 1073, `touch_conf(1075)` 2 -> 4, Kollaps
   D -> B). Schwellen ausschliesslich aus der SSoT: unten
   `cfg.touch_band_pct`, oben der ZP-4-Helfer `_ueb(_kb)`. Symmetrisch OBEN
   und UNTEN; P9 ueber `boden_deklariert_literal` ausgenommen; nur echte
   Durchstiche (`_dkl > cfg.touch_band_pct`).
4. **Fail-Loud-Zweig Z. 959-974** (V019-Zweig, nicht global hinter dem
   V019-Block):
   `len(V1) - len(V1_basis) == 9` -> `== 10`, plus Geometrie-Waechter mit den
   drei Asserts `_dw[1073] <= cfg.touch_band_pct`,
   `_dw[1074] <= cfg.touch_band_pct`, `_dw[1075] > cfg.touch_band_pct`
   (KEIN Wert-Pin; `scan["d"]["low"]` liegt seit Z. 538 vor).

### A2 - Trockenpruefung (vor dem Lauf)

`test/_tmp_e34n13_trocken.py`: alle **5 Anker** treffen genau einmal
(`count == 1`), inklusive des neuen `A_KL_DOCHT`-Paares; der injizierte
`_se_trades`-Quelltext kompiliert (23.985 vs 21.612 Zeichen). Marker-Zaehlung
im *gepatchten* Quelltext belegt die SSoT-Auslesung (keine Literale):
`cfg.touch_band_pct` = 2, `0.12` = **0**, `_ueb(_kb)` = 1, `0.80` = **0**,
`basis_bei(_s0)` = 1.

### A3 - Messlauf `--mode V019` (exit=0, alle Fail-Loud-Asserts bestanden)

| Kennzahl | ZP-4 (alt) | ZP-5(D) (neu) |
|---|---|---|
| V0-Baseline | 14 / +42.450970 (H1 8/+38.919584, H2 6/+3.531386) | unveraendert |
| V1_basis (v0.1) | 14 / +47.815697 | unveraendert |
| **V1_aktiv (V019)** | 23 / +82.614385 | **24 / +88.116626** (ZIEL) |
| H1 | 8 / +38.919584 | 8 / +38.919584 (unveraendert) |
| H2 | 15 / +43.694801 | **16 / +49.197042** |
| P9 (848..1020) | 5 / +23.435111 | 5 / +23.435111 (unveraendert) |
| Delta V019 - v0.1 | +34.798688 | **+40.300929** (Soll +40.300929) |
| `NEU` | 9 Tupel | **10 Tupel** (+ `(1172, 82)`) |
| `V1 - V1_basis` | 9 | **10** |
| Sichtbare Niveauwechsel | 66 (Baseline 205) | 66 (Baseline 205) |
| Sperr-Marker | - | Q29 `x` 51, M6 `^` 30 |

Neu im V019-Lauf (Auszug): `K62@1075 +1.4758`, `K73@1122 +10.7525`,
`K82@1172 +5.5022` (der ZP-5-Trade; Einstieg am Retest, `entry_bar=1173`,
Entry 67.5890). Der Messlauf-Log liegt in
`test/_tmp_e34n13_lauf2_console.txt`, das Protokoll in
`test/tmp_png_aug_sichttest_v019_out.txt` (5.115 B).

**Invarianz-Indiz:** die PNGs **02 (H1-Box)** und **04 (P9-Regime)** haben
exakt dieselben Byte-Groessen wie vor ZP-5 (896.312 / 1.195.846 B) - H1 und P9
blieben visuell unberuehrt; 01/03/05 wurden durch den `K82@1172`-Marker
geaendert.

### A4 - V018-Gegenprobe (Regressionsfreiheit)

`.venv\\Scripts\\python.exe test\\tmp_png_aug_sichttest.py --mode V018
--probe-praefix _tmp_e34n13_probe_v018_ --protokoll-nach
test\\_tmp_e34n13_probe_v018_out.txt` -> **exit=0**, alle Asserts bestanden:

| Kennzahl | Soll | Ist |
|---|---|---|
| V1_aktiv (V018) | 17 / +65.835576 | **17 / +65.835576** |
| H1 | 8 / +38.919584 | 8 / +38.919584 |
| H2 | 9 / +26.915992 | 9 / +26.915992 |
| Delta V018 - v0.1 | +18.019879 | +18.019879 |
| Niveauwechsel | 66 | 66 |

Belegt, dass ZP-5(D) den V018-Pfad nicht beruehrt (der Patch laeuft nur bei
`mode == "V019"` und ist zusaetzlich durch den Laufzeit-Gate
`len(hook.segmente) > 1` abgesichert). Die fuenf Probe-PNGs wurden nach der
Messung geloescht; das Protokoll bleibt als Beleg.

### A5 - PNG-Satz + Betriebsnotiz (Windows-Dateilock)

Satz `aug_sichttest_v019_0*.png`: 01 2.133.327 B, 02 896.312 B, 03 1.772.173 B,
04 1.195.846 B, 05 2.129.083 B. Protokoll:
`test/tmp_png_aug_sichttest_v019_out.txt` (5.115 B).

Betriebsnotiz: Lauf 1 endete mit `OSError [Errno 22]` beim finalen `savefig`
von PNG 05 (Windows-Dateilock / externe Vorschau), **nachdem alle Asserts
bestanden waren** - kein Logikfehler. In Lauf 1 wurden 01-04 nicht
ueberschrieben; nach `Remove-Item test\\aug_sichttest_v019_*.png` und
`Remove-Item test\\tmp_png_aug_sichttest_v019_out.txt` lief Lauf 2 fehlerfrei.

### A6 - Artefakt-Anker E-34n/13 (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/tmp_png_aug_sichttest.py` (Renderer, ZP-5) | 109.022 | `7dab7a300e69c4ffae230b1cb547da508dae8a3801cb6a2fed2f63c5bc6d7a28` |
| `test/_tmp_backup_renderer_pre_zp5.py` | 104.221 | `eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148` |
| `test/_tmp_e34n13_trocken.py` | 1.951 | `fb28d49a548c0e46779119f08a4200417f12ab43d30a5a641f6c6315987bf40a` |
| `test/_tmp_e34n13_out.txt` | 1.046 | `40f68db85eb7c1a3b968d828dc01856bd875610f69454095f1c5e37d89d4600d` |
| `test/_tmp_e34n13_diff.txt` (voller Text-Diff) | 7.767 | `c28421e7ce18ad96497156e64e6e90372776e9fc04e859cb295087ab95035b80` |
| `test/_tmp_e34n13_lauf_console.txt` | 6.814 | `42f062a8d98f49bc1537de3665a2749f5166e68aca047342bad291f71cf25193` |
| `test/_tmp_e34n13_lauf2_console.txt` | 5.264 | `3c612f72a0bdc996106f95de95cae5bbadddb2bf5babe699557d1045bd30a52a` |
| `test/_tmp_e34n13_probe_v018_out.txt` | 5.088 | `b57664eb484d17294d4a8bebd80c7f7899d04ad506dfb78e8430fbb3259248c4` |
| `test/_tmp_e34n13_probe_v018_console.txt` | 5.233 | `f8cc629b89c365119a4d6eca7beb11ffb7865908b9db4970eaee4ee412105cd3` |

**Unveraenderte Anker:** Engine `test/tmp_kanten_engine_replay.py` 196.649 B /
`4a576a766670d684c30381969e4d7349d5786b1b22ea6dda08b93b7d811bb38a`; Adapter
`backtest_lab/phasen_regime_adapter.py` 30.663 B /
`4f50b6b0829ad031613acb9edcfd79c6316a2082cda35152821bf010cb861e83`.

### A7 - Entscheidungen (Textblock) und Restrisiken

1. **ZP-5(D) ist eingebrannt und messbestaetigt:** 24 / +88.116626 R,
   `V1-V1_basis == 10`, V018 unveraendert (17 / +65.835576). Die Sollwerte
   sind damit arretiert (Renderer-SHA `7dab7a30...`).
2. **Waechter statt Wert-Pin** (vom Anwender in Z8/1 entschieden, hier
   umgesetzt): drei Geometrie-Asserts 1073/1074/1075, SSoT-Schwelle
   `cfg.touch_band_pct`; Bar 1072 bleibt bewusst ungeprueft (Schwellen-
   Monotonie, Z2).
3. **Restrisiko Anzeige (offen, Kosmetik):** `shade_phases` (Renderer ~Z. 1046)
   zeichnet weiterhin Literal-Phasen statt A1/A2; die Luecken 1135-1170 und
   1273-1287 bleiben rot schraffiert. Aus E-34m uebernommen, nicht Teil von
   ZP-5(D).
4. **`box_end`-Grenze:** PNG 02 ist byte-gleich zum Vorlauf, enthaelt aber die
   `box_end`-Grenze. Die abschliessende visuelle Abnahme bleibt beim Anwender
   (keine UI-/Regressionstests; Hausregel 4).
5. **Renderer bleibt unversioniert** (gitignored, `test/`); die Arretierung
   erfolgt ueber den SHA-Anker in A6, nicht ueber eine Version.
6. Unveraendert: **kein §75, kein S1, keine S2-Laeufe**, keine UI-/
   Regressionstests, kein `git add -f`.
"""


def main() -> None:
    # Binaer-I/O: der Anker-SHA ist der Datei-SHA (CRLF bleibt erhalten).
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
    # ASCII-only-Nachweis fuer den neuen Abschnitt (Paragraph ist erlaubt).
    print("nicht-ASCII im Abschnitt", sorted({c for c in ABSCHNITT if ord(c) > 127}))


if __name__ == "__main__":
    main()
