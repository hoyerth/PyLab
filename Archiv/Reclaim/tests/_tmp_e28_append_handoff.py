# -*- coding: utf-8 -*-
"""LF-Append: E-28 (Zielsystem-Lokalisierung) an test/SESSION_HANDOFF.md."""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"F:\Python\PyLab\test\SESSION_HANDOFF.md")
SOLL = "d8f6b367bfd6cf7edeece6a91c91f751d082054ca8b44cb9fb2278befc782bd6"

vorher = P.read_bytes()
ist = hashlib.sha256(vorher).hexdigest()
assert ist == SOLL, f"Vorbedingung verletzt: {ist} != {SOLL}"
assert vorher.count(b"\r\n") == 0, "Datei ist nicht LF-clean"

TEXT = """
---

## Phase 2 / E-28 (2026-09-11, l) — Zielsystem-Lokalisierung: **beide Gates erstmals erfuellt**

Ratifiziert und gemessen wurde das **komplette Zielsystem-Buendel** in dem
Fenster, das E-27 fuer Q29 etabliert hat:

    _W(k) = max(0, k - 960)

angewandt auf die **drei** globalen Referenzen der Engine:

1. **Q29** (`_im_aussenquartil`, Z. 2434/2435) — bereits E-27 ratifiziert,
   hier als Konstante mitgefuehrt.
2. **Gegenkante** (`_gegenkante`, Z. 2554 ff.) — der Pool, aus dem `tp2`
   gewaehlt wird.
3. **POC-Anker** (`poc_start`, `berechne_kausalen_histogramm_poc`) — bisher
   `0` (Box-Beginn).

### G0 · Erratum der Variante `gegleb` — 96-Bar-Artefakt

Der E-28-Entwurf hatte eine Variante `gegleb` als „Liveness im Fenster"
etiketiert und dabei `_lebt` (Engine, Z. 2413) verwendet. `_lebt` prueft
jedoch gegen **`cfg.wall_live_bars = 96`** (Q25), **nicht** 960. `gegleb` ist
damit **keine 960er-Variante**, sondern ein 96-Bar-Fenster — und sie ist die
**einzige** Variante, die die AUG-Baseline veraendert (R 38,92 → 26,19;
s. G5). Sie ist als **Artefakt verworfen**. Die ratifizierte
Liveness-Variante heisst `geg960`:

```python
max(b for b, _ in e.wicks if b <= k) >= k - 960   # geg960 (ratifiziert)
max(b for b, _ in e.wicks if b <= k) >= k -   96   # _lebt (Q25-Konstante)
```

Nebenbefund: `geg` (Basis im Fenster) und `geg960` liefern in S2
**nahezu identische** Ergebnisse (s. G3) — die beiden Formulierungen von
„lokal" sind innerhalb des 960er-Fensters austauschbar. Das ist eine
Robustheitsaussage, kein Zufall: die Fensterkante `_W(k)` schneidet den Pool
bereits strukturell, die Liveness ist dann nur noch eine Nachfilterung.

### G1 · Artefakt-Anker (SHA256; `test/` = gitignored)

| Artefakt | SHA256 | Bytes |
|---|---|---|
| `test/_tmp_e28_ziel_lokal.py` | `2c144660f4551e7e4d0f4033d2be7f390774efec50383900b75ee9f6788397f1` | 11.709 |
| `test/_tmp_e28_run_all.py` | `63b7091250c495e899d6e777404b691856667aa6d20cbb6633dbda10afe788a7` | 1.287 |
| `test/_tmp_e28_sammel.py` | `0f9ee198b8a650c62d027fd231bebef799b6e7920aa0fb7c99520b9ac461e08d` | 2.371 |
| `test/_tmp_e28_ziel_s2_base_out.txt` | `d77283a1ab41a1a7486a0855605753908798191e4cb315c0075d2b0341093d94` | 24.210 |
| `test/_tmp_e28_ziel_s2_geg_out.txt` | `0e252b409394140e4f5bf449e321e246974a16dbbc70fcada16f2623b33cdfde` | 24.016 |
| `test/_tmp_e28_ziel_s2_geg960_out.txt` | `2714d89720d95fe3bd299bd7edcc0660e91e7803524658a1341a9e856ccf0cee` | 24.052 |
| `test/_tmp_e28_ziel_s2_poc_out.txt` | `c47480ea5e3824704efa0bea3550f96db9c86a4b7580e13e6c400e408c54a68c` | 25.843 |
| `test/_tmp_e28_ziel_s2_gegpoc_out.txt` | `52ab02c8fad4fa357ba1668bfaf91a2dcb3b7ba3ac75205e6419065bc2e4caf9` | 25.065 |
| `test/_tmp_e28_ziel_s2_geg960poc_out.txt` | `480e8adeaccd65cf23260c22bc13e0b4ea2d3778d5d40f0d791c35473dc324a7` | 25.075 |
| `test/_tmp_e28_ziel_aug_base_out.txt` | `6b67edac07ecd7406b529969e9e1c850571b9f40ab5e84dc2f5008a36109fe72` | 2.190 |
| `test/_tmp_e28_ziel_aug_geg_out.txt` | `66c5452868b4a55f5e4c94d90ac606e7634d4defa2cd8e8276f5796ee3dd1dfb` | 2.171 |
| `test/_tmp_e28_ziel_aug_geg960_out.txt` | `e95e89d96af860d898f9a8df89f5cf5e10f827198103ccdb293bd08e39f681a7` | 2.207 |
| `test/_tmp_e28_ziel_aug_poc_out.txt` | `af77a52e61efe5aa402ec8f7e78be64c3ca0da593e95f681c14321c5c1ee4bdc` | 2.172 |
| `test/_tmp_e28_ziel_aug_gegpoc_out.txt` | `070dcf4042d7da4c1884a26ddb455ca237dc5a3e62840ffbf6d8ae6f9f02539b` | 2.174 |
| `test/_tmp_e28_ziel_aug_geg960poc_out.txt` | `904e009200633f1f6229f8028c8e5ab50f9a2a08667822a417e5b278cd11966c` | 2.184 |
| `test/_tmp_e28_ziel_aug_gegleb_out.txt` | `df87ae0133254a0b2a174711e8be7c9efbaf1d61cd02921b84f3d0fd9bbaf540` | 2.178 |
| `test/_tmp_e28_ziel_aug_geglebpoc_out.txt` | `2b22c8876b906aeb1daf0ef4e3e78725e0a320dbf16d8a8c5608f27d5292351e` | 2.181 |

**Eingriffe (drei, alle additiv zu E-27):**

```python
# (2) Gegenkanten-Pool -- _gegenkante, vor dem max/min
_wh = float(np.max(hi[_W(k):k + 1]))
_wl = float(np.min(lo[_W(k):k + 1]))
pool = [e for e in seite_edges[gegenseite]
        if e.erster_pivot_bar + 2 <= k + 1
        and (not _FLAG[0] or (
             (_wl <= e.basis_bei(k) <= _wh) if _FLAG[0] == 1   # geg
             else (_lebt960(e, k) if _FLAG[0] == 3 else _lebt(e, k))))  # geg960
        and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
             or e.touch_conf(k) >= 2)]

# (3) POC-Anker
poc = berechne_kausalen_histogramm_poc(
    d, (_W(k) if _FLAG[1] else poc_start), k, unter, ober, cfg.num_bins)
```

### G2 · Methodik

Ein Lauf = ein Prozess (E-27/F0); **parallele** Prozesse sind zulaessig, die
Isolation ist pro Prozess (`_se_trades` mutiert `letzter_signal_bar`,
`letzter_sweep_bar`, `cluster_hoch`, `cluster_tief`). `_tmp_e28_run_all.py`
startet alle sechs Varianten in sechs Prozessen; Gesamtlaufzeit **153,7 s**.
Die S2-Laufgrenze ist `box_end_bar = n = 21.624` (Split 17.692). In AUG bleibt
`box_end_bar = 644` unveraendert.

### G3 · S2 — saubere 2-Koordinaten-Matrix (`box_end_bar = n = 21.624`)

`gegenkante ∈ {global, lokalbasis (`geg`), lokal960leb (`geg960`)}` ×
`poc ∈ {global, lokal}`:

| Variante | Gegenk. | POC | Setups | R ges. | R_adj | USD/Tr | ATR/Tr | Q_stop | Gew% | Trade-SHA |
|---|---|---|---|---|---|---|---|---|---|---|
| `base` | global | global | 261 | −70,813603 | −91,649458 | **−0,0206** | −0,3367 | 0,667 | 11,5 | `5a73d37ad2441d49` |
| `geg` | lokal-Basis | global | 259 | +17,686977 | −14,184964 | **+0,0192** | +0,2379 | 0,772 | 7,7 | `82df0037a790e2bd` |
| `geg960` | lokal-960leb | global | 259 | +16,853088 | −15,018853 | **+0,0189** | +0,2331 | 0,772 | 7,7 | `5d0001abed977302` |
| `poc` | global | lokal | 280 | −3,856257 | −27,289551 | **+0,0315** | +0,1638 | 0,782 | 14,3 | `e970721fb1e0ece7` |
| **`gegpoc`** | lokal-Basis | lokal | 271 | **+55,878629** | **+28,807016** | **+0,0526** | **+0,3890** | **0,742** | 12,9 | `9baa8c360c6897c0` |
| **`geg960poc`** | lokal-960leb | lokal | 271 | **+55,871446** | **+28,799833** | **+0,0526** | **+0,3890** | **0,742** | 12,9 | `f9c2a3dd59c8be1d` |

Halbierung:

| Variante | H1 n | H1 R | H1 USD/Tr | H1 Q_stop | H2 n | H2 R | H2 USD/Tr | H2 Q_stop |
|---|---|---|---|---|---|---|---|---|
| `base` | 221 | −59,954233 | −0,0123 | 0,647 | 40 | −10,859370 | −0,0664 | 0,775 |
| `geg` | 219 | +7,189615 | +0,0077 | 0,767 | 40 | +10,497363 | +0,0822 | 0,800 |
| `geg960` | 219 | +6,355726 | +0,0073 | 0,767 | 40 | +10,497363 | +0,0822 | 0,800 |
| `poc` | 239 | −11,914974 | +0,0221 | 0,766 | 41 | +8,058718 | +0,0862 | 0,878 |
| **`gegpoc`** | 232 | +12,126065 | +0,0186 | 0,728 | 39 | **+43,752564** | **+0,2549** | 0,821 |
| **`geg960poc`** | 232 | +12,126065 | +0,0186 | 0,728 | 39 | **+43,745381** | **+0,2549** | 0,821 |

### G4 · Kernbefund: das Gate faellt nur unter **beiden** Koordinaten

| | POC global | POC lokal |
|---|---|---|
| **Gegenkante global** | `base`: USD −0,0206 · Q 0,667 → **Gate nein** | `poc`: USD +0,0315 · Q 0,782 → **Gate nein** |
| **Gegenkante lokal** | `geg`/`geg960`: USD +0,019 · Q 0,772 → **Gate nein** | `gegpoc`/`geg960poc`: USD **+0,0526** · Q **0,742** → **GATE JA** |

Drei Aussagen:

1. **Beide Gates sind erstmals erfuellt.** `USD/Trade > 0` **und**
   `Q_stop ≤ 0,75` — ausschliesslich in der Zelle (lokal, lokal). Jede
   Einzelmassnahme scheitert: die Gegenkante allein kippt USD knapp positiv
   (`+0,019`), reisst aber `Q_stop` ueber 0,75 (0,772); der POC allein kippt
   USD positiver (`+0,0315`), `Q_stop` bleibt aber 0,782. Erst die Kombination
   senkt `Q_stop` auf 0,742 **und** hebt USD/Tr auf +0,0526.
2. **Der POC ist der groessere Hebel, die Gegenkante die Qualitaetssicherung.**
   `R_adj` springt von −14,18 (`geg`) auf **+28,81** (`gegpoc`) — das
   Ergebnis ist **nicht** von einem einzelnen Ausreisser getragen. Unter
   `base` ist `R_adj` −91,65 (der beste Trade wird entfernt und die Bilanz
   bricht ein).
3. **Wirkung auf H2 ist stark, aber richtungsunabhaengig verankert.** H2-R
   −10,86 → **+43,75**; H2-USD/Tr −0,066 → **+0,2549**. H1 bleibt mit
   +12,13 R schwach positiv (USD/Tr +0,0186). Der Gewinner ist also **nicht**
   ein H2-Sonderfall: H1 dreht von −59,95 auf +12,13.

**Achtung (offen, G7):** H2-`Q_stop` = **0,821** liegt ueber 0,75. Das
Gesamt-`Q_stop` (0,742) sind die Tore passiert, die H2-Teilmenge nicht. Nach
`D1` waere ein `Q_stop > 0,75` kategorisch auszuschliessen — hier ist zu
entscheiden, ob `D1` auf Gesamt oder Halbierung angewandt wird.

### G5 · Schritt 2 — AUG: das ratifizierte Buendel ist **beweisbar inert**

`box_end_bar = 644 < 960` ⇒ `_W(k) = 0` fuer **jeden** Box-Bar ⇒ alle drei
Lokalisierungen sind bit-identisch zu `GLOBAL`; `_lebt960` ist fuer jeden
Docht trivial wahr.

| AUG-Variante | Setups | R ges. | R_adj | USD/Tr | Q_stop | Trade-SHA | Verdikt |
|---|---|---|---|---|---|---|---|
| `base` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | Referenz |
| `geg` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `geg960` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `poc` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `gegpoc` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `geg960poc` | 8 | +38,919584 | +23,049550 | +1,4077 | 0,125 | `cfb337221d4014b3` | **inert** |
| `gegleb` (96) | 8 | +26,190829 | +16,946994 | +1,0115 | 0,250 | `c67a27814486df2b` | **Artefakt** |
| `geglebpoc` (96) | 8 | +26,190829 | +16,946994 | +1,0115 | 0,250 | `c67a27814486df2b` | **Artefakt** |

Die August-Baseline (V018: 17 Trades / +65,835576 R bzw. unbewehrte
`_se_trades` 8 Setups / +38,919584 R) ist unter dem **ratifizierten** Buendel
**byte-identisch** geschuetzt. Der Beweis ist konstruktiv (`_W(k) = 0`), nicht
empirisch — er haengt an keiner Hook-Verdrahtung.

### G6 · Ehrliche Bilanz E-28 (Vergleich zu E-27/F6)

| Groesse | E-27 (`base` = Q29 lokal 960) | **E-28 (`geg960poc`)** |
|---|---|---|
| Setups (S2) | 261 | 271 |
| R ges. | −70,813603 | **+55,871446** |
| R_adj | −91,649458 | **+28,799833** |
| USD/Trade | −0,0206 | **+0,0526** |
| ATR/Trade | −0,3367 | **+0,3890** |
| Q_stop | 0,667 | 0,742 |
| H2 R | −10,859370 | **+43,745381** |
| H2 USD/Tr | −0,0664 | **+0,2549** |
| Gate `USD/Trade > 0` | **verletzt** | **erfuellt** |
| Gate `Q_stop ≤ 0,75` | erfuellt | **erfuellt** |

Damit ist erstmals in S2 eine Konfiguration vorhanden, die **beide** in E-27/F6
festgelegten harten Gates passiert. Die Lokalisierung hat sich als das
richtige **Werkzeug** erwiesen: dieselbe Operation (`_W(k) = max(0, k−960)`)
heilt Q29, die Gegenkante **und** den POC-Anker.

### G7 · Offene Entscheidungen (Textblock)

1. **`D1`-Reichweite.** Gesamt-`Q_stop` 0,742 (≤ 0,75), H2-`Q_stop` 0,821
   (> 0,75). Vorgeschlagen wird: `D1` gilt fuer die **Gesamtbilanz** (und
   die Halbierungen werden nur deskriptiv mitgefuehrt), weil bei n = 39 die
   H2-Rate statistisch nicht belastbar ist. Gegenposition: `D1` als
   *Halbierungs*-Gate verwerfen `gegpoc` sofort. Zu entscheiden.
2. **`geg` vs. `geg960`.** Beide sind in S2 nahezu deckungsgleich. Meine
   Empfehlung: **`geg960`** ratifizieren, weil es die *eine* Semantik
   (`_W(k) = 960`) konsequent weitertraegt und die 96-Bar-Konstante
   `wall_live_bars` (Q25) unangetastet laesst. `geg` bleibt deskriptiv.
3. **`tp1_anteil_pct`.** Noch offen: ob der TP1-Anteil (50 %) an die
   lokalisierte Gegenkante gekoppelt werden muss (bisher nicht Gegenstand der
   Messung).
4. **POC-Bins.** `num_bins = 60` wurde bei lokalem Fenster (960 statt 21.624
   Bars) **nicht** nachkalibriert. Die Bin-Breite aendert sich damit
   strukturell. Zu pruefen, ob `num_bins` bei lokalem `poc_start` skaliert
   werden muss.
5. **Reihenfolge.** Nach Zielsystem: **Hybrid-Schliessung auf `L960`**, danach
   der Zustandsautomat (`BALANCE`/`EXPANSION_OBEN`/`EXPANSION_UNTEN`).

Unveraendert: **kein Einbrand in `backtest_lab/phasen_regime_adapter.py`, kein
§75, kein S1-Cache, keine S1-Untersuchung.**
"""

neu = vorher.decode("utf-8") + TEXT
P.write_text(neu, encoding="utf-8", newline="\n")
n_b = P.read_bytes()
assert n_b.count(b"\r\n") == 0, "CRLF nach Append!"
print(f"vorher  {len(vorher)} B  {ist}")
print(f"nachher {len(n_b)} B  {hashlib.sha256(n_b).hexdigest()}")
print(f"delta   {len(n_b) - len(vorher)} B")
