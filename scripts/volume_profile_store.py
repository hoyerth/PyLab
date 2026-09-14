"""
VOLUMENPROFIL-SPEICHER (scripts/volume_profile_store.py)
=========================================================
Persistenz der gerechneten Volumenprofile in einer DuckDB-Datei. Kein
Rechenkern, kein Plot - dieses Modul schreibt und liest nur.

Speicherort
-----------
Default ist eine EIGENE Datei ``data/volume_profiles.duckdb``. Damit werden
die bestehenden Datenbanken (``market_data.duckdb`` = Marktdaten,
``analytics_data.duckdb`` = Indikator-Runs/Signale, ``backtest_data.duckdb``)
nicht angefasst. Der Pfad ist als Parameter frei waehlbar.

Zeitbasis (docs/ZEITBASIS_KANON.md)
-----------------------------------
Gespeichert werden ausschliesslich BKZ-Zeitstempel (``time AT TIME ZONE
'UTC'``, tz-naiv) als Spalten vom Typ ``TIMESTAMP`` OHNE Zeitzone. Damit kann
die DuckDB-Session-Zeitzone (``Europe/Budapest``) die abgelegten Werte nicht
verschieben (K2/F2). Zusaetzlich ist der Bar-Index der Primaerschluessel jeder
Zeile (K5).

Idempotenz
----------
``run_id`` wird deterministisch aus Symbol, Timeframe, Fensterart und den
Volumenparametern gebildet. Ein erneuter Lauf mit identischen Parametern
schreibt dieselben Zeilen (``INSERT OR REPLACE``) - es entstehen keine
Duplikate und keine sich stapelnden Altstaende.

Schema
------
volume_profiles   eine Zeile je Fenster (Level der Zonen-Value-Area ab POC)
volume_profile_nests  eine Zeile je erkanntem Segment (Berg) des Fensters

Aufruf (aus einem Orchestrator):
    from scripts.volume_profile_store import ProfilStore
    with ProfilStore(db_path) as store:
        store.schreibe(zeilen, nest_zeilen)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

import duckdb

# Schema-Version der abgelegten Struktur (bei Aenderungen erhoehen)
SCHEMA_VERSION: str = "1"

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


def _run_id(
    symbol: str, timeframe: str, window_kind: str, params: Dict[str, Any]
) -> str:
    """Bildet eine deterministische Lauf-Kennung.

    Args:
        symbol: Symbol.
        timeframe: Timeframe.
        window_kind: Fensterart.
        params: Volumenparameter (wird kanonisch serialisiert).

    Returns:
        Kurzer Hex-String; identische Parameter ergeben identische Kennung.
    """
    roh = json.dumps(
        {
            "v": SCHEMA_VERSION,
            "symbol": symbol.upper(),
            "timeframe": timeframe.upper(),
            "kind": window_kind,
            "params": params,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class ProfilZeile:
    """Eine Profilzeile (Fenster-Ebene) fuer den Speicher.

    Attributes:
        symbol: Symbol.
        timeframe: Timeframe.
        window_kind: Fensterart (``day``/``week``/``h12``/...).
        label: Fensterlabel.
        bar_start: Erster Bar-Index des Fensters.
        bar_ende: Letzter Bar-Index des Fensters.
        ts_start: Erster BKZ-Zeitstempel (tz-naiv).
        ts_ende: Letzter BKZ-Zeitstempel (tz-naiv).
        n_bars: Anzahl Bars im Fenster.
        n_bars_gefiltert: Anzahl durch den Volumenfilter entfernter Bars.
        vol_summe: Summe des ``tick_volume`` im Fenster (ungefiltert).
        atr: Mittlere Bar-Spanne des Fensters.
        poc: POC der Zonen-Value-Area (globaler POC).
        val: Untere Kante der Zonen-Value-Area (94 %).
        vah: Obere Kante der Zonen-Value-Area (94 %).
        va_zone_pct: Verwendeter Anteil der Zonen-Value-Area.
        va_abdeckung: Tatsaechlich erreichter Anteil.
        val_huelle: Untere Kante der Berg-Huelle (min der Segment-VALs).
        vah_huelle: Obere Kante der Berg-Huelle (max der Segment-VAHs).
        n_segmente: Anzahl erkannter Segmente.
        lobe2: Zweitgipfel/Gipfel (Diagnose).
        poc_streu_atr: POC-Spanne ueber die Konsensparametersaetze (ATR).
        poc_min: Kleinster POC der Konsensmessung.
        poc_max: Groesster POC der Konsensmessung.
        poc_eindeutig: True = POC stabil gegenueber Parameterwechsel.
    """

    symbol: str
    timeframe: str
    window_kind: str
    label: str
    bar_start: int
    bar_ende: int
    ts_start: Any
    ts_ende: Any
    n_bars: int
    n_bars_gefiltert: int = 0
    vol_summe: float = float("nan")
    atr: float = float("nan")
    poc: float = float("nan")
    val: float = float("nan")
    vah: float = float("nan")
    va_zone_pct: float = float("nan")
    va_abdeckung: float = float("nan")
    val_huelle: float = float("nan")
    vah_huelle: float = float("nan")
    n_segmente: int = 0
    lobe2: float = float("nan")
    poc_streu_atr: float = float("nan")
    poc_min: float = float("nan")
    poc_max: float = float("nan")
    poc_eindeutig: bool = False


@dataclass(slots=True)
class NestZeile:
    """Eine Segmentzeile (Nest-Ebene) fuer den Speicher.

    Das Segment traegt seine Fenstergrenzen selbst (``bar_start``/``bar_ende``),
    damit die Zuordnung zum Profil ohne Positionsannahme eindeutig ist. Symbol,
    Timeframe und Fensterart stammen aus dem Speicher-Kontext
    (``ProfilStore``), nicht aus der Zeile.

    Attributes:
        bar_start: Erster Bar-Index des zugehoerigen Fensters.
        bar_ende: Letzter Bar-Index des zugehoerigen Fensters.
        rank: Rang des Segments (0 = groesstes).
        poc: POC des Segments.
        val: Untere Kante der Segment-Value-Area.
        vah: Obere Kante der Segment-Value-Area.
        vol: Volumen des Segmentabschnitts.
        peak_share_pct: Gipfelvolumen relativ zum groessten Segment.
        bin_start: Erster Bin des Segments.
        bin_gipfel: Gipfel-Bin.
        bin_ende: Letzter Bin des Segments.
    """

    bar_start: int
    bar_ende: int
    rank: int
    poc: float
    val: float
    vah: float
    vol: float
    peak_share_pct: float
    bin_start: int = -1
    bin_gipfel: int = -1
    bin_ende: int = -1


class ProfilStore:
    """DuckDB-Speicher fuer Volumenprofile (Kontextmanager).

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

    def schreibe(self, profile: Sequence[ProfilZeile], nests: Sequence[NestZeile]) -> int:
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
                    json.dumps(
                        dict(self.params),
                        sort_keys=True,
                        default=str,
                    ),
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

    def schreibe_run_meta(self, symbol: str, timeframe: str, params: Dict[str, Any],
                          kommentar: str = "") -> None:
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
        n_prof = int(self._con.execute("SELECT COUNT(*) FROM volume_profiles").fetchone()[0])
        n_nest = int(
            self._con.execute("SELECT COUNT(*) FROM volume_profile_nests").fetchone()[0]
        )
        try:
            n_runs = int(
                self._con.execute("SELECT COUNT(*) FROM volume_profile_runs").fetchone()[0]
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


# =============================================================================
# LAUFZEIT-SPEICHER (RAM)
# =============================================================================


class ProfilSpeicher:
    """Laufzeit-Speicher fuer Volumenprofile (RAM, ohne DuckDB).

    Die Profile werden NUR im Arbeitsspeicher gehalten. Das ist der Regelweg:
    ein Profil ist an seinen Parametersatz gebunden und wird bei jeder
    Parameteraenderung sofort ungueltig - eine Ablegung in einer Datei waere
    dann Altbestand, der stillschweigend weiterverwendet werden koennte.
    ``ProfilStore`` (DuckDB) bleibt fuer ausdrueckliche Archivlaeufe daneben
    bestehen.

    Der Speicher haelt Zeilen im selben Vertrag wie ``ProfilStore``
    (``ProfilZeile``/``NestZeile``) und ist nach ``run_id`` gruppiert -
    identische Parameter treffen dieselbe Gruppe, ein erneutes ``merke``
    ERSETZT sie (gleiche Idempotenz wie die DB).

    Attributes:
        symbol: Symbol des Laufs.
        timeframe: Timeframe des Laufs.
        window_kind: Fensterart des Laufs.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        window_kind: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Legt den Laufzeitspeicher an.

        Args:
            symbol: Symbol des Laufs.
            timeframe: Timeframe des Laufs.
            window_kind: Fensterart des Laufs.
            params: Volumenparameter (gehen in die ``run_id`` ein).
        """
        self.symbol = str(symbol)
        self.timeframe = str(timeframe)
        self.window_kind = str(window_kind)
        self.params: Dict[str, Any] = dict(params or {})
        self.run_id = _run_id(symbol, timeframe, window_kind, self.params)
        self._profile: List[ProfilZeile] = []
        self._nester: List[NestZeile] = []

    def __enter__(self) -> "ProfilSpeicher":
        """Kontextmanager-Eintritt.

        Returns:
            Dieser Speicher.
        """
        return self

    def __exit__(self, *exc: object) -> None:
        """Kontextmanager-Austritt (RAM braucht nichts zu schliessen).

        Args:
            *exc: Ausnahmeinformationen (werden nicht unterdrueckt).
        """
        return None

    def merke(
        self, profile: Sequence[ProfilZeile], nests: Sequence[NestZeile]
    ) -> int:
        """Uebernimmt die Profilzeilen des Laufs in den Arbeitsspeicher.

        Ein erneuter Aufruf ersetzt den Bestand dieses ``run_id`` vollstaendig -
        damit kann kein vermischter Stand aus zwei Parameterlaeufen entstehen.

        Args:
            profile: Profilzeilen der Fenster.
            nests: Zu den Profilen gehoerende Segmentzeilen.

        Returns:
            Anzahl uebernommener Profilzeilen.
        """
        self._profile = list(profile)
        self._nester = list(nests)
        return len(self._profile)

    def hole(self, window_kind: Optional[str] = None) -> List[ProfilZeile]:
        """Liefert die Profilzeilen (optional auf eine Fensterart gefiltert).

        Args:
            window_kind: Fensterart-Filter; None = alle.

        Returns:
            Liste der Profilzeilen in Einfuegereihenfolge.
        """
        if window_kind is None:
            return list(self._profile)
        return [z for z in self._profile if z.window_kind == window_kind]

    def hole_nester(
        self,
        window_kind: Optional[str] = None,
        bar_start: Optional[int] = None,
        bar_ende: Optional[int] = None,
    ) -> List[NestZeile]:
        """Liefert die Segmentzeilen mit optionalen Filtern.

        Args:
            window_kind: Fensterart-Filter; None = alle.
            bar_start: Nur Segmente dieses Fensters (None = alle).
            bar_ende: Nur Segmente dieses Fensters (None = alle).

        Returns:
            Gefilterte Liste der Segmentzeilen.
        """
        out = list(self._nester)
        if window_kind is not None:
            out = [z for z in out if z.window_kind == window_kind]
        if bar_start is not None:
            out = [z for z in out if z.bar_start == bar_start]
        if bar_ende is not None:
            out = [z for z in out if z.bar_ende == bar_ende]
        return out

    def zaehle(self) -> Dict[str, int]:
        """Zaehlt die gehaltenen Zeilen.

        Returns:
            Dict mit ``profiles``, ``nests`` und ``runs`` (1, wenn Zeilen
            vorliegen).
        """
        return {
            "profiles": len(self._profile),
            "nests": len(self._nester),
            "runs": 1 if self._profile else 0,
        }

    def leeren(self) -> None:
        """Verwirft alle gehaltenen Zeilen (Parameterwechsel)."""
        self._profile = []
        self._nester = []

    def speicher_mb(self) -> float:
        """ Schaetzt den Speicherbedarf der gehaltenen Zeilen in MByte.

        Returns:
            Grobe Obergrenze in MByte (nur die Zeilenobjekte, ohne Overhead).
        """
        import sys

        gesamt = sum(sys.getsizeof(z) for z in self._profile)
        gesamt += sum(sys.getsizeof(z) for z in self._nester)
        return float(gesamt) / (1024.0 * 1024.0)


class ProfilSpeicherHalter:
    """Haelt MEHRERE Laufzeit-Speicher - einer je Parametersatz (``run_id``).

    Der Halter ist der Einstiegspunkt fuer den Live-Einsatz: eine Ansicht (oder
    ein Diagramm) holt sich ihren Speicher ueber ``hole_oder_anlegen`` und
    bekommt bei gleichem Parametersatz exakt denselben Speicher zurueck - ohne
    Neuberechnung und ohne dass ein Parameterwechsel den alten Stand ueberschreibt.

    Die Schluessel sind die ``run_id``-Werte, also deterministisch aus Symbol,
    Timeframe, Fensterart und Volumenparametern gebildet.

    Attributes:
        HALTER: Prozessweiter Standard-Halter (Bequemlichkeit fuer Live).
    """

    def __init__(self) -> None:
        """Legt einen leeren Halter an."""
        self._speicher: Dict[str, ProfilSpeicher] = {}
        self._reihenfolge: List[str] = []

    def _registriere(self, speicher: ProfilSpeicher) -> str:
        """Traegt einen Speicher ein (intern, ohne Rueckgabeobjekt).

        Args:
            speicher: Laufzeit-Speicher.

        Returns:
            Die ``run_id`` des Speichers.
        """
        if speicher.run_id not in self._speicher:
            self._reihenfolge.append(speicher.run_id)
        self._speicher[speicher.run_id] = speicher
        return speicher.run_id

    def register(self, speicher: ProfilSpeicher) -> str:
        """Traegt einen fertigen Speicher ein und ersetzt gleiche ``run_id``.

        Args:
            speicher: Laufzeit-Speicher.

        Returns:
            Die ``run_id`` des Speichers.
        """
        return self._registriere(speicher)

    def hole(self, run_id: str) -> Optional[ProfilSpeicher]:
        """Liefert den Speicher einer ``run_id``.

        Args:
            run_id: Kennung des Parametersatzes.

        Returns:
            Der Speicher oder None, wenn die Kennung unbekannt ist.
        """
        return self._speicher.get(run_id)

    def hole_oder_anlegen(
        self,
        symbol: str,
        timeframe: str,
        window_kind: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ProfilSpeicher:
        """Liefert den Speicher eines Parametersatzes oder legt ihn neu an.

        Args:
            symbol: Symbol.
            timeframe: Timeframe.
            window_kind: Fensterart.
            params: Volumenparameter (gehen in die ``run_id`` ein).

        Returns:
            Der vorhandene (inhaltlich unveraenderte) oder ein neuer, leerer
            Speicher.
        """
        rid = _run_id(symbol, timeframe, window_kind, dict(params or {}))
        vorhanden = self._speicher.get(rid)
        if vorhanden is not None:
            return vorhanden
        return self.hole(self._registriere(
            ProfilSpeicher(symbol, timeframe, window_kind, params or {})
        ))  # type: ignore[return-value]

    def neuester(self) -> Optional[ProfilSpeicher]:
        """Liefert den zuletzt eingetragenen Speicher.

        Returns:
            Der zuletzt eingetragene Speicher oder None (Halter leer).
        """
        if not self._reihenfolge:
            return None
        return self._speicher.get(self._reihenfolge[-1])

    def run_ids(self) -> List[str]:
        """Liefert die Kennungen in Eintragsreihenfolge.

        Returns:
            Liste der ``run_id``-Werte (aeltester zuerst).
        """
        return list(self._reihenfolge)

    def verwerfen(self, run_id: str) -> bool:
        """Entfernt den Speicher eines Parametersatzes.

        Args:
            run_id: Kennung des Parametersatzes.

        Returns:
            True, wenn ein Speicher entfernt wurde.
        """
        if run_id not in self._speicher:
            return False
        del self._speicher[run_id]
        self._reihenfolge.remove(run_id)
        return True

    def leeren(self) -> None:
        """Verwirft alle gehaltenen Speicher."""
        self._speicher.clear()
        self._reihenfolge.clear()

    def zaehle(self) -> Dict[str, int]:
        """Zaehlt die gehaltenen Speicher und ihre Zeilen.

        Returns:
            Dict mit ``speicher`` (Anzahl Parametersaetze), ``profiles`` und
            ``nests`` (Summen ueber alle Speicher).
        """
        return {
            "speicher": len(self._speicher),
            "profiles": sum(s.zaehle()["profiles"] for s in self._speicher.values()),
            "nests": sum(s.zaehle()["nests"] for s in self._speicher.values()),
        }

    def speicher_mb(self) -> float:
        """Summiert den Speicherbedarf aller gehaltenen Speicher.

        Returns:
            Grobe Obergrenze in MByte.
        """
        return float(sum(s.speicher_mb() for s in self._speicher.values()))

    def __len__(self) -> int:
        """Anzahl gehaltener Speicher."""
        return len(self._speicher)

    def __contains__(self, run_id: object) -> bool:
        """Prueft, ob eine ``run_id`` gehalten wird."""
        return run_id in self._speicher

    def __iter__(self) -> "Iterator[ProfilSpeicher]":
        """Iteriert die Speicher in Eintragsreihenfolge."""
        return iter(self._speicher[r] for r in self._reihenfolge)


# Prozessweiter Standard-Halter: im Live-Einsatz teilen sich Ansichten/Charts
# diesen Halter, damit ein Parametersatz nur EINMAL gerechnet wird.
HALTER: ProfilSpeicherHalter = ProfilSpeicherHalter()
