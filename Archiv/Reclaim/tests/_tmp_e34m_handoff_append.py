# -*- coding: utf-8 -*-
"""Append E-34m an test/SESSION_HANDOFF.md (UTF-8, LF)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "test" / "SESSION_HANDOFF.md"

BLOCK = """

---

## Phase 2 / E-34m (2026-09-11, aa) — EINBRAND: Modus `"V019"` im Renderer (11 Hunks, Zielzonen-Patchset ZP-4) + erste vollstaendige Sichtpruefung

### X0 · Auftrag, Freigabe und Leitplanken

Anwender-Freigabe (2026-09-11): H9-Hilfsfunktion
`_wende_zielzonen_patches_v019(src) -> str` **frei**, zweistufiges Gating
**bestaetigt**, Label `"v0.24 (endogene Segmente A1/A2 + Zielzonen-Patchset
ZP-4)"` **bestaetigt**, Einbrand **jetzt**, unveraendert **kein §75, kein S1,
keine S2-Laeufe**.

### X1 · Was passiert ist

* **Ziel:** `test/tmp_png_aug_sichttest.py` (gitignored, `test/` = `.gitignore:63`).
  97.160 B / 2.075 Z → **104.221 B / 2.242 Z**, CRLF 0 / LF 2.242,
  SHA256 `eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148`.
* **11 Hunks** (H1 Docstring, H2 Imports `ADAPTER_V019` + `import dataclasses`,
  H3 `AdapterMode`, H4 `KONFIGURATION_V019`, H5 Registry, H6 Adapter-Wahl
  (V019-Zweig **vor** der `g4_aktiv`-Kette), H7 `_V19`/`_NEU`/`_VTAG`/
  `_VER_TEXT`, H8 Engine-Guard `box_end == 644`, H9
  `_wende_zielzonen_patches_v019`, H10 Laufzeit-Injektion
  `_zv`/`_ueb`/`_reclaim_stufe_lok`, H11 Laengen-Assert 9).
* **Nur ergaenzende Doku-Korrekturen** gegenueber dem Diff-Entwurf E-34m:
  `FUENF MODI` → `SECHS MODI` (Abschnittsuebersicht), `EIN Vertrag, FUENF
  Instanzen` → `SECHS Instanzen` (Kommentar), Tippfehler `Wevt` → `Webt`
  im neuen Docstring. **Kein Logikdelta.**
* **Unberuehrt:** Adapter `4f50b6b0…` (30.663 B), Engine `4a576a76…`
  (196.649 B). `python -m py_compile` **Exit 0**.

### X2 · Trockenlauf-Audit (VOR dem Schreibzugriff) — `_tmp_e34m_audit.py`

* Basis-13-Anker der Engine: je `count == 1` (13/13).
* ZP-4-Anker im Basis-13-gepatchten `_se_trades`-Quelltext: je `count == 1`
  (4/4: `A_UEB1`, `A_VC`, `A_M6L`, `A_SB`).
* **ZP-4-Soll-Quelltext: 21.956 Zeichen,
  SHA256 `8a3b7070582b620d997c2adfc0bcf3f20e016a94ab97faa84e5143410ee63778`**
  — erzeugt aus den Regeln von `test/_tmp_e34_auto.py` (Z. 381..405), also
  exakt der Mechanik, mit der E-34i die Sollwerte gemessen hat.
* Kompilierbarkeit des vierfach gepatchten Quelltexts: OK.

### X3 · Verifikation NACH dem Einbrand — `_tmp_e34m_verify.py` (ALLE PRUEFUNGEN OK)

* `_wende_zielzonen_patches_v019` definiert (Z. 708); Quelltext-Gate
  `if KONF.mode == "V019":` und Aufruf auf `patched_src` vorhanden.
* **Der vom Renderer selbst erzeugte ZP-4-Quelltext ist byte-identisch zum
  Soll:** 21.956 Zeichen, SHA256 `8a3b7070…`. Damit ist belegt: der
  eingebrannte Patchsatz ist **genau** ZP-4 — nicht mehr und nicht weniger.
* 16 Hunk-Anker je `count == 1` (u. a. `ADAPTER_V019 if KONF.mode`,
  `KONFIGURATION_V019: Final[`, `ziel_delta_rb=34.798688,`,
  `ADAPTER_V019.segmente[1].start_bar`, `ns["_reclaim_stufe"] = _reclaim_stufe_lok`,
  `assert len(V1) - len(V1_basis) == 9`).

### X4 · Lauf `--mode V019` — **alle Fail-Loud-Asserts bestanden**

| Assert | Soll | Ist |
|---|---|---|
| `len(V0)` / `R0` | 14 / +42.450970 | 14 / +42.450970 |
| `len(V1_basis)` / `RB` | 14 / +47.815697 | 14 / +47.815697 |
| `len(V1)` | 23 | **23** |
| `R1` | +82.614385 | **+82.614385** |
| `len(h1_1)` / `sum(h1_1.r)` | 8 / +38.919584 | 8 / +38.919584 |
| `sum(h2_1.r)` | +43.694801 | +43.694801 |
| `P9_BEITRAG` | +23.435111 | +23.435111 |
| `NIVEAUWECHSEL` | 66 | 66 |
| `R1 − RB` | +34.798688 | +34.798688 |
| `len(V1) − len(V1_basis)` | 9 | 9 |
| `REFERENZ` | `[(980, 73)]` | `K73@980 +2.4130` |
| `NEU` (9 + G4-Auto) | 10 | 10 |
| `QUARTETT_R` | +19.806095 | +19.806095 |
| G4 (Hook 3) | 1 Trade `(1002, 77)` | `K77@1002` R +3.629016, LONG |

* **Zielzonen-Neuzugaenge (BKZ):** `K62@1075` +1,4758 · `K73@1122` +10,7525 ·
  `K76@1211` +2,5395 · `K76@1268` −1,0000 · `K73@1272` +1,2547 ·
  `K76@1280` +1,7564 — **deckungsgleich mit E-34i §W3**, zusaetzlich G4
  `K77@1002` und die drei Quartett-Neuzugaenge.
* **Satz:** `aug_sichttest_v019_01_gesamt.png` (2.140.255 B) ·
  `..._02_h1_box.png` (896.312 B) · `..._03_h2_phasen.png` (1.778.529 B) ·
  `..._04_p9_regime.png` (1.195.846 B) · `..._05_kantenkarte.png` (2.135.870 B).
  Protokoll `test/tmp_png_aug_sichttest_v019_out.txt` (5.355 B).
* Plateau-Label (gerendert): `K67 69.975 -> 69.870 (P9-Override) -> 69.899 *  Norm 69.9140`.

### X5 · Nachweis des zweistufigen Gates (beide Stufen gemessen)

* **Laufzeit-Stufe:** im **selben** V019-Prozess bleiben `V0`
  (14 / +42.450970) und `V1_basis` (14 / +47.815697) **unveraendert** — der
  `_zv`-Gate haengt am **gebundenen Adapter** (`DEFAULT_ADAPTER`, 1 Segment),
  nicht am Modus. Ohne diese Stufe waere `V1_basis` mitgepatcht worden.
* **Quelltext-Stufe:** Gegenprobe `--mode V018 --probe-praefix
  _tmp_e34m_probe_v018_ --protokoll-nach test/_tmp_e34m_probe_v018_out.txt`
  liefert **17 / +65.835576 R** (H1 8/+38.919584 · H2 9/+26.915992 ·
  Delta +18.019879) = die arretierten V018-Werte. Der versiegelte v018-Satz
  blieb unberuehrt (Probe-Praefix); die Probe-PNGs wurden geloescht,
  das Probe-Protokoll bleibt als Beleg.

### X6 · Artefakt-Anker E-34m (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `_tmp_e34m_audit.py` | 4.444 | `3917fede116661fd7b42edae3e65c02bbdab5e137a569aca221d4f3f5106d4ba` |
| `_tmp_e34m_audit_out.txt` | 1.816 | `0786aa1afd21ac7b3a2a0ab9b2ff8b65b730b7b4768239a18ddfc8227a1b6b15` |
| `_tmp_e34m_verify.py` | 4.137 | `6385c395c2b4603285878609acc68e2d3a6b01a6701e44b09e26929f53000010` |
| `_tmp_e34m_verify_out.txt` | 2.258 | `08fe3a3055d4288398bdfee73ea978b6c95d7a35170792531c61596a3719f1af` |
| `_tmp_e34m_zp4_soll.txt` | 66 | `7236ec5f79159c2c7030394fd387c34c1132a52ed41c355c0a4fb7fc7eaa124c` |
| `_tmp_e34m_v019_lauf_out.txt` | 10.992 | `631be68513c213386dede7a198daf8fe212966da058dc3c3931e93283daa80f6` |
| `_tmp_e34m_probe_v018_out.txt` | 5.068 | `44adf7d1db3939d8f0022169d9f06749f4d00c9f9197ecac9751eaefff82096a` |
| `test/tmp_png_aug_sichttest_v019_out.txt` | 5.355 | `c4ecd595050edceae1e6dba4ec23805dfcc358fc5d84b0c767fb7c6c16998e35` |

**Renderer-Anker (gitignored):** `test/tmp_png_aug_sichttest.py`
104.221 B, SHA256 `eccc4d77536ac1f8dc068ea2637ed7c2db99f49edee359a407cece4796285148`.
**ZP-4-Quelltext-Soll:** SHA256 `8a3b7070582b620d997c2adfc0bcf3f20e016a94ab97faa84e5143410ee63778`.

### X7 · Offene Entscheidungen (Textblock)

1. **Versionskontrolle des Renderers:** `test/tmp_png_aug_sichttest.py` ist
   ueber `.gitignore:63 (test/)` **nicht versioniert**. Die Arretierung
   erfolgt deshalb — wie bei Engine und Renderer bisher durchgaengig ueblich —
   ueber den **SHA-Anker in diesem Handoff**. Ein Force-Add
   (`git add -f test/tmp_png_aug_sichttest.py`) wuerde die Repo-Konvention
   brechen und die Datei dauerhaft versionieren. **Entscheidung offen.**
2. **Sichtpruefung:** die fuenf PNGs des v019-Satzes sind erzeugt; die
   eigentliche visuelle Abnahme erfolgt **manuell durch den Anwender**.
3. Unveraendert: **kein §75, kein S1, keine S2-Laeufe.**
"""

vorher = HANDOFF.read_bytes()
print(f"vorher : {len(vorher):,} B  "
      f"sha256 {hashlib.sha256(vorher).hexdigest()}")
text = vorher.decode("utf-8")
assert "\r" not in text, "Handoff enthaelt CRLF"
neu = text + BLOCK
HANDOFF.write_bytes(neu.encode("utf-8"))
nachher = HANDOFF.read_bytes()
print(f"nachher: {len(nachher):,} B  "
      f"sha256 {hashlib.sha256(nachher).hexdigest()}")
print(f"CRLF {nachher.count(chr(13).encode())} | "
      f"LF {nachher.count(chr(10).encode())} | "
      f"Zeilen {neu.count(chr(10)) + 1}")
