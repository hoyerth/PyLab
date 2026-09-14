# -*- coding: utf-8 -*-
"""Haengt H20 (AUG26-Vorarbeit Schritte 1-2) an test/SESSION_HANDOFF.md an.

Byte-treu: Prefix wird als Bytes gelesen und unveraendert zurueckgeschrieben;
neuer Abschnitt ausschliesslich CRLF (Datei-Konvention, 7200 CRLF).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent / "SESSION_HANDOFF.md"

ABSCHNITT = """
### H20 - AUG26-Vorarbeit (Schritte 1-2, read-only, 2026-09-12)

Vorgriff auf den Fensterwechsel AUG -> AUG26 (ganzer Monat, kein
Kalender-Schnitt bei Bar 640/644). Dieser Block dokumentiert ausschliesslich
MESSUNGEN; es wurde keine Regel, kein Produktivpfad und keine Engine
geaendert. Bindende Anwenderantworten: F1-F6 (Fenster/Kalender/Archiv/
Quartil/Baseline/IDs) und G1-G5 (Zweispur, kein blinder SEG_LAST, 4-6
Balances, preisbasierte Merge-Regel, sofortige Dokumentation).

#### H20.1 Datenbasis und Datenkante

| Groesse | Wert |
|---|---|
| Fenster | `("2026-08-03", "2026-09-01")` endexklusiv |
| Bars | 1932 (21 Handelstage x 92) |
| Erste/letzte BKZ | 2026-08-03 00:00 / 2026-08-31 22:45 |
| Spanne | 56.5470 .. 71.1390 |
| Wochenenden | 01/02, 08/09, 15/16, 22/23, 29/30 |
| box_end 19.08. | Bar **1104** (alt 644) |
| Offset alt -> neu | **+460** (Bars 03.-09.08. waren im Alt-AUG nicht enthalten) |
| Alt-AUG-Def. | `2026-08-10 .. 2026-08-28`, n = 1288 |

Das Alt-Fenster endete am 27.08.; AUG26 gewinnt zusaetzlich die Bars
28.08. und 31.08. (~184 Bars). Beide Raender sind neu, nicht nur der linke.

#### H20.2 Archivierung (F3)

39 Artefakte per Copy nach `test/archiv/v019_aug_staging/` mit
`MANIFEST.sha256` (39 Eintraege, 4.295 B, SHA256
`22f32ed10af8853a5c77405b368de0257c9f34408a05cdd1ff8aedab53f3907e`).
Nachkontrolle: **39/39 Originale unveraendert, 0 Abweichungen**. Engine
(`53f28e1b...`), Renderer und Adapter nicht beruehrt.

#### H20.3 Kanten-Scan AUG26

90 edges + 26 seeds = **116 Kanten**; Preisspanne 56.5470..71.1390.

#### H20.4 Schritt 1 - Nackte Kanten-Baseline (V0 / V1_basis)

Harness-Konvention wie Renderer Z. 630: `scan["box_end_bar"] = n`
(Voll-Lauf, arretierte Basis); H1/H2-Grenze bleibt der echte Bar 1104.

| Variante | Trades | L/S | Winrate | R_brutto | R_realis.(b) | R_untergr.(a) | Q_stop | H1 (<1104) | H2 (>=1104) |
|---|---|---|---|---|---|---|---|---|---|
| V0 (Engine native) | 18 | 0/18 | 22.2 % | **-7.991154** | -7.991154 | -7.991154 | 12/18 (66.7 %) | 14 / -3.991154 | 4 / -4.000000 |
| V1_basis (13 Patches, DEFAULT_ADAPTER) | 9 | 0/9 | 22.2 % | **-4.696105** | -4.696105 | -4.696105 | 6/9 (66.7 %) | 9 / -4.696105 | 0 / 0.000000 |

Weitere Kennzahlen V0: max. Concurrency LONG 0 / SHORT 3 (Cap 3);
Woche 1 (Bars 0..459) 4 Trades / -4.000000; Alt-AUG-Block (460..1747)
13 Trades / -2.991154; stats `concurrency_blockiert=5`,
`v_s=18`, `kein_raum=8`.
V1_basis: max. Concurrency SHORT 2; Woche 1 4 / -4.000000;
Alt-AUG-Block 5 / -0.696105; `kein_raum=51`.

**Anker-Nachweis (Harness-Treue):** Dieselbe Pipeline auf dem Alt-AUG
(n = 1288, box 644) reproduziert die arretierten Referenzwerte exakt:
V0 = 14 / +42.450970, V1_basis = 14 / +47.815697 -> OK. Die AUG26-Zahlen
sind damit Mechanik, kein Harness-Artefakt.

**Befund Fenster-Instabilitaet (verschaerft):** Der identische
Kalenderblock 10.-27.08. liefert
- standalone Alt-AUG: 14 Trades / **+42.450970**
- als Block in AUG26: 13 Trades / **-2.991154**

Der Katalog wechselt mit dem Fenster (59 vs. 90 edges); die
Aussenkanten-Auswahl kippt dadurch. Der Alt-AUG-Vorsprung ist **kein
Fenster-Invariant**, sondern ein Katalog-Artefakt des 1288-Bar-Zuschnitts.

#### H20.5 Schritt 2 - Roh-Segmente und Merge-Instrumente

Rohester Kausal-Zuschnitt (Ecken-Wechsel, `zusammenfassen` nicht
angewandt): **97 Wechselpunkte, 96 Roh-Segmente, davon 94 unter 77 Bars**;
Abdeckung 1918/1932 Bars = 99.3 %.

Ergebnis der Bestandsregel (`zusammenfassen(..., 77)` = Laengenregel ODER
`_nah`):

| # | Fenster | Bars | Korridor | IST | ausserhalb |
|---|---|---|---|---|---|
| 1 | 14..1396 | 1383 | 57.7990..58.3970 | 56.5470..70.0000 | **1326 (95.9 %)** |
| 2 | 1397..1633 | 237 | 68.3920..69.9310 | 67.4200..69.9240 | 74 (31.2 %) |
| 3 | 1634..1931 | 298 | 67.5530..69.6380 | 65.5190..71.1390 | 146 (49.0 %) |

Segment 1 ist geometrisch toxisch: Decke 16.58 % unter dem Fensterhoch,
Boden 2.21 % ueber dem Fenstertief, 95.9 % der Bars ausserhalb des
eigenen Korridors. Die Laengenregel absorbiert 94 Kurzsegmente in eine
1383-Bar-Kiste. **Schwelle 77 traegt auf AUG26 nicht.**

Positiv: die Alt-Phasenkanten-Transitionen **1493 (= 1033 + 460)** und
**1634 (= 1174 + 460)** werden exakt wiedergefunden. P9 (alt 1308..1480)
wird **nicht** reproduziert (A1-Start -96, A2-Ende +184).

**Ursache des Kollapses:** `zusammenfassen` friert die Korridorgrenzen am
ersten Stueck ein (`SEG_LAST=False`) und vergleicht danach Grenze zu
Grenze. Die Grenzpaare driften monoton, obwohl sich die Korridore stark
ueberlappen (Beispielkette 428..663:
`60.851..65.117 -> 63.040..64.863 -> 64.208..66.459`).

Band-Sweep ueber die drei Instrumente (Kriterium jeweils explizit):

| Band | A) beide Grenzen | B) eine Grenze | C) Kanten-Plateaus (Single-Linkage) | D) Korridor-Kern-Overlap |
|---|---|---|---|---|
| 0,12 % (= Engine-`_nah`) | 95 | 25 | 84 | - |
| 0,30 % | 84 | 24 | 18 | - |
| 0,40 % | - | - | - | 10 |
| 0,50 % | 67 | 20 | 6 | 11 |
| 0,60 % | 62 | 20 | 5 | 12 |
| 0,70 % | - | - | - | 13 |
| 0,80 % | 50 | 17 | 3 | 15 |
| 0,90 % | - | - | - | 20 |
| 1,00 % | 40 | 16 | 3 | - |

Abdeckung in D stets 99.3 %.

**Wichtige Praezisierung zu G4:** Das `_nah` der Engine ist
`cfg.touch_band_pct` = **0,12 %** (SE_BAND_PCT, Touch-Toleranz) - nicht
das vom Anwender gemeinte strukturelle Band 0,5..0,8 %. Mit dem
Engine-Wert ist die Laengenregel die einzig wirksame Kraft; deshalb der
1383-Bar-Monolith.

**Befund: keine 4-6 Balances.** Keines der Instrumente liefert die
erwarteten 4-6 institutionellen Gleichgewichte:
- A/B (Grenzengleichheit) liefern monoton 95..16 Segmente, ohne
  natuerlichen Knick.
- C (Kanten-Plateaus) liefert bei 0,60 % formal 5 Plateau-Cluster - aber
  P4 = `60.6440..70.1880` enthaelt **94 der 116 Kanten**. Das "Plateau"
  ist ein Ketten-Durchmarsch, weil die Kantenlevel im Bereich
  60.6..70.2 quasi-kontinuierlich dicht liegen (Nachbarabstand oft
  0,2-0,6 %). Single-Linkage kann dort nicht trennen.
- D (Korridor-Kern) liefert 10-20 Balances, aber mit **65-100 % Bars
  ausserhalb des Kerns**: z.B. 620..1022 mit Kern `64.912..65.117`
  (0,2 breit) gegen IST `63.485..66.776` = 98.5 % ausserhalb. Das ist ein
  Drift/Trend, keine Balance.

**Kernbefund:** Die Anzahl der "Balances" ist auf AUG26 eine Funktion der
Toleranz, nicht eine Eigenschaft der Daten. Der Mittelbereich
60.6..70.2 ist ein dichtes, quasi-kontinuierliches Levelfeld, das der
Markt trendend durchlaeuft; der Bodenbereich 56.5..58.6 und die
H1-Box-Zone 67.4..70.2 sind die einzigen Zonen mit sichtbarer
Grenz-Haeufung (Top-Grenzkanten: Decke K75 66.4590 12x, K84 66.3640 9x,
K117 69.9750 8x; Boden K99 62.5770 8x, K41 60.8510 6x, K55 63.0400 6x).

#### H20.6 Artefakt-Anker (SHA256; `test/` = gitignored)

| Datei | Bytes | SHA256 |
|---|---|---|
| `test/_chk_aug26_baseline.py` | 11.853 | `70cee627f9acd337bf1792972042b3e28d31e1828fbdead8df63f6a71e36598c` |
| `test/_chk_aug26_baseline_out.txt` | 49.054 | `af6b17b3c3143d4620c8b821a57e03d3b311f49706d2ede83bbeb427f03b2fad` |
| `test/_chk_aug26_anker.py` | 3.585 | `1113608336929beb68f6bcd04dfbc6eafc2e11d6da9be47457a6b6d71c0f9521` |
| `test/_chk_aug26_anker_out.txt` | 533 | `3f420013ac32306bcfb3e40406ed2d305fb0ce8c27d89dfb3fc166c4cae772d2` |
| `test/_chk_aug26_cluster_band.py` | 7.090 | `b31f0112f0920a16a13f9ff0dbe8f9fe01ae7ccfd03a925cbda0bcf5befa61b1` |
| `test/_chk_aug26_cluster_band_out.txt` | 20.364 | `836af11575c2cb3f8928114de882006f433ba40030035c3f35e57e79f8877d71` |
| `test/_chk_aug26_cluster_overlap.py` | 5.023 | `3d4ad23c67e5d163c897a904e23737027ee3838bc1d6fbb74256d350211168ae` |
| `test/_chk_aug26_cluster_overlap_out.txt` | 12.703 | `a9537e863619d6d792babaef41d15213678e009c6068f70d564eeea34799aa9b` |
| `test/_chk_aug26_segmente.py` | - | `dc9e77a614542a01f83520083e1c1e98188588ab58bcf029fccb4c401604bebe` |
| `test/_chk_aug26_segmente_2b.py` | - | `74c6a69a9ce49a6fa77f6ca23a8b071a0a6e5f4f88e6a9fe572dcd9a46f022ec` |
| `test/_tmp_f1_archiv.py` | - | `9a689bdc064d355084f5230581aa0bee3dedc817500b3705afdd408795b3f92f` |
| `test/tmp_kanten_engine_replay.py` (unveraendert) | 200.333 | `53f28e1b6971a64df59beaf3292b466fb37ac86b870278f238a1b385084fd006` |

#### H20.7 Offene Entscheidungen (blockieren den Phasenlauf AUG26)

Der Phasenlauf AUG26 bleibt gesperrt, bis die Segmentierung echte
Struktur liefert. Zu entscheiden:

1. **Instrument.** Grenzengleichheit (A/B), Kanten-Plateau (C) oder
   Korridor-Kern (D)? Keines liefert 4-6; C und D sind die einzigen mit
   Plateau-Semantik.
2. **Toleranz-Begriff.** Soll `_nah` von 0,12 % (Touch) auf ein
   strukturelles Band entkoppelt werden (0,5..0,8 %), oder bleibt
   0,12 % und die Struktur kommt aus einem anderen Kriterium?
3. **Trend-Abweisung.** Wie wird verhindert, dass eine Balance einen
   Trend absorbiert? Kandidat: Abbruch, sobald `Kernbreite / Spanne < x`
   bzw. sobald der Kern schmaler als ein Mindestmass wird. Schwelle x?
4. **Dwell als Primaerkriterium?** Alternative: Balance = Zone mit
   Mindest-Verweildauer (Bars im Kern), nicht Level-Naehe. Dann waere
   AUG26 bei 5-6 Zonen erwartbar; die Level-Naehe wird nachrangig.
5. **Kalendergrenze 19.08.** F2 sagt: reine Reporting-Zone, nie
   Segmentbruch. Bestaetigt gegen den Befund, dass 1104 kein
   Kantenwechsel ist.
6. **Q1-Bilanzierung.** Baseline auf AUG26 ist (b) = (a) = brutto
   (kein ENDE-Trade bei V0/V1_basis). Fuer den Phasenlauf bleibt die
   (a)/(b)-Schranke aus E-34n/14 offen.
"""


def main() -> int:
    alt = P.read_bytes()
    assert b"\r\n" in alt
    assert alt.count(b"\n") == alt.count(b"\r\n"), "Datei enthaelt nackte LF"
    assert alt.endswith(b"\r\n"), "Datei endet nicht auf CRLF"
    neu = ABSCHNITT.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    if b"H20 - AUG26-Vorarbeit" in alt:
        print("H20 existiert bereits -- kein Schreiben")
        return 1
    gesamt = alt + neu
    assert gesamt.startswith(alt)
    assert gesamt.count(b"\n") == gesamt.count(b"\r\n")
    P.write_bytes(gesamt)
    print(f"alt   : {len(alt)} B  sha {hashlib.sha256(alt).hexdigest()}")
    print(f"neu   : {len(gesamt)} B  sha {hashlib.sha256(gesamt).hexdigest()}")
    print(f"delta : +{len(gesamt) - len(alt)} B, "
          f"CRLF {gesamt.count(chr(13).encode() + chr(10).encode())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
