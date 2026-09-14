"""
ARCHIV - VOLUMENPROFIL-SPEICHER (DUCKDB) (scripts/archiv/volume_profile_store_db.py)
====================================================================================
ARCHIVIERT am 2026-09-14. Volumenprofile werden NICHT in einer Datenbank
abgelegt: sie entstehen im Lauf und werden zur Laufzeit gehalten
(``scripts.volume_profile_store.ProfilSpeicher`` + ``HALTER``). Diese Datei
haelt die fruehere DuckDB-Ablage als REFERENZ fest - sie ist nicht mehr Teil
der Engine und wird nicht weiterentwickelt.

Warum keine Datenbankablegung
-----------------------------
Ein Profil ist an seinen Parametersatz gebunden (Symbol, Timeframe,
Fensterart, Bins, Glaettung, Anteile, Filter) und wird bei jeder
Parameteraenderung sofort ungueltig. Eine Dateiablage waere dann Altbestand,
der stillschweigend weiterverwendet werden koennte. Die Laufzeit-Haltung
vermeidet das: derselbe Parametersatz trifft denselben Speicher (``run_id``),
ein geaenderter Parametersatz legt einen NEUEN an - der alte Stand bleibt
unberuehrt, wird aber nie als Grundlage einer neuen Auswertung herangezogen.

Aufruf (nur noch als Referenz):
    from scripts.archiv.volume_profile_store_db import ProfilStore
    with ProfilStore(db_path, symbol, timeframe, window_kind, params) as store:
        store.schreibe(zeilen, nest_zeilen)

Die Zeilenvertraege (``ProfilZeile``/``NestZeile``) und die ``run_id``-Bildung
stammen unveraendert aus dem aktiven Modul ``scripts.volume_profile_store`` -
es gibt nur eine Definition dieser Vertraege.

--- Originalkopf (gekuerzt) --------------------------------------------------

Persistenz der gerechneten Volumenprofile in einer DuckDB-Datei. Kein
Rechenkern, kein Plot - dieses Modul schreibt und liest nur.

Default war eine EIGENE Datei ``data/volume_profiles.duckdb``, damit die
bestehenden Datenbanken (``market_data.duckdb`` = Marktdaten,
``analytics_data.duckdb`` = Indikator-Runs/Signale, ``backtest_data.duckdb``)
nicht angefasst werden.

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Gespeichert wurden ausschliesslich BKZ-Zeitstempel (``time AT TIME ZONE
'UTC'``, tz-naiv) als Spalten vom Typ ``TIMESTAMP`` OHNE Zeitzone. Damit kann
die DuckDB-Session-Zeitzone (``Europe/Budapest``) die abgelegten Werte nicht
verschieben (K2/F2). Zusaetzlich ist der Bar-Index der Primaerschluessel jeder
Zeile (K5).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import duckdb

from scripts.volume_profile_store import (
    SCHEMA_VERSION,
    NestZeile,
    ProfilZeile,
    _run_id,
)

_SQL_PROFILES = """
CREATE TABLE IF NOT EXISTS volume_profiles (
    schema_version  VARCHAR NOT NULL,
    run_id          VARCHAR NOT NULL,
    symbol          VARCHAR NOT NULL,
    timeframe       VARCHAR NOT NULL,
    window_kind     VARCHAR NOT NULL,
    label           VARCHAR NOT NULL,
    bar_start       BIGINT  NOT NULL,
    bar_ende        BIGINT  NOT NULL,
    ts_start        TIMESTAMP NOT NULL,
    ts_ende         TIMESTAMP NOT NULL,
    n_bars          BIGINT  NOT NULL,
    n_bars_gefiltert BIGINT NOT NULL,
    vol_summe       DOUBLE,
    atr             DOUBLE,
    poc             DOUBLE,
    val             DOUBLE,
    vah             DOUBLE,
    va_zone_pct     DOUBLE,
    va_abdeckung    DOUBLE,
    val_huelle      DOUBLE,
    vah_huelle      DOUBLE,
    n_segmente      BIGINT,
    lobe2           DOUBLE,
    poc_streu_atr   DOUBLE,
    poc_min         DOUBLE,
    poc_max         DOUBLE,
    poc_eindeutig   BOOLEAN,
    params_json     JSON,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT now(),
    PRIMARY KEY (run_id, bar_start, bar_ende)
);
"""

_SQL_NESTS = """
CREATE TABLE IF NOT EXISTS volume_profile_nests (
    run_id      VARCHAR NOT NULL,
    symbol      VARCHAR NOT NULL,
    timeframe   VARCHAR NOT NULL,
    window_kind VARCHAR NOT NULL,
    bar_start   BIGINT  NOT NULL,
    bar_ende    BIGINT  NOT NULL,
    rank        INTEGER NOT NULL,
    poc         DOUBLE,
    val         DOUBLE,
    vah         DOUBLE,
    vol         DOUBLE,
    peak_share_pct DOUBLE,
    bin_start   BIGINT,
    bin_gipfel  BIGINT,
    bin_ende    BIGINT,
    PRIMARY KEY (run_id, bar_start, bar_ende, rank)
);
"""


class ProfilStore:
    """DuckDB-Speicher fuer Volumenprofile (archivierte Referenz).

    Attributes:
        db_path: Pfad der DuckDB-Datei.
        run_id: Deterministische Kennung des aktuellen Parametersatzes.
    """

    def __init__(
        self,
        db_path: Path,
        symbol: str,
        timeframe: str,
        window_kind: str,
        params: Dict[str, Any],
    ) -> None:
        """Oeffnet den Speicher und legt das Schema an, falls noetig.

        Args:
            db_path: Pfad der DuckDB-Datei (wird bei Bedarf erzeugt).
            symbol: Symbol des Laufs.
            timeframe: Timeframe des Laufs.
            window_kind: Fensterart des Laufs.
            params: Volumenparameter (gehen in die ``run_id`` ein).
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.symbol = str(symbol)
        self.timeframe = str(timeframe)
        self.window_kind = str(window_kind)
        self.params = dict(params)
        self.run_id = _run_id(symbol, timeframe, window_kind, params)
        self._con = duckdb.connect(str(self.db_path))
        self._con.execute(_SQL_PROFILES)
        self._con.execute(_SQL_NESTS)

    def __enter__(self) -> "ProfilStore":
        """Kontextmanager-Eintritt.

        Returns:
            Dieser Speicher.
        """
        return self

    def __exit__(self, *exc: object) -> None:
        """Schliesst die Verbindung.

        Args:
            *exc: Ausnahmeinformationen (werden nicht unterdrueckt).
        """
        self.close()

    def schreibe(
        self, profile: Sequence[ProfilZeile], nests: Sequence[NestZeile]
    ) -> int:
        """Schreibt Profile und ihre Segmente idempotent.

        Symbol, Timeframe und Fensterart stammen aus dem Speicher-Kontext
        (``run_id``-konsistent); die Zeilen liefern Label, Grenzen und Level.

        Args:
            profile: Profilzeilen der Fenster.
            nests: Zu den Profilen gehoerende Segmentzeilen. Die Zuordnung
                erfolgt ueber ``bar_start``/``bar_ende`` der Segmentzeile.

        Returns:
            Anzahl geschriebener Profilzeilen.
        """
        if not profile:
            return 0
        self._con.executemany(
            """
            INSERT OR REPLACE INTO volume_profiles (
                schema_version, run_id, symbol, timeframe, window_kind, label,
                bar_start, bar_ende, ts_start, ts_ende, n_bars, n_bars_gefiltert,
                vol_summe, atr, poc, val, vah, va_zone_pct, va_abdeckung,
                val_huelle, vah_huelle, n_segmente, lobe2, poc_streu_atr,
                poc_min, poc_max, poc_eindeutig, params_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    SCHEMA_VERSION, self.run_id, self.symbol, self.timeframe,
                    self.window_kind, z.label, int(z.bar_start), int(z.bar_ende),
                    z.ts_start, z.ts_ende, int(z.n_bars), int(z.n_bars_gefiltert),
                    float(z.vol_summe), float(z.atr), float(z.poc), float(z.val),
                    float(z.vah), float(z.va_zone_pct), float(z.va_abdeckung),
                    float(z.val_huelle), float(z.vah_huelle), int(z.n_segmente),
                    float(z.lobe2), float(z.poc_streu_atr), float(z.poc_min),
                    float(z.poc_max), bool(z.poc_eindeutig),
                    json.dumps(dict(self.params), sort_keys=True, default=str),
                )
                for z in profile
            ],
        )
        if nests:
            self._con.executemany(
                """
                INSERT OR REPLACE INTO volume_profile_nests (
                    run_id, symbol, timeframe, window_kind, bar_start, bar_ende,
                    rank, poc, val, vah, vol, peak_share_pct,
                    bin_start, bin_gipfel, bin_ende
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        self.run_id, self.symbol, self.timeframe,
                        self.window_kind,
                        int(z.bar_start), int(z.bar_ende), int(z.rank),
                        float(z.poc), float(z.val), float(z.vah), float(z.vol),
                        float(z.peak_share_pct), int(z.bin_start),
                        int(z.bin_gipfel), int(z.bin_ende),
                    )
                    for z in nests
                ],
            )
        return len(profile)

    def schreibe_run_meta(
        self,
        symbol: str,
        timeframe: str,
        params: Dict[str, Any],
        kommentar: str = "",
    ) -> None:
        """Schreibt eine Metazeile des Laufs (Nachvollziehbarkeit).

        Args:
            symbol: Symbol.
            timeframe: Timeframe.
            params: Volumenparameter.
            kommentar: Freitext (z. B. Grund des Laufs).
        """
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS volume_profile_runs (
                run_id VARCHAR PRIMARY KEY,
                schema_version VARCHAR,
                symbol VARCHAR, timeframe VARCHAR, window_kind VARCHAR,
                params_json JSON, kommentar VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
            )
            """
        )
        self._con.execute(
            """
            INSERT OR REPLACE INTO volume_profile_runs
            (run_id, schema_version, symbol, timeframe, window_kind,
             params_json, kommentar)
            VALUES (?,?,?,?,?,?,?)
            """,
            [
                self.run_id, SCHEMA_VERSION, symbol, timeframe,
                self.window_kind,
                json.dumps(params, sort_keys=True, default=str), kommentar,
            ],
        )

    def lies_profile(
        self, window_kind: Optional[str] = None, nur_diesen_run: bool = True
    ) -> List[Dict[str, Any]]:
        """Liest Profilzeilen als Liste von Dictionaries.

        Args:
            window_kind: Optionaler Filter auf die Fensterart.
            nur_diesen_run: True = nur Zeilen der eigenen ``run_id``.

        Returns:
            Liste von Zeilen-Dictionaries.
        """
        wo: List[str] = []
        par: List[Any] = []
        if nur_diesen_run:
            wo.append("run_id = ?")
            par.append(self.run_id)
        if window_kind:
            wo.append("window_kind = ?")
            par.append(window_kind)
        sql = "SELECT * FROM volume_profiles"
        if wo:
            sql += " WHERE " + " AND ".join(wo)
        sql += " ORDER BY bar_start"
        cur = self._con.execute(sql, par)
        spalten = [d[0] for d in cur.description]
        return [dict(zip(spalten, r)) for r in cur.fetchall()]

    def zaehle(self) -> Dict[str, int]:
        """Zaehlt die Zeilen beider Tabellen.

        Returns:
            Dict mit ``profiles``, ``nests``, ``runs`` (runs = 0, wenn die
            Metatabelle noch nicht existiert).
        """
        n_prof = int(
            self._con.execute(
                "SELECT COUNT(*) FROM volume_profiles"
            ).fetchone()[0]
        )
        n_nest = int(
            self._con.execute(
                "SELECT COUNT(*) FROM volume_profile_nests"
            ).fetchone()[0]
        )
        try:
            n_runs = int(
                self._con.execute(
                    "SELECT COUNT(*) FROM volume_profile_runs"
                ).fetchone()[0]
            )
        except duckdb.CatalogException:
            n_runs = 0
        return {"profiles": n_prof, "nests": n_nest, "runs": n_runs}

    def close(self) -> None:
        """Schliesst die DuckDB-Verbindung (fehlertolerant)."""
        try:
            self._con.close()
        except Exception:
            pass
