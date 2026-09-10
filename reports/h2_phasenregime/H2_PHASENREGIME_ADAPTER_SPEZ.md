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
| K82 | UNTEN | 67,6355 | **67,5273** | – | P12-Boden |
| ~~K74~~ | OBEN | ~~69,613~~ | – | – | **R21-eliminiert (Bar 1104)** |

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
| 4 | **Kausale Kantenlinien** — je Bar `basis_bei(k)` (Treppe) statt statischer Provenienz `e.basis` | offen (J2) |
| 5 | **Sperr-Marker** ✕ = Q29-Sperre, ▲ = M6-Sperre, am sperrenden Bar | offen (J3/J4) |
| 6 | **Titel** `Bars 0..1287` | offen |

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
