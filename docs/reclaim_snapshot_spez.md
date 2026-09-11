# Spezifikation: Reclaim-Snapshot-Engine (Post-Phase-Kanten, Setup B)

> **⚠️ Zeitbasis-Erratum (2026-09-11):** Dieses Dokument verwendet den historisch
> überladenen Begriff „Wanduhr" und teils die `Europe/Berlin`-Projektion (+2 h).
> **Verbindlich ist seit 2026-09-11 `docs/ZEITBASIS_KANON.md`:** Rechenbasis ist
> ausschließlich die **Broker-Kerzen-Zeit (BKZ)** = `time AT TIME ZONE 'UTC'`;
> `Europe/Berlin`/`Europe/Budapest` sind reine Anzeige-Dubletten.
> Abschnitte, die bereits `time AT TIME ZONE 'UTC'` nutzen, sind
> kanonkonform; Zeitangaben aus der alten Berlin-Projektion sind um
> −2 h gegen die BKZ verschoben.


Status: **ARRETIERT / SPEZIFIKATION (Pfad B)**
Datum: 2026-09-06
Bezug: `docs/reclaim_live_lateriz_befund.md` (Commit `b6bcfc6`, §7 Ausblick),
       `scripts/reclaim_live_kernel.py` (Commit `12658a1`, L1-verifiziert),
       `scripts/phasen_volumen_profil.py` (frozen v0.4.0, Commit `691bf56`, bleibt byte-identisch)

---

## 1. Zweck & Einordnung

Die Snapshot-Engine ist die operative Konsequenz des Lateriz-Befunds: Statt die
Phasen-Historie am rechten Rand dynamisch neu zu berechnen (Lateriz 2–46,5 Bars),
werden die Value-Area-Kanten einer **vollendeten** Phase statisch fixiert und nur
noch die aktuellen Bar-Closes gegen diese eingefrorenen Levels geprüft.

**Wichtig:** Das ist eine **neue Signalpopulation** (Post-Phase-Sweeps). Die
historische Baseline (+297,14R S1+S2, CD=12) stammt aus Intra-Phase-Sweeps gegen
die laufende Volume-Zone. Ein Post-Phase-Sweep an einer alten Phase hat **nicht
automatisch** denselben Erwartungswert. Deshalb gilt die **Schritt-0-Doktrin**:
Kein Live-Betrieb, kein Daemon, kein Alarm ohne historische Replay-Validierung
über AUG/S1/S2. Die Baseline bleibt byte-identisch versiegelt.

---

## 2. Kernprinzip

1. Sobald eine Phase historisch vollendet ist (`break_dir is not None`), werden
   ihre Volume-Zonen-Level (`U_zone`=VAH, `L_zone`=VAL, `POC`) statisch fixiert.
2. Es ist **immer genau eine aktive Kante** aktiv: die der jüngsten vollendeten
   Phase. Kein Stacking alter Niveaus.
3. Eingehende Live-Kerzen prüfen ausschließlich:
   - Sweep unter `L_zone` / über `U_zone`?
   - Schließt die Kerze wieder auf der Reclaim-Seite (`in_bar` oder `next_bar`)?
4. Keine Phasen-Neuberechnung, kein Repainting, keine dynamische Zonen-Verschiebung.

---

## 3. Typisierte Datenverträge

```python
from dataclasses import dataclass
from typing import Literal, Optional
import pandas as pd

SignalRichtung = Literal["SHORT", "LONG"]
ReclaimTyp = Literal["in_bar", "next_bar"]
KantenHerkunft = Literal["kernel_vollendete_phase", "manueller_override"]


@dataclass(frozen=True, slots=True)
class StatischeKante:
    """Repraesentiert eine historisch fixierte Value-Area-Kante.

    Primärquelle: letzte vollendete Phase (break_dir is not None) aus
    `berechne_reclaim_signale()`. U_final/L_final sind rein informativ
    (Sekundaerlevel); gehandelt wird ausschliesslich gegen die Zone.
    """
    phase_id: int
    phase_start: pd.Timestamp
    phase_ende: pd.Timestamp
    phase_ende_idx: int          # idx von p.ende im Fenster (p.i_ende)
    aktiv_ab_idx: int            # brk_idx + 1 (erste ueberwachte Bar, kausal)
    u_zone: float                # VAH (Primaerlevel oben)
    l_zone: float                # VAL (Primaerlevel unten)
    poc: float                   # Fair-Value-Target (TP1)
    u_final: Optional[float]     # Sekundaerlevel (Reaktionsextrem, informativ)
    l_final: Optional[float]     # Sekundaerlevel (Reaktionsextrem, informativ)
    quelle: KantenHerkunft = "kernel_vollendete_phase"


@dataclass(frozen=True, slots=True)
class SnapshotSignal:
    """Post-Phase-Reclaim-Signal an einer statischen Kante (emittiert nur,
    wenn alle Gates bestanden sind)."""
    symbol: str
    timeframe: str
    bar_idx: int                 # Trigger-Bar k im Fenster
    bar_ts: pd.Timestamp
    phase_id: int                # Herkunfts-Phase der Kante
    kanten_alter_bars: int       # bar_idx - phase_ende_idx
    richtung: SignalRichtung
    sweep_extrem: float          # high/low der Trigger-Bar (Sweep)
    trigger_close: float         # Bestaetigungs-Close
    reclaim_typ: ReclaimTyp
    einstieg_bar_idx: int        # k+1 (in_bar) bzw. k+2 (next_bar)
    einstieg_preis: float        # open der Einstiegs-Bar (Referenz)
    sl_preis: float              # 0,45 % vom Entry
    tp1_poc: float               # statischer POC der Phase
    tp2_box: float               # Gegenseite: L_zone*(1+Puffer) bzw. U_zone*(1-Puffer)
    crv: float
    crv2: float
```

---

## 4. Kanten-Lebenszyklus (Kausalität)

1. **Kernel-Lauf je Fenster:** Ein Lauf von `berechne_reclaim_signale(df)` pro
   Benchmark-Fenster genügt. Vollendete Phasen sind **invariant gegen spätere
   Bars**: Nach dem Breakout wandert der Segmentierer weiter; Touches werden nie
   nachgetragen. 4b (`_last_grenz_kontakt`) trimmt ausschließlich die offene
   End-Phase (`break_dir is None`) — die nie überwacht wird. ⇒ **Lookahead-frei.**
2. **Aktivierung:** Phase p vollendet bei `brk_idx` (erste der zwei Schluss-Kerzen
   jenseits der Kante; Kernel bestätigt bei Fensterende `M = brk_idx+1`).
   Kante p ist überwacht für `k ∈ [brk_idx+1,  ...)`.
3. **Verfall:** Die Kante p erlischt beim Vollenden der nächsten Phase
   (`brk_idx(p+1)` — die Kette wechselt auf deren Zone) **oder** spätestens nach
   `N_MAX = 192` Bars (2 Handelstage à 96 M15-Bars) ab `aktiv_ab_idx`.
   Uralte Kanten werden nie endlos überwacht (institutionelle Relevanz verfällt).
4. Es ist immer nur die Kante der **jüngsten vollendeten Phase** aktiv. Ein
   `manueller_override` ist nur als expliziter Notfall-Pfad vorgesehen
   (Fehlerquelle), nie Primärquelle.

---

## 5. Signalregeln (kausal, je Bar k im aktiven Kanten-Fenster)

Semantik exakt wie frozen Baseline (`find_reclaim_signals`, Z. 1150–1272),
substituiert die laufende Zone durch die eingefrorene Kante:

| Richtung | Sweep-Bedingung | in_bar (Entry `open[k+1]`) | next_bar (Entry `open[k+2]`) |
| :--- | :--- | :--- | :--- |
| **SHORT** | `high[k] > u_zone` | `close[k] ≤ u_zone` | `close[k] > u_zone` UND `close[k+1] ≤ u_zone` |
| **LONG** | `low[k] < l_zone` | `close[k] ≥ l_zone` | `close[k] < l_zone` UND `close[k+1] ≥ l_zone` |

**Gates (alle Pflicht):**
- Entry auf POC-Seite: SHORT `einstieg_preis > poc`, LONG `einstieg_preis < poc`
  (sonst ist TP1=POC kein gültiges Richtungs-Target).
- `crv ≥ MIN_RECLAIM_CRV` (1,0), `crv = |tp1 − entry| / |sl − entry|`.
- Cooldown `MIN_SIGNAL_ABSTAND_BARS = 12` je Richtung, **Reset bei jeder neuen
  Kante** (spiegelt die Baseline-Initialisierung je Phase).
- **Bounce-Hürde entfällt** (keine Entsprechung post-phase: die `h_ts/l_ts` der
  Phase sind Touches der Schnittmengen-Linie, nicht der Volume-Zone). Ersatz:
  Phasen-Reife (die Zone entstand aus vollwertiger Multi-Mountain-Verteilung) +
  crv-Gate + Cooldown. Im Replay-Report als Sensitivitäts-Schalter ausweisbar.

**Auflösung (exakt Baseline `_aufloesen`):** SL = Entry·(1±0,45 %), TP1 = POC,
TP2 = Gegenseite mit Puffer (SHORT `l_zone·1,20`, LONG `u_zone·0,80`), Split
25/75, kein SL-Nachzug, kein Trailing (`TRAILING_PCT = 0`).

**Bounds:** Trigger-Bar k muss im aktiven Kanten-Fenster liegen; die
Einstiegs-Bar (k+1 bzw. k+2) muss im Datenbestand existieren (`< len(df)`).
Der A3-Phasen-Bound der Baseline entfällt (post-phase gibt es kein `i_ende`).

---

## 6. Gate-Übernahme-Tabelle (Baseline → Snapshot)

| Baseline-Gate | Quelle (frozen) | Snapshot-Übernahme |
| :--- | :--- | :--- |
| Trigger-Level = laufende Zone | Z. 1112–1115 | **Eingefrorene** Zone der vollendeten Phase |
| CRV ≥ 1,0 | Z. 1196/1248 | **Übernommen** |
| Entry auf POC-Seite | Z. 1185/1237 | **Übernommen** |
| Cooldown 12 (D2-asym, Tier-1-Kette) | Z. 1026–1029 | **Übernommen**, Reset je Kante |
| Bounce ≥ 2 (Intra-Phase) | Z. 1179/1231 | **Entfällt** (keine post-phase Entsprechung) |
| A3-Bounds `k+2 ≤ p.i_ende` | Z. 1173/1226 | **Ersetzt** durch `k+2 < len(df)` |
| `_aufloesen` SL/TP/Split | Z. 890–997 | **Exakt übernommen** (Kernel-Port) |

---

## 7. Wanduhr & Datenfenster

- Symbol/Timeframe: **SILVER M15** (Kernel ist 15-min-gebunden,
  `PIVOT_LOOKBACK * 15` Minuten).
- `ts` tz-naiv (UTC-Projektion via `time AT TIME ZONE 'UTC'` + `tz_localize(None)`,
  exakt `load_data`-Semantik). Nie Windows-Lokalzeit als UTC etikettieren.
- Benchmark-Fenster (exakt wie frozen `START`/`ENDE`, inklusiv `>=`, exklusiv `<`):
  - **AUG:** 2026-08-10 … 2026-08-28 (nur Referenz, S1 ⊃ AUG)
  - **S1:**  2026-02-05 … 2026-08-28
  - **S2:**  2025-01-01 … 2025-12-01

---

## 8. Schritt-0-Replay-Harness (deklarativ, noch kein Code)

Datei: `test/tmp_reclaim_snapshot_replay.py` (test/ ist gitignored; Artefakte nur dort).

Ablauf je Fenster (AUG, S1, S2):
1. `berechne_reclaim_signale(df)` — **ein** Kernel-Lauf pro Fenster (kausal, §4.1).
2. Kanten-Kette aus den vollendeten Phasen bilden (Aktivierung `brk_idx+1`,
   Verfall bei nächster Vollendung bzw. 192er-Cap).
3. Bars im aktiven Fenster gegen die eingefrorene Kante scannen (§5).
4. Jedes Signal mit `_aufloesen` auflösen (forward über den restlichen Datenbestand).
5. Report je Fenster: Anzahl Signale, Summe R, PF, Trefferquote, LONG/SHORT-Split,
   Reclaim-typ-Split; zusätzlich Sensitivitäts-Ausweis:
   - alle vollendeten Phasen vs. nur `handelbar`-Phasen,
   - mit/ohne (definitionsoffene) Bounce-Ersatz-Hürde.
6. Laufzeit-Hinweis: S2 ≈ 32k Bars → Kernel-Lauf dominierend (Minutenbereich);
   nur **ein** Lauf je Fenster, kein Rolling.

---

## 9. Benchmark-Gate & Abbruchkriterien

**Gate für Schritt 0 (Live-Freigabe-Voraussetzung):**
- In **S1 UND S2** jeweils: `PF ≥ 1,30` und `Summe R > 0`.
- AUG wird berichtet, ist aber **nicht** gate-relevant (In-Sample-Referenz).

**Abbruch:** Ist der Erwartungswert in S1 oder S2 negativ bzw. unter dem Gate,
wird auch Pfad B als **statistischer Null-Befund** arretiert
(analog §5.3/§5.5/§5.6-Muster) — kein Live-Betrieb, keine Schwellwert-Schönfärberei.

---

## 10. Referenzen

- `docs/reclaim_live_lateriz_befund.md` (Commit `b6bcfc6`) — Ausgangsbefund, §7 Ausblick
- `scripts/reclaim_live_kernel.py` (Commit `12658a1`) — Kernel, `PhaseData`/`VolumeZone`,
  `segmentiere_phasen`, `_aufloesen`, Modulkonstanten (1:1-Spiegel)
- `scripts/phasen_volumen_profil.py` (frozen v0.4.0, Commit `691bf56`) — Referenz,
  bleibt byte-identisch (kein Eingriff, kein `__main__`-Guard)
- Baseline-Kennzahl: +297,14R (S1+S2, CD=12, MIN_SIGNAL_ABSTAND_BARS=12)
