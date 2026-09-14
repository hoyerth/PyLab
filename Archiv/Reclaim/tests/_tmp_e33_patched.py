def _se_trades(scan: Dict, cfg: StraightEdgeHarnessKonfiguration
               ) -> Tuple[List[_SESetup], Dict[str, int]]:
    """Regel-2-Trades an der aeussersten AKTIVEN Kante (D4, 2026-09-08).

    Q1: Die aeusserste Linie handelt ohne V-S >= 3 — die Reclaim-Abweisung
    IST die operative Reife; V-S >= 3 bleibt Schutz innerer (stummer) Linien.
    Q9b/Q13: promovierte Primaer-Anker sind handelbar, Basis eingefroren.
    Q2/Q3/Q17: echter Durchstich + Stufen 1/2/3 (Non-Expansion mit Puffer).
    Q4: F3-Frische referenziert den Sweep-Bar.
    Q6/Q10: SL = Cluster-Extremum (kausal bis Reclaim-Bar) + Puffer.
    Q11/Q16: F2 — Einstieg nur ohne offene Position ODER nach De-Risking
    (Haelfte 1 = TP1). Q8: gleicher Schwung sperrt im Vollrisiko.
    Q5/Q14: TP2 = aeusserste Gegenkante (>= 2 Touches, >= 1.5 %, SCHLAFEND ok).
    Nur in der Box (bars < box_end_bar).
    """
    d = scan["d"]
    hi = d["high"].to_numpy(dtype=float)
    lo = d["low"].to_numpy(dtype=float)
    cl = d["close"].to_numpy(dtype=float)
    op = d["open"].to_numpy(dtype=float)
    alle: List[_SEEdgeH] = list(scan["edges"]) + list(scan["seeds"])
    seite_edges: Dict[KantenSeite, List[_SEEdgeH]] = {
        "OBEN": [e for e in alle if e.seite == "OBEN"],
        "UNTEN": [e for e in alle if e.seite == "UNTEN"]}
    setups: List[_SESetup] = []
    box_end = scan["box_end_bar"]
    stats: Dict[str, int] = {"v_s": 0, "kein_gegner": 0, "f3": 0,
                             "kein_raum": 0, "zyklus_blockiert": 0,
                             "quartil_blockiert": 0, "blocker": 0,
                             "promotionen": 0,
                             "stacking_blockiert": 0,
                             "frisch_blockiert": 0}
    poc_start = 0                       # Balance-Beginn (Box-Beginn)
    letzter_trade: Dict[int, _SESetup] = {}
    getradete_entry_bars: set[int] = set()   # B23-3: Dedup je Entry-Bar
    stacking_liste: List[str] = []        # §7.1 B (Teil 4)
    zyklus_liste: List[str] = []
    quartil_liste: List[str] = []
    blocker_liste: List[str] = []

    def _existiert(e: _SEEdgeH, k: int) -> bool:
        """Linie existiert, sobald ihr level-definierender Pivot bestaetigt ist.

        Bestaetigung = Pivot-Bar + 2 (P1). Fuer den fruehestmoeglichen Entry
        (k+1) bedeutet das: erster_pivot_bar + 2 <= k + 1. Die Keimung
        (>= 2 Touches) ist KEINE Existenzbedingung — sie bestimmt nur die
        ZWISCHEN_LEVEL-Rolle.
        """
        if not e.ist_aktiv_bei(k):
            _ev = ((hi[k] > e.basis_bei(k)) if e.seite == "OBEN"
                   else (lo[k] < e.basis_bei(k)))
            if not (_VSB and (not _LOK or _zv(k)) and _ev):
                return False
        return e.erster_pivot_bar + 2 <= k + 1

    def _lebt(e: _SEEdgeH, k: int) -> bool:
        """Q25: Linie ist am Markt praesent (letzter Kontakt <= wall_live_bars).

        Dormante Crash-Extreme (K3 62.967/Bar 14, K4 63.252/Bar 20) sind keine
        Begrenzung der aktuellen Balance und duerfen die Unterseite nicht
        lahmlegen; eine LEBENDE, nicht erreichte Aussenlinie sperrt dagegen
        jeden Einstieg weiter innen.
        """
        bars = [b for b, _ in e.wicks if b <= k]
        if not bars:
            return False
        return max(bars) >= k - cfg.wall_live_bars

    def _basis_wirksam(e: _SEEdgeH, k: int) -> float:
        return _hook.angewandte_basis(k, e.kid, e.basis_bei(k))

    def _seite_kanten(k: int, seite: KantenSeite) -> List[Tuple[int, float]]:
        return [(e.kid, _basis_wirksam(e, k)) for e in seite_edges[seite]
                if _existiert(e, k)]

    _freigabe_kid: Optional[int] = None

    def _im_aussenquartil(richtung: SignalRichtung, k: int,
                          sweep_px: float) -> bool:
        """Q29: Einstieg nur an der aeusseren lebenden Wand.

        Distanz des Sweep-Extremums zum laufenden Range-Extrem,
        normiert auf die kausale Spanne 0..k. Aeusseres Quartil =
        <= quartil_distanz_pct (Default 25 %).
        """
        _q0 = 0
        if _VC and (not _LOK or _zv(k)):
            _sq = _hook.aktive_phase_bei(k)
            if _sq is not None:
                _q0 = int(_sq.start_bar)
        ex_hi = float(np.max(hi[_q0:k + 1]))
        ex_lo = float(np.min(lo[_q0:k + 1]))
        spanne = ex_hi - ex_lo
        if spanne <= 0.0:
            return True
        distanz = ((ex_hi - sweep_px) if richtung == "SHORT"
                   else (sweep_px - ex_lo)) / spanne * 100.0
        return distanz <= cfg.quartil_distanz_pct

    def _blockiert_durch_aussenkante(richtung: SignalRichtung, k: int,
                                     kd: _SEEdgeH,
                                     sweep_px: float) -> Optional[_SEEdgeH]:
        """M6: Innenlevel-Blocker (kein Fade unter einer Aussenwand).

        Blocker ist die AEUSSERSTE existierende Linie derselben Seite, die
        vom Sweep-Extremum NICHT erreicht wurde (jenseits des Sweeps liegt)
        und deren Abstand zur Kandidatenbasis <= max_seed_distanz_pct
        (0.75 %) ist. Nur _existiert-Linien (AKTIV) wirken als Blocker (F3).
        Die AEUSSERSTE Linie ist entscheidend: eine naehere Innenlinie darf
        die Sperre nicht ausloesen, wenn die Aussenwand selbst erreicht wurde.
        """
        seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
        basis_k = _basis_wirksam(kd, k)
        aussen: Optional[_SEEdgeH] = None
        for e in seite_edges[seite]:
            if e is kd or not _existiert(e, k) or (
                    _VM6 and (not _LOK or _zv(k)) and not _lebt(e, k)):
                continue
            b = _basis_wirksam(e, k)
            if seite == "OBEN":
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue
                if b <= sweep_px:
                    continue                    # erreicht -> kein Blocker
                if aussen is None or b > _basis_wirksam(aussen, k):
                    aussen = e
            else:
                if _freigabe_kid is not None and e.kid == _freigabe_kid:
                    continue
                if b >= sweep_px:
                    continue
                if aussen is None or b < _basis_wirksam(aussen, k):
                    aussen = e
        if aussen is None:
            return None
        b = _basis_wirksam(aussen, k)
        dist = ((b - basis_k) if seite == "OBEN"
                else (basis_k - b)) / basis_k * 100.0
        return aussen if 0.0 < dist <= cfg.max_seed_distanz_pct else None

    def _etabliert(e: _SEEdgeH, k: int) -> bool:
        """Q24: Linie ist etabliert, wenn ihr level-definierender Pivot
        mindestens min_wall_alter_bars zurueckliegt (kein Fade des ersten
        Ausbruchsversuchs einer frischen Linie).
        """
        return k - e.erster_pivot_bar >= cfg.min_wall_alter_bars

    def _kandidat(richtung: SignalRichtung, k: int,
                  sweep_px: float) -> Optional[_SEEdgeH]:
        """Kaskade von aussen nach innen ueber EXISTIERENDE Linien (Regel 2).

        - top = hoechste/tiefste existierende Linie.
        - dist(top) <= 0            -> kein Trade (kein Fading unter der Wand)
        - dist(top) > touch_band    -> top handelt (Q1: Reclaim = Reife)
        - dist(top) <= touch_band   -> in-band beruehrt (kein Sweep) ->
          naechste Linie nach innen; innere Linien brauchen V-S >= 3
        - dist > max_sweep          -> Ueberdehnung, kein Trade
        """
        seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"

        def _dist(e: _SEEdgeH) -> float:
            basis = _basis_wirksam(e, k)
            if richtung == "SHORT":
                return (sweep_px - basis) / basis * 100.0
            return (basis - sweep_px) / basis * 100.0

        pool: List[_SEEdgeH] = []
        for e in seite_edges[seite]:
            if not _existiert(e, k):
                continue
            # B23-2: Anker wirkt erst ab seiner Promotions-Bar (kausal).
            if not ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                    or e.touch_conf(k) >= 2):
                continue                        # Seeds nur ereignisgetrieben
            if not _etabliert(e, k):
                if _dist(e) > cfg.touch_band_pct:
                    _hit(_CUR, "frisch_blockiert")
                continue                        # Q24: Linie noch zu jung
            pool.append(e)
        # Q9b: ein Seed zaehlt NUR, wenn dieser Bar ihn tatsaechlich
        # durchsticht (K3/K4 werden in der Box nie unterschritten).
        for e in seite_edges[seite]:
            if e in pool or not _existiert(e, k) or e.ist_prim_anker:
                continue
            if e.touch_conf(k) >= 2 or not _etabliert(e, k):
                continue
            d = _dist(e)
            if cfg.sweep_mindestdurchstich_pct < d <= _ueb(k):
                pool.append(e)
        if not pool:
            return None
        pool.sort(key=lambda e: _basis_wirksam(e, k),
                  reverse=(seite == "OBEN"))
        if _freigabe_kid is not None:
            pool = [e for e in pool if e.kid != _freigabe_kid]
        for pos, e in enumerate(pool):
            dist = _dist(e)
            if dist < 0.0:
                if _lebt(e, k):
                    return None                 # lebende Wand nicht erreicht
                continue                        # dormante Linie ignorieren
            if dist > _ueb(k):
                return None                     # Ueberdehnung, kein Reclaim
            if dist <= cfg.sweep_mindestdurchstich_pct:
                continue                        # nur Durchstich zaehlt (Teil 7)
            if pos == 0:
                return e                        # Q1: Wand handelt (Reclaim=Reife)
            if e.touch_conf(k) < cfg.min_touches_handelbar:
                continue                        # innere Linie braucht V-S >= 3
            return e
        return None

    def _gegenkante(richtung: SignalRichtung, k: int) -> Optional[_SEEdgeH]:
        """Q5/Q14: aeusserste Gegenkante (>= 2 Touches, SCHLAFEND zulaessig)."""
        gegenseite: KantenSeite = "UNTEN" if richtung == "SHORT" else "OBEN"
        # Block2/Q30: identische Existenz-Semantik wie _kandidat (Pivot+2),
        # bewusst OHNE AKTIV-Gate (Q5/Q14: SCHLAFENDE Gegenkanten erlaubt).
        # Q18/Q30: promovierte Primaer-Anker ohne 2-Touch-Gate.
        pool = [e for e in seite_edges[gegenseite]
                if e.erster_pivot_bar + 2 <= k + 1
                and ((e.ist_prim_anker and k >= e.promoviert_ab_bar)
                     or e.touch_conf(k) >= 2)]
        if not pool:
            return None
        if gegenseite == "OBEN":
            return max(pool, key=lambda e: e.basis_bei(k))
        return min(pool, key=lambda e: e.basis_bei(k))

    for k in range(2, box_end - 3):
        for richtung in ("SHORT", "LONG"):
            sweep_px = float(hi[k]) if richtung == "SHORT" else float(lo[k])
            _seite: KantenSeite = ("OBEN" if richtung == "SHORT" else "UNTEN")
            _CUR[0] = k
            _CUR[1] = richtung
            _freigabe_kid = _hook.hook_1_freigabe_kid(
                k, sweep_px, richtung, _seite_kanten(k, _seite))
            kd = _kandidat(richtung, k, sweep_px)
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s sweep=%.4f kd=%s" % (
                    k, richtung, sweep_px,
                    "None" if kd is None else "K%d b=%.4f" % (
                        kd.kid, _basis_wirksam(kd, k))))
            if kd is None:
                continue
            # --- M6: Innenlevel-Blocker (unerreichte Aussenwand) ---------------
            blk = _blockiert_durch_aussenkante(richtung, k, kd, sweep_px)
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s M6-Blocker=%s" % (
                    k, richtung, "None" if blk is None else "K%d" % blk.kid))
            if blk is not None:
                _hit(_CUR, "blocker")
                blocker_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} sweep={sweep_px:.3f} "
                    f"-> BLOCKER-SPERRE (unerreichte Aussenwand K{blk.kid} "
                    f"{blk.basis_bei(k):.3f})")
                continue
            # --- Q29: Niemandsland-Sperre (aeusseres Quartil) ----------
            _q_ok = _im_aussenquartil(richtung, k, sweep_px)
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s Q29 -> %s" % (
                    k, richtung, "durch" if _q_ok else "SPERRE"))
            if not _q_ok:
                _hit(_CUR, "quartil_blockiert")
                quartil_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} sweep={sweep_px:.3f} "
                    f"-> QUARTIL-SPERRE (Mitte der Range)")
                continue
            seite: KantenSeite = "OBEN" if richtung == "SHORT" else "UNTEN"
            basis = _basis_wirksam(kd, k)
            stufe_n, stufe_name = _reclaim_stufe(seite, k, basis, hi, lo, cl,
                                                 cfg)
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s Stufe=%d" % (k, richtung, stufe_n))
            if stufe_n == 0:
                continue
            entry_bar = k + stufe_n
            reclaim_bar = entry_bar - 1
            # --- Q4: F3-Frische (Sweep-Bar-Referenz) --------------------------
            if k <= kd.letzter_sweep_bar:
                if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s F3-Frische" % (k, richtung))
                _hit(_CUR, "f3")
                continue
            # --- Q6/Q10: Cluster-Extremum kausal bis Reclaim-Bar --------------
            if richtung == "SHORT":
                cluster_ext = float(np.max(hi[k:reclaim_bar + 1]))
                sl = cluster_ext + cfg.sl_buffer_usd
            else:
                cluster_ext = float(np.min(lo[k:reclaim_bar + 1]))
                sl = cluster_ext - cfg.sl_buffer_usd
            # --- Q21/B23: Retest-Zyklus (ersetzt F2-Vollrisiko + Q8) ----------
            # B23-5: letzter_sweep_bar wird NUR bei tatsaechlich genommenem
            # Trade fortgeschrieben (siehe unten) -- ein abgewiesener Kontakt
            # setzt die Uhr nicht zurueck.
            _vor_zeit = letzter_trade.get(kd.kid)
            if (_vor_zeit is not None
                    and entry_bar - _vor_zeit.entry_bar
                    < cfg.retest_zyklus_bars):
                if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s Zyklus-Sperre" % (k, richtung))
                _hit(_CUR, "zyklus_blockiert")
                zyklus_liste.append(
                    f"bar {k:4d} {richtung:5s} K{kd.kid:3d} "
                    f"basis={kd.basis_bei(k):.3f} -> ZYKLUS-SPERRE "
                    f"(letzter Sweep Bar {kd.letzter_sweep_bar}, "
                    f"Abstand {k - kd.letzter_sweep_bar} "
                    f"< {cfg.retest_zyklus_bars})")
                continue
            geg = _gegenkante(richtung, k)
            if geg is None:
                if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_gegner (keine Gegenkante)" % (k, richtung))
                _hit(_CUR, "kein_gegner")
                continue
            gegen_basis = geg.basis_bei(k)
            _h2 = _hook.hook_2_ziel(k, richtung)
            if _h2.modus is _Hook2ZielModus.BLOCKIERT:
                if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s REGIME-VAKUUM" % (k, richtung))
                _hit(_CUR, "vakuum")
                continue
            if _h2.modus is _Hook2ZielModus.PHASE:
                gegen_basis = _h2.ziel_preis
            if richtung == "SHORT":
                if not (gegen_basis < basis):
                    if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                    _hit(_CUR, "kein_raum")
                    continue
                if abs(basis - gegen_basis) / basis * 100.0 < V3_TP_MINDIST_PCT:
                    if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                    _hit(_CUR, "kein_raum")
                    continue
                unter, ober = gegen_basis, basis
            else:
                if not (gegen_basis > basis):
                    if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                    _hit(_CUR, "kein_raum")
                    continue
                if abs(gegen_basis - basis) / basis * 100.0 < V3_TP_MINDIST_PCT:
                    if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                    _hit(_CUR, "kein_raum")
                    continue
                unter, ober = basis, gegen_basis
            poc = berechne_kausalen_histogramm_poc(
                d, poc_start, k, unter, ober, cfg.num_bins)
            if not (unter < poc < ober):
                if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                _hit(_CUR, "kein_raum")
                continue
            entry = float(op[entry_bar])
            tp2 = gegen_basis
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s GEO sl=%.4f e=%.4f poc=%.4f "
                            "tp2=%.4f basis=%.4f" % (
                                k, richtung, sl, entry, poc, tp2, basis))
            if richtung == "SHORT":
                if not (sl > entry > poc > tp2):
                    if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                    _hit(_CUR, "kein_raum")
                    continue
            else:
                if not (sl < entry < poc < tp2):
                    if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                    _hit(_CUR, "kein_raum")
                    continue
            risk = abs(sl - entry)
            if risk <= 0:
                if _DBG is not None and k in _DBGB: _DBG.append("   bar %d %s kein_raum" % (k, richtung))
                _hit(_CUR, "kein_raum")
                continue
            # --- §7.1 B REVOZIERT (Teil 7): kein Stacking-Gate ----------
            # Der Schutz gegen Re-Entry-Spamming liegt beim 12-Bar-
            # Entry-Mindestabstand (B2, Zyklus-Check unten).
            trade = _c_loese_trade(
                hi, lo, cl, entry_bar, entry, richtung, sl, poc, tp2,
                cfg.tp1_anteil_pct)
            if entry_bar in getradete_entry_bars:   # B23-3: Dedup
                continue
            getradete_entry_bars.add(entry_bar)
            kd.letzter_signal_bar = k
            kd.letzter_sweep_bar = k
            # Strenge Regel: keine Seed-Promotion fuer Trades (V-S >= 3).
            if richtung == "SHORT":
                kd.cluster_hoch = max(kd.cluster_hoch, cluster_ext)
            else:
                kd.cluster_tief = (cluster_ext if kd.cluster_tief <= 0.0
                                   else min(kd.cluster_tief, cluster_ext))
            setup = _SESetup(
                bar=k, richtung=richtung, kid=kd.kid, basis=basis,
                sweep=sweep_px, trigger_close=float(cl[k]),
                touch_n=kd.touch_conf(k), poc=poc, tp2=tp2, sl=sl,
                entry=entry, r=trade.r_mult, resultat=trade.resultat,
                stufe=stufe_name or "STUFE_1_IN_BAR", reclaim_bar=reclaim_bar,
                entry_bar=entry_bar, ist_prim_anker=kd.ist_prim_anker,
                grund1=trade.grund1, exit1_bar=trade.exit1_bar,
                exit2_bar=trade.exit2_bar)
            letzter_trade[kd.kid] = setup
            setups.append(setup)
            _hit(_CUR, "SETUP")
            if _DBG is not None and k in _DBGB:
                _DBG.append("   bar %d %s ==> SETUP K%d R=%+.5f" % (
                    k, richtung, kd.kid, float(trade.r_mult)))

    # --- v0.20: Phasenboden-Regel G4 (generischer Hook-3-Konsum) -----------
    # Route A: Der Adapter AUTORISIERT, die Engine exekutiert. Der Guard ist
    # ZWINGEND, weil ``_hook`` im Standalone-Harness und im V0-Referenzlauf
    # des Renderers (``ORIG``, ``__globals__ == engine.__dict__``) NICHT
    # definiert ist. Ohne Guard: NameError. Inertheit ist zweistufig:
    #   (a) keine gebundene ``hook_3_boden_reclaim`` -> kein Block,
    #   (b) ``boden_deklariert_literal is None`` -> Segment uebersprungen.
    # Damit bleiben P9 / P9_DIRECT_69_87 / DEFAULT_ADAPTER / ADAPTER_V014
    # exakt auf Baseline (17 Trades); V01/V014-Bildsaetze byte-identisch.
    _hk_g4 = globals().get("_hook")
    _bspec_g4 = getattr(_hk_g4, "hook_3_boden_reclaim", None)
    if _bspec_g4 is not None:
        _kid_g4 = {e.kid: e for e in alle}
        for _seg_g4 in getattr(_hk_g4, "segmente", ()):
            _lit_g4 = getattr(_seg_g4, "boden_deklariert_literal", None)
            if _lit_g4 is None:
                continue
            # Fensterzugang aus dem Adapter: H1 (bars < 640) wird nicht
            # einmal iteriert - die Regressionsfreiheit ist strukturell.
            for _k_g4 in range(int(_seg_g4.start_bar),
                               int(_seg_g4.end_bar) + 1):
                # (1)+(2) Durchstich unter den deklarierten Boden + Reclaim.
                if not (lo[_k_g4] < _lit_g4 < cl[_k_g4]):
                    continue
                _spec_g4 = _bspec_g4(_k_g4)
                if _spec_g4 is None:
                    continue
                # Keine zweite Wahrheit: Spec-Literal == Segment-Literal.
                assert abs(float(_spec_g4.deklarierter_boden_literal)
                           - float(_lit_g4)) < 1e-12, _spec_g4
                _kante_g4 = _kid_g4.get(int(_spec_g4.boden_kid))
                if _kante_g4 is None:
                    continue
                # (3) V-S >= 3: kausale Touch-Bestaetigung der Bodenkante.
                if _kante_g4.touch_conf(_k_g4) < cfg.min_touches_handelbar:
                    continue
                _eb_g4 = _k_g4 + 1
                if _eb_g4 in getradete_entry_bars:      # B23-3: Dedup
                    continue
                _entry_g4 = float(op[_eb_g4])
                # Deklarierte Regel min(lo[k:k+2]) - Puffer; NICHT das
                # Nachbar-Idiom lo[k:reclaim_bar+1] (hier numerisch identisch,
                # aber bewusst die strengere Regelform).
                _sl_g4 = (float(lo[_k_g4:_eb_g4 + 1].min())
                          - cfg.sl_buffer_usd)
                # POC regel-lokal: Anker = PHASENSTART (nicht poc_start = 0).
                _poc_g4 = berechne_kausalen_histogramm_poc(
                    d, int(_seg_g4.start_bar), _k_g4, float(_lit_g4),
                    float(_spec_g4.tp2), cfg.num_bins)
                if not (_sl_g4 < _entry_g4 < _poc_g4 < _spec_g4.tp2):
                    continue
                _tr_g4 = _c_loese_trade(
                    hi, lo, cl, _eb_g4, _entry_g4, "LONG", _sl_g4,
                    _poc_g4, float(_spec_g4.tp2), cfg.tp1_anteil_pct)
                getradete_entry_bars.add(_eb_g4)
                # Stufe-1-In-Bar bindet Signal-Ausfuehrung an den
                # Entry-Bar-Trigger: ``reclaim_bar = entry_bar`` (V015-Staging,
                # byte-reproduzierend zu §68.5).
                setups.append(_SESetup(
                    bar=_k_g4, richtung="LONG",
                    kid=int(_spec_g4.boden_kid),
                    basis=float(_kante_g4.basis_bei(_k_g4)),
                    sweep=float(lo[_k_g4]), trigger_close=float(cl[_k_g4]),
                    touch_n=int(_kante_g4.touch_conf(_k_g4)),
                    poc=float(_poc_g4), tp2=float(_spec_g4.tp2),
                    sl=_sl_g4, entry=_entry_g4, r=float(_tr_g4.r_mult),
                    resultat=_tr_g4.resultat, stufe="STUFE_1_IN_BAR",
                    reclaim_bar=_eb_g4, entry_bar=_eb_g4,
                    ist_prim_anker=False, grund1=_tr_g4.grund1,
                    exit1_bar=int(_tr_g4.exit1_bar),
                    exit2_bar=int(_tr_g4.exit2_bar)))
    stats["promotionen"] = sum(1 for e in alle if e.ist_prim_anker)
    stats["v_s"] = len(setups)
    stats["zyklus_liste"] = zyklus_liste  # type: ignore[assignment]
    stats["quartil_liste"] = quartil_liste  # type: ignore[assignment]
    stats["blocker_liste"] = blocker_liste  # type: ignore[assignment]
    stats["stacking_liste"] = stacking_liste  # type: ignore[assignment]
    return setups, stats