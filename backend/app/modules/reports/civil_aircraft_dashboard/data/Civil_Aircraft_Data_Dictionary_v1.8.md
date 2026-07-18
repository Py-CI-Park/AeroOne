# Civil Aircraft Data Dictionary v1.8

- Release: 2026-07-14
- Source snapshot: 2026-07-13
- Aircraft: 65
- Canonical source records: 55
- Local PDF attachments: 25
- PDF validation: 25/25 SHA-256, byte-size, PDF header and page-count match

## Core aircraft fields

| Field | Meaning | Unit / rule |
|---|---|---|
| `id` | stable aircraft identifier | URL and selection-state key |
| `model` | display model name | official/commonly used designation |
| `aliases` | search aliases | e.g. `B737`, `MAX 8`, `ARJ21` |
| `manufacturer`, `family` | maker and product family | text |
| `category`, `role` | market segment and passenger/freighter role | text |
| `status`, `statusCode` | programme status | text badge; color is not a value judgement |
| `typicalSeatsMin/Max` | typical passenger envelope | seats; null for freighters |
| `maxSeats` | published/certified maximum | null when unavailable |
| `rangeNm` | representative published maximum range | nautical miles; basis differs by manufacturer |
| `mtowT` | representative maximum takeoff weight | metric tonnes |
| `lengthM`, `spanM`, `heightM` | overall geometry | metres; all three required for same-scale SVG |
| `maxPayloadT`, `cargoM3` | payload and cargo volume | tonnes, cubic metres |
| `comparisonBasis` | seating/range/weight assumptions | read before close performance comparison |
| `fieldEvidence` | field-level source ID, page, state and basis | no generic one-source badge |
| `dataQuality` | completeness, traceability and plotting eligibility | build metadata |
| `localPdfArchive` | internal PDF integrity metadata | 25 records; UI attaches them to canonical sources |

## Unified source registry

The package-level `sources/Civil_Aircraft_Source_Registry_v1.8.json` contains:

| Field | Meaning |
|---|---|
| `metadata.sourceRecordCount` | 55 canonical source records |
| `metadata.localPdfAttachmentCount` | 25 local PDF attachments |
| `sources[]` | canonical source ID, organization, tier, official URL, evidence coverage |
| `sources[].localAttachments[]` | related local PDF filename/path/pages/size/SHA-256/official PDF URL |
| `sources[].archiveStatus` | `local-attached` or `external-only` |

`Civil_Aircraft_PDF_Integrity_v1.8.csv` is a machine QA table, not a second source registry.

## Aircraft verification grades

| Grade | Meaning |
|---|---|
| **A+** | Current OEM/regulator primary evidence directly supports core fields and variant consistency. |
| **A** | Official primary evidence supports major fields; limited page detail or optional gaps allowed. |
| **B+** | Official evidence with legacy/development/cross-check or partial unavailability. |
| **B** | Official development programme, but key performance/geometry is not frozen or published; no guessing. |
| **C** | Secondary-reference only; excluded from the default verified set. |

## Source tiers

| Tier | Meaning |
|---|---|
| **A1** | Regulator-controlled TCDS/certification source |
| **A2** | Current OEM/program official publication or official web page |
| **B1** | Official OEM legacy/archive source |
| **B2** | Official supporting/cross-check source |

## Color policy

1. Manufacturer color: encyclopedia cards and all-aircraft position maps.
2. Comparison slot color 1–6: metric charts, radar, tables and same-scale SVG.
3. Source tier color: document type only, not aircraft superiority.
4. Status color: current / legacy / target-development text badge.
5. Accessibility: marker shape and direct label supplement color.

## Radar modes retained from v1.6

1. `line` (default): no polygon fill.
2. `soft`: all series use 0.06 fill opacity.
3. `active`: only active aircraft uses 0.12 fill opacity.

## No-fallback rule

C929 retains only the official 282–440 seat envelope. MTOW, range and overall geometry are null; it is excluded from same-scale SVG and position maps. The UI explains the exclusion instead of substituting default values.
