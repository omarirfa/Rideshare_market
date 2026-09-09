# NYC airport ride-hail

Every high-volume for-hire trip touching **JFK**, **LaGuardia** or **Newark**,
February 2019 to June 2026 — 122.8 million of them — from the trip records
published by the New York City Taxi and Limousine Commission.

One marimo notebook holds the whole pipeline: the download, the transform, the
storage layer, the analysis and the conclusions.

## What the data says

- **Riders pay more, drivers keep less.** The median airport fare rose 52.1%
  across the archive while the median driver gross rose 34.3%. Payout share fell
  from 69.7% to 63.9%. Median trip distance barely moved, so trip mix does not
  explain the gap.
- **Paying drivers more did not buy market share.** Lyft's payout share overtook
  Uber's at JFK in 2023 and has stayed above it, while Lyft's share of trips
  fell. That points away from pay as the binding constraint and toward matching,
  dispatch and curb operations.
- **The two airports are different products.** Over the last ten months, Uber's
  median fare at LaGuardia runs $7.45 above Lyft's on an identical 9.5-mile
  median, a 15.3% gap. At JFK the gap is 3.5% and runs the other way. A single
  network-wide target misreads one of them.
- **A reporting rule, not a product change.** On-scene coverage for one platform
  goes from 0.16% in February 2025 to 85.6% in March and 100% in April. TLC's
  Wait Time Restrictions rule took effect on 6 March 2025. Curb wait is only
  comparable from that month.
- **Driver pay above rider payment is the minimum-pay floor**, not incentive
  spend. New York's formula pays by mile and minute divided by a utilization
  rate, independent of the fare, so on low-fare airport trips the floor lands
  above what the rider paid.
- **Two questions the data cannot answer.** There is no driver identifier, so no
  segmentation. There are no cancelled trips, so no cancellation rate. Section 8
  says so rather than building a proxy.

## Quick start

```bash
uv run marimo edit nyc_airports.py
```

The notebook carries PEP 723 inline metadata, so `uv` builds the environment
from the file itself. Without `uv`:

```bash
pip install -e ".[dev]"
marimo edit nyc_airports.py
```

## Getting the data

Section 0.10 has a button that fetches the archive and builds the aggregates.
Defaults to the full history: 89 monthly files, about 40 GB of download. One raw
file exists on disk at a time — fetch, filter, write, delete — so peak disk is
about 450 MB plus 36 MB per month kept. Interrupting is safe; completed months
are skipped on the next run.

If you already have the six aggregate tables, drop them in `data/exports/` and
the notebook loads them without downloading anything. They total 164 KB.

Section 2 also loads one month at trip level to demonstrate the cleaning. That
needs `data/processed/airport_2025-01.parquet`, which the extraction produces.




## Sources

- [TLC trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [HVFHV data dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf)
- [Driver pay rules](https://www.nyc.gov/site/tlc/passengers/driver-pay-rules.page)
- [Wait Time Restrictions for FHVs](https://www.nyc.gov/assets/tlc/downloads/pdf/proposed_rules_wait_time_restrictions_fhv.pdf)

The trip records are published by TLC as open data. This repository holds no
trip data; the extraction downloads it from TLC's CDN at run time.

## Licence

MIT for the code. The trip records carry TLC's own terms.