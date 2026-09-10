# H2-Phasenregime-Adapter — READ-ONLY-Spezifikation v0.1

**Status:** Exploration. Kein Produktivcode, keine Änderung an
`test/tmp_kanten_engine_replay.py`. Alle Aussagen sind durch
`test/tmp_hook_semantik_check.py` (+ `_out.txt`) reproduzierbar.

**Arretierte Baseline (nicht antasten):**

| Lauf | Definition | Trades | R |
|---|---|---|---|
| Lauf A (Box) | `entry_bar < 640` | 8 | **+38.964262** |
| Lauf B (Voll) | alle | 14 | **+40.445143** |

V0-Referenz in der Verifikation = Lauf B: H1 8 / +38.9643 R + H2 6 / +1.4809 R.

---

## 1. Kernbefund: Hook 1 ist ein Prädikat an ZWEI Stellen

Regel (A) („Wand-Docht-Exception": der Sweep hat Liquidität an der Wand
selbst abgeholt ⇒ die Wand gilt als **erreicht**) ist mechanisch **nicht**
durch einen Rückgabewert eines einzelnen Aufrufs abbildbar. Sie muss als
**Prädikat** an zwei unabhängigen Stellen desselben Bar-Durchlaufs
ausgewertet werden.

Messung (`test/tmp_hook_semantik_check_out.txt`, Abschnitt A/B/E):

| Variante | Hook-1a Pool | Hook-1b M6 | Kriterium | Scope | H1 n/R | H2 n/R | K73@980 | K73@1020 |
|---|---|---|---|---|---|---|---|---|
| V0 Referenz | – | – | – | – | 8 / +38.9643 | 6 / +1.4809 | – | – |
| V1 F1 `continue` | – | ja | W | 640 | 8 / +38.9643 | 5 / +2.4809 | – | – |
| V2 F2 Pool-Filter allein | ja | – | W | 640 | 8 / +38.9643 | 5 / +2.4809 | – | – |
| **V3 F2 + M6** | ja | ja | W | 640 | 8 / +38.9643 | 7 / +7.9021 | +2.4119 | +3.0093 |
| **V4 F2 + M6** | ja | ja | **M** | 640 | 8 / +38.9643 | 7 / +8.4496 | +2.4119 | +3.0093 |
| V5 F2 + M6 | ja | ja | M | 848 | 8 / +38.9643 | 7 / +7.9021 | +2.4119 | +3.0093 |
| V6 F3 (`continue` + V-S-Erlass) + M6 | – | ja | M | 640 | 8 / +38.9643 | 9 / +6.5170 | +2.4119 | +3.0093 |
| **V7 F2 + M6** | ja | ja | M | **PHASE** | 8 / +38.9643 | 7 / +7.9021 | +2.4119 | +3.0093 |

**Schlüsse:**

1. **V1 und V2 sind inert** — weder `continue` im `dist<0`-Zweig noch der
   Pool-Filter allein erzeugen die Benchmark-Trades. Ursache: die erreichte
   Wand K67 (Basis > Sweep) wird von `_blockiert_durch_aussenkante` (M6)
   weiterhin als Außenwand gesehen und sperrt K73.
2. **Erst 1a + 1b zusammen** liefern K73@980 und K73@1020.
3. **H1 ist in ALLEN Varianten bit-identisch** (8 / +38.964262 R) —
   Scoping `k >= 640` bzw. `k in Phase` schützt die Box vollständig.
4. V6 zeigt: der V-S-Erlass (F3) ist **verzichtbar** und erzeugt sogar
   zwei Zusatztrades (H2 9 / +6.5170 R) ⇒ **nicht verwenden**.
5. Kriterium **M** (Touch-Band 0.12 %) ist für den Benchmark **äquivalent zu W**
   (identische R), verändert aber bei Scope 640 den Park-Trade
   K16@715 → K16@716 (−1.0000 → −0.4525 R).

---

## 2. Hook-Stellen mit Zeilennummern und Variablenverträgen

Quelldatei: `test/tmp_kanten_engine_replay.py` (191.814 B, 4.501 Zeilen).

### Hook 1a — Kandidaten-Pool (`_kandidat`, Z. 2471)

| | |
|---|---|
| Datei/Zeile | Z. 2513–2515 (`if not pool: … / pool.sort(...)`) |
| Einfügepunkt | **nach** Z. 2515, **vor** Z. 2516 `for pos, e in enumerate(pool)` |
| Wirkung | `pool = [e for e in pool if not hook.wand_hat_geliefert(e, k, sweep_px)]` |
| Lokale Verträge | `e: _SEEdgeH`; `k: int`; `sweep_px = hi[k]` (SHORT) / `lo[k]` (LONG); `seite = "OBEN" if richtung=="SHORT" else "UNTEN"`; `pool` bereits nach `basis_bei(k)` sortiert, `reverse=(seite=="OBEN")` ⇒ `pos == 0` = äußerste Wand |
| Danach | Z. 2518 `if dist < 0.0:` → Z. 2519 `if _lebt(e, k): return None` (unverändert!) |

### Hook 1b — M6-Blocker (`_blockiert_durch_aussenkante`, Z. 2428)

| | |
|---|---|
| Datei/Zeile | Z. 2447–2449 (OBEN) und Z. 2452–2454 (UNTEN) |
| Wirkung | unmittelbar nach `if b <= sweep_px: continue` (OBEN) bzw. `if b >= sweep_px: continue` (UNTEN): `if hook.wand_hat_geliefert(e, k, sweep_px): continue  # kein Blocker` |
| Lokale Verträge | `e: _SEEdgeH`; `b = e.basis_bei(k)`; `sweep_px: float`; `kd: _SEEdgeH` (Kandidat); `basis_k = kd.basis_bei(k)` |
| Warum nötig | K67: `basis ≈ 69.9687 > sweep 69.899` ⇒ `b <= sweep_px` ist **False** ⇒ K67 wird `aussen` und blockiert K73 (dist 0.4192 % ≤ `max_seed_distanz_pct` 0.75) |

### Hook 2 — TP-Ziel / Regel (B) (`_se_trades`, Z. 2346)

| | |
|---|---|
| Datei/Zeile | Z. 2612 `gegen_basis = geg.basis_bei(k)`; Ziel wird Z. 2635 `tp2 = gegen_basis` |
| Wirkung | `_pz = hook.phasen_ziel(k, richtung)`; `if _pz is not None: gegen_basis = _pz` |
| Lokale Verträge | `richtung: "SHORT"\|"LONG"`; `basis = kd.basis_bei(k)`; `gegen_basis: float`; nachgelagerte Invarianten Z. 2614/2617/2622/2625 (`tp2 < poc < entry < sl` bzw. gespiegelt) ⇒ zu nahe/ferne Ziele erzeugen `stats["kein_raum"]` |
| Fallback | `None` ⇒ Makro-Gegenkante (heutiges Verhalten) |

### Hook 3 — Phasen-Scope / Initialisierung

| | |
|---|---|
| Datei/Zeile | `_se_scan` Z. 2185 `box_end_bar = int(np.searchsorted(ts_arr, np.datetime64("2026-08-19")))`; `_se_trades` Z. 2549 `for k in range(2, box_end - 3)` |
| Verträge | `ts_arr: datetime64[ns]` (Berlin-Wanduhr-encoded); `box_end_bar == 640`; Bar-Indizes der Engine sind **1:1 identisch** zur v0.4-UTC-Projektion (verifiziert) |
| Wirkung | `hook.ist_im_regime(k)` steuert 1a und 1b gemeinsam |

### `_SEEdgeH` (Z. 2079–2134, `@dataclass(slots=True)`)

Felder: `kid, seite, basis, geburts_bar, wicks: List[Tuple[int, float]],
status, letzter_bar, schlaf_windows, letzter_signal_bar, ist_prim_anker,
erster_pivot_bar, promoviert_ab_bar, letzter_sweep_bar, cluster_hoch,
cluster_tief`.
Methoden: `basis_bei(k)` (Q13-Freeze nur für promovierte Primär-Anker),
`touch_conf(k)` (`b + 2 <= k`), `letzter_touch_conf(k)`, `ist_aktiv_bei(k)`.
**Keine dynamischen Attribute möglich (slots).**

---

## 3. Kriterium „Wand hat geliefert"

```python
# M (Mentor-Vorgabe, robust):
def wand_hat_geliefert(e, k, sweep_px) -> bool:
    basis = e.basis_bei(k)
    return abs(sweep_px - basis) <= basis * touch_band_pct / 100.0   # 0.12 %

# W (Referenz, exakt):
def wand_hat_geliefert(e, k, sweep_px) -> bool:
    return any(b == k and abs(px - sweep_px) < 1e-9 for b, px in e.wicks)
```

- M ist **streng breiter** als W: sie stellt jede Wand frei, deren Basis
  innerhalb 0,12 % des Sweep-Extremums liegt — nicht nur die, deren Docht
  den Sweep gebildet hat. Fail-open-Risiko.
- Für K73@980/@1020 liefern M und W **identische R** (+2.4119 / +3.0093,
  Summe **+5.4212 R**).
- Einziger gemessener Unterschied (Scope 640): K16@715 (−1.0000) →
  K16@716 (−0.4525), Δ **+0.5475 R** im Park.

---

## 4. Phasen-Scope (Hook 3)

v0.4-Baseline (frozen), Bar-Indizes = Engine-Indizes:

| P | start–end | U_final (Decke) | L_final (Boden) | Decke-Kante | Boden-Kante |
|---|---|---|---|---|---|
| P6 | 620–673 | 65.490 | 62.649 | | |
| P7 | 715–792 | 67.201 | 65.604 | | |
| P8 | 802–840 | 68.320 | 67.897 | | |
| **P9** | **848–1020** | 69.9140 | **68.3700** | K67 (Upper1) | K77 (Lower2) |
| P10 | 1030–1075 | 68.2200 | 67.5440 | K84 | K82 (Lower3) |
| P11 | 1082–1134 | 69.3435 | 68.5250 | K78 | K86 |
| P12 | 1171–1272 | 69.5550 | 67.6355 | K73 (Upper2) | K82 |

**Lücken ohne Phasenzuordnung:** 641–847, 1021–1029, 1076–1081,
1135–1170, 1273–Ende.

Gemessen: **PHASE-Scope ≡ Scope 848** (identische Trade-Menge). Der
Unterschied zwischen Scope 640 und PHASE liegt ausschließlich im
Transition-Park (640–847): K16@716 (+0.5475 R) fällt weg.

---

## 5. Ergebnis-Komposition je Scope (Kriterium M)

| Scope | Park 640–847 | Rest > 847 (Zielbereich) | H2 gesamt |
|---|---|---|---|
| 640 | 5 / +3.0283 R | 2 / **+5.4212 R** | 7 / +8.4496 R |
| 848 | 5 / +2.4809 R | 2 / **+5.4212 R** | 7 / +7.9021 R |
| PHASE | 5 / +2.4809 R | 2 / **+5.4212 R** | 7 / +7.9021 R |

**Zielband des Mentors [+5,28 … +5,42 R] wird exakt getroffen: +5.4212 R**
(K73@980 `STUFE_2_KERZE_2` entry 69.4910 / sl 69.9490 / tp2 68.3700 /
R +2.4119; K73@1020 `STUFE_1_IN_BAR` entry 69.5780 / sl 69.9740 /
tp2 68.3700 / R +3.0093; beide `GEWONNEN/TP1`, poc 68.4027).

Nebenwirkungen V0 → V4 (Stats): `blocker` 23→14, `kein_raum` 1→7,
`quartil_blockiert` 56→57, `v_s` 14→15, `zyklus_blockiert` 36→16.

---

## 6. Überarbeiteter Datenvertrag (ersetzt den Entwurf aus der Handoff)

```python
from dataclasses import dataclass
from typing import Optional, Literal, Tuple

Richtung = Literal["SHORT", "LONG"]


@dataclass(frozen=True, slots=True)
class PhasenKante:
    """Eine v0.4-Phase als Regime-Einheit (Bar-Indizes = Engine-Indizes)."""
    phasen_id: str            # "P9" ... "P12"
    start_bar: int            # inklusiv
    end_bar: int              # inklusiv  (behebt Schwaeche (a) der Handoff)
    decke: float              # U_final  -> LONG-Ziel
    boden: float              # L_final  -> SHORT-Ziel
    decke_kid: Optional[int] = None
    boden_kid: Optional[int] = None


class PhasenRegimeAdapter:
    """Read-only Adapter. Wird per Hook in die Engine injiziert."""

    def __init__(self, phasen: Tuple[PhasenKante, ...],
                 touch_band_pct: float = 0.12,
                 luecken_modus: Literal["FAIL_CLOSED", "FAIL_OPEN"] = "FAIL_CLOSED"
                 ) -> None: ...

    # --- Hook 3: Scope ------------------------------------------------
    def phase_bei(self, k: int) -> Optional[PhasenKante]:
        """Bar->Phase-Mapping; None in Luecken (behebt Schwaeche (b))."""

    def ist_im_regime(self, k: int) -> bool:
        """True gdw. k in einer Phase liegt."""

    # --- Hook 1: Regel (A) --------------------------------------------
    def wand_hat_geliefert(self, e, k: int, sweep_px: float) -> bool:
        """Praedikat! Muss an ZWEI Stellen ausgewertet werden:
          1a) _kandidat Z.2515  -> Pool-Filter
          1b) _blockiert_durch_aussenkante Z.2448/2453 -> kein M6-Blocker
        """

    # --- Hook 2: Regel (B) --------------------------------------------
    def phasen_ziel(self, k: int, richtung: Richtung) -> Optional[float]:
        """SHORT -> boden, LONG -> decke; None ausserhalb des Regimes."""
```

### Behobene Schwächen des Handoff-Entwurfs

| Handoff-Entwurf | Problem | Lösung |
|---|---|---|
| `ist_in_phase(k): return k >= phase_start_bar` | kein Phasen-Ende | `start_bar`/`end_bar` + `phase_bei(k)` |
| kein Bar→Phase-Mapping | Lücken unbestimmt | `phase_bei(k) -> Optional[PhasenKante]` + `luecken_modus` |
| `hook_regel_a_freigabe(...) -> bool` | suggeriert 1 Aufrufstelle | Prädikat `wand_hat_geliefert(...)`, 2 dokumentierte Anwendungsstellen |
| kein Rückgabetyp für Ziel | implizit | `phasen_ziel(...) -> Optional[float]` |

---

## 7. Offene Entscheidungsfragen (Mentor)

1. **Kriterium normativ: M (0,12 %-Band) oder W (exakter Docht)?**
   Beide liefern den Benchmark (+5.4212 R). M ist breiter (fail-open) und
   verändert bei Scope 640 den Park-Trade K16 (+0.5475 R).
2. **Transition-Park 640–847: gehört er zum Regime?**
   PHASE/848 ⇒ Park unverändert (5 / +2.4809 R); 640 ⇒ K16@716 (+0.5475 R).
   Das Zielband +5.4212 R ist in beiden Fällen identisch.
3. **Lücken 1021–1029, 1076–1081, 1135–1170: fail-closed (Hook inaktiv)
   oder fail-open (vorige Phase fortschreiben)?**
4. **Hook 2 bei `None`: Fallback auf Makro-Gegenkante (wie V4) oder Trade
   blockieren?** (Blockieren erhöht `kein_raum`.)
5. **Modul-Ort:** `src/phasen_regime_adapter.py` (Produktiv) oder
   `scripts/`? Injektion bleibt vorerst AST/Monkeypatch in `test/`.
6. **Mehrfach-Freistellung:** M kann mehrere Wände gleichzeitig freistellen.
   Gewollt oder auf die sweep-bildende Wand begrenzen?
7. **Kanten-Kids im Vertrag:** `decke_kid`/`boden_kid` (K67/K77 für P9)
   mitführen oder nur Preise? (Mentor nannte K73 für P12-Decke.)

---

# Addendum v0.2 — Read-Only-Sichtung (Mentor-Audit 2, 2026-09-09)

Kein Lauf, kein Compile, kein Test. Nur `Read`, `Get-Content`, `Select-String`,
`certutil -hashfile`, `Get-ChildItem`, `git ls-files`.

## 8. Normative Entscheidungen (fixiert, Mentor)

| # | Entscheidung | Auswirkung auf den Vertrag |
|---|---|---|
| 1 | Kriterium **M** (Touch-Band 0,12 %) | `sweep_im_band` bleibt; Benchmark-R unverändert +5.4212 |
| 2 | Start **Bar 848 / P9** | `start_scope_bar = 848`; Park 640–847 unberührt (5 / +2.4809 R) |
| 3 | **Striktes Fail-Closed** in Lücken | `aktive_phase_bei() -> None`; **kein** Fortschreiben |
| 4 | **Blockade** bei fehlender Gegenkante, **kein** Makro-Fallback | Hook 2 braucht **Tri-State** (s. 9.3) |
| 5 | Zielort `src/phasen_regime_adapter.py` | **Pfad existiert nicht** (s. 9.1) |
| 6 | Freistellung **nur für die sweep-bildende Wand** | Tie-Break-Regel nötig (s. 9.4) |
| 7 | Feste Kanten-`kid` im Vertrag | Typ-Konflikt `int` vs `str` (s. 9.2) |

## 9. Blockernde Befunde (rein lesend verifiziert)

### 9.1 Zielpfad `src/` existiert nicht
`Get-ChildItem -Directory` im Root: `.idea .ipynb_checkpoints .ipython .venv
algos backtest_lab data docs js Notebooks reports scripts signal_lab test
__marimo__` — **kein `src/`**.
Pakete mit `__init__.py`: `backtest_lab/`, `signal_lab/`.
Ohne `__init__.py`: `algos/`, `scripts/` (15 Module, u. a.
`phasen_volumen_profil.py` = v0.4-Baseline, `market_segmentation.py`).
⇒ Entscheidung #5 ist mit der Repo-Struktur nicht kompatibel; Zielort muss
neu bestimmt werden (neu anlegen vs. `backtest_lab/` vs. `scripts/`).

### 9.2 `kid`-Typ: Engine `int` vs. Vertrag `str`
`_SEEdgeH.kid: int` (Z. 2087); `_SESetup.kid` ebenfalls `int`
(`tmp_hook_semantik_check_out.txt`: `K67`, `K73`, `K16`).
Der Mentor-Vertrag deklariert `PhasenKanteInfo.kid: str`.
⇒ Entweder Vertrag auf `int` stellen oder eine Mapping-Schicht
(`"K67" -> 67`) einführen. Empfehlung: **`int`** (keine Konvertierung,
keine Fehlerquelle).

### 9.3 Hook 2 braucht einen dritten Zustand
Entscheidung #4 („Blockade ohne Makro-Fallback") ist mit
`phasen_ziel(...) -> Optional[float]` **nicht** abbildbar, weil `None`
bereits „außerhalb des Regimes ⇒ Makro-Gegenkante" bedeutet.
Erforderlich ist ein diskriminierter Rückgabetyp, z. B.

```python
class ZielQuelle(Enum):
    MAKRO = auto()        # k < start_scope_bar  -> Engine unverändert
    PHASE = auto()        # k in Segment          -> Segmentziel
    BLOCKIERT = auto()    # k >= start_scope_bar, Luecke -> kein Trade
```

Messung: im August-Fenster liegt **kein** Trade in den Lücken
(1021–1029, 1076–1081, 1135–1170) ⇒ die Blockade ist für den Benchmark
**inert** (V0-H2-Trades: 639, 650, 679, 715, 760, 853). Sie ändert aber
den Vertrag und muss daher **vor** dem Modulentwurf fixiert sein.

### 9.4 Tie-Break bei M (Entscheidung #6)
Pool bei Bar 980 (`test/tmp_audit_kandidat_trace_out.txt` Z. 41):
`[(K67, -0.0996), (K73, +0.3193), (K76, +0.5394), (K75, +0.6828), (K78, +0.868)]`.
Bei Bar 1020 (Z. 84): `[(K67, -0.039), (K73, +0.3552), (K76, +0.5753)]`.
⇒ Im Benchmark liegt **genau eine** Kante im 0,12-%-Band (K67).
Strukturell ist das nicht garantiert: liegen zwei Basen < 0,24 % auseinander,
stellt M **beide** frei (Over-Trading-Gefahr laut Mentor-Audit).
⇒ Spez-Ergänzung: freigestellt wird nur die Kante mit
`min |sweep_px - basis_bei(k)|` **innerhalb** des Bandes.
Die Prädikat-Signatur bleibt per Kante: `wand_hat_geliefert(e, k, sweep_px)`.

### 9.5 Statische `basis_preis` vs. kausale Engine-Basis
K67 hat **keine** statische Basis: `basis_bei(980) = 69.9687`,
`basis_bei(1020) = 69.9513` (Trace Z. 5 und 48). `PhasenKanteInfo.basis_preis`
als eingefrorener Skalar wäre also semantisch falsch, sobald die Engine die
kausale Mittel-Basis fortschreibt.
⇒ `basis_preis` nur als **Provenienz-/Anzeigewert** deklarieren; die
Hook-Prüfung muss `e.basis_bei(k)` (Engine-Wahrheit) verwenden.
`touch_bars: Tuple[int, ...]` wird von keinem Hook benötigt
(Engine hält `wicks`) ⇒ optional, rein dokumentarisch.

### 9.6 Kein Provenienz-Kanal für Regime-Trades
`_SESetup` besitzt `grund1`, aber **kein** `grund2`; die Ausgabe
(`stats_kanten_engine_replay.txt`) kennt nur `resultat`/`grund1`.
Eine Markierung „Regime-Trade" würde eine Feld-Erweiterung in der Engine
erfordern ⇒ **Widerspruch zu „Engine unangetastet"**.
⇒ v0.1: **keine** Tagging-Anforderung.

## 10. Baseline-Integrität (verifiziert)

| Datei | Bytes | Zeilen | SHA256 |
|---|---|---|---|
| `test/tmp_kanten_engine_replay.py` | 191.814 | 4.500 | `3ba15c723958161ffc…5255cb006` |
| `docs/artefakte/aug_p11/kanten_engine_replay_v40r.py.snapshot` | 191.814 | 4.500 | `3ba15c723958161ffc…5255cb006` |

**Byte-identisch** (certutil SHA256). ⇒ Die in Abschnitt 2 genannten
Zeilennummern sind gegen die gesperrte Baseline gültig; jede Änderung an der
Engine würde den Audit-Anker brechen.

## 11. Technische Injektions-Invariante

Die Hook-Stellen sind **verschachtelte Closures** innerhalb von `_se_trades`
(`_blockiert_durch_aussenkante` Z. 2428, `_kandidat` Z. 2471) — sie sind
**nicht** modul-level und damit **nicht** per Attribut-Monkeypatch von außen
ersetzbar. Die Bindung des Adapters erfolgt daher ausschließlich über
Namens-Injektion in den `exec`-Namespace der gepatchten `_se_trades`
(nachgewiesen in `tmp_hook_semantik_check.py`: `engine._in_scope = …`,
`engine._wand_erreicht = …`, `engine._phasen_ziel = …`).
⇒ Ein „Adapter-Registry"-Muster ist in v0.1 nicht implementierbar, ohne die
Engine zu ändern.

---

# Addendum v0.3 — Arretierung 1–6 + Q1-Gate (Mentor-Audit 3, 2026-09-09)

Weiterhin read-only: kein Lauf, kein Compile, kein Test, keine Datei-Erstellung.

## 12. Arretierte Entscheidungen

| # | Entscheidung | Wirkung |
|---|---|---|
| 1 | `boden.kid=77` → **Fail-Loud** (`ValueError`) | stummer `Optional`-Pfad verworfen |
| 2 | `ziel_preis_long = 69.9140` (Spiegel U_final) | August-inert (nur 2 SHORT in P9) |
| 3 | Freigabe **nur** bei `dist < 0` | Q1-Setups (`dist >= 0`) unberührt |
| 4 | `provenienz_basis(K67) = 69.9140` | rein dokumentarisch |
| 5 | `boden.provenienz_basis` **und** `ziel_preis_short` bleiben | Struktur vs. Execution |
| 6 | Datei-Erstellung freigegeben | Schritt 2/3 |

## 13. Beweis: das `dist < 0`-Gate ist benchmark-inert

- **A:** `dist(K67)@980 = −0.0996 %`, `@1020 = −0.0390 %` ⇒ Gate erfüllt
  (`tmp_audit_kandidat_trace_out.txt` Z. 5/48).
- **B:** Bei `dist >= 0` ist die Kante erreicht (M6 `continue`) bzw. `pos0`
  handelbar (Q1) ⇒ Gate stellt dort **V0** wieder her.
- **C:** In P9 (848–1020) existiert **kein** V0-Trade (V0-H2: 639, 650, 679,
  715, 760, 853) ⇒ „Rückfall auf V0" kann in P9 nichts erzeugen.
- **D:** In M6 bleiben nach `b <= sweep_px → continue` (OBEN) bzw.
  `b >= sweep_px → continue` (UNTEN) nur Kanten mit `dist < 0` ⇒ Gate in
  Hook 1b **tautologisch**.

⇒ Soll = V5: H2 7 / **+7.9021 R**, Benchmark **+5.4212 R**,
H1 bit-identisch 8 / **+38.964262 R**.

## 14. Kritische Klarstellung zur Implementierung

„Nur im `dist < 0`-Zweig" = **Prädikat-Gate**, **nicht** Verschiebung des
Aufrufs als `continue` in den `dist<0`-Zweig. Letzteres ist Variante **V1**
und gemessen **inert** (H2 5 / +2.4809 R, kein K73-Trade), weil M6 K73
weiterhin sperrt. Zwingend bleibt: **Pool-Filter (1a) + `continue` in M6 (1b)**.

## 15. Korrekturen an der Mentor-Signatur

1. **Kein Default `ist_dist_negativ=True`** — ein vergessenes Argument würde
   den permissiven Pfad stillschweigend aktivieren (Widerspruch zu Fail-Loud).
2. **Vorzeichen intern ableiten** (empfohlen): `dist_pct` aus `sweep_px` und
   `basis_k`; Bedingung exakt `dist_pct >= 0.0 → continue` (strikt `< 0.0`
   wie Z. 2518; `dist == 0.0` ist der Durchstich-Zweig).
   Grund: 1a (`_dist(e)`) und 1b (rohe `b` vs. `sweep_px`) berechnen `dist`
   unterschiedlich — ein externer Flag wäre eine neue Fehlerklasse.
3. **Gate-Kante = `seite_kid`** (genau eine pro Aufruf, Entscheidung #6),
   identisch in 1a und 1b.

## 16. Fail-Loud-Init (`verifiziere_gegen_scan(scan) -> None`)

| Prüfung | Verhalten |
|---|---|
| `decke.kid` existiert | `ValueError` |
| `decke.seite == "OBEN"` | `ValueError` |
| `boden.kid` existiert | `ValueError` |
| `boden.seite == "UNTEN"` | `ValueError` |
| `|basis − provenienz_basis| / provenienz_basis × 100 > 1.0 %` | `ValueError` |

K67-Probe: `69.9687` vs. `69.9140` = **0,0783 %** ⇒ passiert.

## 17. Sollwerte Schritt 3

| Test | Sollwert |
|---|---|
| 1 Fail-Loud | läuft ohne Exception; manipuliertes `kid` → `ValueError` |
| 2 H1 | 8 Trades / **+38.964262 R**, per-Trade-R bit-identisch |
| 3 H2 | 7 / **+7.9021 R**; K73@980 +2.4119, K73@1020 +3.0093, Summe **+5.4212**; Park: K1@639 −1.0000, K3@650 −1.0000, K45@679 +6.4809, K16@715 −1.0000, K51@760 −1.0000; **K59@853 fehlt** |
| 3b BLOCKIERT | `hook_2_ziel(1025,"SHORT").modus is BLOCKIERT`; Aufrufstelle `stats["kein_raum"] += 1` |

---

# Addendum v0.4 — Umsetzung + Verifikation (2026-09-09)

Startsignal erteilt; Schritt 2 und 3 ausgeführt.

## 18. Artefakte

| Datei | Zeilen | Bytes | Format |
|---|---|---|---|
| `backtest_lab/phasen_regime_adapter.py` | 281 | 11.218 | LF, kein BOM |
| `test/tmp_test_phasen_regime_adapter.py` (gitignored) | 246 | 9.785 | LF, kein BOM |

Engine unverändert: `test/tmp_kanten_engine_replay.py` SHA256
`3ba15c723958161f…5255cb006` (nach der Ausführung erneut geprüft).

## 19. Abweichungen vom Mentor-Vertrag (3 Korrekturen, implementiert)

1. **`verifiziere_gegen_scan`-Signatur.** Der Vertrag
   (`Sequence[Mapping[str, object]]`) wäre an `scan["edges"]` gescheitert:
   `_SEEdgeH` ist `@dataclass(slots=True)` ohne `__getitem__`/`__iter__`,
   `"kid" in e` wirft `TypeError`. Neu: `Sequence[Tuple[int, str, float]]`
   (`kid, seite, basis_bei(ref_bar)`) — flache Tupel, Adapter bleibt
   Engine-frei. Basis-Abweichung gegen `provenienz_basis` wird geprüft
   (Toleranz `provenienz_toleranz_pct = 1.0`).
2. **`segmente`-Default.** `()` würde jede Regime-Anfrage still auf
   `BLOCKIERT` setzen. Default ist `(P9,)`.
3. **Eine Auswertung pro (Bar, Richtung).** `_freigabe_kid` wird einmal
   berechnet und von Hook 1a und 1b **geteilt** (statt zwei unabhängiger
   Aufrufe) ⇒ Desynchronisation ausgeschlossen, O(1) statt O(n) pro
   Blocker-Iteration.

## 20. Verifikationsergebnis (`tmp_test_phasen_regime_adapter_out.txt`)

**Test 1 — Fail-Loud: OK.**

| Kante | seite | basis_bei(980) | provenienz | Abweichung |
|---|---|---|---|---|
| K67 | OBEN | 69.9687 | 69.9140 | 0,0783 % |
| **K77** | **UNTEN** | **68.3920** | 68.3700 | **0,0322 %** |

⇒ **`boden.kid = 77` ist damit empirisch bestätigt** (Existenz, Seite UNTEN,
Basis im Band) — der in v0.2 als „unverifiziert" markierte Wert ist gültig.
Negativproben (unbekannte kid, falsche Seite) werfen `ValueError`. ✅

**Test 2 — H1-Regression: OK.**

| Lauf | Trades | R |
|---|---|---|
| V0 (Original) | 8 | +38.964262 |
| V1 (Adapter) | 8 | **+38.964262** |

**Per-Trade-R bit-identisch** (Toleranz 1e-12). ✅

**Test 3 — H2-Benchmark: OK.** 7 Trades / **+7.9021 R**

| sig | Zeit | kid | stufe | entry | sl | tp2 | R |
|---|---|---|---|---|---|---|---|
| 639 | 18.08. 23:45 | 1 | STUFE_1_IN_BAR | 63.5340 | 63.2980 | 66.4590 | −1.0000 |
| 650 | 19.08. 03:30 | 3 | STUFE_3_KERZE_3 | 63.0110 | 62.6710 | 66.4590 | −1.0000 |
| 679 | 19.08. 10:45 | 45 | STUFE_2_KERZE_2 | 63.1810 | 62.7920 | 66.4590 | +6.4809 |
| 715 | 19.08. 19:45 | 16 | STUFE_1_IN_BAR | 65.8820 | 65.9550 | 62.5625 | −1.0000 |
| 760 | 20.08. 08:00 | 51 | STUFE_2_KERZE_2 | 66.9900 | 67.2370 | 62.5625 | −1.0000 |
| **980** | 24.08. 17:00 | **73** | STUFE_2_KERZE_2 | 69.4910 | 69.9490 | **68.3700** | **+2.4119** |
| **1020** | 25.08. 04:00 | **73** | STUFE_1_IN_BAR | 69.5780 | 69.9740 | **68.3700** | **+3.0093** |

K73@980 +2.4119 ✅ · K73@1020 +3.0093 ✅ · **Summe +5.4212 R** ✅ ·
K59@853 entfällt ✅ · Park-Trades unverändert (K16@715, nicht 716 — Scope
848 hält den Park in MAKRO) ✅

**Test 3b — Tri-State: OK.** bar 640 → MAKRO · bar 900 → PHASE (68.37) ·
bar 1025 → BLOCKIERT · bar 1150 → BLOCKIERT ✅

**Stats-Diff V0 → V1:** `kein_raum` 1→11 · `quartil_blockiert` 56→57 ·
`v_s` 14→15 · `zyklus_blockiert` 36→27 · `blocker` 23→23 (unverändert, weil
`_kandidat` bei Bar 980/1020 in V0 vor dem M6-Gate abbrach).

## 21. Status

Schritt 2 und 3 abgeschlossen. Keine Engine-Änderung, keine Regression in H1.
`backtest_lab/phasen_regime_adapter.py` ist **untracked** (Commit offen);
`test/` bleibt gitignored.

---

# Addendum v0.5 — Commit + P12-Trockenübung (2026-09-09)

## 22. Commit

`cd0e1b3` — *feat(backtest_lab): H2-Phasen-Regime-Adapter v0.1 (P9,
Tri-State, Fail-Loud)*. Enthält `backtest_lab/phasen_regime_adapter.py` (281
Zeilen) und diese Spez (511 Zeilen). `test/` bleibt gitignored;
`reports/setup_c/` unverändert untracked.

## 23. P12-Trockenübung (`test/tmp_dryrun_p12.py`, read-only)

### A) Kanten-Identität (Ref-Bar 1259)

| kid | seite | geb | erster_pivot | basis_bei(1259) | touch_conf | aktiv@1259 |
|---|---|---|---|---|---|---|
| 67 | OBEN | 881 | 873 | 69.9458 | 5 | True |
| **73** | **OBEN** | 928 | 909 | **69.6714** | 5 | True |
| 77 | UNTEN | 991 | 934 | 68.3597 | 6 | **False** |
| **82** | **UNTEN** | 1056 | 1031 | **67.5273** | 3 | True |

### B) Fail-Loud P9+P12: **OK** (K73 0,167 % / K82 0,160 % zu Provenienz)

### C) V0-Trades in P12: **0** · Tri-State: 1170 BLOCKIERT, 1171–1272 PHASE,
1273 BLOCKIERT ✅

### D) Sweep-im-Band der P12-Grenzkanten (0,12 %): **4 Treffer**

| bar | Zeit | Richtung | Kante | basis | sweep | dist | Art |
|---|---|---|---|---|---|---|---|
| 1211 | 27.08. 05:45 | SHORT | K73 | 69.6865 | 69.6110 | −0,1083 % | Docht-Defizit |
| 1259 | 27.08. 17:45 | LONG | K82 | 67.5273 | 67.6000 | −0,1076 % | Docht-Defizit |
| 1271 | 27.08. 20:45 | SHORT | K73 | 69.6714 | 69.5910 | −0,1154 % | Docht-Defizit |
| 1272 | 27.08. 21:00 | SHORT | K73 | 69.6714 | 69.7140 | +0,0611 % | Durchstich (Q1) |

### E) Adapter-Lauf (P9+P12)

- **H1 bit-identisch** 8 / +38.964262 R ✅
- **P12: V0 0 Trades → V1 0 Trades** — P12 ist im August **inert**
- H2 V1 = **+7.9021 R** = identisch zum P9-only-Lauf (P12-Beitrag = 0)

### F/G) Warum kein P12-Trade entsteht

| bar | Richtung | Freigabe | Kandidat danach | Sperre |
|---|---|---|---|---|
| 1211 | SHORT | K73 | K76 (dist +0,149 %) | **M6: K67** (69.9458, +0,6308 %) |
| 1271 | SHORT | K73 | K76 (dist +0,109 %) | **M6: K67** (69.9458, +0,6194 %) |
| 1272 | SHORT | – (dist>0) | K73 (dist +0,061 %) | **M6: K67** (69.9458, +0,3938 %) |
| 1259 | LONG | K82 | K62 (dist +0,196 %) | **Q29 Quartil** (67.600 Mitte der Range) |

### Zentraler Befund: invertierte Freigabe-Wirkung in P12

In **P9** war die freigestellte Wand (K67) der *äußere Blocker*; die
Handelswand war die Innenlinie K73. In **P12** ist die freigestellte Wand
(K73) die **Phasen-Decke selbst** ⇒ ihre Freigabe entfernt sie aus dem Pool
und promoviert die Innenlinie K76. Die Außenwand K67 bleibt als M6-Blocker
bestehen — und weil K67 **nicht** die P12-Grenzkante ist, greift
Entscheidung #6: **keine Freigabe für K67 in P12.** Das ist der gewollte
institutionelle Selbstschutz, nicht ein Fehler.

### Konsequenz für v0.2

1. `ziel_preis_short = 67.6355` ist als **Provenienz-Norm** (v0.4 `L_final`)
   gesetzt, aber **empirisch unbelegt**: kein August-Trade konsumiert das
   Ziel. Die Trockenübung validiert **Existenz und Orientierung** der Kanten,
   **nicht** den Zielwert.
2. P12 kann ohne jede Benchmark-Wirkung in `segmente` aufgenommen werden
   (H1/H2 bit-identisch) — es ist dann eine **dokumentarische** Reserve.
3. Stats-Diff V0 → V1 (P9+P12): `blocker` 23→25 · `quartil_blockiert` 56→58 ·
   `kein_raum` 1→11 · `zyklus_blockiert` 36→27 · `v_s` 14→15.

### Offene Frage an den Mentor

Soll P12 als **inertes** Segment in `segmente` aufgenommen werden
(Sicherheit: fail-closed, 0 Benchmark-Wirkung, aber „tote" Konfiguration),
oder bleibt es bis zum Nachweis eines handelbaren P12-Fensters in einem
**separaten** Segment-Katalog (z. B. `P12_RESERVE`) außerhalb der aktiven
Default-Liste?

---

# Addendum v0.6 — Konsolidierung (Mentor-Audit 4, 2026-09-09)

## 24. Entscheidungen

### 24.1 `P12_RESERVE` — bestätigt, aber mit Bindungsbedingung

Die Reserve-Strategie ist bestätigt: `P12_RESERVE` wird definiert,
`segmente` bleibt standardmäßig `(P9,)`. **Zusatzbedingung gegen toten Code:**
Eine Modul-Konstante, die kein Produktionspfad liest, ist per Definition
totes Kapital — genau das, was die Reserve-Strategie verhindern soll. Sie ist
nur dann zulässig, wenn sie **verifiziert** wird. Vorgeschlagene Form:

```python
AKTIVE_DEFAULT_SEGMENTE: Tuple[PhasenSegmentEintrag, ...] = (P9,)

P12_RESERVE: PhasenSegmentEintrag = PhasenSegmentEintrag(
    phasen_id="P12", start_bar=1171, end_bar=1272,
    decke=PhasenKanteInfo(kid=73, provenienz_basis=69.5550),
    boden=PhasenKanteInfo(kid=82, provenienz_basis=67.6355),
    ziel_preis_short=67.6355, ziel_preis_long=69.5550,
)

RESERVE_SEGMENTE: Tuple[PhasenSegmentEintrag, ...] = (P12_RESERVE,)

# im Adapter:
segmente: Tuple[PhasenSegmentEintrag, ...] = AKTIVE_DEFAULT_SEGMENTE
```

Bindung: Der Test prüft `PhasenRegimeAdapter(segmente=RESERVE_SEGMENTE)` mit
`verifiziere_gegen_scan` (Fail-Loud P12). Damit ist die Konstante
**ausgeführt**, nicht nur deklariert. Status: **Entwurf, nicht angewendet**
(Phase: kein Feature-Code).

### 24.2 Commit-Strategie

Dieser Commit enthält **ausschließlich die Spezifikation** (Dokumentation).
Die Moduländerung (24.1) folgt als eigener Commit nach explizitem
Implementierungs-Go. Vorteil: Die P12-Befundlage ist revisionssicher
arretiert, bevor Code sie referenziert.

### 24.3 Transition-Zone 640–847 — Exploration hiermit abgeschlossen

**Die H2-Adapter-Exploration ist mit v0.1 abgeschlossen.** Die
Transition-Zone wird **nicht** als Fortsetzung angehängt, sondern als
eigenes, **baseline-veränderndes** Entscheidungsfeld geführt. Begründung:

1. **Sie ist Teil der arretierten Baseline.** Lauf B (+40.445143 R) enthält
   5 Park-Trades (K1@639, K3@650, K45@679, K16@715, K51@760) mit
   **+2.4809 R**. Eine Fail-Closed-Behandlung würde diese 5 Trades und
   damit die Referenz verändern — das ist keine Adapter-Erweiterung.
2. **Sie läuft heute unter MAKRO.** Beweis aus dem Adapter-Lauf: die
   Park-Trades tragen `tp2 = 66.4590` (K1/K3/K45) bzw. `62.5625`
   (K16/K51) — Makro-Gegenkanten, **nicht** Phasenziele. Der Adapter lässt
   sie unangetastet (`start_scope_bar = 848`).
3. **Die Stichprobe trägt keine Regime-Aussage.** 5 Trades, davon
   **1 Ausreißer** (K45@679 +6.4809 R) und 4 × −1.0000 R. Ohne diesen
   Ausreißer wäre der Park −4.0000 R. Darauf lässt sich kein Regime bauen.
4. **Kein v0.4-Segment deckt 641–847 ab** (Lücke zwischen P8-Ende 840 und
   P9-Start 848). Eine Zuweisung wäre eine neue Struktur-Entscheidung, keine
   Adapter-Frage.

**Fragenkatalog für das spätere, getrennte Vorgehen:**

| # | Frage | Wirkung |
|---|---|---|
| T1 | Soll 641–847 ein eigenes Regime („Settlement/Transition") erhalten? | verändert Lauf B |
| T2 | Falls ja: welche Kanten sind Decke/Boden? (Kandidaten: K20 66.4590, K42 62.5625) | neue Fail-Loud-Prüfung |
| T3 | Falls nein: bleibt MAKRO dauerhaft — und ist das dokumentiert? | reine Dokumentation |
| T4 | Ist der Ausreißer K45@679 (+6.4809 R) reproduzierbar oder Zufall? | Statistik, nicht Adapter |
| T5 | Ändert `start_scope_bar = 848` die Lauf-B-Referenz? (Messung: **nein**) | bereits belegt |

## 25. Stand nach Konsolidierung

| Gegenstand | Status |
|---|---|
| P9 (848–1020, K67/K77, Ziel 68.3700) | **aktiv, verifiziert** (+5.4212 R) |
| P12 (1171–1272, K73/K82, Ziel 67.6355) | **Reserve**, strukturell validiert, empirisch inert |
| H1-Baseline | bit-identisch 8 / +38.964262 R |
| Engine | unverändert (SHA256 `3ba15c72…`) |
| Transition-Zone 640–847 | **offen**, separat, baseline-verändernd |

---

# Addendum v0.7 — Reserve-Struktur implementiert (2026-09-09)

## 26. Umsetzung (Dreiteilung)

`backtest_lab/phasen_regime_adapter.py`:

```python
P9: PhasenSegmentEintrag = ...                 # unverändert
AKTIVE_DEFAULT_SEGMENTE: Tuple[...] = (P9,)
P12_RESERVE: PhasenSegmentEintrag = ...        # kid 73/82, Ziel 67.6355
RESERVE_SEGMENTE: Tuple[...] = (P12_RESERVE,)
# PhasenRegimeAdapter.segmente default = AKTIVE_DEFAULT_SEGMENTE
```

Modul-Docstring erweitert: Dreiteilung dokumentiert, Transition-Zone explizit
als **kein** Segment ausgewiesen.

## 27. Bindungsprüfung (Test 1b, neu)

| Prüfung | Ergebnis |
|---|---|
| Katalog-Bar `REF_BAR_RESERVE = 1259` (für P9 **und** P12 gültig) | K73 `OBEN` 69.6714 · K82 `UNTEN` 67.5273 |
| `verifiziere_gegen_scan(RESERVE_SEGMENTE)` | **OK** (Existenz, Seite, Basisband) |
| `AKTIVE_DEFAULT_SEGMENTE` | `['P9']` |
| `DEFAULT_ADAPTER.segmente` | `['P9']` → Reserve **nicht** aktiv |
| `DEFAULT_ADAPTER.hook_2_ziel(1200, "SHORT")` | **BLOCKIERT** (fail-closed) |

**Begründung des Referenz-Bars:** `REF_BAR = 980` ist für P12 untauglich —
K82 hat `erster_pivot = 1031`, daher liefert `basis_bei(980)` die
Initial-Basis statt der kausalen Mittel-Basis. Bar 1259 ist für beide
Segmente gültig (K67 0,0455 % · K77 0,0150 % · K73 0,167 % · K82 0,160 %).

## 28. Regressionsnachweis nach der Moduländerung

| Prüfung | Soll | Ergebnis |
|---|---|---|
| H1 (bit-identisch) | 8 / +38.964262 R | **8 / +38.964262 R** ✅ |
| K73@980 | +2.4119 | **+2.4119** ✅ |
| K73@1020 | +3.0093 | **+3.0093** ✅ |
| Summe | +5.4212 | **+5.4212** ✅ |
| K59@853 | entfällt | **entfällt** ✅ |
| Tri-State 640/900/1025/1150 | MAKRO/PHASE/BLOCKIERT/BLOCKIERT | **alle OK** ✅ |

Engine unverändert: SHA256 `3ba15c72…`.

## 29. Transition-Zone — Entscheidung geschlossen

**Nicht anfassen.** Dauerhaft MAKRO unter `start_scope_bar = 848`; keine
weiteren Regime-Untersuchungen. Die Zone bleibt exakt der arretierte Zustand
von Lauf B (5 Trades / +2.4809 R). Fragen T1/T2/T4 sind damit geschlossen,
T3 („MAKRO dauerhaft, dokumentiert") ist erfüllt.

---

# Addendum v0.8 — Neuer PNG-Satz für den Sichttest (AUG komplett)

## 30. Auftrag und Artefakt

Auftrag: „mache ein neues Set von PNG für den Sichttest über AUG komplett".

| Datei | Zeilen | Bytes | Status |
|---|---|---|---|
| `test/tmp_png_aug_sichttest.py` | 703 | 32.303 | gitignored (kein Commit) |
| `test/tmp_png_aug_sichttest_out.txt` | – | – | gitignored (Lauf-Protokoll) |

Erzeugt **5 PNGs** (dpi 300) in `test/`, read-only, Engine unverändert
(SHA256 `3ba15c72…5255cb006` nach dem Lauf erneut geprüft):

| # | Datei | Fenster | Pixel | Bytes |
|---|---|---|---|---|
| 01 | `aug_sichttest_01_gesamt.png` | 0..1288 | 6600×3900 | 1.657.807 |
| 02 | `aug_sichttest_02_h1_box.png` | 0..660 | 6000×3600 | 652.507 |
| 03 | `aug_sichttest_03_h2_phasen.png` | 620..1288 | 6600×3600 | 1.168.856 |
| 04 | `aug_sichttest_04_p9_regime.png` | 820..1045 | 6300×3600 | 698.274 |
| 05 | `aug_sichttest_05_kantenkarte.png` | 0..1288 | 6600×3900 | 1.626.925 |

## 31. Eingebaute Asserts (Fail-Loud, alle erfüllt)

| Assert | Soll | Ist |
|---|---|---|
| V0 Trades / R | 14 / ≈ +40.45 | **14 / +40.445143** ✅ |
| H1 V1 (bit-identisch) | 8 / +38.964262 ± 1e-6 | **8 / +38.964262** ✅ |
| H2 V1 | 7 / +7.9021 ± 1e-3 | **7 / +7.902085** ✅ |
| Regime-Summe K73 | +5.4212 ± 1e-3 | **+5.4212** ✅ |

Gesamt V1: **15 Trades / +46.866348 R** (H1 8 / +38.964262 + H2 7 /
+7.902085). Voll-Lauf (`scan["box_end_bar"] = n = 1288`), Adapter v0.1
(`segmente = (P9,)`, `start_scope_bar = 848`), Bindung per RAM-Patch
(identische AST-Anker wie `tmp_test_phasen_regime_adapter.py`).

## 32. Inhalt der Grafiken

| # | Inhalt |
|---|---|
| 01 | Close-Linie + Wicks, alle 15 Trades, H1/H2-Trennung bei 640, Phasen-Zonen, Kanten-Linien mit `kid`, Tombstone-Bänder, Sweep-Sperren (×), H2-Neugeburten (▲), 7-zeiliges Statistik-Panel |
| 02 | Kerzen 0..660, H1-Box grau hinterlegt, 8 H1-Trades (gefüllt), Trade-Detail-Zeile im Panel |
| 03 | Kerzen 620..1288, 7 H2-Trades, **grün = P9 AKTIV**, **grau = P12 RESERVE**, rot schraffiert = Lücken (BLOCKIERT), Park-Zeile (K1/K3/K45/K16/K51 = 5 / +2.4809 R) |
| 04 | P9-Detail: K67/K73/K76/K77/K82 fett, `U_final 69.9140` / `L_final 68.3700 (Ziel)` als Strichlinien, Hook-1/Hook-2-Annotation an Bar 980 + 1020, Sweep-Sperren |
| 05 | Kanten-Landkarte ohne Kerzen (nur Close): 59 edges + 14 seeds, R21-gelöschte Kanten **unsichtbar** (nur Tombstone-Bänder), Statistik zu R21/Promotionen |

## 33. Konventionen (eingehalten)

- Statistik **mittig** im unteren Panel (`stats_panel`, `ha="center"`).
- Legende **oben links** (`legend`, `loc="upper left"`).
- H1/H2-Grenze aus `scan["box_end_bar"]` (640) interpoliert, **nicht**
  hardcodiert — behebt die Altlast des 644-Labels früherer Skripte.
- `matplotlib.use("Agg")` (kein GUI), LF-only, kein BOM, deutsche Docstrings.

## 34. Korrektur während des Laufs

Erster Lauf erzeugte 4 × `UserWarning: Setting the 'color' property will
override the edgecolor or facecolor properties` (Hatch-Flächen in
`shade_phases` bzw. `png_04`). Ursache: `axvspan(color=…, edgecolor=…)`.
Behoben durch `facecolor=C_GAP` + `edgecolor=C_GAP`; zweiter Lauf ist
**warnungsfrei**, Pixelmaße und Bytegrößen der PNGs sind identisch
(deterministisches Rendering). Zusätzlich `box_end` im 01-Label als f-String
verankert.

## 35. Status

Sichttest-Satz bereitgestellt. Da `test/` gitignored ist, sind Skript und
PNGs **nicht** versioniert; Reproduktion:

```
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe test\tmp_png_aug_sichttest.py
```

Kein Engine-Eingriff, keine Adapter-Änderung, keine Baseline-Veränderung.

---

# Addendum v0.9 — Zeitschichten-Korrektur, Audit-Richtigstellung & Artefakt-Hygiene (2026-09-10)

**Freigaben:** Z1–Z5 (Mentor, 2026-09-10). **Wirkung:** Dokumentation und
Artefakt-Hygiene. Keine Regeländerung, kein Engine-Eingriff, keine
Baseline-Veränderung.

---

## 36. Verbindliche Zeitkonvention (bindend für alle Beteiligten)

1. **Broker-OHLC-Zeit ist die einzige Zeitbasis.** Sie wird aus
   `data/market_data.duckdb` bzw. der Referenz-CSV über `time AT TIME ZONE
   'UTC'` erzeugt (Wanduhr-Garantie, `Agents.md`).
2. **Der Bar-Index ist der Primärschlüssel** jeder Aussage. Zeitstempel sind
   nachrangig.
3. **Tabellenpflicht (drei Spalten):** `Bar | Broker/UTC | Berlin (+2 h, nur
   Altzitate)`.

### 36.1 Drei Zeitschichten — Ursache der Desynchronisation

| Schicht | Bar 1211 | Bar 1259 | Verwendung |
|---|---|---|---|
| **Broker / CSV** (`AT TIME ZONE 'UTC'`) | 27.08. **03:45** | 27.08. **15:45** | Rohdaten, ab v0.9 Leitwährung |
| **Engine-Anzeige** (`Europe/Berlin`) | 27.08. **05:45** | 27.08. **17:45** | `_p11`, Tabellen v0.5, PNG-Achsen |
| **Bar-Index** | **1211** | **1259** | alle Gates, `basis_bei(k)` |

Die frühere Tabellenzuordnung paarte **Broker-Zeitstempel mit Bar-Indizes aus
Berlin-Kontext-Tabellen** → 8 Bars (2 h) Versatz. Alle daraus abgeleiteten
Dichtigkeitsurteile (u. a. „Docht 69,49 gehört zu K76") sind damit ungültig.

### 36.2 Arretierte Box-Grenze: `box_end_bar = 640` (Z1)

`640` bleibt als **logische Partitionsgrenze der H1-Baseline eingefroren** —
**nicht** 644. Die Broker/UTC-Konvention gilt für alle **Zeit- und
Datumsangaben**, **nicht** für die Bar-Zählung der Baseline.

> **Interlock (kritisch):** `640` entsteht heute aus
> `np.searchsorted(ts_arr, "2026-08-19")` über die **Berlin-projizierte**
> Spalte (L600 → L2185). Unter Broker-Projektion liefe dieselbe Zeile auf
> **644**:

| Projektion | `box_end_bar` | Lauf A / H1 | H2 (V0) |
|---|---|---|---|
| Berlin (heutiger Stand, `_p11`) | **640** | 8 / **+38.964262** | 6 / +1.480880 |
| Broker/UTC | 644 | 9 / +37.964262 | 5 / +2.480880 |

**Gesamt-R ist in beiden Fällen invariant** (V0 14 / +40.445143 · V1 15 /
+46.866348) — es verschiebt sich ausschließlich die Partition (der Trade mit
`entry_bar = 640`, `K1@639`, −1.0000 R rutscht bei 644 nach H1).

Daraus folgt zwingend: **Zeile 600 musss Berlin bleiben (Z2) UND `640` bleibt
die logische Grenze.** Wer je die Projektion umstellt, muss `box_end_bar` hart
auf `640` setzen — sonst kippt die arretierte H1-Baseline. Diese Kopplung ist
in `Agents.md` als eingefrorene Ausnahme hinterlegt (§40).

### 36.3 `_p11`-Patch bleibt byte-identisch (Z2)

| Artefakt | SHA256 |
|---|---|
| `test/tmp_kanten_engine_replay.py` | `3ba15c723958161fffc28a106a5758bd3e27a6152f0e0235969594a5255cb006` |
| `docs/artefakte/aug_p11/kanten_engine_replay_v40r.py.snapshot` | identisch (byte-gleich) |

**Kein Revert.** Die Berlin-Projektion ist ab v0.9 eine **historische
Anzeige-Abweichung**: Sie berührt keine Zahl der Baseline (Zeilensatz
byte-identisch), nur Labels. Ein Revert würde die Signatur brechen und den
Audit-Trail entwerten. Konsequenz: Zeitangaben in Altdokumenten
(`CHECKPOINT_2026-09-09.md`, Addenda v0.5–v0.8, `docs/`) sind **+2 h** zu
lesen (siehe §36.1).

---

## 37. Richtigstellung der Kanten-Identitäten

### 37.1 K82-Touchmenge (Mean-Beweis, exakt)

```
basis_bei(1259) = (67,535 + 67,553 + 67,494) / 3 = 67,52733  ==  Engine 67,5273
```

| Bar-Index | Broker/UTC | Berlin (+2 h, historisch) | Low | Rolle |
|---|---|---|---|---|
| 1031 | 25.08. 04:45 | 25.08. 06:45 | 67,535 | Wick (erster Pivot) |
| 1056 | 25.08. 11:00 | 25.08. 13:00 | 67,553 | Wick |
| 1172 | 26.08. 17:00 | 26.08. 19:00 | 67,494 | Wick |
| 1075 | 25.08. 15:45 | 25.08. 17:45 | 67,420 | Sweep **unter** dem Band |
| 1259 | 27.08. 15:45 | 27.08. 17:45 | 67,600 | **Sweep im Band** (−0,1076 %) |

Ergebnis: **drei** bestätigte Touches (Typ B erreicht), geschlossene
Mittelbasis 67,52733. „67,60" ist ein **Dochtextremum**, kein Kantenniveau.

### 37.2 K74 = R21-Tombstone → „69,62" ist gestrichen

| Bar-Index | Broker/UTC | Berlin (+2 h, historisch) | Ereignis |
|---|---|---|---|
| 912 | 21.08. 21:00 | 21.08. 23:00 | K74-Pivot (`basis = 69,613`) |
| 1104 | 26.08. 00:00 | 26.08. 02:00 | R21-Löschung K74 (Tombstone) |

| Feld | Wert |
|---|---|
| Kante | K74 OBEN, `basis = 69,613`, `pivot_bar = 912` |
| Status | **gelöscht durch R21 bei Bar 1104** (`R21: geloescht 17 / Tombstones 17`) |
| Konsequenz | In P12 (1171–1272) **existiert diese Linie nicht**; „69,62" wird als Level **gestrichen** |

### 37.3 K73-Touchlage (dreispaltig, normiert)

| Bar-Index | Broker/UTC | Berlin (+2 h, historisch) | `basis_bei` | dist | Urteil |
|---|---|---|---|---|---|
| 1211 | 27.08. 03:45 | 27.08. 05:45 | 69,6865 | **−0,1083 %** | **im 0,12-%-Band → K73-Touch** (Docht-Defizit, Hook greift) |
| 1271 | 27.08. 18:45 | 27.08. 20:45 | 69,6714 | **−0,1154 %** | im Band → K73-Touch |
| 1272 | 27.08. 19:00 | 27.08. 21:00 | 69,6714 | **+0,0611 %** | Durchstich (Q1) |
| 1203 | 27.08. 01:45 | 27.08. 03:45 | – | – | H = 68,987 → **kein** K73-Touch |
| 1264 | 27.08. 17:00 | 27.08. 19:00 | – | – | H = 68,746 → **kein** K73-Touch |

`touch_conf(1259) = 5`. Die frühere Zuordnung „Docht 69,49 gehört zur
Innenkante K76" ist gegenstandslos: **K76 liegt bei 69,507 (Bar 1211) /
69,515 (Bar 1271)**, der reale Docht ist **69,611**. Es gibt bei Bar 1211
**keinen** Dochtpreis 69,49.

### 37.4 Nomenklatur-Register (verbindlich)

Referenz-Bars des Registers (Dreispalten-Pflicht, `Agents.md`):

| Bar-Index | Broker/UTC | Berlin (+2 h, historisch) |
|---|---|---|
| **1211** | 27.08. 03:45 | 27.08. 05:45 |
| **1259** | 27.08. 15:45 | 27.08. 17:45 |

| Kante | Seite | Provenienz-Basis | `basis_bei(1259)` | kausal @1211 | Status |
|---|---|---|---|---|---|
| K67 | OBEN | 69,9140 | 69,9458 | – | M6-Außenwand |
| K73 | OBEN | 69,5550 | **69,6714** | 69,6865 | P12-Decke |
| K76 | OBEN | – | – | **69,507** | Innenlinie |
| K82 | UNTEN | 67,6355 ¹ | **67,5273** | – | P12-Boden |
| ~~K74~~ | OBEN | ~~69,613~~ | – | – | **R21-eliminiert (Bar 1104)** |

**¹ K82 — drei Werte, drei Rollen (Entscheidung: Option (b), revisionssicher).**

`67,6355` bleibt als **historische v0.4-Provenienz-Norm** stehen und wird
**nicht** ersetzt — Altdokumente (v0.4–v0.8, `docs/`) behalten damit ihre
Gültigkeit. Es ist **nicht** die reale Kante am P12-Boden. Abgrenzung:

| Wert | Rolle | Herleitung | Zeilen |
|---|---|---|---|
| **67,6355** | **v0.4-Provenienz-Norm** (historisch) | Altzitat; keine Rekonstruktion aus der heutigen Scan-Rechnung. Als Kante **nicht** handelbar — die Engine führt sie nicht. | – |
| **67,5455** | **finale Scan-Basis** (`e.basis`) | Mittel **aller vier** bestätigten Wicks: `(67,535 + 67,553 + 67,494 + 67,600) / 4 = 67,5455` | Bars 1031 / 1056 / 1172 / 1259 |
| **67,5273** | **kausale Basis** `basis_bei(1259)` | Mittel der **ersten drei** Wicks (§37.1 Mean-Beweis, `pivot_bar + 2 <= 1259`): `(67,535 + 67,553 + 67,494) / 3 = 67,52733` | Bars 1031 / 1056 / 1172 |

**Leseregel:** Provenienz-Norm (Spalte „Provenienz-Basis") ist der
**dokumentarische** Bezugspunkt, `basis_bei(k)` der **operative**. Wo beide
auseinanderfallen (K82: Δ = 0,1082), gilt für jede Handels- und
Darstellungsaussage **`basis_bei(k)`**; die Norm bleibt als Herkunftsvermerk
zitiert. Die Abgrenzung ist damit eindeutig und ohne Verfälschung der
Altdokumente.

**Verankerung im Code (Option (b) ist dort bereits gelebte Praxis):**

| Stelle | Aussage |
|---|---|
| `backtest_lab/phasen_regime_adapter.py` Z. 26–27 (Invariante 2) | „Die Band-Pruefung nutzt IMMER die kausale Basis `basis_bei(k)`; der statische `provenienz_basis`-Wert ist **reine Dokumentation/Audit**." |
| ebd. Z. 73–75 (Docstring `PhasenKanteInfo`) | `provenienz_basis` = „Niveau aus der **v0.4-Baseline** (`U_final`/`L_final`) … NUR Dokumentation/Audit." |
| ebd. Z. 156 (P12-Kommentar) | „Ziel 67.6355 = **v0.4 `L_final`** (Provenienz-Norm, **empirisch noch unbelegt**)." |
| ebd. Z. 162–163 (`P12_RESERVE`) | `boden=PhasenKanteInfo(kid=82, provenienz_basis=67.6355)`, `ziel_preis_short=67.6355` |

Die Norm ist also **nicht** handelbar und **nicht** die Engine-Kante — sie
läuft ausschließlich als **Kommentar- und Auditwert** mit. Genau das verlangt
Option (b).

**Fail-Loud-Probe bleibt grün (1,00-%-Toleranz, Z. 233–248):** Für K82 wird
in der Reserve-Auditierung `basis_bei(1259) = 67,5273` gegen die Norm
geprüft: `|67,5273 − 67,6355| / 67,6355 = 0,1600 %` < `1,00 %`
(mit der finalen Scan-Basis 67,5455 wären es `0,1331 %`). Belegt durch
`test/tmp_test_phasen_regime_adapter.py` (Test 1b: „K 82: seite=UNTEN
basis_bei(1259)=67.5273 … -> OK: P12-Reserve auditiert"). Die Abgrenzung
nach Option (b) bricht die Prüfung **nicht**.

---

## 38. Bestätigte Arretierungen

### 38.1 Entscheidung #6 — M6 bleibt in P12

K67 wird in P12 **nicht** freigegeben. K76-Shorts unter einer unberührten
Außenwand (`basis 69,9458`, dist 0,63 %) sind verboten; der Anstieg auf 69,714
(Bar 1272) ändert daran nichts — er ist ein Durchstich **innerhalb** der
unveränderten Wanddistanz. P12 bleibt `P12_RESERVE`, operativ inert.
**Keine Änderung an `_blockiert_durch_aussenkante`.**

### 38.2 Q29 bleibt global — kein phasen-lokales Quartil

Rohwerte bei Bar 1259 (`ex_hi/ex_lo = hi[:1260]`):

```
ex_hi = 70,000 (Bar 881)   ex_lo = 62,548 (Bar 673)   Spanne = 7,452
dist(LONG, 67,600) = (67,600 − 62,548) / 7,452 × 100 = 67,79 %   Grenze 25 %
```

Die drei SHORT-Treffer passieren das Gate ohnehin (1211: 5,22 % · 1271:
5,49 % · 1272: 3,84 %) — Q29 ist dort **nicht** der Blocker, sondern M6.
Eine Umstellung auf die Phasenspanne wäre eine Kopplung des globalen Filters
an die Segmentdefinition und würde genau **einen** Trade erzwingen → als
Overfitting verworfen. **Keine Änderung an `_im_aussenquartil`.**

---

## 39. Artefakt-Hygiene (Z5)

| Artefakt | Maßnahme | Begründung |
|---|---|---|
| `test/stats_kanten_engine_replay.txt` | **verschoben → `test/trash/`** | Modus-A-Altlast **pre_p11** (Box „Geburt < 18.08., bar 552"), **byte-identisch** zu `test/trash/tmp_backup_gegenprobe_stats.txt` (SHA256 `e0bc32221f26afd09a76c824b0a5846289f0254df3b8f41c9d5724dae78ca59a`), 629.469 B — **nicht** als aktueller Baseline-Report zitierbar |
| `test/tmp_dryrun_p12_out.txt` | **gekennzeichnet, nicht verändert** | Zeiten in Berlin (+2 h) — Beweismittel bleibt unangetastet |
| `test/tmp_hook_semantik_check_out.txt` | **gekennzeichnet, nicht verändert** | ebd. |
| `test/kanten_liste_AUG_mC.txt` | **gekennzeichnet, nicht verändert** | `ts`-Spalte Berlin (+2 h) |
| PNG-Achsen (`aug_sichttest_*.png`, `kanten_engine_*.png`) | **gekennzeichnet, nicht verändert** | x-Labels Berlin (+2 h) |

**Stale Referenz durch den Umzug:** §17 dieser Spez verweist auf den Dateinamen
`stats_kanten_engine_replay.txt` — der Verweis ist historisch zu lesen, die
Datei liegt jetzt unter `test/trash/`. Vollständige Liste:
`reports/aufraeumung/AUFRAEUMUNG_STALE_REFS.md`.

Der laufende `REPORT_TXT`-Schreibpfad der Engine
(`test/tmp_kanten_engine_replay.py`, L108) bleibt **unverändert**; ein
etwaiger künftiger Lauf legt die Datei wieder am alten Ort an.

---

## 40. Invariante in `Agents.md` (Z3)

Neu verankert unter „# Diverse" als **Zeitbasis-Garantie**:

1. **Broker-OHLC-Zeit ist die einzige Zeitbasis** (`time AT TIME ZONE 'UTC'`);
   keine automatische Zeitzonen-Projektion in Auswertungs- oder Display-Logik.
2. **Bar-Index ist der Primärschlüssel**; Tabellen führen
   `Bar | Broker/UTC | Berlin (+2 h, nur Altzitate)`.
3. **Eingefrorene Ausnahme (nicht anfassen):** `Europe/Berlin`-Projektion in
   `test/tmp_kanten_engine_replay.py` Z. 600 und die daraus abgeleitete
   arretierte Grenze `box_end_bar = 640` sind byte-fixiert
   (SHA256 `3ba15c72…`) und **aneinander gekoppelt** — eine Umstellung der
   Projektion verschiebt die Grenze auf 644 und kippt die H1-Partition
   (8/+38.964262 → 9/+37.964262). Änderung nur nach ausdrücklicher manueller
   Freigabe und mit Neu-Arretierung.

---

## 41. Status

| Kennzahl | Wert | Berührt durch v0.9? |
|---|---|---|
| V0 gesamt | 14 / +40.445143 R | nein |
| H1 (Grenze 640) | 8 / +38.964262 R | nein |
| V1 gesamt | 15 / +46.866348 R | nein |
| H2 V1 (P9) | 7 / +7.9021 R | nein |
| Regime-Summe K73 | +5.4212 R | nein |
| Engine SHA256 | `3ba15c72…5255cb006` | nein (unverändert) |

Addendum v0.9 rein dokumentarisch: kein Code ausgeführt, keine Datei der
Engine oder des Adapters angefasst.

---

# Addendum v0.10 — Ausführung der Beschlüsse Q1–Q4 (2026-09-10)

**Freigaben:** Q1–Q4 (Anwender, 2026-09-10). **Wirkung:** eine rein
**lesende Label-Anpassung** in einem gitignored Hilfsskript. Keine
Regeländerung, kein Engine-Eingriff, keine Baseline-Veränderung, keine
PNG-Neugenerierung.

## 42. Ausgeführte Beschlüsse

| # | Beschluss | Ausführung | Artefakt berührt |
|---|---|---|---|
| Q1 | `CHECKPOINT_2026-09-09.md` bleibt historisch | **keine Änderung** | – |
| Q2 | PNG-Achsen → Option (ii): Label-Logik deklarativ auf Broker/UTC | **umgesetzt** (s. 43) | `test/tmp_png_aug_sichttest.py` |
| Q3 | `docs/reclaim_kanten_engine_spez.md` §7.2 Teil 10 unberührt | **keine Änderung** (Verweis trägt §36.3) | – |
| Q4 | Push des Standes `1c9db3e` | **ausgeführt** (`origin/master == 1c9db3e`, 0/0, clean) | – |

## 43. Q2 — Zeitachsen-Label des Sichttest-Skripts

**Prämisse (belegt):** `d["ts"]` stammt aus der Engine-SQL
`SELECT time AT TIME ZONE 'Europe/Berlin' AS ts` (Z. 600, eingefrorene
`_p11`-Ausnahme) ⇒ Berlin (+2 h). Im Skript wurde `ts` **ausschließlich** im
Label-Pfad verwendet (`to_datetime` → `time_axis`-Ticks); **kein** Einfluss auf
Trade-Logik, Asserts oder Engine.

| Stelle | vorher | nachher |
|---|---|---|
| Modul-Docstring (Konventionen) | 2 Punkte | + Zeitachsen-Konvention (Broker/UTC, Verweis v0.9 §36) |
| Zeitbasis-Block (bei `d = scan["d"]`) | `ts = pd.to_datetime(d["ts"])` | `AXIS_TZ_OFFSET_H = -2`<br>`ts = pd.to_datetime(d["ts"]) + pd.Timedelta(hours=AXIS_TZ_OFFSET_H)` |
| `time_axis()` | – | Docstring + `ax.set_xlabel(...)` mit Text `Zeitachse BROKER/UTC (Bar-Index primaer) \| Engine-Konvention Europe/Berlin (+2 h), v0.9 §36` |

`d["ts"]` selbst wird **nicht** mutiert (neue lokale Series). Der Offset ist als
benannte Konstante deklariert und nicht hardcodiert im Label-Ausdruck.

## 44. Verifikation (lesend, ohne Skript-Ausführung)

| Prüfung | Soll | Ist |
|---|---|---|
| `py_compile` | fehlerfrei | **OK** ✅ |
| Offset-Probe Bar 1211 | Berlin 05:45 → Achse **03:45** (Broker) | **27.08 03:45** ✅ |
| Offset-Probe Bar 1259 | Berlin 17:45 → Achse **15:45** (Broker) | **27.08 15:45** ✅ |
| `ts`-Nutzung | nur Label-Pfad | nur Z. 164 / Z. 256 ✅ |
| Encoding | LF, kein BOM | 714 Zeilen, CRLF 0, BOM False ✅ |
| PNG 01–05 Bytes | 1.657.807 / 652.507 / 1.168.856 / 698.274 / 1.626.925 | **identisch** (nicht regeneriert) ✅ |
| Engine SHA256 | `3ba15c72…5255cb006` | unberührt ✅ |

**Keine Neugenerierung:** Die 5 PNGs behalten ihre arretierten Bytegrößen aus
v0.8/Checkpoint. Die Label-Korrektur greift erst bei einem künftigen,
manuell angestoßenen Lauf.

## 45. Status

| Kennzahl | Wert | Berührt? |
|---|---|---|
| V0 gesamt / H1 / V1 / H2 | 14 / 8 / 15 / 7 (R unverändert) | nein |
| Engine SHA256 | `3ba15c72…5255cb006` | nein |
| Sichttest-PNGs (5) | byte-identisch zu v0.8 | nein |
| `test/tmp_png_aug_sichttest.py` | 714 Z. / 33.037 B (gitignored) | Q2 (Labels) |

Offen für die nächste Sitzung: **Wiederaufnahme der H2/2-Analyse
(K73-Decke / K82-Boden) auf der dreispaltigen Matrix** (`Bar | Broker/UTC |
Berlin (+2 h, nur Altzitate)`), Basis §37.

---

# Addendum v0.11 — Forensik K73-Decke in P12: strukturelle Inertheit (2026-09-10)

**Freigaben:** E1–E4 (Mentor/Anwender, 2026-09-10). **Wirkung:** ausschliesslich
Dokumentation. Kein Code ausgefuehrt, kein Engine-Eingriff, keine
Baseline-Veraenderung, keine Adapter-Aenderung.

## 46. Dreispaltige Sweep-Matrix der K73-Decke (P12)

Referenz: `test/archiv/silver_m15_ohlc_2026-08-10_2026-08-28.csv` (1289 Zeilen =
Header + 1288 Bars; Dateizeile = Bar-Index + 2). Zeitbasis Broker/UTC (§36),
Berlin (+2 h) nur als Altzitat. Eichprobe: Bar 980 = 2026-08-24 15:00 UTC
(+2 h = 17:00, deckt §20/Addendum v0.4).

| Bar-Index | Broker/UTC | Berlin (+2 h, historisch) | Open | High | Low | Close | Vol | K73 `basis_bei` | dist (SHORT) |
|---|---|---|---|---|---|---|---|---|---|
| **1211** | 27.08. 03:45 | 27.08. 05:45 | 69,274 | **69,611** | 69,242 | 69,544 | 1958 | 69,6865 | −0,1083 % |
| **1271** | 27.08. 18:45 | 27.08. 20:45 | 69,407 | **69,591** | 69,373 | 69,569 | 2018 | 69,6714 | −0,1154 % |
| **1272** | 27.08. 19:00 | 27.08. 21:00 | 69,575 | **69,714** | 69,410 | 69,500 | 1836 | 69,6714 | +0,0611 % |

**Kreuzbestätigungen:** `High(1211) = 69,611` belegt §37.3 („der reale Docht ist
69,611"; ein Dochtpreis 69,49 existiert nicht) · `Low(1259) = 67,600` belegt
§37.1 („67,60" ist ein Dochtextremum, kein Kantenniveau).

Datenvertrag (informativ, nicht implementiert): `K73P12AuditBefund`
(`bar_index, broker_zeit_utc, berlin_zeit_historisch, high_preis,
kausale_basis_k73, reclaim_stufe_ergebnis, m6_blocker_status,
institutionelles_urteil`).

## 47. M6 und die Reclaim-Stufen (M6 hypothetisch neutralisiert)

### 47.1 Kausale Auswertungsreihenfolge

`_se_trades` (Z. 2550–2575) wertet strikt sequenziell aus:

1. `_kandidat` — Kaskade (Z. 2471–2531)
2. `_blockiert_durch_aussenkante` — **M6** (Z. 2428–2462), Aufruf Z. 2556
3. `_im_aussenquartil` — Q29, Z. 2566
4. `_reclaim_stufe` — Z. 2020–2048, Aufruf Z. 2575

**M6 liegt VOR der Stufenberechnung.** Ein geblockter Kandidat erreicht die
Stufe nie — die Stufenanalyse ist daher zwingend hypothetisch.

### 47.2 M6-Messung (Außenwand K67, `basis_bei = 69,9458`)

| Bar-Index | Kandidat nach Kaskade | Kandidat-Basis | M6-Distanz zu K67 | Wirkung |
|---|---|---|---|---|
| 1211 | K76 | 69,507 | **+0,6308 %** | BLOCKER (≤ `max_seed_distanz_pct` 0,75) |
| 1271 | K76 | 69,515 | **+0,6194 %** | BLOCKER |
| 1272 | **K73** | 69,6714 | **+0,3938 %** | BLOCKER |

### 47.3 Hypothetische Reclaim-Stufe (M6 aus, `_reclaim_stufe` Z. 2020–2048)

Parameter: `touch_band_pct 0,12` · `max_sweep_ueberdehnung_pct 0,60` ·
`doppeltop_puffer_usd 0,01` · `min_touches_handelbar 3` ·
`sweep_mindestdurchstich_pct 0,0`.

| Bar-Index | Kandidat | Durchstich `dist_o` | Folgebars | Stufe |
|---|---|---|---|---|
| 1211 | K76 @ 69,507 | +0,1496 % | 1212: `C 69,480 ≤ 69,507`, `H 69,599 ≤ 69,621` | **STUFE_2_KERZE_2** |
| 1271 | K76 @ 69,515 | +0,1100 % | 1272: `C 69,500 ≤ 69,515`, aber `H 69,714 > 69,601` | **Stufe 0 — kein Signal** |
| 1272 | K73 @ 69,6714 | +0,0611 % | `C 69,500 ≤ 69,6714` (in-bar) | **STUFE_1_IN_BAR** |

### 47.4 Richtigstellung (Faktenlage vs. Formulierung)

Die Kurzform „1272 = Durchstich ohne Halten" ist mit der Engine-Definition
nicht deckungsgleich: `_reclaim_stufe` liefert an **1272** für K73
**`STUFE_1_IN_BAR`** (Close 69,500 kehrt in denselben Bar unter die Basis
69,6714 zurück). Der Trade unterbleibt **allein wegen M6**. Ebenso ist 1211
nicht „kein Reclaim", sondern hypothetisch **`STUFE_2_KERZE_2`** auf der
Innenlinie K76. Nur **1271** liefert mechanisch gar kein Signal
(Non-Expansion verletzt: `H 69,714 > 69,601`).

**Beweisrichtung:** P12 ist nicht deshalb inert, weil Signale fehlen, sondern
weil **jeder** Kandidat in der Schlagdistanz (≤ 0,75 %) einer **unberührten**
Außenwand (K67 69,9458) liegt.

## 48. Institutionelles Verdikt: strukturelle Inertheit (E2/E4)

### 48.1 Rolleninversion als architektonische Gesetzmäßigkeit (E4)

| Phase | Sweep-Bars | freigestellte Kante (Hook 1) | Rolle dieser Kante | äußerste Wand (M6) | Wirkung |
|---|---|---|---|---|---|
| **P9** | 980 / 1020 | **K67** | äußerste Wand, vom Sweep berührt | K67 ist selbst die freigestellte | Innenlinie K73 handelt → **+5,4212 R** |
| **P12** | 1211 / 1271 | **K73** | **Phasen-Decke selbst** | K67 **unberührt** | Kandidat unter unberührter Wand → Sperre |

- P9: `dist(K67)@980 = −0,0996 %` (Sweep 69,899 vs. Basis 69,9687) ⇒ die
  äußerste Wand *hat geliefert* ⇒ Freigabe ⇒ K73 wird handelbar.
- P12: `dist(K73)@1211 = −0,1083 %`, aber K67 liegt 0,4787 % über dem Sweep
  ⇒ die freigestellte Kante ist **nicht** die äußerste ⇒ Entscheidung #6:
  keine Freigabe für K67 ⇒ M6 sperrt.

**Regelaussage (invariant, nicht stichprobenabhängig):** M6 sperrt jeden
Kandidaten, der innerhalb `max_seed_distanz_pct` (0,75 %) unter einer nicht
erreichten, existierenden Außenwand derselben Seite liegt. Diese Aussage hängt
nicht von der Zahl der August-Sweeps ab — sie ist eine Eigenschaft der
Kanten-Geometrie.

### 48.2 Status P12: STRUKTURELL_INERT_RESERVE (E2)

`P12_RESERVE` (1171–1272, Decke K73, Boden K82, Ziel 67,6355 / Spiegel
69,5550) bleibt Reserve und wird **nicht** in `AKTIVE_DEFAULT_SEGMENTE`
aufgenommen.

Kein Freiheitsgrad erzeugt einen legitimen P12-Trade:

1. **M6 bleibt** ⇒ 0 Trades (Ist-Zustand, `P12: V0 0 | V1 0`).
2. **M6 aus** ⇒ 1211 (Stufe 2) und 1272 (Stufe 1) würden handeln — das ist
   aber ein *Fade unter einer unberührten Außenwand* ⇒ Doktrinbruch.
3. **Decke auf K67 umdefiniert** ⇒ Sweep 69,611 liegt 0,4787 % unter
   69,9458 ⇒ **kein Touch** an der Decke ⇒ weiterhin kein Trade.

STATUS: `STRUKTURELL_INERT_RESERVE` (nicht „empirisch leer").

### 48.3 Kausalitätsnachweis `_lebt` vs. `_existiert`

| Prüfung | Zeilen | Semantik | K67 @1211 |
|---|---|---|---|
| `_lebt` | 2398–2409 | letzter Wick-Kontakt ≤ `wall_live_bars` (96) | **False** → Kaskade ueberspringt K67 |
| `_existiert` | 2386–2396 | AKTIV und Pivot bestätigt (`erster_pivot_bar + 2 ≤ k + 1`) | **True** → M6 sieht K67 als Außenwand |

Diese Zweiteilung erhält eine **dormante** Außenwand als institutionellen
Blocker, während dieselbe Linie die Innenkandidaten-Kaskade nicht mehr
aufhält. Beide Prüfungen sind arretiert und werden **nicht** verändert.
(Beleg: `test/tmp_dryrun_p12_out.txt` Abschnitt F weist als Kandidaten
`pos1 K76` aus ⇒ K67 wurde in der Kaskade via `continue` übersprungen.)

## 49. Status

| Kennzahl | Wert | Berührt durch v0.11? |
|---|---|---|
| V0 / H1 / V1 / H2 V1 | 14 / 8 / 15 / 7 (R unverändert) | nein |
| P12-Trades (V0 / V1) | 0 / 0 | nein |
| Engine SHA256 | `3ba15c72…5255cb006` | nein |
| `P12_RESERVE` in `AKTIVE_DEFAULT_SEGMENTE` | nicht enthalten | nein |

Addendum v0.11 rein dokumentarisch: kein Code ausgeführt, keine Datei der
Engine oder des Adapters angefasst.

Nächster Schritt (E3): **Gesamttabelle §37 auf die Dreispalten-Matrix
nachziehen** (Bar-Index als Key; Broker/UTC als Leitwährung; Berlin nur als
Altzitat), danach Abschluss der P12-Teil-Exploration.

---

## 50. Richtigstellung der Zeitbasis (v0.9 §36.1 teilweise revidiert)

**Anlass.** Der PNG-Sichttest zeigte eine um **−2 h** verschobene X-Achse.
Ursache war die in v0.10 §43/§44 gewählte Option (ii) `AXIS_TZ_OFFSET_H = -2`;
sie setzte „Referenz-CSV" mit „Broker-Wanduhr" gleich. Die read-only
Bodenprobe (`test/_tmp_zeitbasis_probe.py`, ausschließlich `SELECT`)
widerlegt diese Gleichsetzung.

### 50.1 Bodenprobe (verifiziert, `data/market_data.duckdb`, SILVER M15)

```
typeof(time)                = TIMESTAMP WITH TIME ZONE
current_setting('TimeZone') = Europe/Budapest        -- Anzeige +02:00
Reihen im Extraktionsfenster (10.08.-29.08.) = 1380
```

| Quelle | Bar 980 | Bar 1211 | Bar 1259 | Rolle |
|---|---|---|---|---|
| DB-Spalte `time` (Session **+02:00**) | 24.08. **17:00** | 27.08. **05:45** | 27.08. **17:45** | **Bar-Zeit = Leitwährung** |
| Engine-SQL Z. 600 (`AT TIME ZONE 'Europe/Berlin'`) → `d["ts"]` | identisch | identisch | identisch | Anzeige-/Label-Pfad |
| `time AT TIME ZONE 'UTC'` | 24.08. 15:00 | 27.08. 03:45 | 27.08. 15:45 | UTC-Projektion |
| Referenz-CSV (`test/archiv/silver_m15_ohlc_2026-08-10_2026-08-28.csv`) | 24.08. 15:00 | 27.08. 03:45 | 27.08. 15:45 | **künstlicher UTC-Export (−2 h)** |

Da DuckDB-Session (`Europe/Budapest`) und `Europe/Berlin` im August-Fenster
**denselben** UTC-Offset (+2 h) tragen, ist `d["ts"]` **identisch mit der
DB-Anzeige** — der Berlin-Patch (§36.3) ist im August also rechnerisch neutral.

CSV-Befund: 1.289 Dateizeilen = 1 Header + **1.288 Datenzeilen ⇒ Bars
0..1287**; **Dateizeile = Bar-Index + 2** (Stichproben 982/1213/1261 =
Bar 980/1211/1259; letzte Zeile = Bar 1287, 27.08. 22:45 UTC). Die CSV ist
**kein eigener Zeitstandard**, sondern ein Export der UTC-Projektion; die
DB liefert im selben Fenster 1.380 Reihen (bis 29.08.).

### 50.2 Beschluss (prominent)

1. **Leitwährung ist die Wanduhr-Bar-Zeit** (DB-Anzeige = `d["ts"]`, +02:00).
   Die in §36.1 als „Broker / CSV (`AT TIME ZONE 'UTC'`)" geführte Zeile
   (03:45 / 15:45) ist die **UTC-Projektion** — sie bleibt Extraktions- und
   Schutzbasis (§50.3), ist aber **nicht** die Leitwährung.
2. **v0.10 §43/§44 ist aufgehoben:** `AXIS_TZ_OFFSET_H = 0`. Die Achse läuft
   **ohne Offset** auf der Bar-Zeit; `d["ts"]` wird nativ gezeichnet und
   etikettiert.
3. **Nomenklatur (nur Klarstellung, keine Zahl geändert):** In §§36.3/§37
   trägt die Spalte **„Broker/UTC"** die UTC-Projektion (CSV-Ebene,
   SQL-Filtergrenzen), die Spalte **„Berlin (+2 h, …)"** die native Wanduhr
   (= Leitwährung). Die Altzitat-Kennzeichnung bleibt gültig, weil sie sich
   auf die **Herkunft der Labels** in v0.5–v0.8 bezieht. Tabellen der Addenda
   ab v0.12 führen daher `Bar | Broker/UTC | Bar-Zeit (+02:00)`.
4. **Unberührt:** §36.2 (`box_end_bar = 640`-Interlock, `_p11` byte-fixiert)
   und §36.3 (SHA256 `3ba15c72…`). Die Filtergrenzen des Extraktions-SQL
   bleiben UTC-formuliert.

### 50.3 Grundsatz (K4, Wortlaut für `Agents.md`)

> DB-Extraktion nutzt `AT TIME ZONE 'UTC'` zum Wanduhr-Schutz; Visualisierung,
> Achsen-Labels und Bar-Zuordnung nutzen **nativ die Wanduhr-Bar-Zeit**
> (`time`). Der **Bar-Index** bleibt Primärschlüssel.

---

## 51. Darstellungsnorm des Sichttests (ab v0.12 verbindlich)

Aus dem Nutzer-Feedback (8 Punkte) abgeleitet, gültig für
`test/tmp_png_aug_sichttest.py`:

| # | Regel | Umsetzung |
|---|---|---|
| 1 | **Candlesticks überall** — `draw_candles(..., "candle")` in Panel 01 und 05 | erledigt |
| 2 | **X-Achse = Bar-Zeit ohne Offset** (§50) | erledigt |
| 3 | **Trade-Kreise immer farbig gefüllt** (`mfc=col`): H1 klein/dünn, H2 groß/dick | erledigt |
| 4 | **Kausale Kantenlinien** — je Bar `basis_bei(k)` (Treppe) statt statischer Provenienz `e.basis` | **erledigt (v0.13)** |
| 5 | **Sperr-Marker** ✕ = Q29-Sperre, ▲ = M6-Sperre, am sperrenden Bar | **erledigt (v0.13)** |
| 6 | **Titel** `Bars 0..1287` | **erledigt (v0.13)** |
| 7 | **Preis am K-Label** + Kennzeichnung des Preiswechsels + Norm-Zitat | **erledigt (v0.13), §54** |

Farbige Kreise sind **nicht** optional: ein weißer Marker (`mfc="none"`)
erzeugte das Fehlbild „Kreis ohne Füllung" und täuschte einen eigenen Fehler
vor (Feedback-Punkt 1 und 3 hatten dieselbe Ursache).

### 51.1 Beleg zur kausalen Linie (Regel 4)

| Kante | statisch `e.basis` | `basis_bei(980)` | `basis_bei(1020)` |
|---|---|---|---|
| K73 | 69,6785 | **69,6765** | **69,6765** |

Der statische Wert ist die **Provenienz-Wurzel**, nicht der zu Bar 980/1020
gültige Pegel (Δ = 0,0020). Das erklärt die optisch „falsche" Lage der
Einstiegspunkte 24./25.08.

---

## 52. Kaskaden-Trace und Schlaf-Fenster-Erstfilter (J5)

### 52.0 Methodik (verbindlich für die Lesart aller Zahlen unten)

`_se_trades` läuft **ausschließlich in der Box**: `for k in range(2, box_end
- 3)` mit `box_end = 640` (Docstring Z. 2359 „Nur in der Box"). Aussagen über
Bars ≥ 640 stammen daher aus einem **rein speicherinternen** Trace
(`scan["box_end_bar"] = 1288` im `dict`; read-only, **keine Datei** angefasst),
der **14 Setups** liefert — deckungsgleich mit der arretierten
Lauf-B-Referenz (14 / +40.445143 R). Die Gate-Listen sind engine-eigen
(`stats["blocker_liste"]`, `stats["quartil_liste"]`, `stats["zyklus_liste"]`,
Z. 2559/2568/2601).

**Gate-Reihenfolge im Kaskadencode (statisch, Z. 2492–2607):**

| Position | Gate | Zeile |
|---|---|---|
| 1 | `_existiert` (**Schlaf-Filter**) | 2492 (Pool) / 2506 (Seed) |
| 2 | M6 `_blockiert_durch_aussenkante` | 2556 |
| 3 | Q29 `_im_aussenquartil` | 2566 |
| 4 | `_reclaim_stufe` (Stufe 0 ⇒ keine Reife) | 2575 |
| 5 | 12-Bar-Zyklus | 2597 |

⇒ Der Schlaf-Filter greift **vor** M6, Q29 und Zyklik: eine schlafende Kante
ist gar nicht im Kandidatenraum.

### 52.1 Belegzeilen (read-only, `test/_tmp_beleg_schlaf.py`)

Mechanik: Z. 2269–2277 — zwei konsekutive Körper jenseits der **laufenden**
Basis (`max(O,C) < e.basis` bei `UNTEN`) ⇒ `SCHLAFEND` +
`schlaf_windows.append((k, None))`; Reaktivierung Z. 2202–2206
(`schlaf_windows[-1] = (start, bar + 2)`).

**K82 (UNTEN, `e.basis` final = 67,5455, `schlaf_windows = [(1074, 1174)]`)**

| Bar | Broker/UTC | Bar-Zeit (+02:00) | O | H | L | C | `max(O,C)` vs `basis_bei(k)` |
|---|---|---|---|---|---|---|---|
| 1073 | 25.08. 15:15 | 25.08. 17:15 | 67,4970 | 67,7430 | 67,4620 | 67,4700 | 67,4970 < 67,5440 → **AUSSEN** |
| 1074 | 25.08. 15:30 | 25.08. 17:30 | 67,4740 | 67,8020 | 67,4550 | 67,5330 | 67,5330 < 67,5440 → **AUSSEN** |

Reaktivierung: Fensterende **1174** = Touch-Bar **1172** + 2 (Wick 67,494 ✔);
Zustand `ist_aktiv_bei(1172) = False`, `ist_aktiv_bei(1174) = True`.

**K79 (UNTEN, `e.basis` final = 68,6260, `schlaf_windows = [(999, 1140), (1149, None)]`)**

| Bar | Broker/UTC | Bar-Zeit (+02:00) | O | H | L | C | `max(O,C)` vs `basis_bei(k)` |
|---|---|---|---|---|---|---|---|
| 998 | 24.08. 19:30 | 24.08. 21:30 | 68,5020 | 68,5720 | 68,4110 | 68,4700 | 68,5020 < 68,6296 → **AUSSEN** |
| 999 | 24.08. 19:45 | 24.08. 21:45 | 68,4730 | 68,4880 | 68,3180 | 68,4660 | 68,4730 < 68,6296 → **AUSSEN** |
| 1148 | 26.08. 11:00 | 26.08. 13:00 | 68,6180 | 68,6760 | 68,5260 | 68,5450 | 68,6180 < 68,6260 → **AUSSEN** |
| 1149 | 26.08. 11:15 | 26.08. 13:15 | 68,5460 | 68,5500 | 68,4360 | 68,4560 | 68,5460 < 68,6260 → **AUSSEN** |

Reaktivierung: Fensterende **1140** = Touch-Bar **1138** + 2 (Wick 68,608 ✔);
der zweite Bruch 1148/1149 öffnet `(1149, None)` (seither durchgehend
schlafend).

### 52.2 Richtigstellungen (prominent)

**K79 (Feedback-Punkt 4).** Der fehlende K79-LONG ist **nicht** Q29-bedingt,
sondern Folge des Schlaf-Fensters `(999, 1140)`. Beleg: K79 erscheint in der
Q29-Liste **ausschließlich außerhalb** des Fensters (Bars 991/992/997 sowie
1145/1146), innerhalb des Fensters **nie** — die Kante wird von `_existiert`
(Z. 2492/2506) vor jeder Pool-/Q29-/M6-Prüfung entfernt.

**K77 (Feedback-Punkt 5).** K77-LONG ist **Q29-gesperrt** (Bars 1002, 1029),
**nicht** durch die 12-Bar-Zyklik.

| Erstes Gate | Bars 1002–1030 |
|---|---|
| `BLOCKER_M6` | **0** |
| `QUARTIL_Q29` | **4** — 1002 K77, 1028 K60, 1029 K77, 1030 K60 |
| `ZYKLUS_12BAR` | **0** |

Q29-Rohwerte (Formel Z. 2419–2426, Grenze 25 %): K79 @991/992/997 =
**77,83 / 79,68 / 78,10 %**; K77 @1002/1029 = **77,29 / 72,97 %**. Alle
gesperrt. (Kontrollwert: Bar 1259 ⇒ 67,79 % — deckungsgleich mit §38.2.)

**K82 am 26.08. (Feedback-Punkt 7).** Bar 1172 liegt **im** Fenster
`(1074, 1174)` (noch `SCHLAFEND`, §52.1) und erreicht zusätzlich Q29 mit
**66,37 %** — doppelt gesperrt.

**Bar 1272 (K73 SHORT, Feedback-Punkt 8).** Die Engine-Liste weist genau
**einen** Eintrag aus: `BLOCKER_M6(K73 SHORT)`. Damit ist §47.4 engine-nativ
bestätigt: 1272 scheitert allein an **M6**, weder an Q29 noch an der
12-Bar-Zyklik.

**K73/K76 ohne SHORT.** `dist < 0` bei lebender Wand ⇒ `return None`
(Z. 2519–2520), **ohne** Log-Eintrag; deshalb erscheinen die Bars
1211/1259/1271 in **keiner** der drei Sperrlisten.

---

## 53. Status

| Kennzahl | Wert | Berührt durch v0.12? |
|---|---|---|
| V0 / H1 / V1 / H2 V1 | 14 / 8 / 15 / 7 (R unverändert) | nein |
| Trace-Setups (`box_end_bar = 1288`, nur im Speicher) | 14 (= Lauf B) | nein |
| P12-Trades (V0 / V1) | 0 / 0 | nein |
| Engine SHA256 | `3ba15c72…5255cb006` | nein |
| `P12_RESERVE` in `AKTIVE_DEFAULT_SEGMENTE` | nicht enthalten | nein |

Addendum v0.12 ist dokumentarisch **plus** Freigabe der Darstellungsnorm
(§51). Keine Datei der Engine oder des Adapters angefasst; alle Bodenproben
(`test/_tmp_zeitbasis_probe.py`, `test/_tmp_beleg_schlaf.py`,
`test/_tmp_gate_trace_j5.py`) sind **read-only** und werden nach Gebrauch
entfernt (§39-Hygiene).

---

## 54. Darstellungsregeln — FIX (ab v0.13, für **alle** Sichtprüfungs-Grafiken)

**Anweisung des Anwenders (2026-09-10):** „Schreibe den Preis an die Linie bei
der K-Nennung; und wenn der Preis sich geändert hat — bitte fix in
Report-Regeln aufnehmen." Nachfolgend das **verbindliche** Regelwerk. Es ist
zugleich der Docstring-Kopf von `test/tmp_png_aug_sichttest.py`; beide Quellen
müssen übereinstimmen.

### 54.1 Preisangabe an der Kante (neu, verbindlich)

1. **Jedes Kanten-Label trägt den Preis.** Format `K<kid> <preis>`; Seeds
   analog `s<kid> <preis>`. Der Preis ist der **kausale** Wert
   `basis_bei(k)` — **nicht** die statische Provenienz `e.basis`.
2. **Preiswechsel werden gekennzeichnet.** Ändert sich der kausale Preis
   entlang der gezeichneten Linie, lautet das Label
   `K<kid> <v_start> -> <v_ende> *`; Label **fett** und mit Rahmen in
   `C_CHG` (`#b8860b`). Am **Detailpanel** (04) und an den Grenzkanten (§54.3)
   wird zusätzlich an jedem Wechselpunkt der neue Preis als Kleintext
   gesetzt.
3. **Norm-Zitat (Option (b), §37.4).** Ist für die Kante eine
   v0.4-Provenienz-Norm hinterlegt und weicht der kausale Wert ab, wird die
   Norm **angehängt, nicht ersetzt**: `K82 67.535 -> 67.545 * Norm 67.6355`.
   Norm-Quelle ist ausschließlich der Adapter
   (`P9.decke/boden`, `P12_RESERVE.decke/boden`) — kein Hardcoding.
4. **Norm-Vergleichsbar = 1259** (`NORM_REF_BAR`): Der Vergleich läuft auf dem
   **vollen** Verlauf, nicht auf dem ggf. beschnittenen Zeichenfenster — sonst
   kippt die Aussage je Panel.
5. **Pflichtangabe im Statistikblock** (Panel 01): Anzahl der
   Preiswechsel-Linien (`*`) und Anzahl der normabweichenden Grenzkanten.

**Beleglauf (Referenz-Bar 1259):**

| Kante | kausal `basis_bei(1259)` | Norm (v0.4) | Δ | Label |
|---|---|---|---|---|
| K67 | 69,9458 | 69,9140 | +0,0318 | `K67 69.975 -> 69.946 * Norm 69.9140` |
| K73 | 69,6714 | 69,5550 | +0,1164 | `K73 69.715 -> 69.679 * Norm 69.5550` |
| K77 | 68,3597 | 68,3700 | −0,0103 | `K77 68.392 -> 68.360 * Norm 68.3700` |
| K82 | 67,5273 | 67,6355 | −0,1082 | `K82 67.535 -> 67.546 * Norm 67.6355` |

Alle vier Grenzkanten weichen ab ⇒ alle vier Labels tragen die Norm. Über den
**vollen** Zeitraum wechseln **54 von 59** Kanten den Preis (laufendes Mittel,
Styling siehe 54.2).

### 54.2 Linienführung, Marker, Achse

6. **Linien sind kausal:** `basis_bei(k)` je Bar (Treppe), maskiert vor
   `pivot_bar + 2`; promovierte Primär-Anker flach (eingefroren). Die
   statische `e.basis` wird **nicht mehr** als Linienniveau gezeichnet.
7. **Sperr-Marker (violett `#8e44ad`):** `x` = Q29-Quartilsperre,
   `^` = M6-Außenwandsperre; gesetzt am **sperrenden Bar** und am
   Sperrpreis (Sweep-Extremum). Quelle sind die engine-eigenen Listen
   `stats["quartil_liste"]` / `stats["blocker_liste"]` (§52.0).
8. **Alle Panels in Kerzen** (`draw_candles(..., "candle")`).
9. **X-Achse = Bar-Zeit (Wanduhr) ohne Offset** (`AXIS_TZ_OFFSET_H = 0`, §50);
   Bar-Index bleibt Primärschlüssel.
10. **Trade-Kreise immer farbig gefüllt** (`mfc=col`); H1 klein/dünn,
    H2 groß/dick.
11. **Titel** führen die Bar-Grenzen als `Bars 0..1287` (`n - 1`).

### 54.3 Layout-Konvention (unverändert)

12. **Statistik mittig** im unteren Panel (Monospace).
13. **Legende oben links**, zweispaltig.
14. **Zusatz-Kleintexte an Wechselpunkten** nur an den Grenzkanten
    (`NORM_KIDS = {67, 73, 77, 82}`) und im Detailpanel; an den übrigen
    Kanten bleibt es beim Label, um die Übersicht nicht zu überladen.

---

## 55. Konsolidat: vom Anwender gesetzte Standards

Vollständige, verbindliche Liste aller Vorgaben des Anwenders, die dieses
Dokument und die zugehörigen Artefakte binden. Spalte „Quelle" nennt den
Fundort; alle Regeln gelten **fortlaufend** und werden nicht zur Disposition
gestellt.

| # | Standard | Inhalt | Quelle |
|---|---|---|---|
| S1 | **Zeitbasis** | DB-Extraktion `AT TIME ZONE 'UTC'` (Wanduhr-Schutz); Visualisierung/Achsen/Labels **nativ Wanduhr-Bar-Zeit** (`time`, `d["ts"]`), Offset 0. Referenz-CSV = **UTC-Export (−2 h)**, kein eigener Standard | §50.2/§50.3, `Agents.md` |
| S2 | **Bar-Index** | Primärschlüssel jeder Aussage; Tabellen dreispaltig `Bar \| Broker/UTC \| Bar-Zeit (+02:00)` | §36.1, §50.2, `Agents.md` |
| S3 | **Engine-Integrität** | `test/tmp_kanten_engine_replay.py` SHA256 `3ba15c72…5255cb006` byte-fixiert; `_p11`-Projektion (Z. 600) und `box_end_bar = 640` **aneinander gekoppelt**, Änderung nur mit ausdrücklicher Freigabe + Neu-Arretierung | §36.2/§36.3, `Agents.md` |
| S4 | **K82-Nomenklatur (Option (b))** | Provenienz-Norm `67,6355` bleibt als historisches Zitat stehen; abgegrenzt von Scan-Basis `67,5455` und kausal `67,5273`; operativ gilt `basis_bei(k)` | §37.4 (Entscheid „Option (b)", 2026-09-10) |
| S5 | **Darstellung** | §54 in Gänze (Preis am Label, `*` bei Preiswechsel, Norm-Zitat, kausale Linien, violette Sperr-Marker, Kerzen, Offset 0, farbige Kreise, Statistik mittig, Legende oben links, Titel `0..1287`) | §51, §54 |
| S6 | **Kaskaden-Lesart** | Gate-Reihenfolge `_existiert` (Schlaf) → M6 → Q29 → Reife → 12-Bar; Aussagen über Bars ≥ 640 nur mit ausgewiesenem Trace (§52.0) | §52.0 |
| S7 | **Testpolitik** | Keine UI-, keine Regressionstests; Logik-/DB-Tests ausschließlich in `test/` (gitignored); Verifikation über `py_compile`, statische Analyse, Code-Inspektion | `Agents.md` §4 |
| S8 | **Reihenfolge Doku → Lauf** | Dokumentation und Generierungsläufe werden nie vermischt: erst Regeln festschreiben/committen, dann erzeugen | §34, K3 |
| S9 | **Entscheidungsausgabe** | Keine Auswahlmenüs; Entscheidungsfragen werden als **Textblock** ausgegeben | `Agents.md` §1 |
| S10 | **Hygiene** | Temporäre Proben read-only, nach Gebrauch gelöscht; Zeitangaben in Altdokumenten sind **+2 h** zu lesen | §39, §36.3 |

---

## 56. Status (v0.13)

| Kennzahl | Wert | Berührt durch v0.13? |
|---|---|---|
| V0 / H1 / V1 / H2 V1 | 14 / 8 / 15 / 7 (R unverändert) | nein |
| Trace-Setups (`box_end_bar = 1288`, nur im Speicher) | 14 (= Lauf B) | nein |
| P12-Trades (V0 / V1) | 0 / 0 | nein |
| Engine SHA256 | `3ba15c72…5255cb006` | nein |
| `P12_RESERVE` in `AKTIVE_DEFAULT_SEGMENTE` | nicht enthalten | nein |
| Preiswechsel-Linien (Label `*`) | 54 von 59 | neu (Darstellung) |
| Grenzkanten mit Norm-Abweichung | 4 von 4 (K67, K73, K77, K82) | neu (Darstellung) |

v0.13 ist ein **Regelwerk-Addendum**: Es friert die Darstellungsnorm (§54) und
alle anwendersetigen Standards (§55) ein. Code der Engine und des Adapters
bleibt unangetastet; ``test/tmp_png_aug_sichttest.py`` ist ein read-only
Renderer und liegt gitignored in `test/`.

---

## Vermerk zur Einordnung (Anwender-Auftrag 2026-09-10)

**Auftragsgegenstand:** Der Anwender hat ein Addendum „K67-Direktauslösung an
Resistance 69.87" mit den Abschnittsnummern §54/§55 unter dem Titel „v0.13"
beauftragt. Beim Einsortieren wurden zwei Konflikte festgestellt und — nach
dem Protokoll **„erst verifizieren, dann schreiben"** (§52.0) — bereinigt:

1. **Versions- und Nummern-Kollision.** „v0.13" ist **bereits vergeben**
   (§§54–56: Darstellungsregeln FIX + Konsolidat der Standards, Commit
   `cd4e15a`). Dieses Addendum läuft deshalb als **v0.14**; die beauftragten
   Abschnitte §54/§55 werden als **§57/§58** geführt, damit Anker und
   Querverweise eindeutig bleiben. Der beauftragte Wortlaut ist in §57/§58
   jeweils als Zitat mitgeführt.
2. **Sechs Zahlenkorrekturen.** Die im Entwurf genannten Werte wurden
   read-only gegen die Engine geprüft. Abweichungen bei Close, Entry, SL und R
   (Ursache: `sl_buffer_usd = 0.05` statt 0,01; `entry = open[entry_bar]`).
   Übersicht in §57.3; die Entwurfswerte bleiben dort als Zitat erhalten.

**Status:** rein dokumentarisch. **Kein Code implementiert** — Adapter und
Engine sind byte-unverändert (SHA256 `3ba15c72…5255cb006`). Alle Zahlen
stammen aus einer **read-only In-Memory-Simulation**
(`test/_tmp_k67_direkt.py`); die Engine-Datei wurde nicht angefasst.

---

## 57. Falsifikation des K73-Umwegs & K67-Direkt-Reclaim

> **Beauftragter Wortlaut (Entwurf):** „Die bisherige Hilfskonstruktion (Hook 1:
> Freistellung von K67, damit K73 handelt) basierte auf einer Verzerrung der
> K67-Basis durch np.mean (69.9687)."

### 57.1 Ausgangsbefund — die `np.mean`-Drift (bestätigt)

K67 ist OBEN, **kein** Primär-Anker; `basis_bei(k)` ist das laufende Mittel der
bestätigten Dochte (`pivot_bar + 2 <= k`). Dochtmenge (5 Wicks):

| Bar | Broker/UTC | Bar-Zeit (+02:00) | Dochtpreis |
|---|---|---|---|
| 873 | 21.08. 05:45 | 21.08. 07:45 | 69,975 |
| 881 | 21.08. 07:45 | 21.08. 09:45 | 70,000 |
| 904 | 21.08. 13:30 | 21.08. 15:30 | 69,931 |
| 980 | 24.08. 15:00 | 24.08. 17:00 | 69,899 |
| 1020 | 25.08. 02:00 | 25.08. 04:00 | 69,924 |

```
basis_bei(980)  = (69,975 + 70,000 + 69,931) / 3              = 69,9687
basis_bei(1020) = (69,975 + 70,000 + 69,931 + 69,899) / 4     = 69,9513
```

| Bar | High | `basis_bei(k)` | dist |
|---|---|---|---|
| 980 | 69,899 | 69,9687 | **−0,0996 %** |
| 1020 | 69,924 | 69,9513 | **−0,0390 %** |

Beide Sweeps liegen damit im Docht-Defizit (`dist < 0`) — der Befund des
Entwurfs ist **reproduziert**. Konsequenz im Ist-Zustand: `_kandidat` liefert
an beiden Bars als handelnde Linie **K73** (K67 wird von Hook 1 freigestellt,
damit K73 handeln kann).

### 57.2 Verankerung an 69.87 — Hypothese (mechanisch bestätigt)

**Provenienz-Vermerk:** `69,87` ist ein **manuell gesetzter institutioneller
Wert des Anwenders**. Er ist **nicht** aus der Engine ableitbar (kein Wick, kein
`e.basis`, kein `basis_bei`) und wird hier ausschließlich als externe Vorgabe
behandelt — analog der Norm-Behandlung in §37.4.

| Bar | Broker/UTC | Bar-Zeit (+02:00) | H | C | dist(69,87) | `cl ≤ 69,87` | Stufe |
|---|---|---|---|---|---|---|---|
| 980 | 24.08. 15:00 | 24.08. 17:00 | 69,8990 | **69,8100** | **+0,0415 %** | ja | **(1, `STUFE_1_IN_BAR`)** |
| 1020 | 25.08. 02:00 | 25.08. 04:00 | 69,9240 | **69,5770** | **+0,0773 %** | ja | **(1, `STUFE_1_IN_BAR`)** |

**Bestätigt wird damit:** beide Bars durchstechen das Niveau
(+0,0415 % / +0,0773 %), schließen in-bar unter dem Niveau, und beide liefern
mechanisch **STUFE_1_IN_BAR** (`_reclaim_stufe` Z. 2018–2034). Die
Kontrollwerte des Entwurfs für dist und Stufe sind **exakt korrekt**.

### 57.3 Richtigstellung des Entwurfs (read-only verifiziert)

| Position | Entwurfswortlaut | **Verifizierter Wert** | Ursache der Abweichung |
|---|---|---|---|
| Bar 980 Close | 69,670 | **69,8100** | Zahl nicht aus der Engine |
| Bar 980 Entry | „Bar 981 Open (69,670)" | **69,8070** = `op[981]` | `entry = open[entry_bar]` (Z. 2634) |
| Bar 980 SL | 69,909 | **69,9490** = 69,8990 + 0,05 | `sl_buffer_usd = 0.05`, nicht 0,01 |
| Bar 980 R | +4,89 R | **+9,9877 R** | folgt aus Entry/SL/TP2 |
| Bar 1020 Close | 69,720 | **69,5770** | Zahl nicht aus der Engine |
| Bar 1020 Entry | „Bar 1021 Open (69,720)" | **69,5780** = `op[1021]` | `entry = open[entry_bar]` |
| Bar 1020 SL | 69,934 | **69,9740** = 69,9240 + 0,05 | `sl_buffer_usd = 0.05` |
| Bar 1020 R | +9,91 R | **+3,0032 R** | folgt aus Entry/SL/TP2 |
| P9-Ertrag | „~ +14,80 R" | **+19,8049 R** (Δ = +14,3837 R) | Level vs. Delta verwechselt |

**R-Nachrechnung (Engine-Formel):**

| Bar | Entry | SL | TP2 | risk | reward | reward/risk | Engine-R |
|---|---|---|---|---|---|---|---|
| 980 (K67) | 69,8070 | 69,9490 | 68,3700 | 0,1420 | 1,4370 | 10,1197 | **+9,9877** |
| 1020 (K67) | 69,5780 | 69,9740 | 68,3700 | 0,3960 | 1,2080 | 3,0505 | **+3,0032** |

### 57.4 Mechanisches Gesamtergebnis (Override P9-lokal, In-Memory)

| Kennzahl | Referenz (ohne Override) | **mit K67 = 69,87** | Δ |
|---|---|---|---|
| V1 gesamt | 15 / +46,866348 R | **17 / +61,250064 R** | **+14,383717 R** |
| H1 (`entry_bar < 640`) | 8 / +38,964262 R | **8 / +38,964262 R** | **0** (bit-identisch) |
| H2 (`entry_bar ≥ 640`) | 7 / +7,902085 R | **9 / +22,285802 R** | +14,383717 R |
| P9-Fenster (848–1020) | +5,4212 R | **+19,8049 R** | +14,3837 R |
| Sperren: blocker / quartil / zyklus | 23 / 57 / 27 | **23 / 57 / 28** | zyklus +1 |

**P9-Trade-Setze mit Override:**

| Bar | Kante | Stufe | Entry-Bar | Entry | SL | TP2 | R |
|---|---|---|---|---|---|---|---|
| 903 | K67 | `STUFE_2_KERZE_2` | 905 | 69,6700 | 69,9810 | 68,3700 | **+4,1198** |
| 980 | **K67** | `STUFE_1_IN_BAR` | 981 | 69,8070 | 69,9490 | 68,3700 | **+9,9877** |
| 981 | K73 | `STUFE_1_IN_BAR` | 982 | 69,4910 | 69,9010 | 68,3700 | **+2,6943** |
| 1020 | **K67** | `STUFE_1_IN_BAR` | 1021 | 69,5780 | 69,9740 | 68,3700 | **+3,0032** |

### 57.5 Nebenfolgen (nicht im Entwurf enthalten — bitte prüfen)

1. **Es ist kein reiner Tausch der beiden Bars.** Zusätzlich entstehen
   **K67@903** (`+4,1198 R`, Entry-Bar 905) und **K73@981** (`+2,6943 R`,
   Entry-Bar 982); die bisherigen **K73@980** und **K73@1020** entfallen. Der
   P9-Zuwachs (+14,3837 R) verteilt sich also auf vier Trades, nicht auf zwei.
2. **Der K73-Umweg ist nicht vollständig falsifiziert.** Mit Override liefert
   K73 an Bar 981 weiterhin einen Treffer ⇒ K67 tritt als *zusätzlicher*
   Direktauslöser auf, ersetzt den K73-Pfad aber nicht vollständig.
3. **Hook 1 wird in dieser Konstruktion gegenstandslos.** Hook 1 verlangt
   `dist < 0`; mit `basis_bei(K67) = 69,87` gilt an beiden Bars `dist > 0`
   ⇒ `hook_1_freigabe_kid` liefert `None`. Die Freistellung erzeugt dann
   keine Wirkung mehr.
4. **Provenienz von 69,87 offen.** Der Wert ist engine-fremd (anwender-set).
   Eine Arretierung müsste ihn als Phase-Override in den Adapter aufnehmen
   (§58), nicht in die Kante selbst.

---

## 58. Entkopplung von der Core-Engine

> **Beauftragter Wortlaut (Entwurf):** „Um die H1-Baseline (+38.964262 R)
> unberührt zu lassen, wird basis_bei in der Core-Engine nicht global
> verändert. Die Verankerung 69.87 wird ausschließlich als phasen-lokaler
> Adapter-Override für P9/H2 modelliert."

### 58.1 Bestätigung der Unberührtheit (verifiziert)

Die Entkopplung ist mechanisch **nachweisbar**: Der Override wurde in der
Simulation auf `P9.start_bar ≤ k ≤ P9.end_bar` (848–1020) begrenzt, also
**oberhalb** der H1-Box (`entry_bar < 640`). Ergebnis:

```
H1 (entry_bar < 640): 8 Trades / +38.964262 R   (bit-identisch zur Referenz)
```

Der H1-Wert ist **auf 6 Dezimalstellen identisch**; `box_end_bar = 640` und die
`_p11`-Projektion bleiben damit unberührt (§36.2/§36.3, S3).

### 58.2 Gegenprobe (Inertheit der Override-Maschinerie)

Mit deaktiviertem Override reproduziert der Lauf die arretierte Referenz
**exakt**: `15 / +46.866348 R`, H1 `8 / +38.964262 R`, H2 `7 / +7.902085 R`,
P9 `+5.4212 R`, K73-Trades `[(980, +2.4119), (1020, +3.0093)]`, K67-Trades
`[]`. ⇒ Werkzeug ist beweisbar nebenwirkungsfrei.

### 58.3 Umsetzungsrahmen (Vorschlag, **nicht** implementiert)

| Punkt | Vorgabe |
|---|---|
| Ort | `backtest_lab/phasen_regime_adapter.py`, Segment `P9` (bzw. Folge-Modul) |
| Form | Phasen-lokaler Niveau-Override je Kante (z. B. `niveau_override` in `PhasenKanteInfo`), **kein** Eingriff in `_SEEdgeH.basis_bei` der Engine |
| Scope | `P9.start_bar .. P9.end_bar`; außerhalb unverändert (MAKRO/H1 unberührt) |
| Provenienz | `69,87` als anwender-gesetzter Wert dokumentieren (engine-fremd) |
| Regelkonformität | Hook 1 bleibt unangetastet; bei `dist > 0` greift regulär `Q1` (Wand handelt) |
| Fail-Loud | `verifiziere_gegen_scan` bleibt aktiv; Override ist **kein** Provenienz-Ersatz (§37.4 / Option (b)) |

**Offene Entscheidungsfragen (Textblock, keine Auswahl):**

1. Ist die Arretierung als **zusätzlicher Phasen-Override** (Vorschlag §58.3)
   oder als **neue Kante** mit eigenem `kid` zu modellieren?
2. Soll `69,87` als `niveau_override` im Adapter verankert und damit
   fail-loud geprüft werden, oder bleibt es ein Kommentar-/Auditwert
   (Option (b), §37.4)?
3. Sollen die zwei Nebenfolge-Trades **K67@903** und **K73@981** mitarretiert
   werden, oder ist nur das Bar-980/1020-Paar Gegenstand der Freigabe?
4. Bleibt die H2-Referenz `+7,902085 R` als Vergleichsanker stehen, obwohl der
   Override sie auf `+22,285802 R` hebt?

---

## 59. Status (v0.14)

| Kennzahl | Wert | Berührt durch v0.14? |
|---|---|---|
| V0 / H1 | 14 / 8 / +38,964262 R | nein |
| V1 (P9, arretiert) | 15 / +46,866348 R | nein |
| H2 V1 (arretiert) | 7 / +7,902085 R | nein |
| Engine SHA256 | `3ba15c72…5255cb006` | nein |
| Adapter | unverändert (kein Override implementiert) | nein |
| Simulationsbefund K67 = 69,87 | 17 / +61,250064 R (Δ +14,383717) | **nur dokumentiert** |

v0.14 ist ein **Befund-Addendum**: Es dokumentiert die Falsifikation des
`np.mean`-Basisfehlers für K67, bestätigt die mechanische Direktauslösung an
69,87, korrigiert sechs Entwurfswerte (§57.3) und legt den Umsetzungsrahmen
der Entkopplung offen (§58) — **ohne** Engine-, Adapter- oder
Darstellungsänderung.

---

# Addendum v0.15 — Ausführung von v0.14: Phasen-Niveau-Override K67 = 69,87 (2026-09-10)

**Freigaben:** Q1–Q5 (Anwender, 2026-09-10; Antworten auf den Textblock in
§58.3 / §57.5). **Wirkung:** Adapter-**Erweiterung** (rein additiv) plus
Arretierung. Engine unberührt. **Status:** umgesetzt und verifiziert.

| Übergabe | Datei / Symbol | Commit |
|---|---|---|
| Adapter | `backtest_lab/phasen_regime_adapter.py` (+133 Z., 0 Entf.) | **`8487145`** |
| Verifikation | `test/tmp_test_v014_override.py` (gitignored) | – |
| Engine | `test/tmp_kanten_engine_replay.py` — SHA256 `3ba15c72…5255cb006` | unberührt |

Die fünf Fragen aus §58.3 sind beantwortet und **so** umgesetzt:

| # | Frage | Entscheidung des Anwenders | Ausführung |
|---|---|---|---|
| Q1 | Override oder neue Kante? | **Phasen-Override im Adapter, keine neue Kanten-ID** | `PhasenKanteInfo.niveau_override` (§60) |
| Q2 | Fail-Loud binden? | **Ja — FAIL-LOUD, strikt `phase == 'P9'`** | `verifiziere_niveau_overrides()` (§61) |
| Q3 | Nebenfolge-Trades? | **Quartett (903, 980, 981, 1020) mitarretieren, kein Cherry-Picking** | `QUARTETT_V014_BARS` (§62) |
| Q4 | Alter H2-Anker? | **BEIDE Werte ausweisen** (keiner verdraengt den anderen) | Benchmark-Register (§63) |
| Q5 | Historie? | **v0.14 behalten, Historie nicht umbiegen** | §64 |

---

## 60. Q1 — Phasen-Override statt neuer Kante

**Entscheidung.** `69,87` wird **nicht** als neue Harness-Kante (`kid`) und
**nicht** als Eingriff in `_SEEdgeH.basis_bei` der Engine modelliert, sondern
als **phasen-lokaler Niveau-Override** an der bestehenden Decke K67 des
Segments P9. Begründung: Der Wert ist engine-fremd (anwender-gesetzt, §57.2);
eine neue `kid` würde die Kanten-Identität (§37.4) und die Sperr-Logik (M6)
verfälschen. K67 bleibt die Decke — nur ihr **Niveau innerhalb P9** ändert
sich.

**Umsetzung (additiv, Bestandsverhalten v0.1 unverändert Default):**

| Element | Inhalt |
|---|---|
| `PhasenKanteInfo.niveau_override: Optional[float] = None` | neues Optional-Feld (Default = keine Wirkung) |
| `PhasenKanteInfo.hat_override() -> bool` | `True` gdw. Override gesetzt |
| `K67_OVERRIDE_69_87 = 69.87` | der anwender-gesetzte Wert, als benannte Konstante |
| `P9_DIRECT_69_87` | Segment P9, `start_bar=848`, `end_bar=1020`, `decke=K67(provenienz 69.9140, override 69.87)`, `boden=K77(68.3700)` |
| `AKTIVE_SEGMENTE_V014 = (P9_DIRECT_69_87,)` | Selektionsliste der v0.14-Variante |
| `AKTIVE_DEFAULT_SEGMENTE = (P9,)` | **unverändert arretiert** (v0.1-Baseline) |
| `PhasenRegimeAdapter.niveau_override_bei(bar, kid)` | liefert den Override **nur** im eigenen Segmentfenster und **nur** für Decke/Boden |
| `PhasenRegimeAdapter.angewandte_basis(bar, kid, basis_engine)` | Injektionsschicht: `override` sonst `basis_engine` unverändert |

**Kernaussage der Entkopplung (§58.1):** Der Override gilt ausschließlich für
`848 ≤ k ≤ 1020`. Die H1-Box (`entry_bar < 640`) liegt vollständig darunter
⇒ `angewandte_basis` liefert dort **immer** die Engine-Basis zurück.

**Auflösung der Nebenfolge §57.5.3:** Mit `basis_bei(K67) = 69,87` gilt an
den Bars 980/1020 `dist > 0`; Hook 1 (`dist < 0`) liefert dort `None` und wird
gegenstandslos — bestätigt, keine Fehlfunktion.

**Konfigurationsstand (unverändert):** `sl_buffer_usd = 0.05`,
`touch_band_pct = 0.12`, `doppeltop_puffer_usd = 0.01`,
`retest_zyklus_bars = 12`, `entry = open[entry_bar]`.

---

## 61. Q2 — Fail-Loud-Bindung an die Phase

**Entscheidung.** Der Override ist eine **phasen-gebundene** Größe und wird
nicht still, sondern **hart** geprüft. `verifiziere_niveau_overrides()` wird
beim Aufbau von `ADAPTER_V014` (Modulimport) erzwungen.

**Phasenbindung (`niveau_override_bei`) — geprüft:**

| Aufruf | Ergebnis | Soll |
|---|---|---|
| `(980, 67)` | `69.87` | Override (in P9, K67-Decke) |
| `(1020, 67)` | `69.87` | Override (Segmentrand, inklusiv) |
| `(980, 73)` | `None` | fremde Kante → Engine-Basis |
| `(847, 67)` | `None` | unterhalb P9 |
| `(1021, 67)` | `None` | oberhalb P9 |
| `(1100, 67)` | `None` | außerhalb (späteres Fenster) |
| `(640, 67)` / `(200, 67)` | `None` | H1-Box → unberührt |
| Boden K77 | ohne Override | `hat_override() == False` |
| `angewandte_basis(980, 67, 69.9687)` | `69.87` | Override schlägt Engine |
| `angewandte_basis(1100, 67, 69.9000)` | `69.9000` | Engine durchgereicht |

**Fail-Loud-Kriterien (`verifiziere_niveau_overrides`) — Negativproben
greifen:**

| Prüfung | Kriterium | Negativprobe | Ergebnis |
|---|---|---|---|
| Endlichkeit/Positivität | `isfinite(ov) and ov > 0` | `-1.0` | `ValueError` ✅ |
| Endlichkeit/Positivität | ebd. | `nan` | `ValueError` ✅ |
| Provenienz-Toleranz | `|ov − provenienz| / provenienz ≤ 1,00 %` | `75.0` (7,2747 %) | `ValueError` ✅ |
| Segmentfenster | `start_bar ≤ end_bar` | – | `ValueError` |
| Positivprobe | `69,87` vs. `69,9140` | – | **0,0629 % → OK** ✅ |

⇒ Ein unplausibler Override kann **nicht** still in Kraft treten. Der
Strength der Bindung liegt auf der Phasen-Zugehörigkeit, nicht auf einer
globalen Zahl.

---

## 62. Q3 — Quartett-Protokoll (mitarretiert, kein Cherry-Picking)

**Entscheidung.** Es wird **nicht** das günstige Bar-980/1020-Paar
herausgegriffen; das vollständige P9-Trade-Set der v0.14-Variante wird als
**Quartett** arretiert: `QUARTETT_V014_BARS = (903, 980, 981, 1020)`.

| Bar-Index | Bar-Zeit (+02:00) | Kante | Stufe | Entry-Bar | Entry | SL | TP2 | R |
|---|---|---|---|---|---|---|---|---|
| **903** | 21.08. 20:45 | **K67** | `STUFE_2_KERZE_2` | 905 | 69,6700 | 69,9810 | 68,3700 | **+4,1198** |
| **980** | 24.08. 17:00 | **K67** | `STUFE_1_IN_BAR` | 981 | 69,8070 | 69,9490 | 68,3700 | **+9,9877** |
| **981** | 24.08. 17:15 | K73 | `STUFE_1_IN_BAR` | 982 | 69,4910 | 69,9010 | 68,3700 | **+2,6943** |
| **1020** | 25.08. 04:00 | **K67** | `STUFE_1_IN_BAR` | 1021 | 69,5780 | 69,9740 | 68,3700 | **+3,0032** |

**Quartett-Summe: +19,804922 R** (= P9-Beitrag v0.14). Kanten-Zuordnung:
903/980/1020 = K67 (Override), 981 = K73 (Engine-Basis). Stufen:
980/981/1020 = `STUFE_1_IN_BAR`, 903 = `STUFE_2_KERZE_2`.

**Damit ist §57.5.1 engine-nativ bestätigt:** v0.14 ist **kein** reiner Tausch
der beiden Bars — es entstehen zwei zusätzliche Trades (K67@903, K73@981),
und die bisherigen K73@980 / K73@1020 entfallen. Beide neuen Trades werden
mitgeführt, nicht das Ergebnis „+9,9877 / +3,0032 R" isoliert.

**R-Nachrechnung (Engine-Formel, `reward/risk`, Beitrag §57.3):**

| Bar | risk = SL − Entry | reward = Entry − TP2 | reward/risk | Engine-R |
|---|---|---|---|---|
| 980 (K67) | 0,1420 | 1,4370 | 10,1197 | **+9,9877** |
| 1020 (K67) | 0,3960 | 1,2080 | 3,0505 | **+3,0032** |

---

## 63. Q4 — Beide Benchmarks, keiner verdraengt den anderen

**Entscheidung.** Die arretierte v0.1-H2-Referenz **bleibt** als
Vergleichsanker stehen; die v0.14-Variante wird **daneben** geführt. Beide
Werte sind im Adapter als read-only Register abgelegt und werden in der
Verifikation gegeneinander geprüft.

**Benchmark-Register (`backtest_lab/phasen_regime_adapter.py`):**

| Konstante | Wert | Rolle |
|---|---|---|
| `BASELINE_V01_H2_R` | **7.902085** | v0.1-Baseline (K73-Umweg, arretiert) |
| `BENCHMARK_V014_H2_R` | **22.285802** | v0.14 (Phasen-Override) |
| `BENCHMARK_V014_GESAMT_R` | **61.250064** | v0.14 gesamt (17 Trades) |
| `BENCHMARK_V014_DELTA_R` | **14.383717** | Zuwachs gegenüber v0.1 |
| `QUARTETT_V014_BARS` | `(903, 980, 981, 1020)` | Arretierung (§62) |

**Konsistenzprobe (im Lauf erzwungen):** `BENCHMARK_V014_H2_R − BASELINE_V01_H2_R
= BENCHMARK_V014_DELTA_R` → `22,285802 − 7,902085 = 14,383717` ✅.

**Verifikationsergebnis (Engine-Lauf, In-Memory-Injektion, Engine byte-unberührt):**

| Kennzahl | Soll | Ist |
|---|---|---|
| V0-Referenz | 14 / +40,445143 R | **14 / +40,445143 R** ✅ |
| v0.1-Baseline über Injektion (bit-identisch) | 15 / +46,866348 R | **15 / +46,866348 R** ✅ |
| H1 (Override-Lauf) | 8 / +38,964262 R | **8 / +38,964262 R** ✅ |
| H2 v0.1 | 7 / +7,902085 R | **7 / +7,902085 R** ✅ |
| H2 v0.14 | 9 / +22,285802 R | **9 / +22,285802 R** ✅ |
| Gesamt v0.14 | 17 / +61,250064 R | **17 / +61,250064 R** ✅ |
| Δ | +14,383717 R | **+14,383717 R** ✅ |
| H2-Zusatztrades | +2 (9 vs. 7) | **9 vs. 7** ✅ |

**Gegenprobe v0.1 (Override-Maschinerie inert, §58.2):** mit deaktiviertem
Override reproduziert der Lauf die Referenz **exakt** — H1 8 / +38,964262,
H2 7 / +7,902085, gesamt 15 / +46,866348. ⇒ Das Werkzeug ist beweisbar
nebenwirkungsfrei.

---

## 64. Q5 — v0.14-Arretierung, Historie unverändert

**Entscheidung.** Die Arretierung erfolgt durch **Hinzufügen** der
v0.14-Variante, nicht durch Überschreiben. `DEFAULT_ADAPTER` bleibt die
arretierte v0.1-Baseline (`segmente = (P9,)`); die v0.14-Variante ist
**explizit zu wählen**:

```python
DEFAULT_ADAPTER = PhasenRegimeAdapter()                     # unverändert
ADAPTER_V014    = PhasenRegimeAdapter(segmente=AKTIVE_SEGMENTE_V014)
ADAPTER_V014.verifiziere_niveau_overrides()                 # erzwungen beim Import
```

**Ausgeschlossen:** Der `np.mean`-Basisfehler (§57.1) wird **nicht** durch
eine Änderung von `_SEEdgeH.basis_bei` korrigiert. Die Core-Engine bleibt
byte-identisch (S3) — die Korrektur lebt ausschließlich als
Injektionsschicht (§60). Ebenso unverändert: `box_end_bar = 640` und die
`_p11`-Projektion (§36.2/§36.3).

**Unberührt / nicht umgebogen:**

| Gegenstand | Status |
|---|---|
| v0.14-Addendum §§57–59 | **bewahrt** (Befund-Stand, keine Umschreibung) |
| P12 / `P12_RESERVE` | Reserve, operativ inert (§48.2) |
| Darstellungsnorm §§54/55 | gültig; PNG-Neuerzeugung mit K67@69,87-Linie separat |
| Hook 1 (`dist < 0`) | unverändert; greift in P9 mit Override nicht mehr (§60) |

---

## 65. Status (v0.15)

| Kennzahl | Wert | Berührt durch v0.15? |
|---|---|---|
| V0 / H1 | 14 / 8 / **+38,964262 R** | nein (bit-identisch) |
| V1 (P9, v0.1 arretiert) | 15 / **+46,866348 R** | nein |
| H2 v0.1 (arretiert) | 7 / **+7,902085 R** | nein |
| H2 v0.14 (neu) | 9 / **+22,285802 R** | **ja (neu arretiert)** |
| Gesamt v0.14 (neu) | 17 / **+61,250064 R** | **ja (neu arretiert)** |
| Δ v0.14 − v0.1 | **+14,383717 R** | **ja (neu arretiert)** |
| P9-Beitrag v0.14 (Quartett) | **+19,804922 R** | **ja (neu arretiert)** |
| `DEFAULT_ADAPTER.segmente` | `(P9,)` (unverändert) | nein |
| `ADAPTER_V014.segmente` | `(P9_DIRECT_69_87,)` | **ja (neu)** |
| Engine SHA256 | `3ba15c72…5255cb006` | **nein (unberührt)** |

v0.15 ist ein **Umsetzungs-Addendum**: Es dokumentiert die additive
Adapter-Erweiterung (Phasen-Niveau-Override K67 = 69,87, fail-loud, strikt an
P9 gebunden), das mitarretierte Quartett und die Nebeneinanderführung **beider**
Benchmarks — bei byte-unveränderter Engine und unangetasteter H1-Baseline.

---

# Addendum v0.16 — Norm-Amendment: Darstellung der V014-Override-Wirklichkeit (2026-09-10)

**Anlass.** Der Anwender hat nach der Renderer-Sichtung die Punkte F1, F3, F4
und F5 entschieden. Drei davon sind **Regeländerungen** an der
Darstellungsnorm §54 und werden hier ausgewiesen.

**Regelhaltung (Option (b), §37.4 — bindend auch für dieses Dokument).** Die
v0.13-Fassung §54 bleibt **wortgetreu stehen** und wird als Zitat behandelt.
Alle Erweiterungen werden **angehängt, nicht ersetzt**; §54 wird **nicht** in
seiner v0.13-Substanz überschrieben. Der Docstring-Kopf von
`test/tmp_png_aug_sichttest.py` spiegelt ab v0.16 **§54 plus §66**.

## 66.0 Änderungsübersicht

| Punkt | Gegenstand | Art | Betroffene §54-Stelle |
|---|---|---|---|
| F1 | Norm-Quelle bleibt deklarierter Gesamtbestand | **Klarstellung** (keine Änderung der Norm) | §54.1.3 |
| F3 | Override-Zone per Grenzlinien, nicht per Fläche | **Ergänzung** (neu Regel 15) | §54.2 |
| F4 | Blasse Referenz-Trades im V014-Modus | **Ausnahme** | §54.2 Regel 10 |
| F5 | Plateau-Syntax für Override-Linien | **Erweiterung** | §54.1 Regeln 1/2 |
| F7 | Renderer-Konfigurationsvertrag, zwei Instanzen | Ergänzung (Artefakt) | §54.3 |
| E4 | Fail-Loud ohne Abschalter | **Klarstellung** | §54 i.V.m. §16/§61 |

## 66.1 Norm-Quelle bleibt der deklarierte Gesamtbestand (F1)

**Entscheidung.** §54.1.3 gilt **unverändert wörtlich**: „Norm-Quelle ist
ausschließlich der Adapter (`P9.decke/boden`, `P12_RESERVE.decke/boden`) —
kein Hardcoding."

Der geprüfte Gegenvorschlag „nur aktive Segmente" wurde **verworfen**, weil er
vier arretierte Aussagen gebrochen hätte:

| Gebrochen | Soll | Mit „nur aktiv" |
|---|---|---|
| §54.1 Beleglauf | 4 Grenzkanten (K67, K73, K77, K82) | nur 2 (K67, K77) |
| §54.1.3 Wortlaut | `P9` **+** `P12_RESERVE` | nur `P9` |
| §55 S5 | verweist auf §54 „in Gänze" | Divergenz Docstring ↔ Spez |
| §56 Status | „4 von 4" normabweichend | „2 von 2" |

Zusätzlich wäre die **Byte-Identität des arretierten V01-Satzes** (§30/§35)
nicht mehr haltbar gewesen (P1 verbietet Eingriffe in den v0.1-Bildsatz).

**Entlastender Nebenbefund (verifiziert).** `_basis_von(kid)` liest die
**Engine**-Basis bei `NORM_REF_BAR = 1259`. Bar 1259 liegt **außerhalb** P9
⇒ die K67-Normaussage (`69,9458 vs. 69,9140`, Δ `+0,0318`, ABWEICHUNG) ist
vom P9-Override **unberührt**. Die P9-Lokalität der Übersteuerung ist im
Norm-Statement damit korrekt abgebildet — es bedarf **keiner** Änderung.

## 66.2 Plateau-Syntax für Override-Linien (Erweiterung §54.1.1/§54.1.2)

**§54.1 Regel 1** wird für Kanten mit `niveau_override` ergänzt:

> Liegt für eine Kante ein phasen-lokaler Niveau-Override vor, lautet das
> Label **`K<kid> <native_start> -> <override> (<phase>-Override) ->
> <native_ende> *`**, gefolgt vom Norm-Zitat nach §54.1.3.

`native_start` ist der **verdrängte** native Wert am ersten gezeichneten Bar
(= `basis_bei` unmittelbar vor bzw. bei Override-Beginn), `native_ende` der
kausale Endwert nach Verlassen des Override-Fensters.

**§54.1 Regel 2** wird ergänzt: Bei Override-Linien ist der `*`-Marker
**verpflichtend** (fett, Rahmen `C_CHG`), auch wenn nur zwei
Preiswechsel-Stufen vorliegen — Unterscheidungsmerkmal „Übersteuerung" statt
„natürlicher Preiswechsel".

**Beleglauf K67 (Auflösung in Einzelbars, verifiziert gegen
`test/tmp_png_aug_sichttest_out.txt`):**

| Bar | native `basis_bei(k)` | wirksam (V014) | Quelle |
|---|---|---|---|
| 875 | 69,9750 | **69,8700** | Override (erster bestätigter Wick = 873) |
| 883 | 69,9875 | **69,8700** | Override |
| 906 | 69,9687 | **69,8700** | Override |
| 982 | 69,9513 | **69,8700** | Override |
| 1021 | 69,9513 | 69,9513 | nativ (Wick 1020 noch unbestätigt: 1022 > 1021) |
| 1022 | 69,9458 | **69,9458** | nativ, alle 5 Wicks |

⇒ native Stufen **5** (Protokollzeile `K67 69.9750 -> 69.9458 (delta -0.0292,
5 Stufen)`) · wirksame Stufen **3** (875 / 1021 / 1022) · `v_ende = 69,9458`
(**nicht** 69,9513).

**Resultierendes Label:**

```
K67 69.975 -> 69.870 (P9-Override) -> 69.946 *  Norm 69.9140
```

Die Linie wird ab Bar **875** starr auf `69.8700` geführt (Kantenmaske
`pivot_bar + 2`), verlässt das Regime geometrisch bei **1021** und nimmt auf
**1022** ihren nativen Endwert an.

## 66.3 Override-Zonen: Grenzlinien statt Fläche (Erweiterung §54.2; neu Regel 15)

**§54.2 wird um Regel 15 ergänzt:**

> **Override-Zonen werden durch vertikale Grenzlinien markiert, nicht durch
> eine überlagernde Fläche.** Je Override-Segment werden zwei gestrichelte
> Vertikalen an `start_bar` und `end_bar + 1` in `C_CHG` mit Kleintext
> gesetzt (`Override <phase> <preis> ab Bar <start>` / `… bis Bar <end>`).
> Ein `axvspan` in `C_CHG` ist unzulässig, weil es mit der Regime-Zone
> (`C_REGIME`, §54.2) und dem Label-Rahmen farblich kollidiert.

Begründung (F3): Der Eintritt ist **nicht** als Linienknick zeichenbar — K67
existiert erst ab Bar 875 (`pivot_bar + 2`), während das Regime institutionell
ab Bar 848 gilt. Die Grenzlinien trennen daher sauber **Regime-Gültigkeit**
(848) von **Kanten-Existenz** (875) und **Austritt** (1021). In Panels, die
Bar 848 nicht enthalten (H1-Box, Panel 02), entfallen die Grenzlinien.

**Geltung:** nur bei `k67_override_aktiv = True` (Modus V014). Im Modus V01
wird weder Linie noch Kleintext erzeugt.

## 66.4 Referenz-Trades im V014-Modus (Ausnahme zu §54.2 Regel 10)

**§54.2 Regel 10** („Trade-Kreise sind **immer** farbig gefüllt (`mfc=col`)")
erhält eine **deklarierte Ausnahme**:

> Im Modus V014 werden die im V014-Lauf **entfallenen** V01-Trades
> (Mengendifferenz `V1_basis \ V1_aktiv`) als **Referenzmarker** gezeichnet:
> gestrichelt, `mfc="none"`, Randfarbe grau, `alpha ≈ 0.45`. Sie sind damit
> von handelnden Trades unterscheidbar und **nicht** als Positionen lesbar.
> Die Regel „handelnde Trades sind farbig gefüllt (`mfc=col`)" bleibt für alle
> Trades beider Läufe unangetastet; die Ausnahme betrifft ausschließlich
> entfallene Referenzmarker.

**Begründung (F4/P4).** Der Sichtprüfer muss den Eingriff unmittelbar sehen:
„innerer Trade eliminiert, durch überlegenen Direkt-Sweep ersetzt". Erwartete
Menge (programmgesteuert, **kein** Hardcoding): `K73@980`, `K73@1020`;
Gegenstück im Aktiv-Lauf: `K67@903`, `K67@980`, `K73@981`, `K67@1020`.

## 66.5 Renderer-Konfiguration und Fail-Loud (F7, E4)

**F7 — ein Vertrag, zwei Instanzen.** Die Konfiguration wird als **eine**
`@dataclass(frozen=True, slots=True)` `RendererKonfiguration` geführt mit den
Instanzen `KONFIGURATION_V01` und `KONFIGURATION_V014`
(`AdapterMode = Literal["V01", "V014"]`). Die Feldwerte sind der arretierte
Assert-Katalog:

| Feld | V01 | V014 |
|---|---|---|
| `ausgabe_praefix` | `aug_sichttest_` | `aug_sichttest_v014_` |
| `protokoll_datei` | `test/tmp_png_aug_sichttest_out.txt` | `test/tmp_png_aug_sichttest_v014_out.txt` |
| `ziel_trades_gesamt` | 15 | 17 |
| `ziel_r_gesamt` | 46,866348 | 61,250064 |
| `ziel_r_h1` | 38,964262 | 38,964262 |
| `ziel_r_h2` | 7,902085 | 22,285802 |
| `ziel_p9_beitrag` | 5,4212 | 19,804922 |
| `k67_override_aktiv` | False | True |
| `niveau_override_wert` | None | 69,8700 |
| `alt_trades_einblenden` | False | True |
| `quartett_bars` | `()` | `(903, 980, 981, 1020)` |

**E4 — Fail-Loud ist nicht optional.** Das im Entwurf vorgesehene Feld
`fail_loud_asserts_aktiv` wird **ersatzlos gestrichen**. Es gibt keinen
Schalter „Asserts aus"; §16 (Fail-Loud-Init) und §61 (Fail-Loud-Override)
sind erzwungen. Bei Abweichung endet der Lauf mit Exit-Code ≠ 0.

**Protokolltrennung (E3).** Der V014-Lauf schreibt in
`test/tmp_png_aug_sichttest_v014_out.txt`. Das v0.1-Protokoll
`test/tmp_png_aug_sichttest_out.txt` ist **versiegeltes** Referenzartefakt und
wird **nicht** überschrieben.

## 66.6 Status (v0.16)

| Kennzahl | Wert | Berührt durch v0.16? |
|---|---|---|
| V0 / H1 | 14 / 8 / +38,964262 R | nein |
| V1 v0.1 (arretiert) | 15 / +46,866348 R | nein |
| H2 v0.1 / H2 v0.14 | 7 / +7,902085 R · 9 / +22,285802 R | nein |
| Norm-Quelle (§54.1.3) | `P9` + `P12_RESERVE` (4 Grenzkanten) | **bestätigt, unverändert** |
| Engine SHA256 | `3ba15c72…5255cb006` | nein |
| Regelbestand | §54 (v0.13) **+** §66 (v0.16) | **erweitert** |

v0.16 ist ein **Regel-Amendment**: Es ergänzt §54 um die Darstellung der
Override-Wirklichkeit (Plateau-Syntax, Grenzlinien, Referenzmarker) und
bestätigt die Norm-Quelle. §54 bleibt als v0.13-Zitat unverändert bestehen.

---

# Addendum v0.17 — Arretierung des V014-Sichttests (2026-09-10)

**Auftrag.** Freigabe der Punkte P1–P4, E1–E5 und F1–F7 sowie Ausführung von
Schritt 2 (Renderer-Umbau) und Schritt 3 (Lauf). **Wirkung:**
Arretierung eines **zweiten**, parallelen Bildsatzes. Der v0.1-Satz bleibt
byte-unverändert. Engine unberührt.

| Übergabe | Gegenstand | Commit |
|---|---|---|
| Regelwerk | §66 Norm-Amendment (v0.16) | **`d677adc`** |
| Adapter | `ADAPTER_V014` + `niveau_override` | `8487145` |
| Renderer | `test/tmp_png_aug_sichttest.py` (gitignored) | – |
| Engine | SHA256 `3ba15c72…5255cb006` | unberührt |

**Entscheide in Kurzform:** P1 ergänzen · P2 `ADAPTER_MODE`-Umschaltung ·
P3 K67 phasen-lokal 69,8700 mit `*` · P4 Quartett voll + Alttrades blass ·
E1 Grenzlinien 848/1021 · E2 Plateau-Syntax · E3 eigenes Protokoll ·
E4 Fail-Loud ohne Abschalter · E5 **verworfen** zugunsten F1.

## 67.1 Renderer-Umbau: ein Vertrag, zwei Instanzen

`test/tmp_png_aug_sichttest.py` ist von einem v0.1-Festverdrahten Renderer auf
den Konfigurationsvertrag nach §66.5 umgestellt (**1.522 Zeilen / 68.813 B**,
LF, kein BOM, SHA256 `e88ec58d79232eff…`).

| Element | Umsetzung |
|---|---|
| `RendererKonfiguration` | `@dataclass(frozen=True, slots=True)`; **ein** Typ, **zwei** Instanzen |
| `KONFIGURATION_V01` / `KONFIGURATION_V014` | Sollwerte = arretierter Assert-Katalog (§66.5) |
| `--mode V01\|V014` | CLI-Umschaltung; **V014 ist Default** |
| `--probe-praefix`, `--protokoll-nach` | Gegenproben ohne Berührung der arretierten Artefakte |
| Fail-Loud | keine Option, kein Schalter; Abweichung ⇒ Exit ≠ 0 |
| Dateinamen | `{PROBE_PRAEFIX or ''}{ausgabe_praefix}{nr}_{rolle}.png` |
| Protokoll | `_Protokoll`-Tee (stdout + Datei), UTF-8, LF, kein BOM |

**Drei Läufe je Modus:**

| Lauf | Hook | Zweck |
|---|---|---|
| `V0` | – (unpatch) | Referenz 14 / +40,445143 R |
| `V1_basis` | `DEFAULT_ADAPTER` | v0.1-Baseline; liefert die **blassen Referenz-Trades** |
| `V1_aktiv` | `adapter` (modusabhängig) | der dargestellte Satz |

Die Referenzmenge wird **programmgesteuert** gebildet (`§66.4`) — als
Schlüsseldifferenz über `(bar, kid)`, nicht als Literal und nicht via
`set()` (Begründung in §67.7).

## 67.2 Injektionsschicht: der Blocker aus der Renderer-Sichtung

**Befund.** Der v0.1-Renderer band einen **6-Fragment**-Patch. Dieser leitete
`basis_bei` **nicht** um; ein gesetztes `ADAPTER_V014` hätte **geräuschlos**
weiter den v0.1-Stand gemalt, während Titel „v0.14" behaupten — ein
unsichtbares Falschbild.

**Behebung.** Der verifizierte **13-Fragment**-Satz aus
`test/tmp_test_v014_override.py` wurde wörtlich übernommen; zusätzlich zu den
v0.1-Fragmenten (`A_KANTEN`, `A_LOOP`, `A_POOL`, `A_M6_OBEN`, `A_M6_UNTEN`,
`A_TP2`) sind nun `_basis_wirksam` und die sieben Anbindungen
`A_DIST`, `A_M6_BASIS`, `A_M6_BASIS_K`, `A_M6_RET`, `A_M6_SORT`,
`A_M6_SORT2`, `A_KBASIS` aktiv. Jedes Fragment wird mit
`assert src.count(_s) == 1` erzwungen.

**Konsequenz:** Ein Patch-Satz, zwei Modi; umgeschaltet wird ausschließlich
die gebundene `PhasenRegimeAdapter`-Instanz.

## 67.3 V01-Regressionsnachweis (Bit-Identität, verifiziert)

Der Gegenproben-Lauf (`--mode V01 --probe-praefix probe_v01_`) erzeugte den
Satz unter Probepräfix; die arretierten Dateien blieben unberührt.

| Datei | Bytes | SHA256 | Gegenprobe |
|---|---|---|---|
| `aug_sichttest_01_gesamt.png` | 1.876.828 | `89ec7acd276b8f8e0027990790179e252c17a3e18cb96e403fdd31b9c33b537a` | **IDEM** |
| `aug_sichttest_02_h1_box.png` | 899.249 | `d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04` | **IDEM** |
| `aug_sichttest_03_h2_phasen.png` | 1.520.409 | `d131deafdafd37eeeaad72235a4667d981f2ac8070baffedc7873a98b67307ff` | **IDEM** |
| `aug_sichttest_04_p9_regime.png` | 881.262 | `91a85baecd2b9abd06691b1f54b55b6856c31a259090d053b11e4c3620afbca4` | **IDEM** |
| `aug_sichttest_05_kantenkarte.png` | 1.905.228 | `0b2b14635cb2c2efc3a3ff0f39fb49afb9760bee3de2657ab3f2473a5cb69444` | **IDEM** |

Alle fünf PNGs sind **SHA256-bit-identisch** (Probepräfix-Dateien anschließend
gelöscht). Die Byte-Größen stimmen exakt mit §35/§53 überein. ⇒ Der Umbau ist
**beweiskräftig verhaltensneutral**; P1 ist gewahrt.

**Zusatzbefund.** Das V01-Protokoll `test/tmp_png_aug_sichttest_out.txt`
(9.784 B, SHA256 `3bd99a781f4921a9…`) wurde durch den V014-Lauf **nicht**
überschrieben — E3 wirksam.

## 67.4 Artefakte des V014-Satzes

| Datei | Bytes | SHA256 |
|---|---|---|
| `aug_sichttest_v014_01_gesamt.png` | 2.049.763 | `25d388e66984a2e3432133fdfaf10901c605cc11ea251bc88d6c9f8383a34117` |
| `aug_sichttest_v014_02_h1_box.png` | 899.249 | `d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04` |
| `aug_sichttest_v014_03_h2_phasen.png` | 1.695.409 | `a055b243463460e8b459e5ad244b18e0b45e74a525f253cf358caae1cdd01fc7` |
| `aug_sichttest_v014_04_p9_regime.png` | 1.151.700 | `1f13a7f7910a62cee10afb64d70acf85f3015a01909ef382bfb299fea981118c` |
| `aug_sichttest_v014_05_kantenkarte.png` | 2.063.329 | `7b022907af4493663e06600892836d999a1e98dcec7e1731c3f458be4f7fbbd3` |

Protokoll: `test/tmp_png_aug_sichttest_v014_out.txt` — 5.363 B, 83 Zeilen,
UTF-8, LF, kein BOM, SHA256 `f1c06678a13a244d…`.

**Pixelbeweis für H1:** `aug_sichttest_v014_02_h1_box.png` ist **byte-identisch**
zu `aug_sichttest_02_h1_box.png` (gleicher SHA256, beide 899.249 B) — die
H1-Box wird selbst durch einen P9-lokalen Niveau-Override **pixelgenau nicht
berührt**.

## 67.5 Verifikationsprotokoll (Lauf `EXIT 0`)

| Kennzahl | Soll | Ist |
|---|---|---|
| V0 Referenz | 14 / +40,445143 R | **14 / +40,445143 R** ✅ |
| V1_basis (v0.1) | 15 / +46,866348 R | **15 / +46,866348 R** ✅ |
| V1_aktiv gesamt | 17 / +61,250064 R | **17 / +61,250064 R** ✅ |
| H1 | 8 / +38,964262 R | **8 / +38,964262 R** ✅ |
| H2 | 9 / +22,285802 R | **9 / +22,285802 R** ✅ |
| P9-Beitrag (Quartett) | +19,804922 R | **+19,804922 R** ✅ |
| Δ v0.14 − v0.1 | +14,383717 R | **+14,383717 R** ✅ |

**Quartett** (`QUARTETT_V014_BARS = (903, 980, 981, 1020)`):

| Bar | Kante | R | Soll |
|---|---|---|---|
| 903 | K67 | +4,1198 | ✅ |
| 980 | K67 | +9,9877 | ✅ |
| 981 | K73 | +2,6943 | ✅ |
| 1020 | K67 | +3,0032 | ✅ |

**Referenzmenge (programmgesteuert):** entfallen `K73@980` (+2,4119),
`K73@1020` (+3,0093) · neu `K67@903`, `K67@980`, `K73@981`, `K67@1020`
(Quadrupel-Kontrolle: `(67, 67, 73, 67)` ✅).

**Norm-Katalog unverändert (F1):** 4 von 4 Grenzkanten normabweichend —
K67 `+0,0318` · K73 `+0,1164` · K77 `−0,0103` · K82 `−0,1082`. Preiswechsel
**54** Linien (identisch zu §56).

## 67.6 Bestätigte Vorhersage aus §66.2

Die in §66.2 hergeleitete Stufenauflösung ist **eingetroffen**:

```
WECHSEL K67   69.8700 -> 69.9458  (delta +0.0758, 3 Stufen)
Plateau-Label K67 (gerendert):
  K67 69.975 -> 69.870 (P9-Override) -> 69.946 *  Norm 69.9140
```

| Vorhersage (§66.2) | Beleg |
|---|---|
| native Stufen 5 | Protokoll v0.1: `K67 69.9750 -> 69.9458 (5 Stufen)` |
| wirksame Stufen **3** | Protokoll V014: `69.8700 -> 69.9458 (3 Stufen)` |
| `v_ende = 69,9458` (**nicht** 69,9513) | Gerendetes Label: `-> 69.946` |
| Linie ab Bar **875** auf 69,8700 | Kantenmaske `pivot_bar + 2` |
| Austritt **1021**, Endwert ab 1022 | Grenzlinie 1021 gesetzt |

## 67.7 Zwei dokumentierte Abweichungen vom Wortlaut

1. **Mengendifferenz über Schlüssel statt `set(...)`.** `_SESetup` ist
   `frozen=True, slots=True` und damit hashbar — ein `set` würde aber
   **feldgleiche** Zeilen stillschweigend kollabieren. Die Differenz wird
   daher über `(bar, kid)` gebildet (`§66.4`-Semantik unverändert, Ergebnis
   wie vorhergesagt). Kein inhaltlicher Unterschied, geringeres Risiko.
2. **Protokollzeile zunächst ohne Norm-Anhang.** Beim ersten V014-Lauf wurde
   das Plateau-Label über `_plateau_label` (ohne Norm-Suffix) protokolliert.
   Korrigiert auf `kanten_label` (gerenderte Fassung inkl.
   `Norm 69.9140`). Der **Bildinhalt** war davon nicht betroffen; die
   Protokollzeile ist es jetzt ebenfalls nicht mehr.

## 67.8 Integrität und Hygiene

| Prüfung | Ergebnis |
|---|---|
| Engine SHA256 | `3ba15c723958161fffc28a106a5758bd3e27a6152f0e0235969594a5255cb006` **unverändert** ✅ |
| `box_end_bar = 640` / `_p11` | unberührt (§36.2/§36.3, S3) ✅ |
| V01-Bildsatz | 5× SHA256-bit-identisch, unverändert ✅ |
| V01-Protokoll | unverändert (9.784 B) ✅ |
| Git-Tree | clean; `HEAD == origin/master == d677adc` ✅ |
| Temporärdateien | Probe-PNGs, Probe-Protokoll, Hash-Skript, Backup nach Gebrauch gelöscht (§39/S10) ✅ |

`test/` bleibt gitignored — Renderer, Protokolle und PNGs sind **nicht**
versioniert; die Reproduktion erfolgt über die beiden Aufrufe im Docstring.
Die Arretierung ist damit **dokumentarisch** (diese Spez) und
**reproduzierbar** (Skript + Zahlen), nicht über Git-Objekte.

## 67.9 Status (v0.17)

| Kennzahl | Wert | Berührt durch v0.17? |
|---|---|---|
| V0 / H1 | 14 / 8 / +38,964262 R | nein |
| V1 v0.1 (arretiert) | 15 / +46,866348 R | nein |
| H2 v0.1 / H2 v0.14 | 7 / +7,902085 R · 9 / +22,285802 R | nein |
| Gesamt v0.14 | 17 / +61,250064 R | nein |
| P9-Beitrag v0.14 | +19,804922 R | nein |
| Norm-Quelle (§54.1.3 / §66.1) | `P9` + `P12_RESERVE` (4 Grenzkanten) | unverändert |
| Bildsätze | v0.1 (5 PNG) **+** v0.14 (5 PNG) | **neu: zweiter Satz arretiert** |
| Engine SHA256 | `3ba15c72…5255cb006` | nein |
| Regelbestand | §54 (v0.13) + §66 (v0.16) + §67 (v0.17) | erweitert |

v0.17 ist ein **Arretierungs-Addendum**: Es friert den V014-Bildsatz samt
Byte-Größen und SHA256 ein, weist die Bit-Identität des V01-Satzes als
Regressionsnachweis aus und protokolliert die bestätigte Vorhersage aus
§66.2. Engine, Adapterlogik und der arretierte v0.1-Satz bleiben unberührt.

**Offen (nicht Teil dieser Arretierung):** die **visuelle Abnahme** des
V014-Satzes durch den Anwender (Schritt 4). Sie kann Korrekturen an der
Darstellung nach sich ziehen; solche Korrekturen wären als
**v0.18-Amendment** auszuweisen, nicht als stille Änderung an §66/§67.


---

# Addendum v0.19 — Q29-Forensik und generische Phasenboden-Regel G4 (2026-09-10)

**Auftrag.** Erkundung und Dokumentation des Q29-Sperrmechanismus
(`quartil_distanz_pct`) und der POC-Geometrie am P9-Boden sowie Herleitung einer
**generischen** Phasenboden-Regel. **Wirkung:** reines **Dokumentations-Addendum**
— Engine, Adapter und beide arretierten Bildsätze bleiben byte-unverändert. Es
wird **kein** Produktivpfad geändert.

| Übergabe | Gegenstand | Status |
|---|---|---|
| Regelwerk | §69 (dieses Addendum) | **neu** |
| Engine | `test/tmp_kanten_engine_replay.py` | SHA256 `3ba15c72…5255cb006` **unberührt** |
| Adapter | `backtest_lab/phasen_regime_adapter.py` | SHA256 `50bd47c6…afd9b4eda` **unberührt** |
| Belegskripte | `test/_tmp_q29_audit*.py`, `test/_tmp_p9_boden_sichtung.py` | gitignored, **rein lesend** |
| Bildsätze | v0.1 (5 PNG) **+** v0.14 (5 PNG) | **unberührt** |

**Entscheide in Kurzform:** Q29 wird **nicht** umgebaut · `poc_start = 0` global
bleibt **tabu** · die Regel wird **generisch** als G4 beschrieben (kein
Hardcoding auf Bar 1002) · Anker der Bodenregel ist **zwingend Literal** · Zugang
ausschließlich über `adapter.segmente` (`AKTIVE_DEFAULT_SEGMENTE = (P9,)`) ·
**v0.18 bleibt für die visuelle Abnahme des V014-Satzes reserviert**.

## 69.0 Geltung und Abgrenzung

1. **append-only.** Dieses Addendum ergänzt; §54 (v0.13), §66 (v0.16) und §67
   (v0.17) bleiben als Zitat unverändert bestehen.
2. **Kein Eingriff.** Alle Aussagen beruhen auf **lesenden** Läufen gegen die
   arretierte Engine und den Adapter; es wurde keine Zeile Produktivlogik
   angefasst.
3. **v0.18 ist belegt.** §67.9 reserviert v0.18 ausdrücklich für die visuelle
   Abnahme des V014-Satzes. Die hier dokumentierte Materie ist davon unabhängig
   und erscheint deshalb als **v0.19 / §69**.
4. **Kein Ertragsanspruch.** Die in §69.5/§69.8 genannten Regel-Erträge sind
   **Papier-Befunde** (rein lesende Rechnung). Sie sind **nicht** Teil einer
   Baseline und **nicht** Teil des arretierten Ertrags.

## 69.1 Q29-Prädikat: Anatomie und Einseitigkeit

Fundstelle: `backtest_lab/phasen_regime_adapter.py`, **Z. 2411–2426**; die
Rückgabe steht in **Z. 2426**:

```python
return distanz <= cfg.quartil_distanz_pct
```

| Eigenschaft | Befund |
|---|---|
| Parameter | `quartil_distanz_pct = 25` |
| Prädikat | **einseitig** — geprüft wird nur die obere Schranke |
| Negative Distanz | **erlaubt** (Sweep unterhalb des Bezugsbodens sperrt nicht) |
| Bezugsrahmen | `ex_lo` / `ex_hi` der laufenden Extremspanne |
| `ex_lo` | ab Bar **673** arretiert auf **62.5480** |
| `ex_hi` | ab Bar **881** arretiert auf **70.0000** |
| `spanne` | **7.4520** (ab 881 konstant) |
| LONG-Limit | `62.5480 + 0.25 · 7.4520 = 64.4110` |
| SHORT-Limit | `70.0000 − 0.25 · 7.4520 = 68.1370` |

Die Einseitigkeit ist die **Wurzel** des in §69.5 beschriebenen Artefakts: Ein
Bar, der den Boden *nach unten* durchsticht, liegt mit **negativer** Distanz auf
der erlaubten Seite.

## 69.2 Sperrwirkung: Anzahl, Verteilung, Schutzbeitrag

| Größe | Adapterlauf | Rohlauf (V0) |
|---|---|---|
| Sperren gesamt | **57** | **56** |
| davon SHORT | 7 | 7 |
| davon LONG | 50 | 49 |
| H1-Sperren | **25** (19 L / 6 S) | – |
| H2-Sperren | **32** (31 L / 1 S) | – |

**H1-Wirkung (Q29 als Schutz):**

| Trade | R |
|---|---|
| K13@310 | −0.361175 |
| K21@378 | −1.000000 |
| K25@429 | −1.000000 |
| **Summe** | **−2.361175** |

⇒ H1 **36.603087** → **38.964262 R**. Q29 rettet in H1 also **+2.361175 R**.

**Gegenprobe (Q29 aus):**

| Bezug | Trades / R | Δ zu 15 / +46.866348 |
|---|---|---|
| Adapter | 19 / **+44.044802 R** | **−2.821546** |
| Roh | 21 / **+35.193931 R** | **−5.251211** |

Die neu hinzukommenden Trades sind **ausnahmslos Verlierer**:
`K13@310`, `K21@378`, `K25@429`, `K79@991` (−0.460371). **Entfallende** Trades:
**keine** (in beiden Bezügen). ⇒ Q29 ist **nicht** ertragsneutral, sondern
**netto ertragsstützend**; ein Abschalten ist **destruktiv** und wurde verworfen.

## 69.3 Schwellen-Sweep und Optionsraum

**Sweep über `quartil_distanz_pct` (Adapterlauf):**

| Schwelle | Trades | R | Sperren |
|---|---|---|---|
| 0 | 2 | +5.924513 | 123 |
| 10 | 9 | +45.092445 | 79 |
| **25 (IST)** | **15** | **+46.866348** | **57** |
| 50 | 18 | +44.505172 | 34 |
| 100 | 19 | +44.044802 | 0 |

Der Ist-Wert **25** liegt am **Optimum** der untersuchten Reihe; sowohl
Verschärfung als auch Lockerung sind ertragsmindernd.

**Option-B-Arme (phasen-lokaler Bezugsrahmen):**

| Arm | Trades | R |
|---|---|---|
| global (IST) | 15 | +46.866348 |
| Fenster 100 | 19 | +44.044802 |
| Fenster 250 | 16 | +45.866348 |
| ab Bar 640 | 17 | +38.024292 |
| **Phasenfenster** | 16 | **+46.405977** |

Der Phasenfenster-Arm ist der einzige, der sich dem Ist-Wert nähert; der Zusatz
besteht aus genau **`K79@991` (−0.460371)**. ⇒ Auch die phasen-lokale Variante
bleibt **unter** dem Ist-Wert. **Verworfen.**

## 69.4 Arme A0–A3: POC-Modell × Q29-Modell

| Arm | POC-Anker | Q29-Modell | Trades | R | H1 | H2 | 991 | 1002 |
|---|---|---|---|---|---|---|---|---|
| **A0 (IST)** | 0 | einseitig, global | 15 | **+46.866348** | 8/+38.964262 | 7/+7.902085 | – | – |
| A1 | 848 | einseitig, global | 13 | +41.445143 | 8/+38.964262 | 5/+2.480880 | – | – |
| A2 | 0 | zweiseitig, phasen-lokal | 16 | +46.433458 | 8/+38.964262 | 8/+7.469196 | – | – (stattdessen **K79@992 −0.43**) |
| A3 | 848 | zweiseitig, phasen-lokal | 17 | +43.927022 | 8/+38.964262 | 9/+4.962759 | – | **K77 +3.6785** |

**Befunde:**

1. **Δ A0→A3 = −2.939326 R.** Die kombinierte Modelländerung ist **destruktiv**.
2. **A1/A3 löschen das P9-Quartett.** Mit `poc_start = 848` entfallen `K73@980`
   (+2.4119) und `K73@1020` (+3.0093) — das **P9-Fenster wird leer**.
3. **H1 ist in allen vier Armen bit-identisch** (8 / +38.964262). Kein POC- oder
   Q29-Modell berührt H1.
4. **Das zweiseitige Q29 tötet 991 nur scheinbar.** Der Artefakt wandert auf
   **`K79@992` (−0.43 R)** — die Sperre ist nicht kausal beseitigt, sondern
   **verschoben**.

⇒ **Konsequenz:** weder `poc_start` global noch das Q29-Prädikat werden
angefasst. Die Bodenfrage wird **regel-lokal** gelöst (§69.8).

## 69.5 POC-Blockade am Bar 1002 (der wahre Blocker)

Der P9-Boden ist **68.4000** — deklarierter Boden der Kante **K77**, nicht
„äußerste Wand" (darunter liegen K60 67.9183 und K62 67.7260). Am Bar **1002**
sind **alle** Vorbedingungen der Bodenregel erfüllt; blockiert wird der Trade
**allein** von der POC-Ordnung.

| Größe | Wert |
|---|---|
| `basis_bei(1002)` | 68.3427 |
| `sweep` = `lo[1002]` | 68.3080 |
| `stufe` | 1 (`STUFE_1_IN_BAR`) |
| `entry_bar` | 1003 |
| `entry` = `open[1003]` | 68.5070 |
| `SL` = 68.3080 − 0.05 | **68.2580** |
| `tp2` | 69.9140 |

Geprüft wird in **Z. 2641** die Ordnung `sl < entry < poc < tp2`:

| `poc_start` | POC | Ordnung `entry > poc` | Ergebnis |
|---|---|---|---|
| **0 (IST)** | **68.3820** | **verletzt** | **kein_raum** |
| 848 | **68.9319** | OK | handelbar |
| 991 | 68.4605 | verletzt | gesperrt |

Mit eingeschränktem Bereich 68.40–69.87: `0 → 68.4368` (verletzt) ·
**`848 → 68.9513` (OK)** · `991 → 68.4613` (verletzt).

**Warum der globale POC hier versagt:** `poc_start = 0` zieht die gesamte
Historie seit Bar 0 in die Bins; das Volumen der tiefen H1-Phase drückt den POC
**unter** den Entry. Der Anker ist damit **phasenfremd**. Ein Ersatz durch 848
innerhalb der Regel ist kausal begründet (Phasenstart P9), wäre **global** aber
eine Baseline-Änderung — deshalb striktes Veto (Entscheid 3).

**Degenerierter Papier-R** bei erzwungener Ordnung (`poc_start = 0`):
**+2.574197** — die Hälfte 1 (TP1 = POC **unter** Entry) wäre −0.502 R. Dieser
Wert ist ein **Befund zur Veranschaulichung**, **kein** Ertrag und **kein**
Regelbestandteil.

## 69.6 Klärung 991 ⇄ 1002 und „57 vs. 56"

**a) 991 ⇄ 1002 koppeln im Ist-Code nicht.** Die Zyklussperre läuft über `kid`
(Z. 2379 `letzter_trade`, Z. 2596–2607); `K79` (991) und `K77` (1002) sind
**verschiedene** Kanten. Messung: **Q29 aus** *und* 991 unterdrückt ⇒ **1002
weiterhin NEIN**. Die Bars **1003–1015 haben keinen Kandidaten**. Eine
`kid`-Kopplung entsteht erst **unter** einer aktiven K77-Regel (dort Abstand
11 < `retest_zyklus_bars` 12, siehe C2).

**b) Kandidaten-/Gate-Trace 985–1015 (Q29 aus):**

| Bar | Kante | `stufe` | Gate-Ergebnis |
|---|---|---|---|
| 991 | K79 | 2 | Kandidat |
| 992 | K79 | 1 | **Zyklussperre** (Abstand 0) |
| 997, 998 | K79 | None | – |
| **1002** | **K77** | **1** | **`kein_raum` (`L-Ordnung`)** |
| 1003–1015 | – | None | – |

**c) „57 vs. 56" ist kein Widerspruch.** Am Bar **998**:
im **Rohlauf** ist `_kandidat = None` (K77 lebt ⇒ Frühausstieg, 56 Sperren);
im **Adapterlauf** nimmt Hook 1 K77 aus dem Pool, K79 wird Kandidat und Q29
sperrt (57 Sperren). **Beide Zahlen sind korrekt** — sie stammen aus
verschiedenen Läufen.

**d) H2-Sperren in P9:** 939, 950, 951, 959, 961, 962, **991**, 992, 997, 998,
**1002** — davon nur **991** und **1002** handelbare Kandidaten.

## 69.7 Kanten-Knicken: 54 von 73 Linien

**Prämisse bestätigt, mit Präzisierung:** Es gibt **keine Feinjustierungslogik**.
Das Knicken ist **rohe `np.mean`-Wirkung** an genau **zwei** Stellen:
`basis_bei` (**Z. 2118**) und `_akzeptiere` (**Z. 2201**).

| Größe | Wert |
|---|---|
| Linien gesamt | 73 (59 Edges + 14 Seeds) |
| geknickt | **54 (≈ 74 %)** |
| \|Δ\| minimal | 0.0007 (K9) |
| \|Δ\| Median | ≈ 0.024 |
| \|Δ\| maximal | **0.0758 (K67: 69.8700 → 69.9458)** |
| Stufen | bis 13 (K17), 12 (K16, K12) |

Das einzige **Einfrieren** ist der Primär-Anker (Z. 2115–2118): Er wird bei der
Promotion auf `aeus_ref` gesetzt (Z. 2248–2250) — also auf das
**Promotions**niveau, **nicht** auf das Ursprungsniveau.

Operativ relevant (|Δ| > `sl_buffer_usd` = 0.05): **K67, K80, K61, K78**.

Relevante Drifter:

| Kante | von | nach |
|---|---|---|
| K67 | 69.8700 | 69.9458 |
| K77 | 68.3920 | 68.3597 |
| K79 | 68.6320 | 68.6260 |
| K71 | 68.8700 | 68.8912 |
| K60 | 67.8970 | 67.9081 |
| K62 | 67.7260 | 67.7328 |

## 69.8 Teil 2 — Generische Phasenboden-Regel G4

**Begriff.** Der *deklarierte Phasenboden* ist der Bodenpreis der **untersten
deklarierten Bodenkante** des betrachteten Segments (hier P9, K77 → **68.4000**).
Er ist ein **Literal** (Anker-Invariante, §69.9).

**Regel (kausal, vektorisierbar, je Bar `k` des Segments):**

```
(1) lo[k]  <  deklarierter_boden_preis
(2) cl[k]  >  deklarierter_boden_preis
(3) touch_conf(bodenkante, k)  >=  3        # V-S >= 3, kausal
(4) deklarierter_boden_preis  ist LITERAL   # kein basis_bei(k)
```

Bei Erfüllung: `entry_bar = k + 1`, `entry = open[entry_bar]`,
`SL = min(lo[k:k+2]) − sl_buffer_usd` (0.05), **POC regel-lokal** (Anker =
**Phasenstart des Segments**), `TP2` = Segment-Override in der Kaskade
**`niveau_override` → `ziel_preis` → `provenienz_basis`**.

**Variantenhistorie (Papier, lesende Rechnung):**

| Variante | Zusatzbedingung | Treffer | R |
|---|---|---|---|
| G0 | roh, ohne Zusatz | 2 | +2.619774 |
| G1 | + neues Extremtief | 2 | +2.619774 |
| G2 | + „äußerste Wand" | **0** | – |
| **G4** | **+ (3) V-S ≥ 3** | **[1002]** | **+3.629016** |
| G3 (forciert) | Ordnung erzwungen, POC-Anker 0 | 1 | +2.595884 (**Ordnung verletzt**) |
| G3 (forciert) | Ordnung erzwungen, POC-Anker 848 | 1 | **+3.629016** |

**G0 ist unzulässig (C6).** Der Treffer an Bar **934** benutzt `e.basis` als
Niveau — das ist **Look-ahead** und damit kein gültiger Kandidat. G1 ändert
nichts (dasselbe Bar). G2 verlangt fälschlich die „äußerste Wand" und liefert 0
Treffer, weil K77 **deklarierter** Boden ist, nicht äußerste Wand (C4). Erst die
kausale Touch-Bestätigung **(3) V-S ≥ 3** isoliert den **einen** handelbaren Bar.

**Der Treffer (regel-konform):**

```
K77@1002  STUFE_1_IN_BAR  entry_bar 1003  entry 68.5070  SL 68.2580
          POC 68.9513 (Anker 848)  TP2 69.8700  risk 0.2490
          -> +3.629016 R  GEWONNEN  (TP1 exit 1011 / TP2 exit 1020)
```

**Kausalitätsnachweis der Touch-Bestätigung:** `touch_conf(K77)` = 1 bei 991 ·
2 bei 1000 · **3 bei 1002** — 1002 ist der **erste handelbare** Bar.

**P9-Bodenanatomie (Beleg, CSV `test/archiv/silver_m15_ohlc_2026-08-10_2026-08-28.csv`):**

| Bar | Zeit (UTC) | Low | Rolle |
|---|---|---|---|
| 881 | – | 70.0000 | P9-Hoch |
| 894 | 2026-08-21 16:30 | 68.870 | Setback (K71-Geburt) |
| 934 | 2026-08-24 03:30 | 68.392 | K77 `piv1`, Wick 1 |
| 991 | 2026-08-24 17:45 | 68.348 | K77 Keimung, Wick 2 |
| 997 | 2026-08-24 19:15 | 68.368 | – |
| 999 | 2026-08-24 19:45 | 68.318 | – |
| 1000 | 2026-08-24 20:00 | **68.288** | **echtes P9-Tief** |
| 1001 | 2026-08-24 20:15 | 68.382 | – |
| **1002** | **2026-08-24 20:30** | **68.308** | **letzter Sweep, Wick 3 (bestätigt bei 1000+2)** |

Ab Bar **1003** kein Rückfall unter 68.40 mehr (Tiefs 68.440 → 68.800).
P9-Fenster 848–1020: `min(low) = 68.2880 @ 1000`, `max(high) = 70.0000 @ 881`.

## 69.9 Anker-Invariante: Literal vs. `basis_bei(k)`

`deklarierter_boden_preis` muss ein **Literal** sein. Wird stattdessen
`basis_bei(k)` als Anker eingesetzt, kippt die Regel von einer gezielten
Bodenprüfung in eine **flächendeckende** Bedingung — der Beleg:

| Anker | Treffer | davon H1 (`< 640`) |
|---|---|---|
| **Literal 68.4000** | **2** | **0** ✅ |
| `basis_bei(k)` | **126** | **122** |

Die lockere `basis_bei(k)`-Variante verteilt Treffer über **P6 9**, **P10 17**,
**P11 24** — also über Segmente, in denen **kein** deklarierter Bodenbruch
stattfindet. Der Literal-Anker ist damit die **einzige** Fassung, die
Additivität (§69.10) erhält. **`basis_bei(k)` als Anker ist verboten.**

## 69.10 Additivitätsnachweis T1–T5

Alle Tests **rein lesend**, gegen den arretierten Stand.

| Test | Umfang | Ergebnis |
|---|---|---|
| **T1 P9** | Regel auf P9 | Kandidat **[1002]** → **+3.629016 R** ✅ |
| **T3 H1** | Regel auf H1 (`bar < 640`) | **0 Treffer** ✅ |
| **T5** | Regel auf P6/P7/P8/P10/P11 | **0 Treffer** ✅ |
| **T4 Kollision** | Entry 1003 ∩ V1_basis-Entry-Bars | **leer** ✅ |
| **T1 P12_RESERVE** | Regel auf P12 | Kandidat **[1259]** → **+2.234280 R** (siehe §69.11) |

V1_basis-Entry-Bars: `{231, 245, 384, 399, 493, 531, 565, 621, 640, 653, 681,
716, 762, 982, 1021}` — Bar **1003** ist **nicht** enthalten.

Die Additivitätsbedingung **0/0/0/0** (kein Zusatz in H1, P6, P7, P8, P10, P11)
ist erfüllt. Der einzige Zusatz liegt in **P9** — dem Segment, das ohnehin
Gegenstand der v0.14-Arbeit ist.

## 69.11 Beobachtung P12_RESERVE (inaktiv im Scope)

Der T1-Lauf wurde **testweise** auch auf **P12** (`P12_RESERVE`, Bars 1171–1272)
angewandt. Ergebnis: genau **ein** Kandidat.

```
Bar 1259  lo 67.600  <  67.6355  <  cl 67.929
          touch_conf(K82) = 3   (K82 piv1 1031, geb 1056)
          -> +2.234280 R   (regelkonform, NICHT spurious)
```

**Bewertung:** Der Kandidat ist **regelkonform** und **nicht** Artefakt — er
liegt aber **außerhalb des freigegebenen Scopes**. Der Zugang der Regel ist
zwingend an **`adapter.segmente`** gebunden (`AKTIVE_DEFAULT_SEGMENTE = (P9,)`);
`P12_RESERVE` ist damit **inert**. Die Beobachtung wird **dokumentiert**, aber
**nicht aktiviert**. Eine Aktivierung wäre ein eigener, ausdrücklich
freizugebender Schritt.

## 69.12 Korrektur-Register C1–C7

| Nr. | Korrigierte Aussage | Feststellung |
|---|---|---|
| **C1** | „991 wird durch `pivot + 2` ausgeschlossen" | Nein — ausschlaggebend ist **V-S ≥ 3** |
| **C2** | „12-Bar-`kid`-Kopplung K79/K77" | Gilt erst **unter** einer K77-Regel (Abstand 11 < 12), **nicht** im Ist-Code |
| **C3** | `k77_trade_ertrag_r = 3.6785` | Das ist nur der **A3**-Wert; regel-eigener POC = **3.629016**, globaler POC degeneriert = 2.595884 |
| **C4** | „68.4000 = äußerste Wand" | Falsch — **deklarierter** Boden (**K77**); K60 (67.9183)/K62 (67.7260) liegen darunter |
| **C5** | „Baseline gefährdet" | Nur in **A1/A3**; A0/A2 unberührt, H1 in allen Armen bit-identisch |
| **C6** | „G0-Trade bei Bar 934 ist gültig" | Nein — benutzt `e.basis`, also **Look-ahead**, unzulässig |
| **C7** | „nächstes Addendum = v0.18" | Falsch — §67.9 reserviert **v0.18** für die visuelle Abnahme; diese Materie ist **v0.19** |

Zusätzlich berichtigt gegenüber dem ersten P9-Arbeitsblock: `touch_2` gehört zu
**991** (nicht 999) · das Reclaim-Fenster war um **8 Bars** verschoben · das
P9-Tief ist Bar **1000** (nicht 999) · der SL lautet **68.2580** (nicht 68.2380)
· „50 Longs" war H1+H2, nicht H1 allein · das Phasenhoch ist **70.0000** (nicht
69.8700).

## 69.13 Integrität und Hygiene

| Prüfung | Ergebnis |
|---|---|
| Engine SHA256 | `3ba15c723958161fffc28a106a5758bd3e27a6152f0e0235969594a5255cb006` **unverändert** ✅ |
| Adapter SHA256 | `50bd47c68d4ff543f3d4314d9c771f1d39425119e1d8ac63049c0d9afd9b4eda` **unverändert** ✅ |
| `box_end_bar = 640` / `Europe/Berlin` (Z. 600) | unberührt (eingefrorene Ausnahme) ✅ |
| `poc_start` | global **0**, unverändert ✅ |
| `quartil_distanz_pct` | **25**, unverändert ✅ |
| V01-Bildsatz / V014-Bildsatz | beide **unberührt** ✅ |
| Produktivcode | **keine** Änderung ✅ |
| Belegskripte | `test/_tmp_q29_audit*.py`, `test/_tmp_p9_boden_sichtung.py` — gitignored, **rein lesend** ✅ |

## 69.14 Status (v0.19)

| Kennzahl | Wert | Berührt durch v0.19? |
|---|---|---|
| V0 / H1 | 14 / 8 / +38.964262 R | nein |
| V1 v0.1 (arretiert) | 15 / +46.866348 R | nein |
| H2 v0.1 / H2 v0.14 | 7 / +7.902085 R · 9 / +22.285802 R | nein |
| Gesamt v0.14 | 17 / +61.250064 R | nein |
| P9-Beitrag v0.14 | +19.804922 R | nein |
| `quartil_distanz_pct` / `poc_start` | 25 / 0 | unverändert |
| Bildsätze | v0.1 (5 PNG) + v0.14 (5 PNG) | unverändert |
| Engine / Adapter SHA256 | `3ba15c72…5255cb006` / `50bd47c6…afd9b4eda` | unverändert |
| Regelbestand | §54 (v0.13) + §66 (v0.16) + §67 (v0.17) + **§69 (v0.19)** | erweitert |
| Regel G4 | **dokumentiert**, nicht aktiviert | **neu** |

v0.19 ist ein **Analyse- und Regel-Addendum**. Es friert **keine** neue Baseline
ein und ändert **keinen** Produktivpfad. Es liefert (a) die vollständige
Q29-/POC-Forensik und (b) die generische Phasenboden-Regel **G4** samt
Anker-Invariante und Additivitätsnachweis. Alle Zusatzerträge sind
**Papier-Befunde**.

**Offen (unverändert):** die **visuelle Abnahme** des V014-Satzes durch den
Anwender. Etwaige Korrekturen daraus sind als **v0.18-Amendment** auszuweisen —
nicht als stille Änderung an §66/§67. §69 bleibt davon unberührt.

**Nicht freigegeben / inert:** Aktivierung der Regel G4 im Produktivpfad ·
Ausweitung auf `P12_RESERVE` (Beobachtung §69.11) · jede Änderung an
`poc_start`, `quartil_distanz_pct` oder am `Europe/Berlin`-/`box_end_bar`-Interlock.

---

# Addendum v0.18 — Abnahme des V014-Satzes, Auflagen A-1…A-5 und G4-Integrationsplan (2026-09-10)

**Auftrag.** Arretierung des **Votums** zur visuellen Abnahme des V014-Satzes
samt der daraus abgeleiteten **Auflagen A-1 … A-5** sowie Vormerkung des
**Integrationsplans für die generische Phasenboden-Regel G4** (§69.8).
**Wirkung:** **Dokumentations-Addendum.** Engine, Adapter und beide arretierten
Bildsätze bleiben **byte-unverändert**; es wird **kein** Produktivpfad geändert.
Die Umsetzung der Auflagen und der G4-Integration bleibt ausdrücklich **offen**
(§68.8).

| Übergabe | Gegenstand | Status |
|---|---|---|
| Regelwerk | §68 (dieses Addendum) | **neu** |
| Abnahmebogen | `reports/h2_phasenregime/ABNAHME_V014_2026-09-10.md` | **abgeschlossen**, committet `07d536f` |
| Engine | `test/tmp_kanten_engine_replay.py` | SHA256 `3ba15c72…5255cb006` **unberührt** |
| Adapter | `backtest_lab/phasen_regime_adapter.py` | SHA256 `50bd47c6…afd9b4eda` **unberührt** |
| Renderer | `test/tmp_png_aug_sichttest.py` | SHA256 `e88ec58d…5014521d` **unberührt** |
| Bildsätze | V01 (5 PNG) + V014 (5 PNG) + V015-Staging (5 PNG) | **unberührt** |

## 68.0 Geltung und Abgrenzung

1. **append-only.** Dieses Addendum ergänzt; §54 (v0.13), §66 (v0.16), §67
   (v0.17) und §69 (v0.19) bleiben als Zitat unverändert bestehen.
2. **v0.18 war reserviert.** §67.9 hat v0.18 ausdrücklich für die visuelle
   Abnahme des V014-Satzes freigehalten; §69.0.3 hat die Q29-/G4-Materie
   deshalb nach v0.19 ausgelagert. Mit diesem Addendum wird die Reservierung
   **eingelöst**.
3. **Kein Eingriff.** Alle Aussagen beruhen auf lesenden Läufen und auf
   Code-Inspektion; keine Zeile Produktivlogik wurde angefasst.
4. **Kein Ertragsanspruch.** Der hier referenzierte G4-Beleg ist ein
   **Nachweis der Regelmechanik** (§68.5), **kein** Baseline-Ertrag.
5. **Trennung.** Das Votum (§68.1) betrifft den **Bildsatz**; der G4-Nachweis
   (§68.5) betrifft die **Regel**. Beide sind ausdrücklich **nicht**
   gegenseitig Bedingung (Beschluss E2).

## 68.1 Votum (wörtlich, arretiert)

**Urheberschaft.** Das Votum wurde vom **Anwender** nach visueller Durchsicht
der Dateien `test/aug_sichttest_v014_01_gesamt.png` … `_05_kantenkarte.png`
erteilt und im Bogen protokolliert. Die IDE hat die Positionen **nicht** am Bild
geprüft.

| Position | Ergebnis |
|---|---|
| Vorbefüllt `☑ PB` (ohne Sichtprüfung) | **34 Positionen** = 32 Tabellenzeilen + 2 Inline (S-0 · Kreuzprobe §69) — 0.1 (6) · 0.2 (6) · B (8) · C02-5 (1) · D7/D9/D10 (3) · E (7) · G6 (1) |
| davon **derselbe** Tatbestand „H1-Panel byte-identisch" | **4 Zeilen** (S-0 · C02-5 · D10 · G6) = **1** Sachbeweis |
| Visuell geprüft | **57** = A (12) + C01 (8) + C02 (4) + C03 (7) + C04 (8) + C05 (5) + D (8) + E (3) + scharfe Einzelprüfung (1) + Kenntnisnahme A-2 (1) |
| davon OK | **53** |
| ABW Klasse 1 | **3** — A-1 (C04-7) · A-3 (C01-8) · A-4 (C03-1) |
| ABW Klasse 2 | **0** (in der visuellen Schicht) |
| ABW Klasse 3 | **0** |
| Kenntnisnahme (A-2) | **1** |

**Gesamturteil V014:** **angenommen mit Auflagen A-1 … A-5.**
**Gesamturteil V01:** **angenommen** auf Basis des G6-Bit-Nachweises
(`d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04`,
899.249 B).

**D1/D2 ist vollständig erfüllt (OK).** Der Soll-String
`K67 69.975 -> 69.870 (P9-Override) -> 69.946 *  Norm 69.9140` ist im Bild
vorhanden und deckt sich mit der Protokollzeile. Eine früher übermittelte
Vorfassung des Durchgangs ist **verworfen** (falscher Prüfpfad
`docs/artefakte/aug_p11/`; nicht existenter String `K67* (piv1 980, 100 Wicks)`;
Fehlzuordnung C02-4/C03-4/C03-6). Der Bogen führt die Verwerfung in Teil V.

## 68.2 Auflagen A-1 … A-5

| # | Auflage | Klasse | Hash-Folge |
|---|---|---|---|
| A-1 | Tick-Dichte **Panel 04** (12 Ticks über 820..1045) | 1 (Kosmetik) | neuer Satz **V015** |
| A-2 | Doppelbelegung Marker `x` (rot §32 · violett §54.2 R7) | 2 (Norm-Schärfung) | neuer Satz **V015** |
| A-3 | Überlappung der Trade-Annotationsboxen in dichten Bereichen | 1 (Kosmetik) | neuer Satz **V015** |
| A-4 | Position `P9 AKTIV` / `P12 RESERVE` am oberen Rand | 1 (Kosmetik) | neuer Satz **V015** |
| A-5 | §66.5 gilt **nicht** für Panel 02 (Byte-Identität hat Vorrang) | 2 (Norm-Schärfung) | **keine** — Spez-Klarstellung (§68.3) |

**Reihenfolge (bindend).** Dieses Addendum wird **vor** der Abarbeitung der
Auflagen arretiert (Bogen Teil VI, Beschluss 5). Die Umsetzung von A-1 … A-4
erfolgt **gebündelt** und erzeugt einen **neuen Satz V015** mit eigenem
Lebenszyklus; die Hashes in Bogen 0.1/0.2 bleiben davon unberührt (Bogen
Teil III).

## 68.3 A-5 — Klarstellung zu §66.5 (Regel-Konflikt)

**Befund.** §66.5 verlangt, die drei V014-Zusatzeinträge der Legende
(`LEG_MODUS`) in **allen** Panels zu führen. §67.4 / G6 verlangt dagegen, dass
das H1-Panel `aug_sichttest_v014_02_h1_box.png` **byte-identisch** zum
V01-Panel bleibt (`d9f35876…`, 899.249 B). Die Legende ist **Bestandteil der
gespeicherten Figur** und damit des Hashes. Beide Forderungen sind gleichzeitig
**nicht** erfüllbar.

**Beleg (Code-Inspektion).** `LEG_BASIS` = **9** Einträge, `LEG_MODUS` = **3**.
`png_02_h1_box` ruft `legend(ax1, LEG_BASIS)` (Z. 1086); die Panels 01/03/05
rufen `LEG_BASIS + [Tombstone] + LEG_MODUS` (Z. 1025 / 1168 / 1428) ⇒ **13**.
Panel 02 trägt damit **9** statt **13** Einträge.

**Entscheid.** Der **Regressionsanker hat Vorrang.** §66.5 wird wie folgt
eingeschränkt:

> **§66.5-Ausnahme (neu, v0.18).** Die Erweiterung der Legende um die drei
> V014-Zusatzeinträge gilt **NICHT für Panel 02 (H1-Box)**. Um den
> Regressionsanker `aug_sichttest_v014_02_h1_box.png` ==
> `d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04`
> (§67.4 / G6) byte-identisch zu halten, behält Panel 02 die unverkürzte
> Baseline-Legende (`LEG_BASIS`, 9 Einträge). Die übrigen Panels führen die
> Erweiterung unverändert.

**Konsequenz für die Prüflinie C02-4/D8.** Diese Positionen sind im V014-Satz
**erfüllt** (Panel 02 trägt bewusst die Baseline-Legende); sie sind **nicht**
als Mangel zu führen.

**Hinweis auf eine Reserve.** Sollte die H1-Byte-Invariante in einer künftigen
Version planmäßig aufgegeben werden, entfällt diese Ausnahme automatisch —
dann ist C02-4/D8 auf die Regelform des §66.5 zurückzuführen.

## 68.4 Stand des Abnahmebogens (Änderungen)

| Ort | Änderung |
|---|---|
| Kopf | Status `VORBEFÜLLT` → **`ABGESCHLOSSEN`**; Hinweis zur Granularität (verbindlich ist die Zusammenfassung in Teil V) |
| I.1 | Kenntnisnahme **A-2** abgehakt |
| Teil III | Auflagenkette auf **fünf** geöffnet (A-5 mit Quelltext-Beleg und Wortlaut); Zusatz zur Hash-Relevanz |
| Teil V | **Votum** ausgefüllt (53 / 3 / 0 / 0 / 1 Kenntnisnahme), Auflagenliste, G4-Abgrenzung, Begründung, Datum/Kürzel |
| Teil VI | Konsequenz für den Git-Stand (Endstand mit Votum, ein Commit) |
| Teil VIII | Status V014-Durchgang **abgeschlossen**; VIII.7-Geltung präzisiert; Restliste aktualisiert |
| VIII.7 | unverändert (Anhang, append-only) |

**Granularität.** Übermittelt wurde eine **Zusammenfassung je Block**; die
Einzelzeilen I.1–I.5 tragen weiterhin `☐ OK ☐ ABW`. Verbindlich ist die
Zusammenfassung in Teil V.

## 68.5 Nachweis der Regel G4 (§69.8) — V015-Staging

**Gegenstand.** Das Staging-Skript
`test/tmp_png_aug_sichttest_v015_g4.py` rendert den **kanonischen** Renderer
erneut mit **10** in-memory gepatchten Fragmenten (jeder Anker fail-loud
`assert count == 1`); kanonischer Code, Engine und Adapter bleiben
byte-unverändert.

| Kennzahl | V014 | **V015** | Δ |
|---|---|---|---|
| Trades | 17 | **18** | +1 |
| R gesamt | +61,250064 | **+64,879080** | +3,629016 |
| H1 | 8 / +38,964262 | 8 / +38,964262 | **0 (bit-fest)** |
| H2 (Bucket ≥ 640) | 9 / +22,285802 | **10 / +25,914818** | +1 |
| P9-Regimebeitrag | +19,804922 | **+23,433938** | +3,629016 |
| H2-LONGS (Adapter-Regime ≥ 848) | 0 | **1** | +1 |

**Abgrenzung „H2" (bindend).** „H2" im Sinne des Null-LONG-Asserts ist das
**Adapter-governed Regime ab `P9.start_bar = 848`**: **0 → 1 Long**. Der **rohe
Bucket** `entry_bar >= box_end` (640) enthält den arretierten MAKRO-Transition-
Park `[640..847]` mit **3 LONG-Trades** (K1@639 −1,0 · K3@650 −1,0 ·
K45@679 +6,480880) und lautet **3 → 4 Longs**. Beide Zählweisen sind korrekt und
werden ab v0.18 gemeinsam ausgewiesen.

**H1-Invariante.** `aug_sichttest_v015_02_h1_box.png` ist **byte-identisch** zu
`aug_sichttest_02_h1_box.png` (`d9f35876…`, 899.249 B) — assertiert im Lauf
(`h1_byte_invariante`). Der G4-Trade liegt mit `entry_bar = 1003 ≥ 848` außerhalb
jeder H1-Reichweite.

**Satz V015 (Staging, gitignored).**

| # | Datei | Bytes | SHA256 |
|---|---|---|---|
| 1 | `aug_sichttest_v015_01_gesamt.png` | 2.114.674 | `93853367f7057ac5d4d1518e5a2ef229f0f1137a8f1c270e219c1383c260d991` |
| 2 | `aug_sichttest_v015_02_h1_box.png` | 899.249 | `d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04` |
| 3 | `aug_sichttest_v015_03_h2_phasen.png` | 1.760.205 | `ca361af3721bfbcc5001f45ea1b48655c2dec3c05a75e7c562b14a186c750212` |
| 4 | `aug_sichttest_v015_04_p9_regime.png` | 1.226.458 | `4113ad2381760d0811d10ed295beb7f65ee31214d4971bd5db364505002fc032` |
| 5 | `aug_sichttest_v015_05_kantenkarte.png` | 2.124.935 | `4160d1ae76dce67ae60936dc202985404717500fed2e0c154f544118d8de8c14` |
| P | `tmp_png_aug_sichttest_v015_out.txt` | 5.366 | `47e478e51cd3727dabaad4cce6b9c49c157f09af938a4e4dcc9fdc5f62089cd7` |

**Residuen (deklariert, nicht korrigiert).** Kein Neu-Lauf — die Hashes bleiben
eingefroren; Revisionssicherheit schlägt Textkosmetik.

| # | Residuum |
|---|---|
| 1 | Protokollzeile `Neu im V014-Lauf: …` stammt aus dem kanonischen Renderer (müsste „V015" heißen); rein beschriftend. |
| 2 | `Delta V015-v0.1: +18.012733 R (Soll +18.012732)` — Rundung in der 6. Stelle (Assert-Toleranz 1e-4). |
| 3 | Protokollzeile `Quartett : … | Summe +23.433938 R` listet nur die vier Quartett-Bars (Summe +19,804922 R), weist als „Summe" aber den P9-Regimebeitrag inkl. G4 aus; die **Bild-Statistik** trennt korrekt (`QUARTETT` / `P9-REGIME-BEITRAG`). |
| 4 | **V-S-Zählung:** im Staging `stats["v_s"] = 17` bei 18 Trades (Injektion **post-return**), im Produktivlauf `18` (Einschub **vor** `stats["v_s"]`, Engine Z. 2676). Kein Fehler — Deklaration. |

## 68.6 Integrationsplan G4 (Vormerkung, **nicht** freigegeben)

Architektur: **Der Adapter autorisiert, die Engine exekutiert.** Der Adapter
bleibt engine- **und** marktdatenfrei.

**Adapter (`backtest_lab/phasen_regime_adapter.py`)**

1. **Feld** `boden_deklariert_literal: Optional[float] = None` auf
   `PhasenSegmentEintrag` — **als letztes Feld** (alle vorhergehenden haben
   Defaults; Keyword-Konstruktion der Bestandssegmente bleibt kompatibel).
   `None` = **inert**.
2. **Rückgabe-Vertrag** (vier Felder, alles andere wird im Executor aus
   `cfg`/`seg` aufgelöst — keine zweite Wahrheit):

   ```python
   @dataclass(frozen=True, slots=True)
   class BodenReclaimSpec:
       phasen_id: str
       boden_kid: int
       deklarierter_boden_literal: float
       tp2: float
   ```

3. **Hook 4:** `hook_3_boden_reclaim(self, bar_idx: int)
   -> Optional[BodenReclaimSpec]`. Kein Marktskalar, kein Fremd-Callable
   (Variante F3/1).
4. **TP2-Auflösung** über den Override:
   `self.angewandte_basis(bar_idx, seg.decke.kid, seg.ziel_preis_long)`
   → **69,8700** statt `hook_2_ziel` = 69,9140. Latenter Bestand: in P9 wurde
   nie ein LONG gehandelt, die Diskrepanz blieb unsichtbar — als Kommentar am
   Hook zu dokumentieren.
5. **Fail-Loud** `verifiziere_boden_literale()` neben
   `verifiziere_niveau_overrides()`: endlich, `> 0`,
   `< seg.decke.provenienz_basis`, Fenster nicht leer. Die Plausibilisierung
   erfolgt **nicht** über `basis_bei` (68,4000 vs. 68,3427 = +0,0837 %) — der
   Nachweis „Literal stammt nie aus `basis_bei`" ist **strukturell**
   (Code-Inspektion).
6. **Aktivierung** nur über ein **neues** Segment
   `P9_BODEN_RECLAIM` (Literal 68,4000) in `AKTIVE_SEGMENTE_V015` /
   `ADAPTER_V015`. `P9`, `P9_DIRECT_69_87`, `DEFAULT_ADAPTER` und `ADAPTER_V014`
   bleiben **unberührt (inert)**.

**Engine (`test/tmp_kanten_engine_replay.py`)**

7. **Einschubstelle:** Post-Loop, **vor** `stats["v_s"] = len(setups)`
   (Z. 2676) → der G4-Trade zählt in `v_s` (**17 → 18**).
8. **Fenster:** `range(seg.start_bar, seg.end_bar + 1)` — **nicht** `range(n)`;
   operative Form von „Zugang nur über `adapter.segmente`". H1 ist damit
   **strukturell** unerreichbar.
9. **Dedup:** `getradete_entry_bars` (Z. 2380) **wiederverwenden**.
10. **Regel-Primitive:** `touch_conf(k)` aus der Engine-Kante (Bedingung 3);
    `berechne_kausalen_histogramm_poc` mit Anker `seg.start_bar` und Band
    `[boden_literal, tp2]`; `_c_loese_trade` für die Auflösung.
11. **SL-Fenster** ist die **deklarierte** Regel `min(lo[k:k+2]) −
    cfg.sl_buffer_usd` — **nicht** das Idiom `lo[k:reclaim_bar+1]` (zufällig
    identisch 68,2580, aber nicht dasselbe).
12. **`entry_bar = bar_idx + 1`** (Stufe 1) wird abgeleitet, nicht übergeben.
13. **Neuer SHA = neue Arretierung.** Die Engine-Revision ist mit **eigenem**
    Reproduktionsnachweis zu arretieren; die Tabellen auf `3ba15c72…` bleiben
    für v0.13–v0.19 historisch gültig und werden **nicht** überschrieben.

**Verworfene Artefakte.** `PhasenAdapterHookErweiterung` und
`PhasenBodenAuditStatus`: **ersatzlos gestrichen.** `Final` ist im
`@dataclass`-Rumpf kein Konstantenmarker (Instanzfeld); die Dokumentation
gehört in den Modul-Docstring (wie Hook 1/2).

## 68.7 Integrität und Hygiene

| Prüfung | Ergebnis |
|---|---|
| Engine SHA256 | `3ba15c723958161fffc28a106a5758bd3e27a6152f0e0235969594a5255cb006` **unverändert** ✅ |
| Adapter SHA256 | `50bd47c68d4ff543f3d4314d9c771f1d39425119e1d8ac63049c0d9afd9b4eda` **unverändert** ✅ |
| Renderer SHA256 | `e88ec58d79232eff1d0634a938ec67fd627b500643775f707365e97a5014521d` **unverändert** ✅ |
| `box_end_bar = 640` / `Europe/Berlin` (Z. 600) | unberührt (eingefrorene Ausnahme) ✅ |
| V01- / V014-Bildsatz | beide **byte-identisch** (vor == nach dem V015-Lauf geprüft) ✅ |
| H1-Panel | in V01, V014 **und** V015 identisch `d9f35876…` / 899.249 B ✅ |
| Produktivcode | **keine** Änderung ✅ |
| V015-Lauf | `EXIT 0`; nur neue Dateien mit Präfix `aug_sichttest_v015_` erzeugt ✅ |

## 68.8 Status (v0.18)

| Kennzahl | Wert | Berührt durch v0.18? |
|---|---|---|
| V0 / H1 | 14 / 8 / +38,964262 R | nein |
| V1 v0.1 (arretiert) | 15 / +46,866348 R | nein |
| H2 v0.1 / H2 v0.14 | 7 / +7,902085 R · 9 / +22,285802 R | nein |
| Gesamt v0.14 | 17 / +61,250064 R | nein |
| P9-Beitrag v0.14 | +19,804922 R | nein |
| V015-Staging (Regel-Beleg) | 18 / +64,879080 R | **neu, nicht Baseline** |
| Bildsätze | V01 (5) + V014 (5) + V015-Staging (5) | V015-Staging **dokumentiert** |
| Engine / Adapter / Renderer SHA256 | `3ba15c72…` / `50bd47c6…` / `e88ec58d…` | unverändert |
| Regelbestand | §54 (v0.13) + §66 (v0.16) + §67 (v0.17) + **§68 (v0.18)** + §69 (v0.19) | erweitert |
| Auflagen | A-1 · A-2 · A-3 · A-4 · **A-5** | **neu**, Umsetzung **offen** |
| Regel G4 im Produktivpfad | **nicht aktiviert** | unverändert inert |

v0.18 ist ein **Abnahme- und Planungs-Addendum**. Es friert das **Votum** und
die **Auflagenkette** ein und formuliert die §66.5-Ausnahme (§68.3). Es ändert
**keinen** Produktivpfad und **keine** Baseline.

**Nicht freigegeben / inert:** Umsetzung der Auflagen A-1 … A-4 vor der
v0.18-Arretierung · Aktivierung der Regel G4 im Produktivpfad (§68.6 ist
**Planung**, nicht Freigabe) · Ausweitung auf `P12_RESERVE` ·
jede Änderung an `poc_start`, `quartil_distanz_pct` oder am
`Europe/Berlin`-/`box_end_bar`-Interlock.
---

# Addendum v0.20 — Invariante-1-Präzisierung, Errata zu §68.6 und native G4-Integration (Route A) (2026-09-10)

**Auftrag.** Überführung der generischen Phasenboden-Regel **G4** (§69.8) aus
der Planung (§68.6) in den Produktivpfad: Adapter erweitert, Engine um den
guard-geschützten Hook-3-Konsum erweitert, Renderer um den persistenten Modus
`V015`. **Wirkung:** Code- und Dokumentations-Addendum. Die arretierten
Bildsätze V01 und V014 bleiben **byte-unverändert** (nachgewiesen, §70.6).

| Übergabe | Gegenstand | Status |
|---|---|---|
| Adapter | `backtest_lab/phasen_regime_adapter.py` | **erweitert**, `0f3f8765…` |
| Engine | `test/tmp_kanten_engine_replay.py` | **erweitert**, `ea2f72a8…` (gitignored) |
| Renderer | `test/tmp_png_aug_sichttest.py` | **erweitert**, `c730b287…` (gitignored) |
| Bildsätze | V01 (5) + V014 (5) | **byte-identisch** (Regressionsschutz) |
| Bildsatz | V015 (5) | **neu, native Engine-Rechnung** |
| Regelbestand | §54 + §66 + §67 + §68 + §69 + **§70** | erweitert |

## 70.0 Geltung und Abgrenzung

1. **append-only.** §54 (v0.13), §66 (v0.16), §67 (v0.17), §68 (v0.18) und
   §69 (v0.19) bleiben als Zitat unverändert bestehen.
2. **Einlösung.** §70 löst die Vormerkung des §68.6 ein. Der dort als
   „**nicht** freigegeben" geführte Integrationsplan ist damit ausgeführt.
3. **Route A.** Die Exekution liegt **engine-nativ** — nicht in einem
   Renderer-AST-Patch. Der Adapter **autorisiert**, die Engine **exekutiert**.
4. **Inertheit by default.** `P9`, `P9_DIRECT_69_87`, `DEFAULT_ADAPTER` und
   `ADAPTER_V014` bleiben unverändert; der neue Modus ist ausschließlich über
   `P9_BODEN_RECLAIM` / `AKTIVE_SEGMENTE_V015` / `ADAPTER_V015` erreichbar.

## 70.1 Errata zu §68.6 (redaktionell — der Code ist maßgeblich)

| # | §68.6-Stelle | Fehler | Korrektur |
|---|---|---|---|
| **E-1** | P7: „Post-Loop, **vor** `stats["v_s"] = len(setups)` (Z. 2676)" | Off-by-one | `stats["v_s"]` steht in **Z. 2677**; Z. 2676 ist `stats["promotionen"] = …`. Der Einschub ist **zwischen** beiden zulässig. |
| **E-2** | P1: „**als letztes Feld** (alle vorhergehenden haben Defaults)" | Begründung sachlich falsch | **7 von 9** Feldern sind defaultlos. Korrekte Begründung: **alle** `PhasenSegmentEintrag`-Instanzen (Produktiv und Test) sind **Keyword**-Konstruktionen; kein `fields()`/`asdict()`-Reflexionszugriff im Repo. Die Handlung (Feld am Ende) bleibt richtig. |
| **E-3** | P3: „`hook_3_boden_reclaim(self, bar_idx)`" | Vertrag unvollständig | Der Hook autorisiert **fensterbasiert** (`start_bar <= k <= end_bar` → `BodenReclaimSpec`). Die **Marktbedingungen** `lo[k] < literal < cl[k]` und `touch_conf(boden, k) >= 3` prüft die **Engine**. |
| **E-4** | P7/P13: „neuer SHA = neue Arretierung" | unpräzise | `test/` ist **gitignored** (`.gitignore:63`). Die Arretierung ist **urkundlich** (SHA256 im Dokument + Protokoll), nicht git-objektbasiert. |

## 70.2 Präzisierung Invariante 1 (Adapter-Docstring)

> **Invariante 1 (v0.20).** Die Engine-Datei ist bis v0.19 unverändert
> geblieben. Ab v0.20 wird sie **ausschließlich** um den duck-typisierten,
> guard-geschützten Konsum von `hook_3_boden_reclaim` erweitert
> (`globals().get("_hook")`; **zweistufig inert**). Jede weitere Änderung an
> der Engine bleibt unzulässig. Der historische SHA
> `3ba15c723958161fffc28a106a5758bd3e27a6152f0e0235969594a5255cb006` gilt für
> **v0.13–v0.19**.

**Zweistufige Inertheit (bindend).** Stufe (a): keine gebundene
`hook_3_boden_reclaim` → Block übersprungen. Stufe (b):
`boden_deklariert_literal is None` → Segment übersprungen. Nur so bleiben der
V0-Referenzlauf (`ORIG`, ohne `_hook`) und alle Bestandsadapter auf Baseline.

## 70.3 Adapter v0.20

| Kennzahl | Wert |
|---|---|
| SHA256 | `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` |
| Umfang | 25.783 B (Vorstand 19.496 B, `+139 / −4` Zeilen) |
| Vorstand | `50bd47c68d4ff543f3d4314d9c771f1d39425119e1d8ac63049c0d9afd9b4eda` |

**Neu:**
1. Feld `boden_deklariert_literal: Optional[float] = None` auf
   `PhasenSegmentEintrag` (**letztes Feld**, kollisionsfrei).
2. `BodenReclaimSpec` (`frozen=True, slots=True`) — **vier** Felder:
   `phasen_id`, `boden_kid`, `deklarierter_boden_literal`, `tp2`.
3. `hook_3_boden_reclaim(bar_idx: int) -> Optional[BodenReclaimSpec]`.
   TP2 über `angewandte_basis(bar_idx, seg.decke.kid, seg.ziel_preis_long)`
   → **69.8700** (nicht `hook_2_ziel` = 69.9140).
4. `verifiziere_boden_literale()` — fail-loud: endlich, `> 0`, **strikt unter**
   `seg.decke.provenienz_basis`, Fenster nicht leer.
5. `P9_BODEN_LITERAL = 68.4000`, `P9_BODEN_RECLAIM`, `AKTIVE_SEGMENTE_V015`,
   `ADAPTER_V015` (mit erzwungenem `verifiziere_niveau_overrides()` **und**
   `verifiziere_boden_literale()`).

**Fenstervertrag (E-3).** `hook_3_boden_reclaim` liefert für jedes `k` in
`[848, 1020]` einen Spec; `847`, `1021`, `0`, `1287` → `None`.

## 70.4 Engine v0.20 (Route A)

| Kennzahl | Wert |
|---|---|
| SHA256 neu | `ea2f72a8de81d632909da72d79b158b0760e6dfc05c6c9047559a4fbf7d437a5` |
| Umfang | 196.012 B (Vorstand 191.814 B, `+4.198 B`) |
| SHA256 historisch | `3ba15c72…5255cb006` (gültig v0.13–v0.19) |
| Zeilenenden | CRLF (4.572), stilgerecht erhalten |

**Einschubstelle.** Post-Loop, unmittelbar nach `setups.append(setup)` und
**vor** `stats["promotionen"]` / `stats["v_s"]` (Z. 2677, Erratum E-1). Der
G4-Trade zählt dadurch in `v_s` (**17 → 18**).

| # | Regelbestandteil | Umsetzung |
|---|---|---|
| 1 | Zugang | `globals().get("_hook")` + `getattr(..., "hook_3_boden_reclaim", None)` |
| 2 | Fenster | `for _seg_g4 in _hk.segmente:` → `range(start_bar, end_bar + 1)` |
| 3 | Bedingung (1)+(2) | `lo[k] < literal < cl[k]` |
| 4 | Autorisierung | `_spec_g4 = _bspec_g4(k)`; `None` → `continue` |
| 5 | Bedingung (3) | `touch_conf(boden_kid, k) >= cfg.min_touches_handelbar` (3) |
| 6 | Dedup | `getradete_entry_bars` (Z. 2380) wiederverwendet |
| 7 | Entry | `entry_bar = k + 1`, `entry = open[entry_bar]` |
| 8 | SL | `min(lo[k:k+2]) − cfg.sl_buffer_usd` (**nicht** `lo[k:reclaim+1]`) |
| 9 | POC | regel-lokal, Anker = **Phasenstart** (848), Band `[literal, tp2]` |
| 10 | Auflösung | `_c_loese_trade(..., tp1=poc, tp2=spec.tp2, cfg.tp1_anteil_pct)` |
| 11 | `reclaim_bar` | `= entry_bar` (Stufe-1-In-Bar; byte-reproduzierend zu §68.5) |
| 12 | Binding | `ist_prim_anker=False`; **kein** neuer `stats`-Key |

**Kein Markt-Skalar über die Grenze.** Der Adapter bleibt engine- und
marktdatenfrei; die Engine liest das Literal aus dem **Spec**, nicht aus dem
Segment (Assert `|spec.literal − seg.literal| < 1e-12`).

## 70.5 Renderer-Modus `V015` (persistent)

| Kennzahl | Wert |
|---|---|
| SHA256 | `c730b2875cc4695b139f5d49e5179306f19d160cf9b862822e16f9c005b6a632` |
| Umfang | 73.845 B (Vorstand 68.813 B, `+5.032 B`), 21 Patch-Anker (`count == 1`) |
| Vorstand | `e88ec58d79232eff1d0634a938ec67fd627b500643775f707365e97a5014521d` |

* `AdapterMode = Literal["V01", "V014", "V015"]`; CLI **`--mode V015`**.
* Neues Feld **`g4_aktiv: bool`** (konsistent zu `k67_override_aktiv`); in V01
  und V014 explizit `False` → Bestandsverhalten unverändert.
* `KONFIGURATION_V015` mit Praefix `aug_sichttest_v015_` (**Übernahme**, §70.7).
* G4-Kennzeichnung: Ring (`ms 17.5`, `mfc="none"`, `C_CHG`) + Text
  `G4 RECLAIM` am **engine-berechneten** Trade; Legendeneintrag in `LEG_MODUS`.
* **Panel 02 führt `LEG_MODUS` nicht** (Z. 1086) und enthält keinen G4-Trade
  (`entry_bar = 1003`) → H1-Byte-Invariante **strukturell** gesichert.

## 70.6 4-Stufen-Nachweis (ausgeführt 2026-09-10)

| Stufe | Prüfung | Ergebnis |
|---|---|---|
| **1** | `py_compile` Adapter + Engine + Renderer | **OK** |
| **2** | Standalone-Inertheit | 14 → **14** (`ADAPTER_V014`) → **15** (`ADAPTER_V015`); G4 `+3.629016 R` |
| **3** | Renderer V01 / V014 | **10 / 10 PNG byte-identisch** |
| **4** | Renderer nativ `--mode V015` | **18 Trades / +64.879080 R**; H1 bit-fest |

**G4-Treffer (regel-konform, unverändert §69.8):**

```
K77@1002  LONG  entry_bar 1003  entry 68.5070  SL 68.2580
          POC 68.9513 (Anker 848)  TP2 69.8700  risk 0.2490
          -> +3.629016 R  GEWONNEN  (TP1 exit 1011 / TP2 exit 1020)
```

**Additivität.** `NEU = [(903,67), (980,67), (981,73), (1002,77), (1020,67)]`,
`REFERENZ = [(980,73), (1020,73)]` unverändert; H1 `8 / +38.964262 R`
**bit-fest**.

## 70.7 Satz V015 und Ablösung des Stagings

**Der native Lauf löst das §68.5-Staging ab.** Das Staging-Skript
(`test/tmp_png_aug_sichttest_v015_g4.py`, `2c9ec39c…`) bleibt als **historisches
Einweg-Artefakt** archiviert; es führte den Trade **extern injiziert** ein.
Ab v0.20 rechnet die **kanonische Engine** nativ.

| # | Datei | Bytes | SHA256 |
|---|---|---|---|
| 1 | `aug_sichttest_v015_01_gesamt.png` | 2.104.231 | `1b219fca0f927cf3bc1888b10ea90e9b846bef81bae76aa7a3c3d5f6992221ff` |
| 2 | `aug_sichttest_v015_02_h1_box.png` | 899.249 | `d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04` |
| 3 | `aug_sichttest_v015_03_h2_phasen.png` | 1.752.577 | `93600b60312e4a3ef37466322ec2ceee1ed1833769b30aba69684c886edc519f` |
| 4 | `aug_sichttest_v015_04_p9_regime.png` | 1.228.012 | `ffb6fc70e293875aefe3acdfae585fd564df07cfa117afea69a2d706f77f7670` |
| 5 | `aug_sichttest_v015_05_kantenkarte.png` | 2.113.754 | `b1e744cd1b40fff642db83f70d884d843991ce33a073075da0cb3964fa4b18ac` |
| P | `tmp_png_aug_sichttest_v015_out.txt` | 5.507 | `b7c4142a1a06f2d4aaafb381acad505ad54d0c6336a15a880e17d7bc08c02835` |

**Abgelöste Staging-Hashes (§68.5, historisch):** `93853367…`, `d9f35876…`,
`ca361af3…`, `4113ad23…`, `4160d1ae…` — Panel 02 stimmt weiterhin überein
(`d9f35876…`), die übrigen vier sind **durch die native Rechnung ersetzt**.

**Protokoll-Kopf (nativ):**

```
AUG-SICHTTEST -- PNG-SATZ (Modus V015, Adapter v0.15 G4)
  V1_aktiv (V015) : 18 Trades / +64.879080 R  (H1 8/+38.964262 | H2 10/+25.914818)
  Quartett       : ... | QUARTETT +19.804922 R
  G4-PHASENBODEN (§69.8): K77@1002 entry 68.5070 sl 68.2580 tp2 69.8700 | R +3.629016 | literaler Boden 68.4000 | LONG
```

## 70.8 Residuen des §68.5-Stagings — aufgelöst

| # | Residuum (§68.5) | Auflösung v0.20 |
|---|---|---|
| 1 | Logzeile `Neu im **V014**-Lauf` | modusabhängig: `Neu im {KONF.mode}-Lauf` |
| 2 | `Delta V015-v0.1: +18.012733 (Soll +18.012732)` | Soll im Modus V015 auf `18.012732` geführt |
| 3 | `Quartett … \| Summe +23.433938` (falsche Summe) | **`QUARTETT_R`** eingeführt; drei Stellen getrennt: `QUARTETT +19.804922 R` neben `G4-PHASENBODEN … +3.629016 R` |
| 4 | `V-S` 17 (Staging) vs. 18 (Produktiv) | entfällt — Einschub **vor** `stats["v_s"]` (Z. 2677) |

## 70.9 Auflagen A-1 … A-4 (unverändert offen)

Die kosmetischen Auflagen aus §68.2 bleiben **zurückgestellt** (Mentor-Vorgabe:
keine Kosmetik vor der Kernlogik). A-5 ist mit §68.3 abschließend geregelt.

| # | Auflage | Status |
|---|---|---|
| A-1 | Tick-Dichte Panel 04 | offen |
| A-2 | Doppelbelegung Marker `x` | offen (Klasse 2) |
| A-3 | Überlappung Trade-Annotationsboxen | offen |
| A-4 | Position `P9 AKTIV` / `P12 RESERVE` | offen |

## 70.10 Integrität und Hygiene

| Prüfung | Ergebnis |
|---|---|
| Adapter SHA256 | `0f3f8765…ec2b01b` · 25.783 B |
| Engine SHA256 | `ea2f72a8…fd437a5` · 196.012 B (gitignored, urkundlich) |
| Renderer SHA256 | `c730b287…b6a632` · 73.845 B (gitignored, urkundlich) |
| V01-Bildsatz | 5 / 5 **byte-identisch** zu v0.13 ✅ |
| V014-Bildsatz | 5 / 5 **byte-identisch** zu v0.17 ✅ |
| H1-Panel | `d9f35876…` / 899.249 B in **allen drei** Familien ✅ |
| `box_end_bar = 640` / `Europe/Berlin` (Z. 600) | unberührt (eingefrorene Ausnahme) ✅ |
| `poc_start`, `quartil_distanz_pct` | unverändert ✅ |

## 70.11 Status (v0.20)

| Kennzahl | Wert | Berührt durch v0.20? |
|---|---|---|
| V0 / H1 | 14 / 8 / +38,964262 R | nein |
| V1 v0.1 (arretiert) | 15 / +46,866348 R | nein |
| H2 v0.1 / H2 v0.14 | 7 / +7,902085 R · 9 / +22,285802 R | nein |
| Gesamt v0.14 | 17 / +61,250064 R | nein |
| P9-Beitrag v0.14 | +19,804922 R | nein |
| **V015 (nativ, Route A)** | **18 / +64,879080 R** | **neu: Baseline v0.20** |
| H1 v0.20 | 8 / +38,964262 R | **bit-fest** |
| H2 v0.20 | 10 / +25,914818 R | neu |
| P9-Beitrag v0.20 | +23,433938 R | neu |
| Regelbestand | §54 + §66 + §67 + §68 + §69 + **§70** | erweitert |
| Auflagen | A-1 · A-2 · A-3 · A-4 | **offen** |

v0.20 ist ein **Integrations-Addendum**. Es hebt G4 in den Produktivpfad und
führt mit V015 die **neue Baseline** (18 Trades / +64,879080 R). Die
v0.1-/v0.14-Benchmarks bleiben als historische Referenz gültig.

**Nicht freigegeben / inert:** Umsetzung der Auflagen A-1 … A-4 ·
Ausweitung auf `P12_RESERVE` (§69.11) · jede Änderung an `poc_start`,
`quartil_distanz_pct` oder am `Europe/Berlin`-/`box_end_bar`-Interlock ·
weitere Engine-Eingriffe über den Hook-3-Konsum hinaus.

---

# Addendum v0.21 — Auflagenbereinigung A-1..A-4, V016-Arretierung und Errata (2026-09-10)

**Auftrag.** Finale Bereinigung der Auflagen A-1 bis A-4 aus der V014-Abnahme
im Renderer, Trennung der Lebenszyklen ueber den Praefix `v016` und das neue
Feld `auflagen_aktiv`, Konservierung der Panel-02-Invarianz sowie
Dokumentation des V014-P03-Befunds.

| Uebergabe | Gegenstand | Status |
|---|---|---|
| Renderer | `test/tmp_png_aug_sichttest.py` | **erweitert**, `ca0db364…` (gitignored) |
| Bildsatz | V016 (5 PNG + Protokoll) | **neu, sichtgeprueft (Votum OK)** |
| Altsaetze | V01, V014, V015 | **modus-gated konserviert** (siehe E-5 / E-12) |
| Handoff | `test/SESSION_HANDOFF.md` | **append** (Wiederaufnahme + V016-Arretierung) |
| Regelbestand | §54 + §66 + §67 + §68 + §69 + §70 + **§71** | erweitert |

## 71.0 Geltung und Abgrenzung

1. **append-only.** §54, §66, §67, §68, §69 und §70 bleiben als Zitat bestehen.
2. **Drei Lebenszyklen.** `V015` bleibt der arretierte Nachweis der **reinen**
   G4-Mechanik (§70.7). `V016` ist der auflagenbereinigte Produktionssatz.
   `V01`/`V014` bleiben als historische Benchmarks gueltig.
3. **Neuer Diskriminator.** Die Auflagen wirken ausschliesslich bei
   `KONF.auflagen_aktiv is True` (**nicht** bei `KONF.g4_aktiv`). Ohne diese
   Trennung waere `--mode V015` nach dem Patch nicht mehr reproduzierbar
   gewesen — Erratum **E-11** (Blocker, vor der Ausfuehrung erkannt).

## 71.1 Auflagenbereinigung (V016)

| Auflage | Pruefpunkt | Umsetzung in V016 |
|---|---|---|
| **A-1** | C04-7 | X-Achse Panel 04: **8 Ticks im 25er-Raster** (`range(850, 1050, 25)`). Signatur `time_axis(..., ticks: Union[int, Sequence[int]])` rueckwaertskompatibel — ein `int` liefert unveraendert `np.linspace`. |
| **A-2** | A11 / §11 | Der **rote** Sweep-Sperren-Marker wandert auf den Diamond (`"d"`; `ms=7.5` in P01/P05, `ms=8.5` in P03/P04). Der **violette** Q29-Marker bleibt `"x"` (§54.2 R7). |
| **A-3** | C01-8 | Entzerrung des K67-Clusters ueber die Offset-Tabelle `ANNOT_OFFSET`: `(1020, 67): (0, -18)`, `(980, 67): (0, 22)`. Bars `< 640` verbleiben in der Bestandsformel. |
| **A-4** | C03-1 | Zonenlabels (`P9 AKTIV` / `P12 RESERVE`) via Axes-Fraction `y = 0.92` (`get_xaxis_transform`). Der P04-Text `P9 AKTIV 848-1020` wird nach `(0.82, 0.94)` (`transAxes`) entzerrt. |

**Neufassung des Pruefpunkts C04-7.** Der V014-Bogen fuehrt C04-7 als „12 Ticks
ueber 820..1045". Fuer den V016-Satz ist er zu lesen als: **8 Ticks im
25er-Raster (850, 875, …, 1025) mit Bar-Zeit-Labels.** Die uebrigen
C04-Pruefpunkte bleiben unveraendert gueltig.

**Bewusst unveraendert.** `Luecke BLOCKIERT` (Panel 04) bleibt auf seinem
Bestandsplatz (Beschluss E10); das `G4 RECLAIM`-Label und die
Override-Annotationsboxen bleiben im Default (Beschluss E9, Nachjustierung
erst nach Sichturteil).

## 71.2 Panel-02-Invarianz (H1-Anker)

Zur Wahrung des kryptografischen H1-Regressionsankers
(`d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04`,
899.249 B) gilt fuer **Panel 02** eine dokumentierte Ausnahme — analog zur
Ausnahme A-5 aus §66.5. Der Handlungstraeger ist die **unveraenderte** Liste
`LEG_BASIS`; ein zusaetzliches Symbol `LEG_BASIS_P02` wurde **nicht**
eingefuehrt:

* Panel 02 ruft weiterhin `legend(ax1, LEG_BASIS)` auf (Z. 1270) und zeichnet
  den roten Marker mit dem **Literal** `"x"` und `ms=8` (Z. 1249).
* `LEG_BASIS` selbst wurde **nicht** angetastet. Der bereinigte
  Sweep-Legendeneintrag entsteht ausschliesslich in der neuen Hilfsfunktion
  `_leg_basis_sweep()`, die nur Panels 01, 03 und 05 verwenden.
* Folge: der Anker ist in **V01, V014, V015 und V016** byte-identisch.

## 71.3 Errata

**E-5 (Praezisierung der Altsatz-Garantie, §68.6).** §68.6 fuehrt A-1 … A-4 als
hash-relevant und haelt fest, „die Hashes in Teil 0.1 bleiben davon
unberuehrt". Praezise gilt: alle vier Auflagen sind **modus-gated** auf
`auflagen_aktiv`. `V01` bleibt daher **5/5 byte-identisch**; der arretierte
`V015`-Satz (§70.7) bleibt **5/5 byte-identisch**. `V014` bleibt es fuer
P01/P02/P04/P05 — **nicht** fuer P03 (siehe E-12).

**E-11 (Auflagen-Diskriminator, Blocker).** Ein Gate auf `KONF.g4_aktiv` haette
`V015` mitveraendert und die in §70.7 arretierten Hashes entwertet. Deshalb
wurde das eigene Feld `auflagen_aktiv` eingefuehrt:
`V01 False · V014 False · V015 False · V016 True`.

**E-12 (V014 Panel 03 — ueberholt §70.6 Stufe 3 und §70.10).** Die in v0.20
eingefuehrte Trennung von `QUARTETT_R` (+19,804922 R) und `P9_BEITRAG`
(+23,433938 R) in der Statistikzeile `_p9z` wurde **innerhalb** des Zweigs
`if KONF.k67_override_aktiv:` und damit **nicht** auf den G4-Modus gegatet.
Sie veraenderte daher **unbeabsichtigt** auch `V014` Panel 03. Die Aussage
„V014 5/5 byte-identisch" ist damit fuer **P03 unzutreffend**.

| Rendererstand | V014 P03 | Bytes |
|---|---|---|
| vor dem v015-Patch (`e88ec58d…`) | `a055b243463460e8…` | 1.695.409 |
| ab v0.20 (`c730b287…`, `ca0db364…`) | `f8505d124c3dddf3…` | 1.694.382 |

`a055b243…` ist damit gueltig fuer **v0.17–v0.19** und ab **v0.20 ueberholt**.
Der aktuelle Stand reproduziert ihn nicht mehr; ein Wiederherstellen waere
eine eigene Neu-Arretierung und ist **nicht** erfolgt. Die uebrigen vier
V014-Panels sind unveraendert.

## 71.4 Ausfuehrungsbefunde (Lehren aus der Gegenprobe)

Die 3-fach-Gegenprobe (V01/V014/V015 gegen den Vorstand `c730b287…`) hat zwei
Fehler im ersten Patchlauf gefangen, die reine Code-Inspektion **nicht**
gezeigt haette:

| # | Befund | Ursache | Behebung |
|---|---|---|---|
| **B-1** | `V016` Panel 02 wurde `899.798 B` statt `899.249 B` — H1-Anker gebrochen | Der Patch ersetzte den Sweep-Eintrag **in `LEG_BASIS` selbst** | `LEG_BASIS` unangetastet; bereinigter Eintrag nur in `_leg_basis_sweep()` (E2 / §71.2) |
| **B-2** | `V01`/`V014` P03/P04 veraendert | `ms=8` der Panels 03/04 wurde auf `SWEEP_MARKER_MS` (7.0) abgebildet | eigene Konstante `SWEEP_MARKER_MS_GROSS` (8.0; V016: 8.5) |

**Lehre.** Panel-lokale Marker-Groessen brauchen eigene Konstanten, und die
H1-Ausnahme muss die eingefrorene Liste **unberuehrt** lassen. Beides ist
durch die Gegenprobe belegt, nicht durch Theorie.

**Neutralitaetsnachweis.** Vorstand `c730b287…` und gepatchter Stand
`ca0db364…` erzeugen in V01, V014 und V015 **15/15 byte-identische** PNGs
(5 Panels × 3 Modi). Der V015-Satz (§70.7) bleibt damit vollstaendig gueltig.

## 71.5 V016-Artefakte und Benchmark-Arretierung

Sichtpruefung durch den Anwender am 2026-09-10 abgeschlossen — **Votum OK**.

**Benchmark V016:** **18 Trades / +64,879080 R**
(H1 8 / +38,964262 R · H2 10 / +25,914818 R · P9-Beitrag +23,433938 R ·
Quartett +19,804922 R · G4 K77@1002 +3,629016 R).

| # | Datei | Bytes | SHA256 |
|---|---|---|---|
| 1 | `test/aug_sichttest_v016_01_gesamt.png` | 2.117.515 | `1ac695a40ed0241f0db135e6c1dd8f303b32a17ab4c42d6b5193ed7abf25ac10` |
| 2 | `test/aug_sichttest_v016_02_h1_box.png` | 899.249 | `d9f35876442593c529083f194ab50cc37e7691a65794dfe6456a311c1b7cbb04` |
| 3 | `test/aug_sichttest_v016_03_h2_phasen.png` | 1.760.655 | `81cae5e376cd9d7dd76597b3a941c3d1bd2358fadb258eb734dca85f7df11b72` |
| 4 | `test/aug_sichttest_v016_04_p9_regime.png` | 1.210.084 | `b18e2a55d83368d0436a2fa00357ce3aa69a93ee8326641dfbd555828a6edccc` |
| 5 | `test/aug_sichttest_v016_05_kantenkarte.png` | 2.122.100 | `00d56362423941f9d794d837313052d24d8a94fcd517b9b529de0dc7cb299b9f` |
| P | `test/tmp_png_aug_sichttest_v016_out.txt` | 5.520 | `2969723c6abb9b8f97512a84d15ff3e95fecb91398cdc72b4195c98b113578d7` |

**Renderer:** `test/tmp_png_aug_sichttest.py` =
`ca0db364f6955c29c103e10e16935428115cc47c8a937c86df2d6431791cd3e3`,
79.314 B (Vorstand `c730b287…`, 73.845 B; 28 wirksame Patches, davon `A-16`
als bewusster No-op).

**Unberuehrt:** Adapter `0f3f8765…`, Engine `ea2f72a8…`. Die Auflagen sind
rein rendererseitig.

## 71.6 Integritaet

| Pruefung | Ergebnis |
|---|---|
| H1-Anker `d9f35876…` / 899.249 B | **in V01, V014, V015 und V016** ✅ |
| V01-Bildsatz vs. `c730b287…` | **5/5 identisch** ✅ |
| V014-Bildsatz vs. `c730b287…` | **5/5 identisch** (P03-Historie siehe E-12) ✅ |
| V015-Bildsatz vs. §70.7 | **5/5 identisch** ✅ |
| `py_compile` Renderer | OK ✅ |
| Engine / Adapter | unveraendert ✅ |

## 71.7 Status und offene Punkte

| Kennzahl | Wert |
|---|---|
| V0 / H1 | 14 / 8 / +38,964262 R (unveraendert) |
| V015 (arretiert, §70.7) | 18 / +64,879080 R |
| **V016 (sichtgeprueft)** | **18 / +64,879080 R** |
| Regelbestand | §54 + §66 + §67 + §68 + §69 + §70 + **§71** |
| Auflagen A-1 … A-4 | **abgeschlossen** (V016) |

**Offen:**

1. **`SWEEP_MARKER_P02`** ist als Konstante deklariert, wird aber **nicht
   referenziert** (Panel 02 zeichnet das Literal `"x"`). Bewusst nicht
   entfernt, um den sichtgeprueften Renderer-Stand `ca0db364…` nicht zu
   entwerten; Bereinigung erst mit der naechsten Renderer-Revision.
2. **A-2 in Panel 02** bleibt als dokumentierte Ausnahme bestehen (Anker
   hat Vorrang, §66.5-Entscheid / §71.2).
3. **A-3-Nachjustierung** (E9): ob die beiden Offsets die Kollision mit den
   Override-Boxen und dem `G4 RECLAIM`-Label vollstaendig loesen, entscheidet
   das Sichturteil; bis dahin bleibt es beim deklarierten Umfang.
4. **E-12** ist dokumentiert, aber der V014-P03-Hash **nicht** neu arretiert.

**Naechster Auftrag:** H2-Marktanalyse (Phase P10 ab Bar 1021).

# Addendum v0.22 — Generationswechsel V017: Kanten-Extremum, M6-Heilung und die Renderer-Beschluesse P-1 … P-3 (2026-09-10)

## 72.0 Geltung und Abgrenzung

Dieses Addendum setzt §71 fort und ist mit §54 (Darstellungsgarantie), §66
(V014-Override), §67–§69 (Q29 / G4) und §70 (native G4-Integration, Route A)
kompatibel. Es regelt drei Dinge:

1. den **Einbrand einer neuen Engine-Generation V017** in
   `test/tmp_kanten_engine_replay.py` — ausgeloest durch die
   Kanten-Knick-Forensik: die kausale Kantenlinie ist das **Extremum** der
   bestaetigten Dochte, nicht deren Mittelwert;
2. die **Heilung des M6-Kausalitaetspfades** im selben Hunk;
3. die **Renderer-Beschluesse P-1, P-2 und P-3** des Anwenders.

**Nicht** Gegenstand: die H2-Marktanalyse (P10 ab Bar 1021) und eine
Neu-Arretierung des V014-Panel-03-Hashes (bleibt **E-12**).

## 72.1 Zero-Trust-Ablauf und Einbrand

Der Einbrand erfolgte in drei Stufen. Bis zur ausdruecklichen Freigabe wurde
die arretierte Engine **nicht** angefasst.

| Stufe | Gegenstand | Ergebnis |
|---|---|---|
| 1 | Backups | `_tmp_backup_engine_pre_v017.py` = `ea2f72a8…` / 196.012 B (**byte-identisch** zur arretierten Engine, verifiziert) · `_tmp_backup_renderer_pre_v017.py` = `ca0db364…` / 79.314 B |
| 2 | Wegwerf-Kandidat | `_tmp_engine_v017cand.py` = `4a356765…` / 196.083 B, erzeugt durch `_tmp_make_v017cand.py` **mit erhaltenem CRLF** |
| 3 | Probe-Lauf | `--mode V017 --engine test/_tmp_engine_v017cand.py --probe-praefix probe_v017_` → 5 PNG, alle Asserts gruen; Anwender-Sichtpruefung bestaetigt |

Stufe 3 ist der **urkundliche** Vorlauf; der Satz liegt als
`test/probe_v017_01..05.png` (prae-Einbrand, §72.8) neben dem Produktionssatz.
Der Uebertrag auf den produktiven Pfad erfolgte als **Byte-Kopie**, nicht als
Editor-Roundtrip — dadurch ist die CRLF-Struktur der Engine beweisbar erhalten.
Nach dem Einbrand: `py_compile` OK.

## 72.2 Die Motoraenderung: ein einziger Hunk

Die gesamte Aenderung der Engine-Generation besteht aus **einem**
zusammenhaengenden Hunk in `_SEEdgeH.basis_bei` (Z. 2118, **+3/−1**):

```diff
@@ -2115,7 +2115,9 @@
         if self.ist_prim_anker:
             return self.basis
         px = [p for b, p in self.wicks if b + 2 <= k]
-        return float(np.mean(px)) if px else self.basis
+        if px:
+            return float(min(px) if self.seite == "OBEN" else max(px))
+        return float(self.wicks[0][1])
```

| Groesse | vorher | nachher |
|---|---|---|
| SHA256 | `ea2f72a8de81d632909da72d79b158b0760e6dfc05c6c9047559a4fbf7d437a5` | `4a3567659990586cb507f51e10575bdc9b64d82745523034c206b188e19f7298` |
| Bytes | 196.012 | 196.083 (**+71**) |
| Umbrueche | 4.574 (CRLF) | 4.574 (CRLF, unveraendert) |

**Regel F (Kanten-Extremum).** Die kausale Kantenlinie ist die
**institutionelle Liquiditaetsgrenze**, nicht der Schwerpunkt:
`OBEN` = **tiefstes** Hoch, `UNTEN` = **hoechstes** Tief der jeweils
bestaetigten Dochte. Clusterbildung, Kanten-IDs (`kid`), R21-Semantik und
Tombstones bleiben unberuehrt; **alle 73 Kanten-IDs sind stabil**.

Verworfene Varianten — dokumentiert, damit sie **nicht erneut** geprueft
werden:

| Variante | Regel | Verdikt |
|---|---|---|
| A | Mittel + `_stab`-Patch | **Nulloperation**: `e.basis == basis_bei(mbar)`; Ziele verfehlt |
| B / G | K73 driftet auf 69,5100 | Ziele verfehlt |
| C | H1-Trade verloren | verworfen |
| D / E / H / I | Ziele verfehlt | verworfen |
| **F** | **Extremum der bestaetigten Dochte** | **einzige Variante, die beide Anwenderzielniveaus trifft** |

Anwenderzielniveaus: **K73 → 69,6110** = tiefstes Touch-Hoch (Bars 1122 /
1211 / 1272 = 69,7090 / **69,6110** / 69,7140) · **K82 → 67,6000** = hoechstes
Touch-Tief (Bars 1031 / 1056 / 1172 / 1259 = 67,5350 / 67,5530 / 67,4940 /
**67,6000**). Die Sichtspanne K73 betraegt nur **0,149 %** (Herleitung allein
ueber Bars 1072–1226).

## 72.3 M6-Heilung (im selben Hunk)

Der dritte Teil des Hunk (`return float(self.wicks[0][1])`) heilt einen
**Look-ahead im M6-Aussenwandpfad**: `_existiert()` erlaubt
`k = erster_pivot_bar + 1`. Dort fiel `basis_bei` bisher auf `self.basis`
zurueck — das ist das **End-Mittel** der Wick-Liste, also Zukunftsinformation.

**Isolationsnachweis.** Die beiden Teile des Hunk wurden **getrennt** geprueft
(drei Wegwerf-Engines, `optimize=1`, sonst identischer Aufbau):

| Variante | Regel | Rueckfall |
|---|---|---|
| **A** = eingebrannt | Extremum (`min`/`max`) | `self.wicks[0][1]` |
| **B** = ohne Heilung | Extremum (`min`/`max`) | `self.basis` (alter Pfad) |
| **C** = Vorgaenger | Mittelwert (`np.mean`) | `self.basis` |

| Vergleich | Trade-Schluessel | R je Trade | Q29-Liste | M6-Anzahl | Niveauwechsel |
|---|---|---|---|---|---|
| **A gegen B** (nur Heilung) | identisch | **identisch** | identisch (69) | identisch (24) | identisch (66) |
| **A gegen C** (Hunk total) | 17 vs 18 | verschieden | **69 vs 57** | **24 vs 23** | **66 vs 205** |

**Ergebnis.** Die Heilung ist **handelsneutral** (kein Trade, kein R-Wert, kein
Blocker faellt weg oder kommt hinzu) — aber sie ist **nicht wirkungslos**: sie
korrigiert **einen** journalierten Wert. Genau eine M6-Blocker-Zeile traegt
einen Preis, der erst durch den Rueckfall entsteht — und dort wird sie
**kausal**:

```text
A (geheilt) : bar  658 LONG  K  3 basis=62.967 sweep=62.925 -> BLOCKER-SPERRE (unerreichte Aussenwand K48 62.577)
B (alt)     : bar  658 LONG  K  3 basis=62.967 sweep=62.925 -> BLOCKER-SPERRE (unerreichte Aussenwand K48 62.562)
```

`62,577` ist der **erste bekannte** Dochtpreis der Aussenwand K48 und war am
Bar 658 **tatsaechlich bekannt**; `62,562` war das End-Mittel der Wick-Liste,
also Zukunftsinformation. Die Heilung macht das Journal damit **kausal**, ohne
das Handelns zu veraendern. Das Fenster dieses Effekts ist genau der Fall
„Wick-Liste noch nicht vollstaendig bestaetigt".

**Der zusaetzliche M6-Blocker stammt nicht von der Heilung.** Die Zeile
`bar 658 LONG K3` existiert in **A und B**, nicht aber in **C** — sie ist eine
Folge der **Extremum-Regel** (§72.2). M6 zaehlt damit 24 (V017) gegen 23
(V016).

**Wichtig:** `np.nan` waere an dieser Stelle unzulaessig — NaN-Vergleiche sind
durchgaengig `False` und wuerden den M6-Blocker **lautlos abschalten**; der
Renderer maskiert bereits selbst (Z. 719-723). Der Rueckfall liefert deshalb
den ersten **bekannten** Docht, nicht „nichts".

## 72.4 Renderer-Beschluesse P-1 … P-3

Alle drei wurden im Renderer `test/tmp_png_aug_sichttest.py` umgesetzt; die
Ergebnisdatei ist **`3d6a4788…` / 92.915 B** (vorher `ca0db364…` / 79.314 B).

| Beschluss | Inhalt | Umsetzung |
|---|---|---|
| **P-1** | `--probe-praefix` **ERSETZT** das Ausgabe-Praefix (statt es voranzustellen) | neuer Aufloeser `PRAEFIX = PROBE_PRAEFIX or KONF.ausgabe_praefix`; ebenso `PROTOKOLL_DATEI`; alle 5 PNG-Ausgabestellen und der Protokollpfad umgestellt |
| **P-2** | Engine-Kennung und Niveauwechsel-Zeile **strikt auf V017 gaten** | beide `log()`-Zeilen in `if _V17:` gekapselt |
| **P-3** | Nomenklatur trennen (Niveauwechsel **und** Netto-Preiswechsel) | neues Feld `netto_preiswechsel_baseline` (Default 54 = V016-Wert); Wortlaut in Statistikblock **und** Protokoll |

**P-2 war nicht kosmetisch.** Die beiden Kennungszeilen waren zuvor
**ungated** und hatten das arretierte V016-Protokoll veraendert (5.430 statt
5.520 B). Nach der Gatelung ist `tmp_png_aug_sichttest_v016_out.txt` wieder
**byte-identisch** zum Arretierungsstand `2969723c…` / 5.520 B — nachgewiesen
durch Gegenprobe in §72.9.

**P-3 Wortlaut (verbindlich, gerendert und protokolliert):**

```text
Linien mit Netto-Preiswechsel: 41 (Baseline 54) | Niveauwechsel gesamt: 66 (Baseline 205)
```

Der Default `--mode` bleibt **V014**; V017 wird ausschliesslich explizit
aufgerufen, damit automatisierte Altaufrufe nicht umschalten.

## 72.5 Neuarretierte Sollwerte (V016 → V017)

Weil die Kantenformel im **Motor** liegt, wandert neben `R1` auch der
ungepatchte Referenzlauf `V0` und die v0.1-Basis `R_B` mit der Generation.
Die Sollwerte sind Fail-Loud-Asserts in der Konfiguration
(`KEIN` Abschalter — §66.5 / E4).

| Kennzahl | V016 (arretiert) | **V017 (neu)** |
|---|---|---|
| `V0` / `R0` | 14 / +40,445143 | **14 / +42,450970** |
| `V0` Aufteilung | — | H1 7 / +39,919584 · H2 7 / +2,531386 |
| `V1_basis` / `R_B` | 15 / +46,866348 | **14 / +47,815697** |
| `V1_aktiv` / `R1` | 18 / +64,879080 | **17 / +65,835576** |
| H1 (Trades / R) | 8 / +38,964262 | **7 / +39,919584** |
| H2 (R) | +25,914818 | **+25,915992** |
| P9-Regimebeitrag | +23,433938 | **+23,435111** |
| Delta `R1 − R_B` | +18,012732 | **+18,019879** |
| Quartett-R | +19,804922 | **+19,806095** |
| K67-Quartett-Summe | 17,1107 | **17,110608** |
| G4 `K77@1002` | +3,629016 | **+3,629016** (bit-identisch) |
| `REFERENZ` | (980,73), (1020,73) | **(980,73)** |
| `NEU` | 5 Schluessel | **4 Schluessel** |
| Niveauwechsel (sichtbar) | 205 | **66** |
| Linien mit Netto-Preiswechsel | 54 | **41** |
| Sperr-Marker Q29 | 57 | **69** |
| Sperr-Marker M6 | 23 | **24** |
| Lebende Kanten | 59 edges + 14 seeds = 73 | **59 + 14 = 73** (unveraendert) |

**Kausale Endniveaus bei Bar 1287** (Provenienz-Basis → kausaler Wert):

| Kante | Seite | Provenienz `e.basis` | kausal `basis_bei(1287)` | Norm v0.4 | Abweichung |
|---|---|---|---|---|---|
| K67 | OBEN | 69,9458 | **69,8990** | 69,9140 | −0,0150 |
| K73 | OBEN | 69,6785 | **69,6110** | 69,5550 | +0,0560 |
| K77 | UNTEN | 68,3597 | **68,4130** | 68,3700 | +0,0430 |
| K82 | UNTEN | 67,5455 | **67,6000** | 67,6355 | −0,0825 |

Alle vier Grenzkanten bleiben **Norm-Abweichung** und tragen daher weiterhin
das Norm-Zitat als **Option (b)** (Norm wird angehaengt, nicht ersetzt).

### 72.5.1 H1-Box V017 (7 Trades / +39,919584 R)

| Kante | Signal-Bar | Entry-Bar | Stufe | Richtung | R |
|---|---|---|---|---|---|
| K20 | 229 | 231 | STUFE_2_KERZE_2 | SHORT | +6,889303 |
| K20 | 242 | 245 | STUFE_3_KERZE_3 | SHORT | +3,925121 |
| K5 | 398 | 399 | STUFE_1_IN_BAR | LONG | +5,697713 |
| K16 | 490 | 491 | STUFE_1_IN_BAR | SHORT | −0,475084 |
| K16 | 509 | 510 | STUFE_1_IN_BAR | SHORT | −0,347446 |
| K20 | 529 | 531 | STUFE_2_KERZE_2 | SHORT | +8,359943 |
| K20 | 564 | 565 | STUFE_1_IN_BAR | SHORT | +15,870034 |

**Direktvergleich gegen V016** (V016 gemessen mit `--mode V016 --engine
test/_tmp_backup_engine_pre_v017.py`, also auf `ea2f72a8…`):

| Kante | Signal-Bar | V016 R | V017 R | Status |
|---|---|---|---|---|
| K20 | 229 | +6,924513 | +6,889303 | bleibt, R wandert (tp2 63,6047 → 63,6190) |
| K20 | 242 | +3,947913 | +3,925121 | bleibt, R wandert |
| K8 | 383 | −0,401786 | — | **entfaellt** |
| K5 | 398 | +5,658254 | +5,697713 | bleibt, R wandert |
| K16 | 492 | −0,482566 | — | **entfaellt** (ersetzt) |
| K16 | 490 | — | −0,475084 | **neu** |
| K16 | 509 | — | −0,347446 | **neu** |
| K20 | 529 | +8,391264 | +8,359943 | bleibt, R wandert |
| K20 | 564 | +15,926670 | +15,870034 | bleibt, R wandert |
| K8 | 620 | −1,000000 | — | **entfaellt** |
| **Summe** | | **8 / +38,964262** | **7 / +39,919584** | +0,955322 R bei einem Trade weniger |

Drei V016-Trades entfallen (`K8@383`, `K16@492`, `K8@620`), zwei kommen hinzu
(`K16@490`, `K16@509`); die fuenf gemeinsamen Trades behalten Bar und Kante,
ihr R wandert jedoch mit den Kantenpreisen (`tp2` 63,6047 → 63,6190 bzw.
63,4745 → 63,4850). **Treiber ist allein §72.2** — die Trades der H1-Box
werden nicht vom Adapter gesteuert, sondern von den Kanten des Motors.

Der Adapter greift ausschliesslich ab `start_scope_bar` und bleibt damit
**MAKRO**; H1 wandert dennoch mit, weil die **Kantenformel selbst** im Motor
liegt (§72.2).

### 72.5.2 H2-Expansion V017 (10 Trades / +25,915992 R)

| Kante | Signal-Bar | Entry-Bar | Richtung | R | Anmerkung |
|---|---|---|---|---|---|
| K1 | 639 | 640 | LONG | −1,000000 | |
| K3 | 650 | 653 | LONG | −1,000000 | |
| K45 | 679 | 681 | LONG | +6,480880 | |
| K16 | 714 | 715 | SHORT | −1,000000 | Signal-Bar **714** (V016: 715) |
| K51 | 760 | 762 | SHORT | −1,000000 | |
| K67 | 903 | 905 | SHORT | +4,119775 | STUFE_2_KERZE_2, entry 69,6700 |
| K67 | 980 | 981 | SHORT | +9,987676 | STUFE_1_IN_BAR, entry 69,8070 |
| K73 | 981 | 982 | SHORT | +2,695488 | STUFE_1_IN_BAR, entry 69,4910 |
| K77 | 1002 | 1003 | LONG | +3,629016 | **G4-Reclaim** (§69.8) |
| K67 | 1020 | 1021 | SHORT | +3,003157 | STUFE_1_IN_BAR, entry 69,5780 |

**Quartett-R:** K67@903 +4,119775 · K67@980 +9,987676 · K73@981 +2,695488 ·
K67@1020 +3,003157 = **+19,806095** (K67-Anteil +17,110608).
**Transition-Park 640–847:** K1@639, K3@650, K45@679, K16@**714**, K51@760
= 5 / **+2,480880 R**. G4 `K77@1002` bleibt mit **+3,629016 R bit-identisch**
zu V016.

## 72.6 Erratum E-13 — die Altsatz-Garantie ist geoeffnet

§68.6 / E-5 sicherten zu, dass die im V014-Lauf **entfallenen** v0.1-Trades
als Referenzmarker sichtbar bleiben — namentlich `K73@980` **und**
`K73@1020`. Diese Garantie gilt fuer die **alte** Engine-Generation und ist
fuer V017 **aufgehoben**:

> **E-13.** In der Generation V017 existiert `K73@1020` **bereits im
> v0.1-Referenzlauf nicht mehr**. Die Mengendifferenz `V1_basis \ V1_aktiv`
> schrumpft von zwei auf **einen** Eintrag (`K73@980`, +2,412991 R). Der
> statische `REFERENZ`-Sollwert ist entsprechend auf `((980, 73),)`
> reduziert; die Renderer-Asserts sind mitgezogen, es gibt **keinen**
> stillen Durchlauf.

Ursache ist §72.2: mit der Extremum-Regel wandert das P9-Signal an Bar 980
von `K73` auf `K67`. Der v0.1-Referenzlauf der neuen Generation liefert
`K73@980 +2,412991` und `K67@1020 +3,002241`; der Adapter-Lauf daraus
`K67@980 +9,987676`, `K73@981 +2,695488` und `K67@1020 +3,003157`.

## 72.7 Zaehler: Niveauwechsel und Netto-Preiswechsel

Die beiden Kennzahlen sind **verschieden** und werden ab v0.22 getrennt
gefuehrt (Beschluss P-3):

| Kennzahl | Definition | V016 | V017 |
|---|---|---|---|
| **Niveauwechsel gesamt** | jeder Preiswechsel an **jedem** Bar, an dem die Linie bestaetigt ist (`pivot_bar + 2 <= k`) — exakt die Renderer-Maskierung | 205 | **66** |
| **Linien mit Netto-Preiswechsel** | Kanten, deren **Label** die Form `v0 -> v1 *` traegt (Startwert ≠ Endwert) | 54 | **41** |

**Korrektur einer frueheren Fehlzahl.** Die im §71-Umfeld notierte Zahl
„259" war ein **Artefakt eigener Zaehlung**: sie entstand, wenn der Bar
**vor** der Bestaetigung mitgezaehlt wird (je Linie ein Phantom-Sprung).
„Niveauwechsel 205 → 66" ist der korrekte, maskierte Wert; er ist als
**hartes Literal** im Renderer hinterlegt:

```python
assert NIVEAUWECHSEL == KONF.niveauwechsel_gesamt, (...)
```

Der kosmetische Text im Bild schuetzt vor keiner Regression — dieser Assert
schon. In V01 … V016 lauten die Zeilen **wortgleich** wie zuvor.

## 72.8 Artefakte und Arretierung

**Engine (eingebrannt)**

| Datei | SHA256 | Bytes |
|---|---|---|
| `test/tmp_kanten_engine_replay.py` | `4a3567659990586cb507f51e10575bdc9b64d82745523034c206b188e19f7298` | 196.083 |
| `test/_tmp_backup_engine_pre_v017.py` (Vorgaenger) | `ea2f72a8de81d632909da72d79b158b0760e6dfc05c6c9047559a4fbf7d437a5` | 196.012 |
| `test/_tmp_engine_v017cand.py` (Kandidat, identisch zur Engine) | `4a356765…` | 196.083 |
| `backtest_lab/phasen_regime_adapter.py` (**unveraendert**) | `0f3f8765b1682910a7332b2bcb6f30f79fb56afaec180bdca674693d3ec2b01b` | 25.783 |

**Renderer**

| Datei | SHA256 | Bytes |
|---|---|---|
| `test/tmp_png_aug_sichttest.py` (neu, P-1/P-2/P-3) | `3d6a4788788375576ce37e4658598d4d0b7cbf8b44bb48e087d3185cef656c1e` | 92.915 |
| `test/_tmp_backup_renderer_pre_v017.py` (Vorgaenger) | `ca0db364f6955c29c103e10e16935428115cc47c8a937c86df2d6431791cd3e3` | 79.314 |

**Produktionssatz V017** (`aug_sichttest_v017_01..05.png`)

| Panel | SHA256 | Bytes |
|---|---|---|
| `01_gesamt` | `550091f5359df47b7868e13bd1f1b734cb0c17e2e3109b30e53bd9aedf43010e` | 2.071.320 |
| `02_h1_box` | `42427164f88f9e93513d724eb7822b46d711c3ce990e5592f5bd220dd7250a2b` | 874.523 |
| `03_h2_phasen` | `85926341eb86c84d60a9e2e6edebce489e2198a5c498b6aecf13b4c6898612dd` | 1.717.237 |
| `04_p9_regime` | `b53095565c4d4fdd7b758d40b469ac3fa085a0e80188d9807d69c54171738842` | 1.195.065 |
| `05_kantenkarte` | `91c8dd6164f4410b1b9009728e9ff8a0b2ca74f26718123018df90602892b5f1` | 2.069.665 |
| **Protokoll** `test/tmp_png_aug_sichttest_v017_out.txt` | `866308081f94f2311337547ba32e1968f72ec4bef13b021658ca35e3889b4750` | 5.044 |

**Zero-Trust-Probesatz** (prae-Einbrand, Kandidaten-Engine `_tmp_engine_v017cand.py`)

| Panel | SHA256 | Bytes |
|---|---|---|
| `probe_v017_01_gesamt.png` | `8aa8d690d321873c542397712f538f9996a1517db456d7ffb88006a76d1e9a46` | 2.071.949 |
| `probe_v017_02_h1_box.png` | `42427164…` | 874.523 |
| `probe_v017_03_h2_phasen.png` | `6a74f186c5ebdb455173bb2bbdacfe22f36d9492129b576e5867a7a5ecbbe7eb` | 1.717.672 |
| `probe_v017_04_p9_regime.png` | `d4b85aa5790314b338aff249c5ec0f8d04295a9fca98c0f4a6e43fced27f8769` | 1.195.768 |
| `probe_v017_05_kantenkarte.png` | `6777deebc40605cbc1e231ffb95ba1da4175305aeee8dd1d4b37bd442c3a3a5e` | 2.070.112 |
| Protokoll `test/_tmp_probe_v017_out.txt` | `996ef9aba33099aecd4ee201e6d0f7731aadeb9b6dde66152d57adfdb39ba527` | 4.960 |

**Warum Probe- und Produktionssatz differieren.** Beide laufen mit derselben
Engine-Bytes; die Panels 01/03/04/05 tragen in der Kopfzeile den **Namen der
geladenen Engine** (`_tmp_engine_v017cand.py` vs. `tmp_kanten_engine_replay.py`).
Panel 02 fuehrt keine solche Zeile und ist deshalb in beiden Saetzen
**bit-identisch** (`42427164…` / 874.523 B).

## 72.9 Integritaet und Neutralitaetsnachweise

Alle Nachweise wurden als **gezielte Einzelpruefungen** gefahren (keine
Regressionstests); die Gegenproben nutzen `--engine` und `--probe-praefix`.

| # | Pruefung | Ergebnis |
|---|---|---|
| 1 | `py_compile` Engine und Renderer | OK |
| 2 | Assert-Paritaet Renderer-Kopf, 5 Modi | **5/5 OK** (V01 … V016 unveraendert; V017 auf neue Sollwerte) |
| 3 | **V015** Satz + Protokoll gegen Arretierung (Renderer `3d6a4788…`, Engine `ea2f72a8…`) | **5/5 PNG und Protokoll `b7c4142a…` / 5.507 B byte-identisch** |
| 4 | **V016** Satz + Protokoll gegen Arretierung (dito) | **5/5 PNG und Protokoll `2969723c…` / 5.520 B byte-identisch** |
| 5 | **V01** Satz gegen Arretierung (dito) | **5/5 PNG byte-identisch** |
| 6 | **A/B-Neutralitaet P-1…P-3** (Klon des Vorstands `ca0db364…` mit gepinnter Backup-Engine) | erzeugt fuer V014 dieselben Bytes wie der neue Renderer → **P-1…P-3 sind wirkungsneutral** |
| 7 | **Rueckweg** V01 / V016 mit `--engine test/_tmp_backup_engine_pre_v017.py` | **5/5 PNG byte-identisch** je Modus; V016-Protokoll ebenfalls byte-identisch |
| 8 | G4 `K77@1002` gegen V016 | **+3,629016 R bit-identisch** |
| 9 | Kanten-IDs | **alle 73 stabil** |
| 10 | Produktionslauf V017 ohne Probe-Optionen | alle Asserts gruen, 5 PNG + Protokoll geschrieben |
| 11 | **M6-Heilung isoliert** (Varianten A/B/C, §72.3) | handelsneutral (Trades, R, Q29, M6-Zahl, Niveauwechsel gleich); genau **ein** journalierter Wert wird kausal (`K48` 62,562 → 62,577) |
| 12 | H1-Box V016 gegen V017 direkt verglichen | 3 Trades entfallen, 2 kommen hinzu, 5 wandern im R (§72.5.1) |

**E-14 (V01-Protokoll, historisch — neu).** Die arretierte Datei
`test/tmp_png_aug_sichttest_out.txt` (9.784 B) ist ein
**Konsolen-Mitschnitt der v0.1-Aera in UTF-16 LE** (BOM `FF FE`) und traegt
den **alten Wortlaut** („Adapter v0.1, P9 aktiv", ohne `V1_basis`-Zeile, ohne
`Override-Info`-Zeile). Sie ist ein **Protokoll der Zeitgeschichte**, kein
Reproduktionsartefakt: `log.schreibe()` erzeugt UTF-8 ohne BOM. Die
zugehoerigen **PNGs reproduzieren 5/5 byte-identisch** (Zeile 5). Keine
Neu-Arretierung, kein Eingriff.

**E-12 bleibt gueltig (V014 Panel 03).** Die Abweichung ist **nicht** durch
P-1…P-3 entstanden: der Vorstands-Klon `ca0db364…` erzeugt mit gepinnter
Backup-Engine exakt `f8505d124c3dddf3…` / 1.694.382 B — identisch zum neuen
Renderer. Der arretierte Wert bleibt `a055b243463460e8…` / 1.695.409 B aus der
Zeit vor dem v015-Patch. Die uebrigen vier V014-Panels sind byte-identisch.
Der V014-**Protokoll**text driftete gleichursaechlich (`Summe` → `QUARTETT`,
`Delta v0.14-v0.1` → `Delta V014-v0.1`).

## 72.10 Generationsbindung der Engine: Fail-Loud und Rueckweg

Der Renderer laedt **eine** Engine-Datei. Nach dem Einbrand traegt sie die
V017-Formel; die Modi V01 … V016 sind damit **nicht mehr** mit ihr
reproduzierbar. Das ist **gewollt** und wird **nicht** stillschweigend
ausgehebelt:

```text
$ python test/tmp_png_aug_sichttest.py --mode V016
AssertionError: (14, 42.450969915773506)      # Z. 639, erster Assert
```

Der erste Fail-Loud-Assert stoppt den Lauf, **bevor** eine einzige PNG
entsteht — es kann also kein falscher V016-Satz geschrieben werden. Der
Rueckweg ist explizit und erprobt (§72.9 Zeile 7):

```text
python test/tmp_png_aug_sichttest.py --mode V016 ^
    --engine test/_tmp_backup_engine_pre_v017.py
```

Damit bleiben alle arretierten Saetze V01 … V016 **vollstaendig
reproduzierbar**; sie sind nur an die Vorgaenger-Engine **gebunden**. Die
`--engine`-Option akzeptiert ausschliesslich Pfade innerhalb `test/`
(Schutz gegen versehentliches Ueberschreiben der arretierten Engine).

## 72.11 Status und offene Punkte

| Kennzahl | Wert |
|---|---|
| **V017 (eingebrannt)** | **17 Trades / +65,835576 R** |
| davon H1 | 7 / +39,919584 R |
| davon H2 | 10 / +25,915992 R |
| Engine-Generation | `4a356765…` (V017) |
| Regelbestand | §54 + §66 + §67 + §68 + §69 + §70 + §71 + **§72** |
| Renderer | `3d6a4788…` (P-1 · P-2 · P-3 umgesetzt) |
| Errata | E-5 · E-11 · E-12 · **E-13** (Altsatz-Garantie geoeffnet) · **E-14** (V01-Protokoll) |

**Offen:**

1. **`test/` ist gitignored** (`.gitignore:63`). Von den hier genannten
   Artefakten ist **nur `test/SESSION_HANDOFF.md` getrackt**; Engine,
   Renderer, Kandidat, Backups, PNG und Protokolle sind **untracked**. Die
   Arretierung erfolgt daher **urkundlich ueber SHA256** in diesem Dokument
   und im Handoff — **kein** `git add -f` (Anwenderentscheid).
2. **`SWEEP_MARKER_P02`** bleibt als deklarierte, nicht referenzierte
   Konstante stehen (§71.7 Punkt 1); Panel 02 fuehrt das Literal `"x"`.
3. **E-12** ist dokumentiert, der V014-P03-Hash ist **nicht** neu arretiert.
4. **Englische Fassung** dieses Addendums existiert nicht und ist nicht
   vorgesehen.

**Naechster Auftrag:** H2-Marktanalyse (Phase P10 ab Bar 1021) — unveraendert.
