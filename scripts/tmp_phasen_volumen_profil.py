"""
SILVER M15: RANGE-PHASEN NACH VOLUME-PROFIL (POC/VAH/VAL + Multi-Mountain).

BASIS = tmp_phasen_move_m15.py (Backup bleibt erhalten). NEU: Die
Phasen-Grenzen werden durch das VOLUME-PROFIL je Phase definiert:

- Jede M15-Bar verteilt ihr tick_volume proportional ueber ihren
  High-Low-Bereich auf Preis-Bins (Standard-Volume-Profile).
- Das Histogramm wird geglaettet und in "BERGE" (Mountain) zerlegt:
  getrennt durch Taeller, die tiefer als VALLEY_REL des kleineren
  Nachbar-Peaks liegen. Nur signifikante Berge (>= MIN_MOUNTAIN_PCT
  des dominierenden Volumens) zaehlen.
- Jeder Berg bekommt seinen eigenen POC/VAH/VAL (VA_PCT-Value-Area).
- ZONEN-MODELL (Variante A, "Huelle"):
    OBEN  = hoechste VAH aller signifikanten Berge
    UNTEN = tiefste  VAL aller signifikanten Berge
    MITTE = POC des volumenstaerksten Bergs
    Zwischen-Berge erscheinen als Sub-POC/Sub-VAH/Sub-VAL (gestrichelt).
- Die bisherigen Schnittmengen-Linien bleiben als "REAKTIONS-Extreme"
  (dick gestrichelt) erhalten - sie zeigen die getesteten Rander,
  waehrend die Volume-Zone zeigt, WO DAS GELD WIRKLICH LIEGT.
- VA_PCT ist bewusst als Parameter herausgezogen (70 = Standard, 85/90 =
  breitere Value-Area) - wird spaeter getestet.
- SETUP B (RECLAIM/FAKEOUT) nach Patrick Nill (P1): Eine Bar sticht kurz
  ueber VAH (oder unter VAL) aus und schliesst wieder innerhalb der Zone
  (oder die Folge-Bar bestaetigt den Reclaim). Einstieg nach Bestaetigung.
  TRADE-MANAGEMENT (User-Vorgabe):
    - SL bei Entry = SL_PCT (0.45%) vom Einstiegspreis
    - TP1 = POC (Fair Value, 50% der Position)
    - KEIN SL-NACHZUG: Die Restcharge (50%) behaelt den Einstiegs-SL und
      laeuft zum TP2 = anderes Box-Ende (innen TP2_PUFFER_PCT 0.20%).
    - Alle Trades werden VOLLSTAENDIG aufgeloest (bis Datenende,
      sonst Close zum letzten Kurs).
  Die Zone wird KAUSAL bis zur Signal-Bar berechnet (laufendes
  Volume-Profil, kein Lookahead).

Die Phasen-SEGMENTIERUNG (Etablierung/Ausbruch/Moves) bleibt zunaechst
die kausale Schnittmengen-Logik aus dem Backup-Skript - erst die
GRENZEN/Darstellung werden durch das Volume-Profil bestimmt.

KAUSALITAET / KEIN LOOKAHEAD (wie im Backup):
- Pivot-Bestaetigung nachlaufend (Lag PIVOT_LOOKBACK).
- Geburtszone nur mit bestaetigten Pivots (cutoff am Phasenstart).
- Regel-7-Finalize (letzter Grenz-Kontakt) ist POST-HOC am Datenende.
"""
import duckdb
import pandas as pd
import numpy as np
import sys
from pathlib import Path

OUT_PNG = Path(__file__).resolve().parent / "tmp_phasen_volumen_profil.png"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"
TOL = 0.34            # USD Close-Breakout-Toleranz (entscheidender Ausbruch)
                      #   GETESTET (Reihentest 05.02.-28.08.26, 73-127 Signale):
                      #   Sweet Spot 0.34: +250.80R / avg +2.01 / 65% WR / 125
                      #   Signale (0.33 +248.90R, 0.32 +244.48R, 0.30 alt
                      #   +238.44R / 62% WR). Unter 0.30: zu fruehe Ausbrueche
                      #   kosten R; ueber 0.35: Ausbrueche zu spaet, Phasen
                      #   laufen zu lange. Robustes Plateau 0.30-0.34.
                      #   Per --tol=N testbar.
TOL_TOUCH = 0.15      # "enger Touch": Pivot innerhalb dieser Distanz zur Grenze
MIN_TOUCHES = 3       # je Grenze fuer "handelbar"
MIN_CANDLES = 46
MIN_PHASE_CANDLES = 46  # GEGENSTEUERUNG (Uebersegmentierung): eine Phase darf
                        #   erst nach >= dieser Candles ausbrechen. Kausal
                        #   (j-i >= MIN_PHASE_CANDLES), kein Lookahead.
MIN_CLUSTER = 2       # min. Pivot-Treffer, damit eine Spitze ein Level bildet
MIN_ESTABLISH = 4     # Touches GESAMT (H+L) auf beiden Grenzen, bevor Ausbrueche
                      #   zaehlen. FIX (Trader): "3 Ankerpunkte insgesamt" statt
                      #   "3 je High UND 3 je Low" (alt: je Seite getrennt).
                      #   GETESTET (Reihentest 05.02.-28.08.26, 53-73 Signale):
                      #   Sweet Spot 4: +169.82R / avg +2.36 / 64% WR / 72 Signale
                      #   (1-3 identisch +152.14R, 5 +136.95R, 6 +132.54R).
                      #   4. Anker filtert frisch etablierte, noch volatile
                      #   Zonen; ab 5 werden zu viele Phasen erst spaeter
                      #   handelbar. Per --establish=N testbar.
DENSITY_BAND = 0.15   # Cluster-Fenster (+/-) fuer Level-Berechnung
MIN_SPREAD_PCT = 1.5  # % minimale Handelsspanne (Breite/UNTEN) fuer handelbare Phase
ERWEITERUNG_PCT = 1.0 # % HH/LL-Erweiterung: Spitze bis 1% ueber der Grenzkante
                      #   erweitert die Range (Linie wandert in die Schnittmenge),
                      #   darueber hinaus ist sie kein Teil des Levels
SHIFT_TOL = 0.05      # USD: erst ab dieser Aenderung gilt eine Linie als
                      #   "verschoben" (unterdrueckt Rauschen in der Entwicklung)
GRENZ_KONTAKT_TOL = 0.0  # USD: Toleranz fuer "Pivot erreicht Grenzlinie"
                         #   (H-Pivot >= OBEN-TOL bzw. L-Pivot <= UNTEN+TOL).
                         #   0.0 = Pivot muss die Linie wirklich beruehren,
                         #   damit der Do-19:00-Kontakt (69.714) der letzte ist
FENSTER_PIVOTS = 100    # Gleitendes Pivot-Fenster fuer die Schnittmengen-Linie:
                        #   Nur die letzten N Pivots je Seite bilden die Linie.
                        #   Verhindert das "Einfrieren" an alten Extremen bei
                        #   langen Phasen (z.B. Juni/Juli: U blieb auf 72.88,
                        #   Kurs pendelte 55-70 -> nie etabliert). Bei kurzen
                        #   Phasen (August, <100 Pivots) unveraendert.
PIVOT_LOOKBACK = 2    # Pivot-Bestaetigungs-Lag (Bars): Ein Pivot bei Bar k
                      #   wird erst in Bar k+PIVOT_LOOKBACK bekannt gegeben
                      #   (kein Zentrums-Lookahead, kausal fuer Replay-Tests)
# ---------- VOLUME-PROFIL-PARAMETER ----------
VA_PCT = 0.93         # Value-Area-Anteil je Berg (0.70 = Standard, 0.85/0.90 = breiter)
                      #   GETESTET (Reihentest 05.02.-28.08.26, 42-79 Signale):
                      #   Sweet Spot 0.93: +124.25R / avg +1.66 / 60% WR / 75 Signale
                      #   (0.96 +125.11R / avg +2.05, aber nur 61 Signale; 0.90
                      #   +99.73R / 56% WR). Breitere Value-Area = weiter entfernte
                      #   TP1/TP2 = groessere R. 1.00 kollabiert (Zone = Range,
                      #   0 Signale); 0.93 bleibt sicher davor. Per --va-pct=N testbar.
NUM_BINS = 60         # Preis-Bins fuer das Volume-Profil
SMOOTH_WIN = 3        # Histogramm-Glaettung (Bins)
VALLEY_REL = 0.15     # Tal-Relation: Tal < 15% des kleineren Nachbar-Peaks trennt Berge
                      #   GETESTET (Reihentest 05.02.-28.08.26, 69-78 Signale):
                      #   Sweet Spot 0.15: +152.14R / avg +2.08 / 64% WR / 73 Signale
                      #   (0.14 +148.21R, 0.20 +151.76R, 0.35 alt +134.94R / 61% WR).
                      #   Kleinere Werte trennen zu wenige Berge (engere Zone),
                      #   groessere verschmelzen Berge (mehr Signale, niedrigere
                      #   Qualitaet). Plateau 0.14-0.20. Per --valley-rel=N testbar.
MIN_MOUNTAIN_PCT = 4.0  # Sekundaer-Berg muss >= 4% des dominanten Volumens haben
                        #   GETESTET (Reihentest 05.02.-28.08.26, 72-76 Signale):
                        #   Sweet Spot <= 4.0: +134.94R / avg +1.78 / 61% WR / 76
                        #   Signale (0/2/4 identisch - keine relevanten Berge
                        #   zwischen 4-8%). Default 8.0: +124.25R / 60% WR.
                        #   Kleine Sub-Berge erweitern die Zone -> weiter entfernte
                        #   TP1/TP2 -> groessere R (max +10.69R). Ab 60% Abfall.
                        #   Per --mountain-pct=N testbar.
MIN_RECLAIM_CANDLES = 0   # min. Bars einer Phase, bevor Setup-B-Signale zaehlen
                          #   GETESTET (Reihentest 05.02.-28.08.26, 13-125 Signale):
                          #   Sweet Spot 0: +238.44R / avg +1.91 / 62% WR / 125
                          #   Signale - fast 50% MEHR RENDITE als 30 (+169.82R)
                          #   bei nur ~2 Tagen/Signal statt ~3.5 (125 Signale in
                          #   7 Monaten). Monoton: je frueher Signale zaehlen,
                          #   desto mehr Summe R; Winrate stabil 62-64%. Die
                          #   "jungen" Signale sind netto klar profitabel.
                          #   Per --reclaim-candles=N testbar.
MIN_RECLAIM_BOUNCE = 2    # min. Bounce-Nummer an der Kante.
                          #   GETESTET (Reihentest 05.02.-28.08.26, 51-85 Signale):
                          #   Sweet Spot bounce=2: +96.60R / avg +1.32 / 53% WR
                          #   (bounce=1 +91.60R / 47% WR; bounce=3 +66.80R / 55% WR).
                          #   Bo=1-Signale sind zu 82% Verluste (14/17, netto -5.26R)
                          #   und werden gefiltert. Per --bounce=N testbar.
MIN_RECLAIM_CRV = 1.0     # min. CRV (Risiko-Ertrag) fuer ein Signal (Patrick ~1:3)
MIN_SIGNAL_ABSTAND_BARS = 12  # Cooldown: keine 2 Signale gleicher Richtung in 12 Bars
                              #   GETESTET (Reihentest 05.02.-28.08.26, 82-95 Signale):
                              #   Sweet Spot CD=12: +91.60R / avg +1.08 (klar vor CD=8
                              #   +91.25, CD=10 +84.81, CD=14 +88.92, CD=16 +82.83).
                              #   Fruherer CD=16-Default stammte nur aus Aug+Jun mit
                              #   50/50-Split - haelt dem grossen Sample nicht stand.
SL_PCT = 0.45             # SL bei Entry: % vom Einstiegspreis (SHORT +, LONG -)
                          #   GETESTET (Reihentest 05.02.-28.08.26, 82 Signale):
                          #   Sweet Spot 0.35-0.45; 0.45 = hoechster avg R +0.98
                          #   und beste Winrate 63% bei minimaler Signalanzahl.
TP2_PUFFER_PCT = 0.20     # % vom Level-Preis: TP2 VOR dem anderen Box-Ende (innen)
                          #   SHORT: TP2 = L_zone * (1+0.20%) | LONG: TP2 = U_zone * (1-0.20%)
                          #   GETESTET (Reihentest 05.02.-28.08.26, 73 Signale):
                          #   Sweet Spot 0.20: +99.73R / avg +1.37 / 56% WR
                          #   (0.10 +99.69R / 53% WR; 0.15 +96.60R / 53% WR).
                          #   Groessere Puffer (0.30/0.50) steigern nur die WR,
                          #   kosten aber -14R gegenueber 0.20.
# --- TRADE-MANAGEMENT-VARIANTEN (Setup B / Setup C) ---
ANTEIL_TP1 = 25           # % der Position, die bei TP1 (POC) geschlossen wird
                          #   GETESTET (Reihentest 05.02.-28.08.26, 82 Signale):
                          #   25/75 = Kompromiss: +82.83R / avg +1.01 bei deutlich
                          #   besserer Winrate als 0/100 (+85.49R, aber nur 44%).
                          #   50/50 = 63% Winrate, aber -2.7R Rendite.
                          #   KEIN SL-NACHZUG (konsequent entfernt): Die Restcharge
                          #   behaelt den Einstiegs-SL -> TP2 (Box-Ende) wird trotz
                          #   Pullbacks erreichbar (Trader-Punkt 2).
TRAILING_PCT = 0.0        # >0: Trailing-Stop-Modus statt festem TP1/TP2 (Trader-Punkt 4):
                          #   SL folgt dem Preis mit X% Abstand vom letzten Extrem.
                          #   GETESTET (Reihentest 05.02.-28.08.26, 73 Signale, in
                          #   Kopie tmp_phasen_volumen_profil_trail.py, korrigierte
                          #   Logik: initialer SL hart -1R max, Trailing nur fuer
                          #   Gewinner): bester Wert 0.80 mit +83.45R / avg +1.14 /
                          #   67% WR - DEM FESTEM TP1/TP2-MODUS UNTERLEGEN
                          #   (Baseline +99.73R / avg +1.37). Trailing schneidet die
                          #   grossen TP2-Runner (Box-Ende) ab. NICHT VERWERFEN:
                          #   fuer SETUP C (Move-Trades) ggf. weiter nuetzlich.
TRADE_MOVES = False       # Setup C (Trader-Punkt 3): Ausbruchs-Moves handeln
                          #   (Einstieg nach 2-Close-Bestaetigung, Exit am Ende des Moves)
START = "2026-08-10"
ENDE = "2026-08-28"

# Kommandozeilen-Override fuer Parametertests (z.B. --sl-pct=0.3, --start=2026-06-01)
for _a in sys.argv[1:]:
    if _a.startswith("--sl-pct="):
        SL_PCT = float(_a.split("=", 1)[1])
        print(f"==> SL_PCT ueberschrieben: {SL_PCT}")
    if _a.startswith("--va-pct="):
        VA_PCT = float(_a.split("=", 1)[1])
        print(f"==> VA_PCT ueberschrieben: {VA_PCT}")
    if _a.startswith("--mountain-pct="):
        MIN_MOUNTAIN_PCT = float(_a.split("=", 1)[1])
        print(f"==> MIN_MOUNTAIN_PCT ueberschrieben: {MIN_MOUNTAIN_PCT}")
    if _a.startswith("--valley-rel="):
        VALLEY_REL = float(_a.split("=", 1)[1])
        print(f"==> VALLEY_REL ueberschrieben: {VALLEY_REL}")
    if _a.startswith("--establish="):
        MIN_ESTABLISH = int(_a.split("=", 1)[1])
        print(f"==> MIN_ESTABLISH ueberschrieben: {MIN_ESTABLISH}")
    if _a.startswith("--tol="):
        TOL = float(_a.split("=", 1)[1])
        print(f"==> TOL ueberschrieben: {TOL}")
    if _a.startswith("--reclaim-candles="):
        MIN_RECLAIM_CANDLES = int(_a.split("=", 1)[1])
        print(f"==> MIN_RECLAIM_CANDLES ueberschrieben: {MIN_RECLAIM_CANDLES}")
    if _a.startswith("--start="):
        START = _a.split("=", 1)[1]
        print(f"==> START ueberschrieben: {START}")
    if _a.startswith("--ende="):
        ENDE = _a.split("=", 1)[1]
        print(f"==> ENDE ueberschrieben: {ENDE}")
    if _a.startswith("--bounce="):
        MIN_RECLAIM_BOUNCE = int(_a.split("=", 1)[1])
        print(f"==> MIN_RECLAIM_BOUNCE ueberschrieben: {MIN_RECLAIM_BOUNCE}")
    if _a.startswith("--crv="):
        MIN_RECLAIM_CRV = float(_a.split("=", 1)[1])
        print(f"==> MIN_RECLAIM_CRV ueberschrieben: {MIN_RECLAIM_CRV}")
    if _a.startswith("--cooldown="):
        MIN_SIGNAL_ABSTAND_BARS = int(_a.split("=", 1)[1])
        print(f"==> MIN_SIGNAL_ABSTAND_BARS ueberschrieben: {MIN_SIGNAL_ABSTAND_BARS}")
    if _a.startswith("--anteil-tp1="):
        ANTEIL_TP1 = float(_a.split("=", 1)[1])
        print(f"==> ANTEIL_TP1 ueberschrieben: {ANTEIL_TP1}")
    if _a.startswith("--tp2-puffer="):
        TP2_PUFFER_PCT = float(_a.split("=", 1)[1])
        print(f"==> TP2_PUFFER_PCT ueberschrieben: {TP2_PUFFER_PCT}")
    if _a == "--sl-nachzug=0":
        print("==> SL-Nachzug wurde konsequent entfernt (kein Effekt mehr)")
    if _a == "--sl-be=1":
        print("==> SL-Breakeven wurde konsequent entfernt (kein Effekt mehr)")
    if _a.startswith("--trailing="):
        TRAILING_PCT = float(_a.split("=", 1)[1])
        print(f"==> TRAILING_PCT ueberschrieben: {TRAILING_PCT}")
    if _a == "--moves=1":
        TRADE_MOVES = True
        print("==> TRADE_MOVES aktiviert (SETUP C: Move-Trades)")

# ---------- 1) Daten ----------
con = duckdb.connect(str(DB_PATH), read_only=True)
df = con.execute(f"""
    SELECT time AT TIME ZONE 'UTC' AS ts, open, high, low, close, tick_volume
    FROM ohlcv_bars
    WHERE symbol='SILVER' AND timeframe='M15'
      AND time AT TIME ZONE 'UTC' >= DATE '{START}'
      AND time AT TIME ZONE 'UTC' <  DATE '{ENDE}'
    ORDER BY time
""").fetchdf()
con.close()
df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
df["idx"] = np.arange(len(df))

# ---------- 2) Pivots ----------
def find_pivots(d, n=PIVOT_LOOKBACK):
    """Zentrierte Pivot-Erkennung (Lookback n nach links UND rechts).

    Die DETEKTION nutzt weiterhin n Zukunfts-Bars (Pivot-Definition).
    Der Phasen-Loop gibt die Pivots aber erst mit Lag n bekannt (kausal) -
    die Pivot-MENGE bleibt identisch, nur die Bekanntgabe ist nachlaufend.
    """
    h, l = d["high"].values, d["low"].values
    hi, lo = pd.Series(h), pd.Series(l)
    is_hi = (hi == hi.rolling(2*n+1, center=True, min_periods=1).max()) & (hi.shift(n) < h) & (hi.shift(-n) < h)
    is_lo = (lo == lo.rolling(2*n+1, center=True, min_periods=1).min()) & (lo.shift(n) > l) & (lo.shift(-n) > l)
    is_hi[:n] = False; is_hi[-n:] = False
    is_lo[:n] = False; is_lo[-n:] = False
    piv = pd.DataFrame({
        "ts": d["ts"], "price": np.where(is_hi, h, np.where(is_lo, l, np.nan)),
        "typ": np.where(is_hi, "H", np.where(is_lo, "L", "")),
    })
    return piv[piv["typ"] != ""].copy()

piv = find_pivots(df.reset_index(drop=True), n=PIVOT_LOOKBACK).sort_values("ts").reset_index(drop=True)
print(f"Pivots (Lookback {PIVOT_LOOKBACK}): {len(piv)} | Candles: {len(df)}")

# ---------- 3) Schnittmengen-Linie (dominante Grenzen) ----------
def level_schnittmenge(prices, target_typ="H", band=DENSITY_BAND,
                       min_cluster=MIN_CLUSTER, erweiterung_pct=ERWEITERUNG_PCT):
    """
    Schnittmengen-Linie der extremen Spitzen-Ebene (Trader-Sicht).

    1. Einzel-Ausreisser (lokale Dichte < min_cluster, z.B. Fr-Tief 67.883)
       bilden KEIN Level.
    2. EXTREMER KERN: oberste (H) / tiefste (L) Spitzen-Gruppe mit
       >= min_cluster Treffern im Band.
    3. ERWEITERUNGS-POOL: Spitzen bis erweiterung_pct ueber/unter der
       Kern-Kante gehoeren zur Grenze (HH/LL <= 1% erweitert die Range).
    4. Linie = getrimmte Schnittmenge des Pools OHNE das absolute Extrem,
       damit die Linie nicht am hoechsten/niedrigsten Wert klebt, sondern
       in der Schnittmenge der Mehrheit liegt.
    """
    arr = np.array(prices, dtype=float)
    if not len(arr):
        return None
    # 1) lokale Dichte je Spitze (Anzahl Spitzen im Band)
    d = np.array([np.sum(np.abs(arr - x) <= band) for x in arr])
    m = d >= min_cluster
    if not m.any():
        return float(np.max(arr)) if target_typ == "H" else float(np.min(arr))
    sel = arr[m]
    # 2) extremer Kern: Spitzen im Band um das absolute Extrem der signifikanten
    ext = float(np.max(sel)) if target_typ == "H" else float(np.min(sel))
    kern = sel[np.abs(sel - ext) <= band]
    if not len(kern):
        kern = sel
    # 3) Erweiterungs-Pool: Kern-Kante +/- band, bis erweiterung_pct darueber/darunter
    if target_typ == "H":
        kante = float(np.min(kern))
        pool = sel[sel >= kante - band]
        pool = pool[pool <= kante * (1 + erweiterung_pct / 100.0)]
    else:
        kante = float(np.max(kern))
        pool = sel[sel <= kante + band]
        pool = pool[pool >= kante * (1 - erweiterung_pct / 100.0)]
    if not len(pool):
        pool = kern
    # 4) getrimmte Schnittmenge ohne das absolute Extrem
    if len(pool) > 1:
        if target_typ == "H":
            pool = pool[pool != np.max(pool)]
        else:
            pool = pool[pool != np.min(pool)]
    return float(np.mean(pool)) if len(pool) else float(np.mean(kern))


def n_touches(prices, level, band=DENSITY_BAND):
    """Anzahl Pivots innerhalb +/- band um ein Level."""
    if level is None or not prices:
        return 0
    return int(np.sum(np.abs(np.array(prices) - level) <= band))


def _linie(prices, typ):
    """Schnittmengen-Linie ueber ein GLEITENDES Pivot-Fenster (robust).

    Nutzt nur die letzten FENSTER_PIVOTS Pivots je Seite, damit die Linie
    dem aktuellen Preisniveau folgt und nicht an alten Extremen einfriert
    (z.B. Phase 05.06-27.08: U=72.88, Kurs pendelte 55-70 -> nie etabliert).
    Bei kurzen Phasen (<= FENSTER_PIVOTS Pivots) identisch zur vollen Linie.
    """
    if prices is None or not len(prices):
        return None
    w = prices if len(prices) <= FENSTER_PIVOTS else prices[-FENSTER_PIVOTS:]
    return level_schnittmenge(w, typ)


def _final_level(schnitt, birth, typ):
    """Schnittmengen-Linie, verstaerkt um die Geburtszone."""
    if schnitt is None:
        return birth
    if birth is None:
        return schnitt
    return max(schnitt, birth) if typ == "H" else min(schnitt, birth)


def _final_level_bestaetigt(schnitt, birth, typ, conf_ts):
    """Finale Grenze (Variante C): Geburtszone NUR uebernehmen, wenn real getestet.

    conf_ts ist der Zeitpunkt des ersten Pivots innerhalb DENSITY_BAND um die
    Geburtszone (None = nie bestaetigt). Ohne Bestaetigung bleibt die finale
    Linie die reine Schnittmenge (keine Vermutung, dass der Kurs zurueckkehrt).
    """
    if schnitt is None:
        return birth
    if birth is None or conf_ts is None:
        return schnitt
    return max(schnitt, birth) if typ == "H" else min(schnitt, birth)


def _birth_level(birth, typ):
    """FIX Birth: Geburtszone nur mit signifikanten Niveaus (>= MIN_CLUSTER).

    Analog level_schnittmenge ("Einzel-Ausreisser bilden KEIN Level"):
    birth_h/birth_l duerfen NICHT am Max/Min eines einzelnen Pivots kleben.
    Ein einzelner Spike im Ausbruchs-Move (z.B. 72.950 am 05.06) wuerde sonst
    die Obergrenze der neuen Phase fuer Wochen auf einen toten Wert pinnen.
    Rueckgabe: Level nur, wenn >= MIN_CLUSTER Pivots im DENSITY_BAND liegen.
    """
    if birth is None or len(birth) == 0:
        return None
    prices = birth.loc[birth["typ"] == typ, "price"].values.astype(float)
    if not len(prices):
        return None
    d = np.array([np.sum(np.abs(prices - x) <= DENSITY_BAND) for x in prices])
    sel = prices[d >= MIN_CLUSTER]
    if not len(sel):
        return None
    return float(np.max(sel)) if typ == "H" else float(np.min(sel))


def _last_grenz_kontakt(h_prices, h_ts, l_prices, l_ts, U_final, L_final, tol=0.0):
    """
    Letzter Pivot, der die finale Grenzlinie tatsaechlich erreicht hat.

    - OBEN: H-Pivot >= U_final - tol
    - UNTEN: L-Pivot <= L_final + tol
    Rueckgabe: (ts, price, typ) des spaetesten Kontakts oder (None, None, None).
    """
    best_ts = best_pr = best_typ = None
    if U_final is not None:
        for ts, pr in zip(h_ts, h_prices):
            if pr >= U_final - tol and (best_ts is None or ts > best_ts):
                best_ts, best_pr, best_typ = ts, pr, "H"
    if L_final is not None:
        for ts, pr in zip(l_ts, l_prices):
            if pr <= L_final + tol and (best_ts is None or ts > best_ts):
                best_ts, best_pr, best_typ = ts, pr, "L"
    return best_ts, best_pr, best_typ


# ---------- 3b) VOLUME-PROFIL (POC/VAH/VAL + Multi-Mountain) ----------
def build_volume_profile(sub, num_bins=NUM_BINS):
    """Baut das Volume-Profil (Volumen pro Preis-Bin) fuer ein Phasen-DataFrame.

    Jede Bar verteilt ihr tick_volume proportional ueber ihren High-Low-
    Bereich auf die ueberlappenden Bins. Vektorisiert ueber die Bar-Anteile.
    """
    if sub.empty:
        return None
    pmin, pmax = float(sub["low"].min()), float(sub["high"].max())
    if pmax <= pmin:
        return None
    edges = np.linspace(pmin, pmax, num_bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(num_bins)

    lows = sub["low"].values.astype(float)
    highs = sub["high"].values.astype(float)
    vols = sub["tick_volume"].values.astype(float)
    for lo, hi, v in zip(lows, highs, vols):
        if hi <= lo or v <= 0:
            continue
        lo_b = int(np.clip(np.searchsorted(edges, lo, side="right") - 1, 0, num_bins - 1))
        hi_b = int(np.clip(np.searchsorted(edges, hi, side="left") - 1, 0, num_bins - 1))
        if lo_b == hi_b:
            vol[lo_b] += v
        else:
            # proportionaler Anteil je Bin
            ov = np.array([
                max(0.0, min(hi, edges[b + 1]) - max(lo, edges[b]))
                for b in range(lo_b, hi_b + 1)
            ])
            tot = ov.sum()
            if tot > 0:
                vol[lo_b:hi_b + 1] += v * ov / tot
    return {"centers": centers, "edges": edges, "vol": vol, "pmin": pmin, "pmax": pmax}


def smooth_vol(vol, win=SMOOTH_WIN):
    """Glaettet das Histogramm (gleitender Mittelwert)."""
    if win <= 1 or len(vol) < win:
        return vol.astype(float)
    return np.convolve(vol, np.ones(win) / win, mode="same")


def find_mountains(vol_s, min_pct=MIN_MOUNTAIN_PCT, valley_rel=VALLEY_REL):
    """Findet getrennte 'Berge' im (geglaetteten) Volume-Profil.

    Berg = Bereich zwischen signifikanten Taellern. Ein Tal trennt zwei
    Berge, wenn sein Volumen < valley_rel * min(linker, rechter Peak).
    Nur Berge mit Peak >= min_pct % des dominierenden Peaks zaehlen.
    Rueckgabe: Liste von (start_idx, peak_idx, end_idx), sortiert nach
    Volumen absteigend.
    """
    n = len(vol_s)
    if n < 3:
        return []
    mountains = []
    start = 0
    for i in range(1, n - 1):
        if vol_s[i] <= vol_s[i - 1] and vol_s[i] < vol_s[i + 1]:
            left_peak = float(np.max(vol_s[start:i + 1]))
            right_peak = float(np.max(vol_s[i:n]))
            threshold = min(left_peak, right_peak) * valley_rel
            if vol_s[i] < threshold:
                p_idx = start + int(np.argmax(vol_s[start:i + 1]))
                if vol_s[start:i + 1].max() > 0:
                    mountains.append((start, p_idx, i))
                start = i
    p_idx = start + int(np.argmax(vol_s[start:n]))
    if vol_s[start:n].max() > 0:
        mountains.append((start, p_idx, n - 1))

    if not mountains:
        return []
    max_vol = max(vol_s[p] for _, p, _ in mountains)
    mountains = [m for m in mountains if vol_s[m[1]] >= max_vol * min_pct / 100.0]
    mountains.sort(key=lambda m: -vol_s[m[1]])
    return mountains


def va_for_mountain(vol_s, edges, mountain, dominant_peak, va_pct=VA_PCT):
    """VAH/VAL/POC fuer einen Berg (va_pct-Value-Area um den POC).

    dominant_peak = Bin-Index des volumenstaerksten Bergs (fuer peak_share_pct).
    """
    s, p, e = mountain
    poc = float((edges[p] + edges[p + 1]) / 2)
    total = float(vol_s[s:e + 1].sum())
    target = total * va_pct
    lo, hi = p, p
    acc = float(vol_s[p])
    while acc < target and (lo > s or hi < e):
        down = float(vol_s[lo - 1]) if lo > s else -1.0
        up = float(vol_s[hi + 1]) if hi < e else -1.0
        if down >= up and down >= 0:
            lo -= 1
            acc += down
        elif up >= 0:
            hi += 1
            acc += up
        else:
            break
    share = 100.0
    if dominant_peak is not None and vol_s[dominant_peak] > 0:
        share = float(vol_s[p] / vol_s[dominant_peak] * 100.0)
    return {
        "poc": poc,
        "val": float(edges[lo]),
        "vah": float(edges[hi + 1]),
        "vol": total,
        "peak_share_pct": share,
    }


def compute_volume_zone(sub):
    """Komplettes Volume-Zonen-Paket fuer eine Phase (Variante A, Huelle).

    Rueckgabe-Dict:
      profile       : rohes Profil (centers/edges/vol)
      mountains     : Liste [(s, p, e)]
      peaks         : Liste von Berg-Dicts {poc, val, vah, vol, peak_share_pct}
      U_zone        : hoechste VAH aller Berge
      L_zone        : tiefste  VAL aller Berge
      POC           : POC des volumenstaerksten Bergs
      n_mountains   : Anzahl signifikanter Berge
    """
    prof = build_volume_profile(sub)
    if prof is None:
        return None
    vol_s = smooth_vol(prof["vol"])
    mountains = find_mountains(vol_s)
    if not mountains:
        return None
    dominant_peak = mountains[0][1]
    peaks = []
    for m in mountains:
        va = va_for_mountain(vol_s, prof["edges"], m, dominant_peak)
        peaks.append(va)
    # Huelle (Variante A)
    U_zone = max(p["vah"] for p in peaks)
    L_zone = min(p["val"] for p in peaks)
    POC = peaks[0]["poc"]  # volumenstaerkster Berg
    return {
        "profile": prof,
        "mountains": mountains,
        "peaks": peaks,
        "U_zone": U_zone,
        "L_zone": L_zone,
        "POC": POC,
        "n_mountains": len(peaks),
    }


# ---------- 4) Segmentierung: Range-Phasen mit entscheidendem Ausbruch ----------
piv_typ = dict(zip(piv["ts"], piv["typ"]))
df["is_pivot"] = df["ts"].isin(piv_typ)

phases = []
moves = []
i = 0
n = len(df)
prev_ende_ts = None   # Ende der Vor-Phase -> Geburtszone der neuen Phase
while i < n:
    h_acc, l_acc = [], []          # Pivot-Preise der Phase
    h_ts, l_ts = [], []            # Pivot-Zeitpunkte der Phase
    est_idx = None                 # Candle-Index der Etablierung (>= MIN_ESTABLISH Anker gesamt)
    brk_idx, brk_dir = None, None  # bestaetigter Ausbruch
    hist_U, hist_L = [], []        # Level-Historie: (ts, angewandter Linienwert)
    last_U = last_L = None         # letzter aufgezeichneter Linienwert
    U_conf_ts = L_conf_ts = None   # Variante C: 1. realer Test der Geburtszone

    # Geburtszone = Preise zwischen Vorphasen-Ende und Phasenstart.
    # Der Ausbruchsbereich wird zur Widerstands-/Unterstuetzungszone der neuen
    # Phase: z.B. Phase 2 erbt das Hoch 69.684 (Di 02:45) als Widerstand -
    # die Di-Rally bis 69.27 bleibt dadurch ein Retest, kein Phasenende.
    if prev_ende_ts is not None:
        # L3-Fix (KAUSAL): Nur Pivots in der Geburtszone, die zum Phasenstart
        # bereits BESTAETIGT waren (Lag PIVOT_LOOKBACK). Unbestaetigte Pivots
        # der letzten PIVOT_LOOKBACK Bars vor dem Phasenstart sind ausgeschlossen.
        cutoff_birth = df["ts"].iloc[i] - pd.Timedelta(minutes=PIVOT_LOOKBACK * 15)
        birth = piv[(piv["ts"] > prev_ende_ts) & (piv["ts"] <= cutoff_birth)]
        # FIX Birth: nur signifikante Niveaus (>= MIN_CLUSTER) vererben.
        birth_h = _birth_level(birth, "H")
        birth_l = _birth_level(birth, "L")
    else:
        birth_h = birth_l = None

    phasen_start = df["ts"].iloc[i]   # FIX Doppelzaehlung: Referenz fuer Pivot-Skip
    j = i
    while j < n:
        row = df.iloc[j]
        ts = row["ts"]
        # L1/L2-Fix (KAUSAL): Ein Pivot bei Bar j-PIVOT_LOOKBACK wird erst in
        # Bar j bekannt gegeben. Die Pivot-MENGE bleibt identisch - nur der
        # Bekanntgabezeitpunkt ist um PIVOT_LOOKBACK Bars nachlaufend.
        if j - PIVOT_LOOKBACK >= 0 and df["is_pivot"].iloc[j - PIVOT_LOOKBACK]:
            t_prev = df["ts"].iloc[j - PIVOT_LOOKBACK]
            # FIX Doppelzaehlung: Ein Pivot VOR dem Phasenstart gehoert zur
            # Vor-Phase (er wurde dort ueber den Lag bereits aufgenommen und
            # war meist der letzte Grenz-Kontakt). Ohne diesen Skip faende die
            # Phasen-Ende-Suche ihn als "letzten Touch" -> Ende < Start
            # (degenerierte Phasen, z.B. "Fri 14:45 -> 14:15").
            if t_prev < phasen_start:
                pass
            elif piv_typ[t_prev] == "H":
                pv = df["high"].iloc[j - PIVOT_LOOKBACK]
                h_acc.append(pv); h_ts.append(t_prev)
                # Variante C: erster realer Test der OBEN-Geburtszone
                # (H-Pivot innerhalb DENSITY_BAND unterhalb der Zone)
                if U_conf_ts is None and birth_h is not None and abs(pv - birth_h) <= DENSITY_BAND:
                    U_conf_ts = t_prev
            else:
                pv = df["low"].iloc[j - PIVOT_LOOKBACK]
                l_acc.append(pv); l_ts.append(t_prev)
                # Variante C: erster realer Test der UNTEN-Geburtszone
                if L_conf_ts is None and birth_l is not None and abs(pv - birth_l) <= DENSITY_BAND:
                    L_conf_ts = t_prev

        U = _linie(h_acc, "H")
        L = _linie(l_acc, "L")

        # Etablierung: Zone eroeffnet ab MIN_ESTABLISH ANKERPUNKTE GESAMT (H+L).
        # FIX (Trader): nicht 3 je High UND 3 je Low, sondern 3 insgesamt.
        if est_idx is None and U is not None and L is not None \
                and n_touches(h_acc, U) + n_touches(l_acc, L) >= MIN_ESTABLISH:
            est_idx = j

        # Historie AB Etablierung: angewandte Linienwerte (inkl. Geburtszone)
        # nur bei signifikanter Verschiebung (> SHIFT_TOL) festhalten.
        # So zeigt die Entwicklung nur echte Zonen-Aenderungen, kein Rauschen
        # und keine Einzel-Ausreisser vor der Etablierung.
        if est_idx is not None:
            U_applied = _final_level(U, birth_h, "H")
            L_applied = _final_level(L, birth_l, "L")
            if U_applied is not None and (last_U is None or abs(U_applied - last_U) > SHIFT_TOL):
                hist_U.append((ts, U_applied)); last_U = U_applied
            if L_applied is not None and (last_L is None or abs(L_applied - last_L) > SHIFT_TOL):
                hist_L.append((ts, L_applied)); last_L = L_applied

        # Ausbruch-Check NUR nach Etablierung UND Mindest-Candles in der Phase.
        # Referenz: eigene Schnittmengen-Linie, verstaerkt um die Geburtszone.
        if est_idx is not None and (j - i) >= MIN_PHASE_CANDLES and j + 1 < n:
            h_ref = U if U is not None else None
            l_ref = L if L is not None else None
            if birth_h is not None:
                h_ref = max(h_ref, birth_h) if h_ref is not None else birth_h
            if birth_l is not None:
                l_ref = min(l_ref, birth_l) if l_ref is not None else birth_l
            if h_ref is not None and row["close"] > h_ref + TOL and df["close"].iloc[j + 1] > h_ref + TOL:
                brk_idx, brk_dir, brk_kante = j, "up", h_ref
                break
            if l_ref is not None and row["close"] < l_ref - TOL and df["close"].iloc[j + 1] < l_ref - TOL:
                brk_idx, brk_dir, brk_kante = j, "down", l_ref
                break
        j += 1

    # Finale Grenzen: Schnittmengen-Linie, Geburtszone nur bei realem Test
    U_final = _final_level_bestaetigt(_linie(h_acc, "H"), birth_h, "H", U_conf_ts)
    L_final = _final_level_bestaetigt(_linie(l_acc, "L"), birth_l, "L", L_conf_ts)

    if brk_idx is None:
        # Phase laeuft bis Datenende
        ende_ts = df["ts"].iloc[n - 1]
        phases.append({
            "start": df["ts"].iloc[i], "ende": ende_ts,
            "U_final": U_final, "L_final": L_final,
            "h_prices": h_acc, "l_prices": l_acc,
            "h_ts": list(h_ts), "l_ts": list(l_ts),
            "birth_h": birth_h, "birth_l": birth_l,
            "U_conf_ts": U_conf_ts, "L_conf_ts": L_conf_ts,
            "U_ts": h_ts[-1] if h_ts else None, "L_ts": l_ts[-1] if l_ts else None,
            "U_hist": hist_U, "L_hist": hist_L,
            "break_dir": None, "brk_idx": None, "brk_kante": None,
        })
        break

    # Phasen-Ende = letzter Touch der GEGENgrenze vor dem Ausbruch
    # (defensiv: nur Pivots >= Phasenstart, sonst Ende < Start moeglich)
    if brk_dir == "down":
        t_arr = np.array([abs(x - U_final) <= TOL_TOUCH and t >= phasen_start
                          for x, t in zip(h_acc, h_ts)]) if h_acc else np.array([], dtype=bool)
        if t_arr.any():
            k = int(np.where(t_arr)[0][-1])
            ende_ts, ende_pr = h_ts[k], h_acc[k]
        else:
            ende_ts, ende_pr = df["ts"].iloc[i], None
        moves.append({"dir": "down", "von_ts": ende_ts, "von_pr": ende_pr,
                      "bis_ts": df["ts"].iloc[brk_idx], "bis_pr": float(df["low"].iloc[brk_idx])})
    else:
        t_arr = np.array([abs(x - L_final) <= TOL_TOUCH and t >= phasen_start
                          for x, t in zip(l_acc, l_ts)]) if l_acc else np.array([], dtype=bool)
        if t_arr.any():
            k = int(np.where(t_arr)[0][-1])
            ende_ts, ende_pr = l_ts[k], l_acc[k]
        else:
            ende_ts, ende_pr = df["ts"].iloc[i], None
        moves.append({"dir": "up", "von_ts": ende_ts, "von_pr": ende_pr,
                      "bis_ts": df["ts"].iloc[brk_idx], "bis_pr": float(df["high"].iloc[brk_idx])})

    # Nur Pivots bis zum Phasen-Ende verwenden (frisch berechnete Grenzen)
    h_clean = [p for p, t in zip(h_acc, h_ts) if t <= ende_ts]
    l_clean = [p for p, t in zip(l_acc, l_ts) if t <= ende_ts]
    h_clean_ts = [t for t, p in zip(h_ts, h_acc) if t <= ende_ts]
    l_clean_ts = [t for t, p in zip(l_ts, l_acc) if t <= ende_ts]
    phases.append({
        "start": df["ts"].iloc[i], "ende": ende_ts,
        "U_final": _final_level_bestaetigt(_linie(h_clean, "H"), birth_h, "H", U_conf_ts),
        "L_final": _final_level_bestaetigt(_linie(l_clean, "L"), birth_l, "L", L_conf_ts),
        "h_prices": h_clean, "l_prices": l_clean,
        "h_ts": h_clean_ts, "l_ts": l_clean_ts,
        "birth_h": birth_h, "birth_l": birth_l,
        "U_conf_ts": U_conf_ts, "L_conf_ts": L_conf_ts,
        "U_ts": h_ts[len(h_clean) - 1] if h_clean else None,
        "L_ts": l_ts[len(l_clean) - 1] if l_clean else None,
        "U_hist": hist_U, "L_hist": hist_L,
        "break_dir": brk_dir, "brk_idx": brk_idx, "brk_kante": brk_kante,
    })
    prev_ende_ts = ende_ts
    i = brk_idx

# ---------- 4b) L4: DATENENDE-FINALIZE (Regel 7, D1-Variante) ----------
# Eine etablierte Phase, die OHNE 2-Close-Ausbruch bis zum Datenende laeuft,
# endet am letzten Pivot, der die finale Grenzlinie tatsaechlich erreicht hat
# (H-Pivot >= OBEN bzw. L-Pivot <= UNTEN). Danach folgt der Move in die
# Gegenrichtung. Beispiele:
#   Phase 1: letzter OBEN-Kontakt Di 25.08 02:00 (High 69.924) -> Crash-Move
#   Phase 2: letzter OBEN-Kontakt Do 27.08 19:00 (High 69.714) -> Dreh nach unten
# WICHTIG (KAUSALITAET): Dieser Schritt ist bewusst POST-HOC (erst am
# Datenende ausfuehrbar). Er ist NICHT kausal umformulierbar - im Replay
# "springt" die laufende Phase am letzten Bar auf ihren letzten Kontakt.
# Fuer identische Ergebnisse mit dem Rueckblick-Skript ist genau diese
# D1-Variante noetig (ehrliche Forward-Tests wuerden stattdessen D2 nutzen).
if phases and phases[-1]["break_dir"] is None:
    p = phases[-1]
    t_last, pr_last, typ_last = _last_grenz_kontakt(
        p["h_prices"], p["h_ts"], p["l_prices"], p["l_ts"],
        p["U_final"], p["L_final"], GRENZ_KONTAKT_TOL)
    if t_last is not None and t_last < p["ende"]:
        h_ok = [k for k, t in enumerate(p["h_ts"]) if t <= t_last]
        l_ok = [k for k, t in enumerate(p["l_ts"]) if t <= t_last]
        p["h_prices"] = [p["h_prices"][k] for k in h_ok]
        p["h_ts"] = [p["h_ts"][k] for k in h_ok]
        p["l_prices"] = [p["l_prices"][k] for k in l_ok]
        p["l_ts"] = [p["l_ts"][k] for k in l_ok]
        p["ende"] = t_last
        p["U_final"] = _final_level_bestaetigt(_linie(p["h_prices"], "H"), p["birth_h"], "H", p["U_conf_ts"])
        p["L_final"] = _final_level_bestaetigt(_linie(p["l_prices"], "L"), p["birth_l"], "L", p["L_conf_ts"])
        p["U_ts"] = p["h_ts"][-1] if p["h_ts"] else None
        p["L_ts"] = p["l_ts"][-1] if p["l_ts"] else None
        p["U_hist"] = [(t, v) for t, v in p["U_hist"] if t <= t_last]
        p["L_hist"] = [(t, v) for t, v in p["L_hist"] if t <= t_last]
        # Move nach dem letzten Grenz-Kontakt bis zum Datenende (Gegenrichtung)
        sub = df[df["ts"] > t_last]
        if len(sub) and typ_last == "H":
            k = sub["low"].idxmin()
            moves.append({"dir": "down", "von_ts": t_last, "von_pr": float(pr_last),
                          "bis_ts": sub.loc[k, "ts"], "bis_pr": float(sub.loc[k, "low"])})
        elif len(sub) and typ_last == "L":
            k = sub["high"].idxmax()
            moves.append({"dir": "up", "von_ts": t_last, "von_pr": float(pr_last),
                          "bis_ts": sub.loc[k, "ts"], "bis_pr": float(sub.loc[k, "high"])})

# ---------- 5) Candle-Statistik je Phase ----------
for p in phases:
    mask = (df["ts"] >= p["start"]) & (df["ts"] <= p["ende"])
    p["n_candles"] = int(mask.sum())
    p["handels_h"] = p["n_candles"] * 15 / 60
    p["i_start"] = int(df.loc[mask, "idx"].min()) if p["n_candles"] else 0
    p["i_ende"] = int(df.loc[mask, "idx"].max()) if p["n_candles"] else 0
    p["touches_h"] = len(p["h_prices"])
    p["touches_l"] = len(p["l_prices"])
    p["close_h"] = n_touches(p["h_prices"], p["U_final"])
    p["close_l"] = n_touches(p["l_prices"], p["L_final"])
    p["spread"] = (p["U_final"] - p["L_final"]) if (p["U_final"] and p["L_final"]) else 0.0
    p["spread_pct"] = p["spread"] / p["L_final"] * 100.0 if p["L_final"] else 0.0
    p["handelbar"] = (p["touches_h"] >= MIN_TOUCHES and p["touches_l"] >= MIN_TOUCHES
                      and p["n_candles"] >= MIN_CANDLES and p["spread_pct"] >= MIN_SPREAD_PCT)
    # Entwicklungs-Historie: Startposition (erste etablierte Linie) + Verschiebungen
    p["U_init"] = p["U_hist"][0][1] if p["U_hist"] else p["U_final"]
    p["L_init"] = p["L_hist"][0][1] if p["L_hist"] else p["L_final"]
    p["n_U_shifts"] = len(p["U_hist"]) - 1 if len(p["U_hist"]) > 1 else 0
    p["n_L_shifts"] = len(p["L_hist"]) - 1 if len(p["L_hist"]) > 1 else 0
    # Variante C: Projektionswert = Geburtszone, wenn sie die finale Grenze bestimmt
    p["U_proj_val"] = (p["birth_h"] if (p["birth_h"] is not None and p["U_final"] is not None
                                        and abs(p["U_final"] - p["birth_h"]) < 1e-9) else None)
    p["L_proj_val"] = (p["birth_l"] if (p["birth_l"] is not None and p["L_final"] is not None
                                        and abs(p["L_final"] - p["birth_l"]) < 1e-9) else None)

# ---------- 5a) VOLUME-ZONEN je Phase (POC/VAH/VAL + Multi-Mountain) ----------
for p in phases:
    mask = (df["ts"] >= p["start"]) & (df["ts"] <= p["ende"])
    sub = df[mask]
    vz = compute_volume_zone(sub)
    if vz is None:
        p["vol_zone"] = None
    else:
        p["vol_zone"] = vz
        p["U_zone"] = vz["U_zone"]   # OBEN aus Volume (hoechste VAH)
        p["L_zone"] = vz["L_zone"]   # UNTEN aus Volume (tiefste VAL)
        p["POC"] = vz["POC"]         # MITTE aus Volume (POC dominant)
        p["n_berge"] = vz["n_mountains"]
        p["zone_breite"] = vz["U_zone"] - vz["L_zone"]

# ---------- 5b) UEBERSICHT (erweiterter Testbereich ab 10.08.) ----------
# Regression-Check gegen die 21.08.-Trader-Sicht ist hier bewusst aus: Der
# erweiterte Bereich erzeugt zusaetzliche Vor-Phasen. Die Phase(n) ab 21.08.
# muessen weiterhin der Trader-Sicht entsprechen.
# STAND 31.08.2026 (Fixes: MIN_ESTABLISH-Summe + Birth-Cluster + MIN_PHASE_CANDLES):
#   Phase 1 = 21.08 05:00 -> 25.08 02:00 (U 69.914 / L 68.370) - Level identisch
#   zur alten Referenz, nur Start 5h spaeter.
#   Die alte Phase-2-Referenz "25.08 04:30 -> 27.08 19:00" existiert nicht mehr:
#   sie wird jetzt in mehrere Phasen 10-14 aufgesplittet (kein 1-Monats-Zombie
#   mehr). Neue Phase 2 = 25.08 04:30 -> 25.08 15:45 (U 68.220 / L 67.544),
#   OBEN-Geburtszone ohne Bestaetigung (NIE).
_erwartet = [
    {"start": "2026-08-21 05:00", "ende": "2026-08-25 02:00", "U": 69.914, "L": 68.370},
    {"start": "2026-08-25 04:30", "ende": "2026-08-25 15:45", "U": 68.220, "L": 67.544},
]
print("\n=== VERIFIKATION (Referenz 21.08.-Sicht) ===")
_fmt = lambda t: t.strftime("%Y-%m-%d %H:%M")
_relevant = [p for p in phases if p["start"] >= pd.Timestamp("2026-08-21 00:00")]
for k, p in enumerate(_relevant[:2]):
    e = _erwartet[k]
    ok = (_fmt(p["start"]) == e["start"] and _fmt(p["ende"]) == e["ende"]
          and p["U_final"] is not None and abs(p["U_final"] - e["U"]) < 0.01
          and p["L_final"] is not None and abs(p["L_final"] - e["L"]) < 0.01)
    if e.get("U_conf") is not None:
        ok = ok and p.get("U_conf_ts") is not None and _fmt(p["U_conf_ts"]) == e["U_conf"]
    print(f"Phase {k+1} (ab 21.08): {'OK ' if ok else 'ABWEICHUNG'} "
          f"{_fmt(p['start'])} -> {_fmt(p['ende'])} "
          f"| OBEN {p['U_final']:.3f} (erw. {e['U']}) | UNTEN {p['L_final']:.3f} (erw. {e['L']})")
    if e.get("U_conf"):
        _c = p.get("U_conf_ts")
        print(f"    OBEN-Geburtszone bestaetigt: {_fmt(_c) if _c is not None else 'NIE'} (erw. {e['U_conf']})")
print(f"RESULTAT: {len(phases)} Phasen gesamt, {len(_relevant)} ab 21.08. (Referenz-Abgleich oben)")

# ---------- 5c) SETUP B: RECLAIM/FAKEOUT-SIGNALE (Patrick Nill, P1) ----------
# Patricks bevorzugtes Setup: Der Kurs sticht kurz aus einer etablierten
# Zone aus (Fakeout, Liquiditaet/Stop-Jagd) und kehrt sofort zurueck
# (Reclaim). Einstieg NACH Bestaetigung, Ziel = POC (Fair Value), SL
# hinter der Kante.
#
# KAUSALITAET: Fuer jede Kandidaten-Bar wird das Volume-Profil NUR bis zu
# dieser Bar berechnet (laufende Zone - kein Lookahead). Die finale
# Phasen-Zone dient nur als Kandidaten-Screening; Bars, die nur die
# laufende, nie die finale Kante erreichen, gelten als "Zone noch nicht
# etabliert" und werden uebersprungen (passt zu Patricks 3-Touch-Regel).
def _laufende_zone(df, p, k):
    """Volume-Zone kausal bis Bar k (inklusive)."""
    return compute_volume_zone(df.iloc[p["i_start"]:k + 1])


def _bounce_nr(h_prices, h_ts, l_prices, l_ts, ts_k, U, L):
    """Bounce-Nummer je Seite: Anzahl Pivots bis ts_k an der Kante + 1."""
    n_h = 1 + sum(1 for pr, t in zip(h_prices, h_ts)
                  if t <= ts_k and abs(pr - U) <= DENSITY_BAND)
    n_l = 1 + sum(1 for pr, t in zip(l_prices, l_ts)
                  if t <= ts_k and abs(pr - L) <= DENSITY_BAND)
    return n_h, n_l


def _aufloesen(df, s, sl_pct=None, anteil_tp1=ANTEIL_TP1,
               trailing_pct=TRAILING_PCT):
    """Loest beide Haelfte eines Setup-B-Signals VOLLSTAENDIG auf.

    Regeln (User-Vorgabe):
    1) SL bei Entry: SL_PCT (0.45%) vom Einstiegspreis
       (SHORT: entry*(1+p), LONG: entry*(1-p))
    2) KEIN SL-NACHZUG: Der SL der Restcharge bleibt am Einstiegs-SL, damit
       TP2 (Box-Ende) trotz Pullbacks erreichbar bleibt (Trader-Punkt 2).
    3) Alle Trades werden aufgeloest: Fenster bis Datenende; falls eine
       Haelfte offen bleibt, Close zum letzten Kurs.
    Konservativ: SL und TP in derselben Bar -> SL zuerst.

    VARIANTEN:
    - anteil_tp1: % der Position, die bei TP1 (POC) geschlossen wird
      (50 = 50/50, 100 = alles bei TP1, kein Runner).
    - trailing_pct > 0: TRAILING-MODUS statt festem TP1/TP2. Der SL folgt
      dem Preis mit X% Abstand vom letzten Extrem (SHORT: ueber dem
      hoechsten High, LONG: unter dem tiefsten Low) und zieht nur nach
      (Ratchet). Exit, sobald der Kurs den Trail-SL beruehrt; sonst Close
      am Datenende.

    Rueckgabe-Dict mit r1/r2 (R-Multiple je Haelfte), exit1/exit2,
    pnl, r_mult (gewichtetes R), resultat, tp1_hit, tp2_hit.
    """
    if sl_pct is None:
        sl_pct = SL_PCT
    e_bar = s["einstieg_bar"]
    entry = s["einstieg_preis"]
    typ = s["typ"]
    tp1, tp2, poc = s["tp1"], s["tp2"], s["POC"]
    p = sl_pct / 100.0
    if typ == "SHORT":
        sl_init = entry * (1 + p)
    else:
        sl_init = entry * (1 - p)
    hi = df["high"].values[e_bar:]
    lo = df["low"].values[e_bar:]
    cl = df["close"].values[e_bar:]
    n = len(hi)
    risk = abs(sl_init - entry)
    if risk <= 0:
        risk = 1e-9

    def _first(mask):
        return int(np.argmax(mask)) if mask.any() else n

    def _r(exit_price):
        return ((entry - exit_price) / risk if typ == "SHORT"
                else (exit_price - entry) / risk)

    # --- VARIANTE TRAILING: kein festes TP1/TP2, SL folgt dem Preis ---
    if trailing_pct > 0:
        tr = trailing_pct / 100.0
        sl = sl_init
        ext = entry
        grund = "ENDE"
        exit_pr = float(cl[-1])
        for k2 in range(n):
            if typ == "SHORT":
                if hi[k2] >= sl:
                    exit_pr, grund = float(sl), "TRAIL"
                    break
                ext = max(ext, float(hi[k2]))
                sl = max(sl, ext * (1 + tr))
            else:
                if lo[k2] <= sl:
                    exit_pr, grund = float(sl), "TRAIL"
                    break
                ext = min(ext, float(lo[k2]))
                sl = min(sl, ext * (1 - tr))
        r = _r(exit_pr)
        return {"r1": r, "r2": r, "exit1": exit_pr, "exit2": exit_pr,
                "grund1": grund, "grund2": grund,
                "pnl": r * risk, "r_mult": r,
                "resultat": ("GEWONNEN" if r > 1e-9
                             else ("VERLOREN" if r < -1e-9 else "NEUTRAL")),
                "tp1_hit": False, "tp2_hit": False,
                "sl_hit1": grund == "TRAIL", "sl_hit2": grund == "TRAIL",
                "sl_init": sl_init}

    if typ == "SHORT":
        t1 = _first(lo <= tp1)
        t2 = _first(lo <= tp2)
        t_sl_i = _first(hi >= sl_init)
    else:
        t1 = _first(hi >= tp1)
        t2 = _first(hi >= tp2)
        t_sl_i = _first(lo <= sl_init)

    # --- Haelfte 1: TP1 (POC) ---
    if t1 < t_sl_i:
        r1, ex1, g1 = _r(tp1), tp1, "TP1"
    elif t_sl_i < t1:
        r1, ex1, g1 = -1.0, sl_init, "SL"
    elif t_sl_i < n:                  # gleiche Bar: konservativ SL zuerst
        r1, ex1, g1 = -1.0, sl_init, "SL"
    else:                             # weder TP1 noch SL erreicht
        r1, ex1, g1 = _r(cl[-1]), cl[-1], "ENDE"

    # --- Haelfte 2: TP2 (Box-Ende); SL bleibt am Einstiegs-SL (KEIN Nachzug) ---
    # Der Runner behaelt den Entry-SL, damit Pullbacks ihn nicht vorzeitig
    # ausstoppen und TP2 (Box-Ende) trotzdem erreichbar bleibt.
    sl2 = sl_init
    t_sl2 = t_sl_i
    if t2 < t_sl2:
        r2, ex2, g2 = _r(tp2), tp2, "TP2"
    elif t_sl2 < n:
        r2, ex2, g2 = _r(sl2), sl2, "SL"
    else:
        r2, ex2, g2 = _r(cl[-1]), cl[-1], "ENDE"

    _w1 = anteil_tp1 / 100.0
    _w2 = 1.0 - _w1
    if _w2 <= 0:
        r2, g2 = 0.0, "-"   # ex2 bleibt gefuellt (nur Gewicht 0)
    r_mult = _w1 * r1 + _w2 * r2
    pnl = r_mult * risk
    resultat = ("GEWONNEN" if r_mult > 1e-9
                else ("VERLOREN" if r_mult < -1e-9 else "NEUTRAL"))
    return {"r1": r1, "r2": r2, "exit1": ex1, "exit2": ex2,
            "grund1": g1, "grund2": g2,
            "pnl": pnl, "r_mult": r_mult, "resultat": resultat,
            "tp1_hit": g1 == "TP1", "tp2_hit": g2 == "TP2",
            "sl_hit1": g1 == "SL", "sl_hit2": g2 == "SL",
            "sl_init": sl_init}


def find_reclaim_signals(df, p, min_candles=MIN_RECLAIM_CANDLES,
                         min_bounce=MIN_RECLAIM_BOUNCE, min_crv=MIN_RECLAIM_CRV,
                         cooldown_bars=MIN_SIGNAL_ABSTAND_BARS):
    """Setup-B-Signale (Reclaim/Fakeout) fuer eine Phase - kausal.

    OBERKANTE (SHORT):  high[k] > U_laufend UND close[k] <= U_laufend
                        (Reclaim in derselben Bar) -> Einstieg Open[k+1]
                        ODER close[k+1] <= U_laufend (Folge-Bar bestaetigt)
                        -> Einstieg Open[k+2]
    UNTERKANTE (LONG):  symmetrisch mit L_laufend.

    Filter (Patrick Nill):
    - Einstieg muss auf der richtigen Seite des POC liegen (SHORT: ueber
      POC, LONG: unter POC), sonst ist das Fair-Value-Ziel bereits erreicht.
    - Bounce-Nummer >= min_bounce (Default 1 = jede signifikante Kante; die
  3-Touch-Regel ist via --bounce=3 zuschaltbar).
    - CRV >= min_crv (Risiko-Ertrag, SL = SL_PCT vom Einstieg).
    - Cooldown: keine 2 Signale gleicher Richtung innerhalb cooldown_bars.
    """
    sigs = []
    vz_full = p.get("vol_zone")
    if vz_full is None:
        return sigs
    U_full, L_full = vz_full["U_zone"], vz_full["L_zone"]
    hi = df["high"].values
    lo = df["low"].values
    cl = df["close"].values
    op = df["open"].values
    ts = df["ts"].values
    last_bar = {"SHORT": -10 ** 9, "LONG": -10 ** 9}
    tp2_puffer = TP2_PUFFER_PCT / 100.0
    sl_p = SL_PCT / 100.0

    # Kandidaten-Screening: Bars ausserhalb der FINALEN Kante (vektorisiert)
    cand = np.where((hi > U_full) | (lo < L_full))[0]
    cand = cand[(cand >= p["i_start"]) & (cand < p["i_ende"])]

    for k in cand:
        if k - p["i_start"] + 1 < min_candles:
            continue
        vz = _laufende_zone(df, p, k)
        if vz is None:
            continue
        U, L, POC = vz["U_zone"], vz["L_zone"], vz["POC"]
        ts_k = ts[k]
        nb_h, nb_l = _bounce_nr(p["h_prices"], p["h_ts"],
                                p["l_prices"], p["l_ts"], ts_k, U, L)

        # --- OBERKANTE: Fakeout nach oben + Reclaim -> SHORT ---
        if hi[k] > U:
            if cl[k] <= U:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 1 <= p["i_ende"] and cl[k + 1] <= U:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if (reclaim is not None and e_bar <= p["i_ende"]
                    and e_preis > POC                      # Short ueber Fair Value
                    and nb_h >= min_bounce                 # 3-Touch-Regel
                    and k - last_bar["SHORT"] >= cooldown_bars):
                sl = e_preis * (1 + sl_p)                  # SL 0.2% ueber Entry
                tp1 = POC
                tp2 = L * (1 + tp2_puffer)                 # Innen-Puffer vor Box-Ende
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    last_bar["SHORT"] = k
                    sig = {"typ": "SHORT", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                           "reclaim": reclaim, "einstieg_bar": int(e_bar),
                           "einstieg_preis": e_preis,
                           "U_laufend": U, "L_laufend": L, "POC": POC,
                           "tp1": tp1, "tp2": tp2, "sl": sl,
                           "crv": crv, "crv2": crv2, "bounce_nr": nb_h}
                    sig.update(_aufloesen(df, sig))
                    sigs.append(sig)

        # --- UNTERKANTE: Fakeout nach unten + Reclaim -> LONG ---
        if lo[k] < L:
            if cl[k] >= L:
                e_bar, e_preis, reclaim = k + 1, float(op[k + 1]), "in_bar"
            elif k + 1 <= p["i_ende"] and cl[k + 1] >= L:
                e_bar, e_preis, reclaim = k + 2, float(op[k + 2]), "next_bar"
            else:
                e_bar, reclaim = None, None
            if (reclaim is not None and e_bar <= p["i_ende"]
                    and e_preis < POC                       # Long unter Fair Value
                    and nb_l >= min_bounce                  # 3-Touch-Regel
                    and k - last_bar["LONG"] >= cooldown_bars):
                sl = e_preis * (1 - sl_p)                  # SL 0.2% unter Entry
                tp1 = POC
                tp2 = U * (1 - tp2_puffer)                 # Innen-Puffer vor Box-Ende
                risk = abs(sl - e_preis)
                crv = abs(tp1 - e_preis) / risk if risk > 0 else np.nan
                crv2 = abs(tp2 - e_preis) / risk if risk > 0 else np.nan
                if not np.isnan(crv) and crv >= min_crv:
                    last_bar["LONG"] = k
                    sig = {"typ": "LONG", "bar": int(k), "ts": pd.Timestamp(ts[k]),
                           "reclaim": reclaim, "einstieg_bar": int(e_bar),
                           "einstieg_preis": e_preis,
                           "U_laufend": U, "L_laufend": L, "POC": POC,
                           "tp1": tp1, "tp2": tp2, "sl": sl,
                           "crv": crv, "crv2": crv2, "bounce_nr": nb_l}
                    sig.update(_aufloesen(df, sig))
                    sigs.append(sig)
    return sigs


reclaim_signals = []
for _pi, _p in enumerate(phases, 1):
    for _s in find_reclaim_signals(df, _p):
        _s["phase"] = _pi
        reclaim_signals.append(_s)
reclaim_signals.sort(key=lambda s: s["ts"])
# Statistik (alle Trades VOLLSTAENDIG aufgeloest)
_n_win = sum(1 for s in reclaim_signals if s["resultat"] == "GEWONNEN")
_n_loss = sum(1 for s in reclaim_signals if s["resultat"] == "VERLOREN")
_n_neu = sum(1 for s in reclaim_signals if s["resultat"] == "NEUTRAL")
_n_tp1 = sum(1 for s in reclaim_signals if s["tp1_hit"])
_n_tp2 = sum(1 for s in reclaim_signals if s["tp2_hit"])
_n_sl1 = sum(1 for s in reclaim_signals if s["sl_hit1"])
_n_sl2 = sum(1 for s in reclaim_signals if s["sl_hit2"])
_n_trail = sum(1 for s in reclaim_signals if s.get("grund1") == "TRAIL")

# ---------- 5d) SETUP C: MOVE-TRADES (Breakout-Riding, optional) ----------
# Trader-Punkt 3: "oft sind auch die Move-Downs und Move-Ups selbst sehr gute
# Trades". Nach einem bestaetigten 2-Close-Ausbruch (brk_idx) wird in
# Ausbruchsrichtung eingestiegen (Open der Bar NACH der Bestaetigung =
# brk_idx+2, kausal). Der Move endet mit dem Ausbruch der FOLGE-Phase
# (oder am Datenende) - Exit = Open der Bar nach dessen 2-Close-Bestaetigung.
# SL: hinter der gebrochenen Kante + SL_PCT Puffer.
move_signals = []
_mw = _ml = _mn = 0
if TRADE_MOVES:
    for _k, _ph in enumerate(phases):
        if _ph["break_dir"] is None or _ph["brk_idx"] is None or _ph["brk_kante"] is None:
            continue
        _dir = _ph["break_dir"]
        _typ = "SHORT" if _dir == "down" else "LONG"
        _e_bar = _ph["brk_idx"] + 2          # Open nach 2-Close-Bestaetigung
        if _e_bar >= n:
            continue
        _entry = float(df["open"].iloc[_e_bar])
        _kante = float(_ph["brk_kante"])
        # SL hinter der gebrochenen Kante (bzw. am Entry, falls dieser
        # bereits jenseits der Kante liegt)
        if _typ == "SHORT":
            _sl = max(_entry, _kante) * (1 + SL_PCT / 100.0)
        else:
            _sl = min(_entry, _kante) * (1 - SL_PCT / 100.0)
        # Exit: Ausbruch der Folge-Phase = Ende des Moves (kausal, 2-Close)
        if _k + 1 < len(phases) and phases[_k + 1]["brk_idx"] is not None:
            _x_bar = phases[_k + 1]["brk_idx"] + 2
            if _x_bar >= n:
                _x_bar = n - 1
                _x_pr = float(df["close"].iloc[_x_bar])
                _x_grund = "DATENENDE"
            else:
                _x_pr = float(df["open"].iloc[_x_bar])
                _x_grund = "MOVE-ENDE"
        else:
            _x_bar = n - 1
            _x_pr = float(df["close"].iloc[_x_bar])
            _x_grund = "DATENENDE"
        # SL-Check waehrend des Ritts (nur falls Fenster nicht leer)
        if _x_bar >= _e_bar:
            _seg_hi = df["high"].values[_e_bar:_x_bar + 1]
            _seg_lo = df["low"].values[_e_bar:_x_bar + 1]
            if _typ == "SHORT":
                _hits = np.where(_seg_hi >= _sl)[0]
            else:
                _hits = np.where(_seg_lo <= _sl)[0]
            if len(_hits):
                _x_pr, _x_grund = float(_sl), "SL"
        _risk = abs(_sl - _entry)
        if _risk <= 0:
            _risk = 1e-9
        _r_m = ((_entry - _x_pr) / _risk if _typ == "SHORT"
                else (_x_pr - _entry) / _risk)
        _res = ("GEWONNEN" if _r_m > 1e-9
                else ("VERLOREN" if _r_m < -1e-9 else "NEUTRAL"))
        move_signals.append({
            "phase": _k + 1, "ts": df["ts"].iloc[_e_bar],
            "typ": _typ, "einstieg_preis": _entry, "sl": _sl,
            "exit": _x_pr, "grund": _x_grund, "r": _r_m,
            "resultat": _res, "kante": _kante,
            "von_ts": _ph["ende"], "bis_ts": df["ts"].iloc[_x_bar],
        })
    _mw = sum(1 for s in move_signals if s["resultat"] == "GEWONNEN")
    _ml = sum(1 for s in move_signals if s["resultat"] == "VERLOREN")
    _mn = sum(1 for s in move_signals if s["resultat"] == "NEUTRAL")

# ---------- 6) Ausgabe ----------
pd.set_option("display.width", 230)
print("\n=== PHASEN (VOLUME-PROFIL: POC/VAH/VAL-Zonen) ===")
for i, p in enumerate(phases, 1):
    u_str = f"{p['U_final']:.3f}" if p['U_final'] is not None else "N/A"
    l_str = f"{p['L_final']:.3f}" if p['L_final'] is not None else "N/A"
    ok = " [HANDELBAR]" if p["handelbar"] else ""
    print(f"Phase {i}: {p['start']:%a %d.%m %H:%M} -> {p['ende']:%a %d.%m %H:%M} "
          f"({p['handels_h']:.1f}h, {p['n_candles']}C){ok} "
          f"| Pivots: {p['touches_h']}H/{p['touches_l']}L")
    vz = p.get("vol_zone")
    if vz is not None:
        print(f"    VOLUME-ZONE: OBEN {vz['U_zone']:.3f} | MITTE(POC) {vz['POC']:.3f} | UNTEN {vz['L_zone']:.3f} "
              f"| Breite {p['zone_breite']:.3f} | {p['n_berge']} Berg(e)")
        for j, pk in enumerate(vz["peaks"], 1):
            print(f"      Berg {j}: POC {pk['poc']:.3f} | VAL {pk['val']:.3f} | VAH {pk['vah']:.3f} "
                  f"| Vol {pk['vol']:.0f} | Peak-Anteil {pk['peak_share_pct']:.0f}%")
    else:
        print(f"    VOLUME-ZONE: keine (zu wenig Daten)")
    # Referenz: bisherige Schnittmengen-Linien
    print(f"    REAKTIONS-Extreme (Schnittmengen): OBEN {u_str} | UNTEN {l_str} "
          f"(dick gestrichelt im Chart)")
    if p["U_hist"]:
        dev_u = " -> ".join(f"{t:%a %H:%M} {v:.3f}" for t, v in p["U_hist"])
        print(f"    OBEN-Entwicklung ({p['n_U_shifts']} Verschiebungen): {dev_u}")
    if p["L_hist"]:
        dev_l = " -> ".join(f"{t:%a %H:%M} {v:.3f}" for t, v in p["L_hist"])
        print(f"    UNTEN-Entwicklung ({p['n_L_shifts']} Verschiebungen): {dev_l}")
    if p.get("U_proj_val") is not None:
        _c = p.get("U_conf_ts")
        z = f"bestaetigt {_c:%a %H:%M}" if _c is not None else "NIE bestaetigt (Projektion)"
        print(f"    OBEN-Geburtszone {p['U_proj_val']:.3f}: {z}")
    if p.get("L_proj_val") is not None:
        _c = p.get("L_conf_ts")
        z = f"bestaetigt {_c:%a %H:%M}" if _c is not None else "NIE bestaetigt (Projektion)"
        print(f"    UNTEN-Geburtszone {p['L_proj_val']:.3f}: {z}")

print("\n=== MOVES (Phasenwechsel) ===")
for m in moves:
    d = (m["bis_ts"] - m["von_ts"]).total_seconds() / 60
    print(f"{'UP  ' if m['dir']=='up' else 'DOWN'} {m['von_ts']:%a %H:%M} ({m['von_pr']:.3f}) "
          f"-> {m['bis_ts']:%a %H:%M} ({m['bis_pr']:.3f})  "
          f"{m['bis_pr']-m['von_pr']:+.3f} USD in {d:.0f} min")

_trail_txt = f" | TRAILING {TRAILING_PCT:.2f}%" if TRAILING_PCT > 0 else ""
_nach_txt = "SL bleibt am Entry (kein Nachzug)"
_ant_txt = (f"{ANTEIL_TP1:.0f}/{100-ANTEIL_TP1:.0f}" if 0 < ANTEIL_TP1 < 100
            else ("100/0" if ANTEIL_TP1 >= 100 else "0/100"))
print(f"\n=== SETUP B: RECLAIM-SIGNALE (SL {SL_PCT:.1f}% Entry; {_nach_txt}; "
      f"TP2=Box-Ende innen 0.15%; Split {_ant_txt}{_trail_txt}; alle aufgeloest) ===")
if not reclaim_signals:
    print("  keine Signale")
for s in reclaim_signals:
    typ = "SHORT" if s["typ"] == "SHORT" else "LONG "
    print(f"  P{s['phase']:2d} {s['ts']:%a %d.%m %H:%M} {typ} Rec {s['reclaim']:8s} "
          f"Ein {s['einstieg_preis']:.3f} | SL {s['sl']:.3f} | TP1 {s['tp1']:.3f} | TP2 {s['tp2']:.3f} "
          f"| CRV {s['crv']:.2f} | Bo {s['bounce_nr']} | H1 {s['exit1']:.3f} ({s['grund1']}) {s['r1']:+.2f}R | "
          f"H2 {s['exit2']:.3f} ({s['grund2']}) {s['r2']:+.2f}R | {s['resultat']} {s['r_mult']:+.2f}R")

print(f"\n=== STATISTIK SETUP B (SL {SL_PCT:.1f}% Entry; {_nach_txt}; Split {_ant_txt}{_trail_txt}) ===")
print(f"  Signale: {len(reclaim_signals)} | GEWONNEN {_n_win} | VERLOREN {_n_loss} | NEUTRAL {_n_neu}")
if _n_win + _n_loss > 0:
    print(f"  Trefferquote: {100.0*_n_win/(_n_win+_n_loss):.0f}% (nur entschiedene)")
_s = sum(s["r_mult"] for s in reclaim_signals) if reclaim_signals else 0.0
print(f"  Summe R: {_s:+.2f} | avg R: {(_s/len(reclaim_signals) if reclaim_signals else 0):+.2f} "
      f"| max R: {max(s['r_mult'] for s in reclaim_signals):+.2f} | min R: {min(s['r_mult'] for s in reclaim_signals):+.2f}")
print(f"  TP1(POC) erreicht: {_n_tp1}/{len(reclaim_signals)} | TP2(Box-Ende) erreicht: {_n_tp2} "
      f"| SL Haelfte1: {_n_sl1} | SL Haelfte2: {_n_sl2} | TRAIL-Exit: {_n_trail}")

# --- SETUP C Ausgabe (nur bei --moves=1) ---
if TRADE_MOVES:
    print(f"\n=== SETUP C: MOVE-TRADES (Breakout-Riding; SL {SL_PCT:.1f}% hinter der Kante) ===")
    if not move_signals:
        print("  keine Signale")
    for s in move_signals:
        print(f"  P{s['phase']:2d} {s['ts']:%a %d.%m %H:%M} {s['typ']:5s} "
              f"Ein {s['einstieg_preis']:.3f} | SL {s['sl']:.3f} | Kante {s['kante']:.3f} "
              f"| Exit {s['exit']:.3f} ({s['grund']}) | {s['r']:+.2f}R | {s['resultat']}")
    print(f"\n=== STATISTIK SETUP C (MOVE-TRADES) ===")
    print(f"  Signale: {len(move_signals)} | GEWONNEN {_mw} | VERLOREN {_ml} | NEUTRAL {_mn}")
    if _mw + _ml > 0:
        print(f"  Trefferquote: {100.0*_mw/(_mw+_ml):.0f}% (nur entschiedene)")
    _sm = sum(s["r"] for s in move_signals) if move_signals else 0.0
    print(f"  Summe R: {_sm:+.2f} | avg R: {(_sm/len(move_signals) if move_signals else 0):+.2f} "
          f"| max R: {max(s['r'] for s in move_signals):+.2f} | min R: {min(s['r'] for s in move_signals):+.2f}")

print("\n=== HANDELBARE RANGES (Filter: >= %d Touches je Grenze, >= %d Candles, Breite >= %.1f%%) ==="
      % (MIN_TOUCHES, MIN_CANDLES, MIN_SPREAD_PCT))
ranges = [p for p in phases if p["handelbar"]]
for i, p in enumerate(ranges, 1):
    print(f"\nRange {i}: {p['start']:%a %d.%m %H:%M} -> {p['ende']:%a %d.%m %H:%M}  ({p['handels_h']:.1f}h)")
    vz = p.get("vol_zone")
    if vz is not None:
        print(f"    VOLUME-ZONE OBEN  {vz['U_zone']:.3f} | MITTE(POC) {vz['POC']:.3f} | UNTEN {vz['L_zone']:.3f} "
              f"| Breite {p['zone_breite']:.3f} | {p['n_berge']} Berg(e)")
        for j, pk in enumerate(vz["peaks"], 1):
            print(f"      Berg {j}: POC {pk['poc']:.3f} | VAL {pk['val']:.3f} | VAH {pk['vah']:.3f} "
                  f"| Peak-Anteil {pk['peak_share_pct']:.0f}%")
    print(f"    REAKTIONS-Extreme (Schnittmengen): OBEN {p['U_final']:.3f} | UNTEN {p['L_final']:.3f}")

# ---------- 6a) STATISTIK-PAKET + TRADE-TEXTFILE (fester Dateiname je Chart) ----------
# Die Box im Chart und das Textfile nutzen DIESELBEN Zahlen (eine Quelle).
_n_calls = sum(1 for s in reclaim_signals if s["typ"] == "LONG")
_n_sells = sum(1 for s in reclaim_signals if s["typ"] == "SHORT")
_decided = _n_win + _n_loss
_winrate = 100.0 * _n_win / _decided if _decided else 0.0
_avg_crv = (sum(s["crv"] for s in reclaim_signals) / len(reclaim_signals)
            if reclaim_signals else 0.0)
_sum_r = sum(s["r_mult"] for s in reclaim_signals)
# % Gesamtgewinn: Summe R x Risiko je Trade (SL_PCT% vom Entry)
_gewinn_pct = _sum_r * SL_PCT
_stat_lines = [
    f"STATISTIK {START} - {ENDE}",
    f"# CALLS (LONG):  {_n_calls:2d}   # SELLS (SHORT): {_n_sells:2d}",
    f"WINRATE:  {_winrate:.0f}%  ({_n_win}W/{_n_loss}L/{_n_neu}N)",
    f"avg CRV:  {_avg_crv:.2f}",
    f"Summe R:  {_sum_r:+.2f}",
    f"Gesamtgewinn: {_gewinn_pct:+.2f}% (Risiko {SL_PCT:.2f}%/Trade)",
]
# Nur SETUP B in der Statistik (Header + Grafik); SETUP C kommt spaeter.

# Textfile mit allen Trades zum exakten Nachpruefen (immer gleicher Name)
OUT_TXT = OUT_PNG.with_suffix(".txt")
_fmt_ts = lambda t: t.strftime("%Y-%m-%d %H:%M")
with open(OUT_TXT, "w", encoding="utf-8") as _f:
    # 1) Header = identisch mit dem Statistik-Label im Chart
    _f.write("\n".join(_stat_lines) + "\n\n")

    # 2) Alle Setup-B-Trades mit allen Rohwerten
    _f.write("=== SETUP B: RECLAIM-SIGNALE (alle Trades) ===\n")
    _f.write(f"Parameter: SL_PCT={SL_PCT} | "
             f"TP2_PUFFER_PCT={TP2_PUFFER_PCT} | Split {_ant_txt} | "
             f"TRAILING_PCT={TRAILING_PCT} | "
             f"MIN_RECLAIM_BOUNCE={MIN_RECLAIM_BOUNCE} | MIN_RECLAIM_CRV={MIN_RECLAIM_CRV} | "
             f"Cooldown={MIN_SIGNAL_ABSTAND_BARS} Bars | KEIN SL-NACHZUG\n")
    _f.write("Nr | Phase | Signal-Bar(ts)      | Typ   | Reclaim  | EntryBar | Entry   | SL      | TP1     | TP2     | "
             "CRV   | CRV2  | Bo | Exit1   | Grund | R1    | Exit2   | Grund | R2    | R-mult | Resultat\n")
    for _i, s in enumerate(reclaim_signals, 1):
        _f.write(f"{_i:2d} | P{s['phase']:<2d} | {_fmt_ts(s['ts'])} | {s['typ']:5s} | {s['reclaim']:8s} | "
                 f"{s['einstieg_bar']:8d} | {s['einstieg_preis']:.3f} | {s['sl']:.3f} | {s['tp1']:.3f} | {s['tp2']:.3f} | "
                 f"{s['crv']:.2f} | {s['crv2']:.2f} | {s['bounce_nr']:2d} | "
                 f"{s['exit1']:.3f} | {s['grund1']:5s} | {s['r1']:+.2f} | "
                 f"{s['exit2']:.3f} | {s['grund2']:5s} | {s['r2']:+.2f} | {s['r_mult']:+.2f} | {s['resultat']}\n")
    if not reclaim_signals:
        _f.write("(keine Signale)\n")

    # 3) Setup-C-Moves (nur bei --moves=1)
    if TRADE_MOVES:
        _f.write("\n=== SETUP C: MOVE-TRADES ===\n")
        _f.write("Nr | Phase | Entry-Bar(ts)     | Typ   | Entry   | SL      | Kante   | Exit    | Grund     | R     | Resultat\n")
        for _i, s in enumerate(move_signals, 1):
            _f.write(f"{_i:2d} | P{s['phase']:<2d} | {_fmt_ts(s['ts'])} | {s['typ']:5s} | "
                     f"{s['einstieg_preis']:.3f} | {s['sl']:.3f} | {s['kante']:.3f} | "
                     f"{s['exit']:.3f} | {s['grund']:9s} | {s['r']:+.2f} | {s['resultat']}\n")
        if not move_signals:
            _f.write("(keine Signale)\n")
print(f"Trades-Textfile gespeichert: {OUT_TXT}")

# ---------- 7) Chart ----------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(17, 9))
idx = df["idx"].values
ax.plot(idx, df["high"], color="#bbb", lw=0.5)
ax.plot(idx, df["low"], color="#bbb", lw=0.5)

colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
for i, p in enumerate(phases):
    c = colors[i % len(colors)]
    ax.axvspan(p["i_start"], p["i_ende"], color=c, alpha=0.07)
    vz = p.get("vol_zone")
    if vz is None:
        continue

    # --- VOLUME-ZONE (Variante A, "Huelle") ---
    # OBEN  = hoechste VAH aller signifikanter Berge  (solid gruen)
    # UNTEN = tiefste  VAL aller signifikanter Berge  (solid rot)
    # MITTE = POC des volumenstaerksten Bergs         (orange Strich-Punkt)
    ax.hlines(vz["U_zone"], p["i_start"], p["i_ende"], color="#1a7d1a", lw=2.4, alpha=0.95)
    ax.hlines(vz["L_zone"], p["i_start"], p["i_ende"], color="#c00000", lw=2.4, alpha=0.95)
    ax.hlines(vz["POC"], p["i_start"], p["i_ende"], color="#e07b00", lw=1.8, ls="-.")
    ax.text(p["i_start"] + 2, vz["U_zone"] + 0.10, f"OBEN(VAH) {vz['U_zone']:.2f}",
            fontsize=8, color="#1a7d1a", fontweight="bold", va="bottom")
    ax.text(p["i_start"] + 2, vz["L_zone"] - 0.10, f"UNTEN(VAL) {vz['L_zone']:.2f}",
            fontsize=8, color="#c00000", fontweight="bold", va="top")
    ax.text(p["i_start"] + 2, vz["POC"] + 0.10, f"POC {vz['POC']:.2f}",
            fontsize=8, color="#e07b00", fontweight="bold", va="bottom")

    # --- Sub-Berge: eigene POC/VAH/VAL fein gepunktet (Mehr-Berg-Struktur) ---
    for j, pk in enumerate(vz["peaks"], 1):
        if j == 1 and vz["n_mountains"] == 1:
            continue  # einziger Berg ist bereits als Zone gezeichnet
        ax.hlines(pk["vah"], p["i_start"], p["i_ende"], color="#2ca02c", lw=1.0, ls=":", alpha=0.75)
        ax.hlines(pk["val"], p["i_start"], p["i_ende"], color="#d62728", lw=1.0, ls=":", alpha=0.75)
        ax.hlines(pk["poc"], p["i_start"], p["i_ende"], color="#e07b00", lw=0.9, ls=":", alpha=0.75)

    # --- REAKTIONS-Extreme (Schnittmengen) als dicke gestrichelte Referenz ---
    if p["U_final"] is not None:
        ax.hlines(p["U_final"], p["i_start"], p["i_ende"], color="k", lw=1.6, ls="--", alpha=0.55)
        ax.text(p["i_start"] + 2, p["U_final"] + 0.28, f"REAKTION OBEN {p['U_final']:.2f}",
                fontsize=7.5, color="k", alpha=0.8, fontweight="bold", va="bottom")
    if p["L_final"] is not None:
        ax.hlines(p["L_final"], p["i_start"], p["i_ende"], color="k", lw=1.6, ls="--", alpha=0.55)
        ax.text(p["i_start"] + 2, p["L_final"] - 0.28, f"REAKTION UNTEN {p['L_final']:.2f}",
                fontsize=7.5, color="k", alpha=0.8, fontweight="bold", va="top")

# --- Setup-B-Signale (Reclaim/Fakeout) im Chart markieren ---
for s in reclaim_signals:
    x = s["bar"]
    if s["typ"] == "SHORT":
        y = float(df["high"].iloc[x])
        ax.scatter(x, y, marker="v", s=85, color="#c00000", zorder=6,
                   edgecolor="w", linewidths=0.5)
        txt = f"REC S {s['einstieg_preis']:.2f} CRV {s['crv']:.1f}"
    else:
        y = float(df["low"].iloc[x])
        ax.scatter(x, y, marker="^", s=85, color="#1a7d1a", zorder=6,
                   edgecolor="w", linewidths=0.5)
        txt = f"REC L {s['einstieg_preis']:.2f} CRV {s['crv']:.1f}"
    if s["resultat"] == "GEWONNEN":
        txt += " WIN"
    elif s["resultat"] == "VERLOREN":
        txt += " LOSS"
    ax.annotate(txt, (x, y),
                xytext=(x, y + (0.45 if s["typ"] == "SHORT" else -0.45)),
                fontsize=7.5, ha="center",
                color="#c00000" if s["typ"] == "SHORT" else "#1a7d1a",
                fontweight="bold")

for m in moves:
    ix = df["idx"][df["ts"] == m["von_ts"]].iloc[0] if (df["ts"] == m["von_ts"]).any() else np.nan
    iy = df["idx"][df["ts"] == m["bis_ts"]].iloc[0] if (df["ts"] == m["bis_ts"]).any() else np.nan
    if np.isnan(ix) or np.isnan(iy):
        continue
    # Gelbe Move-Label entfernt (nur Pfeil bleibt) - 31.08.2026
    ax.annotate("", xy=(iy, m["bis_pr"]), xytext=(ix, m["von_pr"]),
                arrowprops=dict(arrowstyle="->", color="k", lw=2.2, connectionstyle="arc3,rad=0.0"))

step = max(8, len(df) // 16)
ticks = np.arange(0, len(df), step)
ax.set_xticks(ticks)
ax.set_xticklabels([df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks], rotation=45, ha="right", fontsize=8)
ax.set_xlim(-1, len(df))
ax.set_title(f"SILVER M15 {START} - {ENDE} - VOLUME-PROFIL-ZONEN (VA_PCT {VA_PCT:.0f}%) + "
             f"SETUP B RECLAIM-SIGNALE (Pfeil = Fakeout, Ziel POC)")
ax.set_ylabel("USD")
ax.grid(alpha=0.3)

# Legende: Volume-Zone vs. Sub-Berge vs. REAKTIONS-Extreme vs. Setup B
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color="#1a7d1a", lw=2.4, label="OBEN (VAH-Zone)"),
    Line2D([0], [0], color="#c00000", lw=2.4, label="UNTEN (VAL-Zone)"),
    Line2D([0], [0], color="#e07b00", lw=1.8, ls="-.", label="MITTE (POC)"),
    Line2D([0], [0], color="#2ca02c", lw=1.0, ls=":", label="Sub-Berg VAH"),
    Line2D([0], [0], color="#d62728", lw=1.0, ls=":", label="Sub-Berg VAL"),
    Line2D([0], [0], color="k", lw=1.6, ls="--", label="REAKTIONS-Extreme (Schnittmengen)"),
    Line2D([0], [0], marker="v", color="w", markerfacecolor="#c00000", ms=8,
           label="Setup B: Reclaim SHORT"),
    Line2D([0], [0], marker="^", color="w", markerfacecolor="#1a7d1a", ms=8,
           label="Setup B: Reclaim LONG"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=8, framealpha=0.9)

# --- Statistik-Box rechts neben der Legende (Daten aus 6a, identisch mit Textfile) ---
ax.text(0.28, 0.985, "\n".join(_stat_lines), transform=ax.transAxes,
        fontsize=8, va="top", ha="left", family="monospace",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#fdf6e3",
                  edgecolor="gray", alpha=0.95))

fig.tight_layout()
fig.savefig(OUT_PNG, dpi=130)
print(f"\nChart gespeichert: {OUT_PNG}")
