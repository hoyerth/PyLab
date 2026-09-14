# -*- coding: utf-8 -*-
"""S3.2 -- Engine-Patch V017 -> V018: _lade_fenster auf BKZ (AT TIME ZONE 'UTC').

Chirurgischer **Byte-Ebene**-Ersatz in ``test/tmp_kanten_engine_replay.py``.
Die Datei ist CRLF-kodiert (Teil des arretierten Byte-Hashs) -- deshalb wird
ausschliesslich auf ``bytes`` gearbeitet, damit die Zeilenenden unangetastet
bleiben.

Fail-Loud: Der alte Block muss EXAKT einmal vorkommen; sonst kein Schreiben.

Aufruf:
    .venv\\Scripts\\python.exe test\\_tmp_s3_engine_patch.py [--apply]
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT: Path = Path(__file__).resolve().parent.parent
ENGINE: Path = ROOT / "test" / "tmp_kanten_engine_replay.py"

OLD_LF: str = '''def _lade_fenster(fenster: FensterTyp) -> pd.DataFrame:
    """OHLCV-Fenster tz-naiv (time AT TIME ZONE 'UTC', Wanduhr)."""
    start, ende = FENSTER[fenster]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    d = con.execute(f"""
        -- Wanduhr-Invariante (Mentor): MT5-Epochs sind Berlin-encoded.
        -- ANZEIGE = Berlin-Wanduhr; die Fenstergrenzen unten bleiben
        -- UTC-formuliert, damit der Zeilensatz (und damit alle
        -- arretierten Kennzahlen) byte-identisch bleibt.
        SELECT time AT TIME ZONE 'Europe/Berlin' AS ts, open, high,
               low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
    """).fetchdf()
'''

NEW_LF: str = '''def _lade_fenster(fenster: FensterTyp) -> pd.DataFrame:
    """OHLCV-Fenster tz-naiv (time AT TIME ZONE 'UTC' = BKZ).

    Zeitbasis-Kanon K1/K4 (`docs/ZEITBASIS_KANON.md`): Rechenbasis ist
    ausschliesslich die Broker-Kerzen-Zeit (BKZ) = ``time AT TIME ZONE
    'UTC'``. Regionale Projektionen (`Europe/Berlin`/`Europe/Budapest`)
    sind reine Anzeige-Dubletten und werden hier nicht verwendet.

    Returns:
        DataFrame mit ``ts`` (BKZ, tz-naiv) sowie open/high/low/close/
        tick_volume, aufsteigend nach ``ts``.
    """
    start, ende = FENSTER[fenster]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    d = con.execute(f"""
        -- Zeitbasis-Kanon K1/K4 (docs/ZEITBASIS_KANON.md):
        -- SELECT und WHERE nutzen dieselbe Basis (BKZ = AT TIME ZONE 'UTC').
        -- Die frueher verwendete Berlin-Projektion erzeugte einen
        -- DST-abhaengigen Offset (+1 h Winter / +2 h Sommer) und verschob
        -- Kalendergrenzen um 4 bzw. 8 Bars.
        -- Migration V017 -> V018: box_end_bar 640 -> 644.
        SELECT time AT TIME ZONE 'UTC' AS ts, open, high,
               low, close, tick_volume
        FROM ohlcv_bars
        WHERE symbol='SILVER' AND timeframe='M15'
          AND time AT TIME ZONE 'UTC' >= DATE '{start}'
          AND time AT TIME ZONE 'UTC' <  DATE '{ende}'
        ORDER BY time
    """).fetchdf()
'''

HDR_OLD_LF: str = ("Datenvertrag: df-Spalten ts (tz-naiv)/open/high/low/close/tick_volume, geladen\n"
                   "mit ``time AT TIME ZONE 'UTC'`` (Wanduhr-Invariante). Fenster exakt wie frozen:")
HDR_NEW_LF: str = ("Datenvertrag: df-Spalten ts (tz-naiv)/open/high/low/close/tick_volume, geladen\n"
                   "mit ``time AT TIME ZONE 'UTC'`` (BKZ-Kanon, `docs/ZEITBASIS_KANON.md`).\n"
                   "Fenster exakt wie frozen:")

TITLE_OLD_LF: str = "# DATEN-LADUNG (Wanduhr-Invariante)"
TITLE_NEW_LF: str = "# DATEN-LADUNG (BKZ-Kanon: AT TIME ZONE 'UTC')"


def _crlf(s: str) -> bytes:
    """Konvertiert LF-Quelltext in CRLF-Bytes.

    Args:
        s: Text mit LF-Zeilenenden.

    Returns:
        UTF-8-Bytes mit CRLF-Zeilenenden.
    """
    return s.replace("\n", "\r\n").encode("utf-8")


def main() -> None:
    """Fuehrt den Patch aus bzw. zeigt den Dry-Run."""
    do_apply: bool = "--apply" in sys.argv
    raw = ENGINE.read_bytes()
    sha_before = hashlib.sha256(raw).hexdigest()
    crlf_n = raw.count(b"\r\n")
    print(f"S3.2 Engine-Patch -- Modus: {'APPLY' if do_apply else 'DRY-RUN'}")
    print(f"  SHA vorher      : {sha_before}")
    print(f"  Bytes / CRLF    : {len(raw)} / {crlf_n}")

    old, new = _crlf(OLD_LF), _crlf(NEW_LF)
    hdr_old, hdr_new = _crlf(HDR_OLD_LF), _crlf(HDR_NEW_LF)
    ttl_old, ttl_new = _crlf(TITLE_OLD_LF), _crlf(TITLE_NEW_LF)

    checks = {
        "OLD-Block": (raw.count(old), 1),
        "DATEN-LADUNG": (raw.count(ttl_old), 1),
        "Datenvertrag": (raw.count(hdr_old), 1),
    }
    ok = True
    for name, (cnt, want) in checks.items():
        flag = "OK " if cnt == want else "ERR"
        if cnt != want:
            ok = False
        print(f"  {flag} Treffer {name:<13}: {cnt} (erwartet {want})")
    if not ok:
        print("  ABBRUCH: Muster nicht eindeutig -- kein Schreiben.")
        return

    out = raw.replace(old, new).replace(ttl_old, ttl_new).replace(hdr_old, hdr_new)
    print(f"  Bytes nachher   : {len(out)}")
    print(f"  CRLF nachher    : {out.count(chr(13).encode() + chr(10).encode())}")
    print(f"  Restprojektion  : {out.count(chr(39).encode() + b'Europe/Berlin' + chr(39).encode())} "
          f"(AT TIME ZONE 'Europe/Berlin', erwartet 0)")

    if do_apply:
        ENGINE.write_bytes(out)
        sha_after = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
        print(f"  SHA nachher     : {sha_after}")
    else:
        print("  (kein Schreiben -- Dry-Run)")


if __name__ == "__main__":
    main()
