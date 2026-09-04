"""
SILVER M15: RANGE-PHASEN NACH TRADER-SICHT (Fr 21.08. - Do 27.08.2026).

NEUE PHASEN-DEFINITION (wie vom Trader vorgegeben):
- Phase 1: Fr 21.08. 00:00 -> Di 25.08. 02:00   OBEN ~69.9, UNTEN ~68.4
- Phase 2: Di 25.08. 04:30 -> Do 27.08. 19:00   OBEN ~69.67, UNTEN ~67.56

ERKENNUNGS-REGELN (Schnittmengen- statt Pivot-Ausbruchslogik):
1. Grenzlinien = SCHNITTMENGEN-LINIE der extremen Spitzen-Ebene:
   - Einzel-Ausreisser (lokale Dichte < MIN_CLUSTER, z.B. Fr-Tief 67.883)
     bilden KEIN Level.
   - EXTREMER KERN = oberste (H) / tiefste (L) Spitzen-Gruppe mit
     >= MIN_CLUSTER Treffern im Band.
   - ERWEITERUNGS-POOL: Spitzen bis ERWEITERUNG_PCT (1%) ueber/unter der
     Kern-Kante gehoeren zur Grenze - ein HH/LL <= 1% erweitert die Range.
   - Linie = getrimmte Schnittmenge des Pools OHNE das absolute Extrem:
     sie klebt weder am hoechsten/niedrigsten Wert noch an den kleineren
     Spitzen, sondern liegt in der Schnittmenge der Mehrheit.
2. Eine Phase ist ETABLIERT, wenn BEIDE Grenzen >= MIN_ESTABLISH Touches
   haben. Erst danach koennen Ausbrueche die Phase beenden - der Fr-Run
   68.0->70.0 baut nur die Obergrenze auf und beendet Phase 1 nicht.
3. ENTSCHIEDENDER AUSBRUCH = 2 aufeinanderfolgende Closes brechen die
   Grenz-Referenz um mehr als TOL. Referenz = eigene Schnittmengen-Linie,
   verstaerkt um die GEBURTSZONE (Bereich zwischen Vorphasen-Ende und
   Phasenstart, z.B. Hoch 69.684 Di 02:45 als Widerstand von Phase 2).
   Wicks zaehlen nicht: Phase 1 endete nicht am Mo-Tief 68.288, weil alle
   Closes ueber dem Niveau blieben.
4. Phasen-Ende = letzter Touch der GEGENgrenze vor dem Ausbruch
   (z.B. Di 02:00 Hoch 69.924 an OBEN 69.9 -> Phase 1 endet Di 02:00).
5. Neue Phase beginnt am ersten bestaetigten Ausbruchs-Close (Di 04:30).
   Durch die Geburtszonen-Referenz bleibt die Di-Rally bis 69.27 ein
   Retest innerhalb von Phase 2 und kein Phasenende.
6. MIN_SPREAD_PCT (1.5%): Phasen mit geringerer Breite (U-L)/L sind nicht
   handelbar und werden gefiltert.
7. LETZTER GRENZ-KONTAKT: Erreicht eine etablierte Phase das Datenende
   OHNE 2-Close-Ausbruch, endet sie am letzten Pivot, der die finale
   Grenzlinie tatsaechlich erreicht hat (H-Pivot >= OBEN bzw. L-Pivot
   <= UNTEN, +/- GRENZ_KONTAKT_TOL). Danach folgt der Move in Gegenrichtung.
   Beispiel Phase 2: letzter OBEN-Kontakt Do 27.08 19:00 (High 69.714 an
   OBEN 69.67) -> Phase 2 endet dort, danach dreht der Kurs nach unten.
   Symmetrie zu Phase 1: auch dort endet die Phase am letzten OBEN-Kontakt
   Di 25.08 02:00 (High 69.924 an OBEN 69.91), gefolgt vom Crash-Move.

KAUSALITAET / KEIN LOOKAHEAD (Umstellung fuer Forward-/Replay-Tests):
- L1/L2: Pivot-Bestaetigung ist NACHLAUFEND (Lag PIVOT_LOOKBACK). Ein Pivot
  bei Bar k wird erst in Bar k+PIVOT_LOOKBACK in die Phase aufgenommen.
  Die Pivot-MENGE bleibt identisch - nur der Bekanntgabezeitpunkt ist um
  PIVOT_LOOKBACK Bars verzoegert (kein Zentrumsfenster als Lookahead).
- L3: Geburtszone enthaelt nur Pivots, die zum Phasenstart bereits
  bestaetigt waren (cutoff = Phasenstart - PIVOT_LOOKBACK*15min).
- L4: Regel 7 ist ein expliziter DATENENDE-FINALIZE (post-hoc, Abschnitt 4b):
  Er kuerzt eine laufende Phase am letzten bestaetigten Grenz-Kontakt.
  Er ist NICHT kausal umformulierbar - im Replay springt die Phase am
  letzten Bar rueckwaerts auf den letzten Kontakt (D1-Variante).

VARIANTE C - GEERBTE LINIE ALS "PROJEKTION" (Transparenz ohne Vermutung):
- Die aus der GEBURTSZONE geerbte Grenze (z.B. OBEN 69.684 fuer Phase 2)
  ist zunaechst NUR eine PROJEKTION: Sie wird GESTRICHELT gezeichnet, weil
  unklar ist, ob der Kurs in die alte Range zurueckkehrt.
- Erst beim ERSTEN REALEN TEST (H-Pivot >= OBEN - DENSITY_BAND bzw.
  L-Pivot <= UNTEN + DENSITY_BAND, innerhalb der Phase) wird die Linie auf
  "REAL" (solid) gesetzt - ab diesem Zeitpunkt ist die Zone bestaetigt.
- Die FINALE Grenze uebernimmt die Geburtszone NUR, wenn sie real getestet
  wurde (sonst keine Vermutung -> finale Linie = reine Schnittmenge).
- Die AUSBRUCHS-SCHRANKE (h_ref/l_ref) bleibt davon unberuehrt: Ein echter
  Bruch muss IMMER ueber die alte Range hinausgehen (latente Referenz).
- Beispiel Phase 2: OBEN 69.684 wird Mi 04:30 durch High 69.709 real
  bestaetigt -> bis dahin gestrichelt, danach solid. U_final bleibt 69.684.
"""
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

OUT_PNG = Path(__file__).resolve().parent / "tmp_phasen_move_m15.png"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "market_data.duckdb"
TOL = 0.30            # USD Close-Breakout-Toleranz (entscheidender Ausbruch)
TOL_TOUCH = 0.15      # "enger Touch": Pivot innerhalb dieser Distanz zur Grenze
MIN_TOUCHES = 3       # je Grenze fuer "handelbar"
MIN_CANDLES = 46
MIN_CLUSTER = 2       # min. Pivot-Treffer, damit eine Spitze ein Level bildet
MIN_ESTABLISH = 3     # Touches auf BEIDEN Seiten, bevor Ausbrueche zaehlen
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
PIVOT_LOOKBACK = 2    # Pivot-Bestaetigungs-Lag (Bars): Ein Pivot bei Bar k
                      #   wird erst in Bar k+PIVOT_LOOKBACK bekannt gegeben
                      #   (kein Zentrums-Lookahead, kausal fuer Replay-Tests)
START = "2026-08-10"
ENDE = "2026-08-28"

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
    est_idx = None                 # Candle-Index der Etablierung (beide Seiten >= MIN_ESTABLISH)
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
        birth_h = birth.loc[birth["typ"] == "H", "price"].max() if birth["typ"].eq("H").any() else None
        birth_l = birth.loc[birth["typ"] == "L", "price"].min() if birth["typ"].eq("L").any() else None
    else:
        birth_h = birth_l = None

    j = i
    while j < n:
        row = df.iloc[j]
        ts = row["ts"]
        # L1/L2-Fix (KAUSAL): Ein Pivot bei Bar j-PIVOT_LOOKBACK wird erst in
        # Bar j bekannt gegeben. Die Pivot-MENGE bleibt identisch - nur der
        # Bekanntgabezeitpunkt ist um PIVOT_LOOKBACK Bars nachlaufend.
        if j - PIVOT_LOOKBACK >= 0 and df["is_pivot"].iloc[j - PIVOT_LOOKBACK]:
            t_prev = df["ts"].iloc[j - PIVOT_LOOKBACK]
            if piv_typ[t_prev] == "H":
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

        U = level_schnittmenge(h_acc, "H")
        L = level_schnittmenge(l_acc, "L")

        # Etablierung: beide Grenzen muessen genug getestet worden sein
        if est_idx is None and U is not None and L is not None \
                and n_touches(h_acc, U) >= MIN_ESTABLISH and n_touches(l_acc, L) >= MIN_ESTABLISH:
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

        # Ausbruch-Check NUR nach Etablierung.
        # Referenz: eigene Schnittmengen-Linie, verstaerkt um die Geburtszone.
        if est_idx is not None and j + 1 < n:
            h_ref = U if U is not None else None
            l_ref = L if L is not None else None
            if birth_h is not None:
                h_ref = max(h_ref, birth_h) if h_ref is not None else birth_h
            if birth_l is not None:
                l_ref = min(l_ref, birth_l) if l_ref is not None else birth_l
            if h_ref is not None and row["close"] > h_ref + TOL and df["close"].iloc[j + 1] > h_ref + TOL:
                brk_idx, brk_dir = j, "up"
                break
            if l_ref is not None and row["close"] < l_ref - TOL and df["close"].iloc[j + 1] < l_ref - TOL:
                brk_idx, brk_dir = j, "down"
                break
        j += 1

    # Finale Grenzen: Schnittmengen-Linie, Geburtszone nur bei realem Test
    U_final = _final_level_bestaetigt(level_schnittmenge(h_acc, "H"), birth_h, "H", U_conf_ts)
    L_final = _final_level_bestaetigt(level_schnittmenge(l_acc, "L"), birth_l, "L", L_conf_ts)

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
            "break_dir": None,
        })
        break

    # Phasen-Ende = letzter Touch der GEGENgrenze vor dem Ausbruch
    if brk_dir == "down":
        t_arr = np.array([abs(x - U_final) <= TOL_TOUCH for x in h_acc]) if h_acc else np.array([], dtype=bool)
        if t_arr.any():
            k = int(np.where(t_arr)[0][-1])
            ende_ts, ende_pr = h_ts[k], h_acc[k]
        else:
            ende_ts, ende_pr = df["ts"].iloc[i], None
        moves.append({"dir": "down", "von_ts": ende_ts, "von_pr": ende_pr,
                      "bis_ts": df["ts"].iloc[brk_idx], "bis_pr": float(df["low"].iloc[brk_idx])})
    else:
        t_arr = np.array([abs(x - L_final) <= TOL_TOUCH for x in l_acc]) if l_acc else np.array([], dtype=bool)
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
        "U_final": _final_level_bestaetigt(level_schnittmenge(h_clean, "H"), birth_h, "H", U_conf_ts),
        "L_final": _final_level_bestaetigt(level_schnittmenge(l_clean, "L"), birth_l, "L", L_conf_ts),
        "h_prices": h_clean, "l_prices": l_clean,
        "h_ts": h_clean_ts, "l_ts": l_clean_ts,
        "birth_h": birth_h, "birth_l": birth_l,
        "U_conf_ts": U_conf_ts, "L_conf_ts": L_conf_ts,
        "U_ts": h_ts[len(h_clean) - 1] if h_clean else None,
        "L_ts": l_ts[len(l_clean) - 1] if l_clean else None,
        "U_hist": hist_U, "L_hist": hist_L,
        "break_dir": brk_dir,
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
        p["U_final"] = _final_level_bestaetigt(level_schnittmenge(p["h_prices"], "H"), p["birth_h"], "H", p["U_conf_ts"])
        p["L_final"] = _final_level_bestaetigt(level_schnittmenge(p["l_prices"], "L"), p["birth_l"], "L", p["L_conf_ts"])
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

# ---------- 5b) UEBERSICHT (erweiterter Testbereich ab 10.08.) ----------
# Regression-Check gegen die 21.08.-Trader-Sicht ist hier bewusst aus: Der
# erweiterte Bereich erzeugt zusaetzliche Vor-Phasen. Die Phase(n) ab 21.08.
# muessen weiterhin der Trader-Sicht entsprechen.
_erwartet = [
    {"start": "2026-08-21 00:00", "ende": "2026-08-25 02:00", "U": 69.914, "L": 68.370},
    {"start": "2026-08-25 04:30", "ende": "2026-08-27 19:00", "U": 69.684, "L": 67.571,
     "U_conf": "2026-08-26 04:30"},
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

# ---------- 6) Ausgabe ----------
pd.set_option("display.width", 230)
print("\n=== PHASEN (Trader-Sicht, Schnittmengen-Linien) ===")
for i, p in enumerate(phases, 1):
    u_str = f"{p['U_final']:.3f}" if p['U_final'] is not None else "N/A"
    l_str = f"{p['L_final']:.3f}" if p['L_final'] is not None else "N/A"
    ok = " [HANDELBAR]" if p["handelbar"] else ""
    print(f"Phase {i}: {p['start']:%a %d.%m %H:%M} -> {p['ende']:%a %d.%m %H:%M} "
          f"({p['handels_h']:.1f}h, {p['n_candles']}C) | OBEN {u_str} | UNTEN {l_str} "
          f"| Breite {p['spread']:.3f} ({p['spread_pct']:.2f}%){ok} "
          f"| Pivots: {p['touches_h']}H/{p['touches_l']}L | Grenz-Touches: {p['close_h']}H/{p['close_l']}L")
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

print("\n=== HANDELBARE RANGES (Filter: >= %d Touches je Grenze, >= %d Candles, Breite >= %.1f%%) ==="
      % (MIN_TOUCHES, MIN_CANDLES, MIN_SPREAD_PCT))
ranges = [p for p in phases if p["handelbar"]]
for i, p in enumerate(ranges, 1):
    b = (p['U_final'] - p['L_final']) if (p['U_final'] and p['L_final']) else 0.0
    print(f"\nRange {i}: {p['start']:%a %d.%m %H:%M} -> {p['ende']:%a %d.%m %H:%M}  ({p['handels_h']:.1f}h)")
    print(f"    OBEN  {p['U_final']:.3f}  ({p['close_h']}x Grenz-Touches von {p['touches_h']} H-Pivots)")
    print(f"    UNTEN {p['L_final']:.3f}  ({p['close_l']}x Grenz-Touches von {p['touches_l']} L-Pivots)")
    print(f"    Breite {b:.3f} USD | Highs nahe Grenze: "
          f"{[float(round(x,3)) for x in p['h_prices'] if abs(x-p['U_final'])<=DENSITY_BAND]} | Lows nahe Grenze: "
          f"{[float(round(x,3)) for x in p['l_prices'] if abs(x-p['L_final'])<=DENSITY_BAND]}")

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

    # --- Zonen-Entwicklung: alte Linienpositionen vor den Verschiebungen ---
    # Variante C: Die Hist-Treppe endet an der Geburtszonen-Bestaetigung
    # (dort beginnt die solid-Linie), nicht am Phasenende.
    for (hist, typ, offs, final, conf_ts) in [
            (p["U_hist"], "OBEN", 0.12, p["U_final"], p.get("U_conf_ts")),
            (p["L_hist"], "UNTEN", -0.20, p["L_final"], p.get("L_conf_ts"))]:
        if not hist:
            continue
        xs = [df["idx"][df["ts"] == t].iloc[0] for t, _ in hist]
        ys = [v for _, v in hist]
        hist_end = p["i_ende"]
        if conf_ts is not None:
            m = df["idx"][df["ts"] == conf_ts]
            if len(m) and int(m.iloc[0]) > xs[0]:
                hist_end = int(m.iloc[0])
        # Schritt bis hist_end mit dem Endwert ergaenzen (Treppe schliesst)
        if final is not None and (not xs or xs[-1] < hist_end):
            xs = xs + [hist_end]
            ys = ys + [final]
        ax.step(xs, ys, where="post", color=c, lw=1.0, alpha=0.45, ls="--")
        ax.plot(xs[:-1] if final is not None else xs, ys[:-1] if final is not None else ys,
                "o", color=c, ms=3.5, alpha=0.55)
        # Startposition (= aelteste etablierte Linie) an ihrem Zeitpunkt markieren
        ax.text(xs[0], hist[0][1] + offs, f"{typ} START {hist[0][1]:.2f}",
                fontsize=7.5, color=c, alpha=0.85, fontweight="bold")

    # --- finale Grenzen (Variante C) ---
    # Geburtszone = GESTRICHELTE Projektion bis zur 1. realen Bestaetigung,
    # danach SOLID (bestätigte Zone). Ohne Bestaetigung bleibt die Projektion
    # gestrichelt und die finale Linie ist die reine Schnittmenge.
    for (proj_val, conf_ts, final, typ, offs) in [
            (p.get("U_proj_val"), p.get("U_conf_ts"), p["U_final"], "OBEN", 0.15),
            (p.get("L_proj_val"), p.get("L_conf_ts"), p["L_final"], "UNTEN", -0.25)]:
        if final is None:
            continue
        conf_idx = None
        if conf_ts is not None:
            m = df["idx"][df["ts"] == conf_ts]
            if len(m):
                conf_idx = int(m.iloc[0])
        if proj_val is not None and conf_idx is not None:
            # Projektion (geerbte Geburtszone) gestrichelt bis zur Bestaetigung
            ax.hlines(proj_val, p["i_start"], conf_idx, color=c, lw=1.5, alpha=0.7, ls="--")
            ax.text(p["i_start"], proj_val + offs, f"{typ} PROJ {proj_val:.2f}",
                    fontsize=8.5, color=c, alpha=0.85, fontweight="bold")
            # ab Bestaetigung: real (solid)
            ax.hlines(final, conf_idx, p["i_ende"], color=c, lw=2.2, alpha=0.95)
            ax.text(conf_idx, final + offs, f"{typ} {final:.2f}",
                    fontsize=8.5, color=c, fontweight="bold")
        elif proj_val is not None:
            # NIE bestaetigt: Projektion bleibt gestrichelt (schwach), finale Linie = reine Schnittmenge
            ax.hlines(proj_val, p["i_start"], p["i_ende"], color=c, lw=1.2, alpha=0.4, ls="--")
            ax.text(p["i_start"], proj_val + offs, f"{typ} PROJ {proj_val:.2f}",
                    fontsize=8.5, color=c, alpha=0.7, fontweight="bold")
            ax.hlines(final, p["i_start"], p["i_ende"], color=c, lw=2.0, alpha=0.9)
            ax.text(p["i_start"], final + offs, f"{typ} {final:.2f}",
                    fontsize=8.5, color=c, fontweight="bold")
        else:
            # keine (grenzbestimmende) Geburtszone: normale finale Linie
            ax.hlines(final, p["i_start"], p["i_ende"], color=c, lw=2.0, alpha=0.9)
            ax.text(p["i_start"], final + offs, f"{typ} {final:.2f}",
                    fontsize=8.5, color=c, fontweight="bold")

for m in moves:
    ix = df["idx"][df["ts"] == m["von_ts"]].iloc[0] if (df["ts"] == m["von_ts"]).any() else np.nan
    iy = df["idx"][df["ts"] == m["bis_ts"]].iloc[0] if (df["ts"] == m["bis_ts"]).any() else np.nan
    if np.isnan(ix) or np.isnan(iy):
        continue
    ax.annotate("", xy=(iy, m["bis_pr"]), xytext=(ix, m["von_pr"]),
                arrowprops=dict(arrowstyle="->", color="k", lw=2.2, connectionstyle="arc3,rad=0.0"))
    ax.text((ix + iy) / 2, (m["von_pr"] + m["bis_pr"]) / 2,
            f"Move {'DOWN' if m['dir']=='down' else 'UP'}\n{m['von_pr']:.2f}->{m['bis_pr']:.2f}",
            fontsize=8, color="k", ha="center", va="center", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.8))

step = max(8, len(df) // 16)
ticks = np.arange(0, len(df), step)
ax.set_xticks(ticks)
ax.set_xticklabels([df["ts"].iloc[t].strftime("%a %d.%m %H:%M") for t in ticks], rotation=45, ha="right", fontsize=8)
ax.set_xlim(-1, len(df))
ax.set_title(f"SILVER M15 21.-27.08.2026 - Schnittmengen-Phasen + Zonen-Entwicklung "
             f"(P1 Fr-Di 69.9/68.4 -> P2 Di-Do 19h 69.67/67.56, Geburtszone gestrichelt bis Bestaetigung)")
ax.set_ylabel("USD")
ax.grid(alpha=0.3)

# Legende: finale Zone vs. historische Linienpositionen
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color="gray", lw=2.0, label="finale Zone (bestätigt)"),
    Line2D([0], [0], color="gray", lw=1.5, ls="--", label="Geburtszone (Projektion, bis Bestätigung)"),
    Line2D([0], [0], color="gray", lw=1.2, ls="--", label="alte Linienposition (vor Verschiebung)"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor="gray", ms=4,
           label="Verschiebungs-Zeitpunkt"),
]
ax.legend(handles=legend_elements, loc="upper right", fontsize=8, framealpha=0.9)

fig.tight_layout()
fig.savefig(OUT_PNG, dpi=130)
print(f"\nChart gespeichert: {OUT_PNG}")
