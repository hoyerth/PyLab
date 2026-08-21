  ═══ KONZEPT: Einheitliche Signal-Engine v3 (RAM für visuell · DB für Analytics) ═════

  Kernidee: Die Ereignis-Normalisierung (SignalEvents) ist die EINZIGE Wahrheit.
  Das Modul signal_service.py kennt ZWEI Speicher-Implementierungen hinter dem
  GLEICHEN Interface – in der visuellen Session wird in den RAM geschrieben
  (kein DB-Schreiben!), in der Massenauswertung in die analytics_data.duckdb.
  Der Chart und die DB-Zeile entstehen aus demselben normalisierten Event.

  Nutze Vektorisierung wo möglich

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  algos/base_indicator.py   (ABC + Contracts, NEU)                            │
  │  class BaseIndicator: compute(df, symbol, timeframe) -> IndicatorResult      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │  ma_indicator / grid_indicator  ── compute() ──┐                              │
  │  (weitere)                                      ▼                             │
  │                                     IndicatorResult                            │
  │                                     ├─ df          (OHLCV + Berechnungen)     │
  │                                     ├─ events      (NUR Treffer, normalisiert)│
  │                                     └─ plot_meta   (Farben/Linienstile)       │
  └─────────────────────────────────────────────────────────────────────────────┘
                                              │
                      ┌───────────────────────┴────────────────────────┐
                      ▼                                                ▼
       ┌────────────────────────────────┐              ┌──────────────────────────┐
       │  VISUELLE SESSION (RAM)        │              │  ANALYTICS (Massen-DB)   │
       │  SignalStore(memory)           │              │  SignalStore(duckdb)     │
       │  = In-Memory-Repository        │              │  = persist_run(result)   │
       │                                │              │                          │
       │  compute() → events in RAM     │              │  Param-Grid → compute()  │
       │  Chart-Adapter liest events    │              │  → events → Batch in     │
       │  direkt aus dem Memory-Store   │              │    analytics_data.duckdb │
       │  KEIN DB-Zugriff, KEIN Schreib │              │  (nur Treffer)           │
       └────────────────────────────────┘              └──────────────────────────┘
                       beide nutzen die GLEICHE Normalisierung:
                       events → to_events_frame()  (eine Funktion, ein Format)
  ─────────────────────────────────────────────────────────────────────────────

  1. EINHEITLICHES EVENT-FORMAT (algos/signal_events.py, NEU)
  ─────────────────────────────────────────────────────────────────────────────
  @dataclass
  class SignalEvent:
      time: pd.Timestamp      # Treffer-Zeitpunkt
      signal_type: str        # "swing_change" | "circle_yellow" | "circle_fuchsia"
      direction: int          # 1=Long, -1=Short, 0=neutral
      price: float            # Kurs am Treffer
      strength: float         # 0.0–1.0
      meta: Dict[str, Any]    # z.B. {"ma_col":"ma_ehma_6"} / {"level":64.30}

  @dataclass
  class IndicatorResult:
      symbol, timeframe, indicator_name, params
      df: pd.DataFrame        # angereichert (ma_*, grid_*)
      events: List[SignalEvent]
      plot_meta: Dict[str, Any]

      def to_events_frame(self) -> pd.DataFrame:   # ← DIE Normalisierung
          """Eine flache Tabelle: time, signal_type, direction, price,
             strength, meta_json + symbol/timeframe/indicator/params.
             RAM-Chart UND DB-Persistenz füttern sich daraus."""

  2. EIN MODUL, ZWEI SPEICHER (algos/signal_service.py, NEU)
  ─────────────────────────────────────────────────────────────────────────────
  class SignalService:                      # EIN Interface
      def store_result(self, result: IndicatorResult) -> None
      def get_events(self, **filters) -> pd.DataFrame
      def clear(self) -> None

  class MemorySignalService(SignalService):
      """Visuelle Session: hält IndicatorResult + Events im RAM.
         Kein DB-Schreiben. Chart-Adapter liest hieraus.             """
      _results: List[IndicatorResult]      # RAM
      def store_result(self, r): self._results.append(r)
      def get_events(self, ...): return pd.concat(r.to_events_frame() ...)
      def clear(self): self._results.clear()

  class DuckDBSignalService(SignalService):
      """Analytics: schreibt dieselben Events nach analytics_data.duckdb.
         Gleiches to_events_frame() → gleiche Spalten wie im RAM.      """
      def store_result(self, r): persist_run(r)   # run + signal_events
      def get_events(self, ...): SELECT ... FROM signal_events ...

  # HINWEIS: Beide nutzen 100 % dieselbe Normalisierung. Die einzige
  # Entscheidung ist die Store-Instanz → Vorteil: einmal getestet, überall korrekt.

  3. DATENBANK (nur Analytics-Pfad, analytics_data.duckdb)
  ─────────────────────────────────────────────────────────────────────────────
  CREATE TABLE indicator_runs (
      run_id VARCHAR PRIMARY KEY,           -- sha256(indikator+params+symbol+tf)
      indicator_name VARCHAR, symbol VARCHAR, timeframe VARCHAR,
      params_json JSON, created_at TIMESTAMPTZ DEFAULT now()
  );
  CREATE TABLE signal_events (
      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      run_id VARCHAR REFERENCES indicator_runs(run_id),
      time TIMESTAMPTZ, signal_type VARCHAR,
      direction TINYINT, price DOUBLE, strength DOUBLE, meta_json JSON
  );
  Massen-Query (nur Treffer):
  SELECT r.symbol, r.timeframe, e.time, e.signal_type, e.direction,
         e.price, e.strength
  FROM signal_events e JOIN indicator_runs r USING (run_id)
  WHERE r.symbol=? AND r.timeframe=? AND e.signal_type IN ('swing_change','circle_yellow')
  ORDER BY e.time;

  4. WORKFLOWS
  ─────────────────────────────────────────────────────────────────────────────
  VISUELL (01_Chart_Inspector.py):
    service = MemorySignalService()               # RAM, nichts wird geschrieben
    result  = ma.compute(df, SYMBOL, TIMEFRAME)   # + grid.compute(...)
    service.store_result(result)                  # → RAM
    show_chart(..., results=[ma_result, grid_result])
    # Chart-Adapter baut Marker aus result.events (RAM), MAs/Grid aus df+plot_meta.
    # Jeder Slider-/Parameter-Update überschreibt den RAM-Store (clear + neu).

  ANALYTICS (02_signal_lab.py, NEU):
    service = DuckDBSignalService()               # → analytics_data.duckdb
    for params in param_grid:
        result = indicator.compute(df, ...)
        service.store_result(result)              # Batch-INSERT, nur Treffer
    # Danach: get_events() als DataFrame → Table/Export/VectorBT

  5. BESTANDSINDIKATOREN → compute()-MIGRATION (Logik bleibt unverändert)
  ─────────────────────────────────────────────────────────────────────────────
  MAIndicator:   Richtungswechsel → SignalEvent("swing_change", dir=±1,
                 price=close, strength=1.0)
  GridIndicator: hit_circles → gelb = "circle_yellow", fuchsia = "circle_fuchsia";
                 Grid-Linien/Level wandern in plot_meta (nur Optik, keine Events).

  6. OFFENE DESIGNPUNKTE
  ─────────────────────────────────────────────────────────────────────────────
  • Grid-Anker "last_bar": für historische Massenscans ggf. anchor_mode="per_bar".
  • Warmup: compute() rechnet über Warmup; RAM-Chart filtert sichtbares Fenster,
    DB-Persistenz kann optional den Warmup-Bereich ausschließen.
  • Zeitzonen: Events in UTC halten; Chart rendert mit tz_offset_hours.

 Kurz zusammengefasst: compute() erzeugt einmalig IndicatorResult mit normalisierten SignalEvents. Ein SignalService-Interface mit zwei Implementierungen (Memory für die visuelle Session ohne DB, DuckDB für Analytics) konsumiert dieselben
 Events über dieselbe to_events_frame()-Normalisierung. So bleibt die Optik quelloffen im RAM überprüfbar und die Massenauswertung nutzt exakt dieselbe Datenbasis.