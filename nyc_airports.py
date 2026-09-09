# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars>=1.0",
#     "altair>=5.0",
#     "pyarrow>=15.0",
#     "pygwalker>=0.5",
#     "requests",
#     "orjson",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")

with app.setup:
    import logging
    import os
    import re
    import time
    from collections.abc import Callable, Iterator
    from contextlib import contextmanager
    from dataclasses import dataclass
    from datetime import UTC, datetime
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import orjson
    import polars as pl
    import requests

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    logging.Formatter.converter = time.localtime
    log = logging.getLogger("airports")


@app.cell
def _():
    SECTIONS = [
        ("0", "Extraction: fetch, transform, store, build, run", "0 · Extraction"),
        ("1", "Helpers: loading, charts and derivations", "1 · Helpers"),
        ("2", "Loading", "2 · Loading"),
        (
            "3",
            "Analysis of the loaded data, before any cleaning",
            "3 · Analysis of the loaded data",
        ),
        ("4", "Preprocessing", "4 · Preprocessing"),
        (
            "5",
            "Analysis after preprocessing, and PyGWalker",
            "5 · Analysis after preprocessing",
        ),
        ("6", "Conclusions", "6 · Conclusions"),
        ("7", "Platform against platform", "7 · Platform against platform"),
        ("8", "The five questions", "8 · The five questions"),
        ("9", "Sources and tools", "9 · Sources and tools"),
    ]
    SOURCES = [
        (
            "TLC trip record data",
            "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
            "The monthly HVFHV files that §0 downloads.",
        ),
        (
            "HVFHV data dictionary",
            "https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf",
            "Every column, re-dated 18 March 2025.",
        ),
        (
            "Taxi zone lookup",
            "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
            "Zone 132 is JFK, 138 is LaGuardia, 1 is Newark.",
        ),
        (
            "Driver pay rules",
            "https://www.nyc.gov/site/tlc/passengers/driver-pay-rules.page",
            "The minimum-pay standard behind §6.",
        ),
        (
            "Wait Time Restrictions for FHVs",
            "https://www.nyc.gov/assets/tlc/downloads/pdf/proposed_rules_wait_time_restrictions_fhv.pdf",
            "The rule that starts on-scene reporting in March 2025.",
        ),
        (
            "TLC industry reports",
            "https://www.nyc.gov/site/tlc/about/aggregated-reports.page",
            "Monthly totals, for a check against the trip records.",
        ),
    ]
    TOOLS = [
        ("marimo", "https://docs.marimo.io", "The reactive notebook this file runs in."),
        ("Polars", "https://docs.pola.rs", "Every scan, filter and aggregate."),
        (
            "Vega-Altair",
            "https://altair-viz.github.io",
            "Every chart, through one registered theme.",
        ),
        ("PyGWalker", "https://kanaries.net/pygwalker", "The drag-and-drop view in §5.2."),
        (
            "Apache Parquet",
            "https://parquet.apache.org",
            "The storage format for the slices and the aggregates.",
        ),
    ]
    GLOSSARY = [
        (
            "JFK",
            "John F. Kennedy International Airport, in Queens, New York City",
            "The larger of the two airports that dispatch pickups. It runs overnight.",
        ),
        (
            "LGA",
            "LaGuardia Airport, in Queens, New York City",
            "The domestic airport. It closes overnight and its fares are shorter.",
        ),
        (
            "EWR",
            "Newark Liberty International Airport, in Newark, New Jersey",
            "A different state. A New York licence can set down there but cannot "
            "collect a dispatched fare.",
        ),
        (
            "TLC",
            "New York City Taxi and Limousine Commission",
            "The regulator. It licenses the platforms, sets the minimum pay standard "
            "and publishes the trip records this notebook reads.",
        ),
        (
            "FHV",
            "for-hire vehicle",
            "Any licensed vehicle that carries a passenger for a fare and is not a "
            "yellow or green taxi.",
        ),
        (
            "HVFHV",
            "high-volume for-hire vehicle",
            "The licence class for a service that dispatches more than 10,000 trips a "
            "day. Only a few companies qualify, which is why the market is small.",
        ),
        (
            "NYC",
            "New York City",
            "The five boroughs. The licence is a city licence, which is why New Jersey matters.",
        ),
        (
            "CBD",
            "central business district",
            "Manhattan below 60th Street. A trip that enters it pays the congestion "
            "fee that appears from January 2025.",
        ),
        (
            "WAV",
            "wheelchair accessible vehicle",
            "A vehicle class with its own request and match flags in the trip record.",
        ),
        (
            "HHI",
            "Herfindahl-Hirschman index",
            "The sum of squared percentage shares. 10,000 is one platform taking "
            "every trip, and 2,500 is the threshold for a highly concentrated market.",
        ),
        (
            "CDN",
            "content delivery network",
            "The host that serves the monthly trip files.",
        ),
        (
            "pp",
            "percentage points",
            "The unit for a difference between two shares. A move from 63% to 65% is "
            "two percentage points, not two percent.",
        ),
    ]
    return GLOSSARY, SECTIONS, SOURCES, TOOLS


@app.cell(hide_code=True)
def _(GLOSSARY, SECTIONS, SOURCES, TOOLS, contents_list, gloss, glossary_list, link_list):
    mo.vstack(
        [
            mo.md("# NYC airport ride-hail"),
            mo.md(
                gloss(
                    "Every high-volume for-hire trip touching **JFK**, **LGA** or "
                    "**EWR**, the three airports of New York City, from the trip "
                    "records that the TLC publishes. Hover over any short form for "
                    "its meaning, or open the glossary below."
                )
            ),
            mo.ui.tabs(
                {
                    "Contents": contents_list(SECTIONS),
                    "Glossary": glossary_list(GLOSSARY),
                    "Sources": link_list(SOURCES),
                    "Tools": link_list(TOOLS),
                }
            ),
        ],
        gap=0.9,
    )
    return


@app.cell(hide_code=True)
def _(gloss):
    mo.md(
        gloss(r"""
    Sections 3 and 5 analyse the *same* data before and after cleaning. The
    difference between them is the argument for the cleaning.

    **The market is not the two names you expect.** Four licensees hold an HVFHV
    licence across the archive. Juno paid drivers a larger share of the rider payment
    than either survivor. Via ran a pooling product, and most of its JFK riders asked
    for a shared ride. Both stopped trading before 2022, and neither model survives.
    §7.1 puts all four side by side.

    **EWR is a one-way airport.** It sits in New Jersey, and an NYC licence cannot
    collect a fare in another state. EWR takes millions of dropoffs and almost no
    dispatched pickup. Any comparison that treats it as a third market is wrong.
    """)
    )
    return


@app.cell(hide_code=True)
def _(contents_list, gloss):
    mo.vstack(
        [
            mo.md("## 0 · Extraction"),
            mo.md(
                gloss(
                    "The TLC publishes one file for each month, about 40 GB in total "
                    "and 500 million rows. Airport trips are 7.7% of that. This "
                    "pipeline keeps the 122.8 million rows that touch JFK, LGA or EWR "
                    "and drops the rest."
                )
            ),
            contents_list(
                [
                    ("0.1", "Setup: imports and logging", "0.1 Setup"),
                    ("0.2", "Scope and schema: domain constants", "0.2 Scope and schema"),
                    ("0.3", "Where it goes: <code>Paths</code>", "0.3 Where it goes"),
                    ("0.4", "Calendar: year and month arithmetic", "0.4 Calendar"),
                    ("0.5", "Fetch: one month off the CDN", "0.5 Fetch"),
                    (
                        "0.6",
                        "Transform: the airport filter and every derived column",
                        "0.6 Transform",
                    ),
                    (
                        "0.7",
                        "Store: slim on write, recompute ratios on read",
                        "0.7 Store: 111.7 MB to 36.2 MB for each month",
                    ),
                    (
                        "0.8",
                        "Build: <code>build_month</code> and <code>build_archive</code>",
                        "0.8 Build",
                    ),
                    ("0.9", "Aggregates: the tables the notebook loads", "0.9 Aggregates"),
                    ("0.10", "Run", "0.10 Run"),
                ]
            ),
            mo.md(
                "**The default scope is the full archive.** `build_archive()` with no "
                "arguments gets every month from February 2019 to the newest month on "
                "the CDN. There is no scope to select. The button in §0.10 starts the "
                "download, because a 40 GB download at notebook start is a trap."
            ),
            mo.accordion(
                {
                    "Filter at scan time": mo.md(
                        "Each monthly file holds 18 to 20 million rows. Airport trips are "
                        "7.7% of them. Predicate and projection pushdown cuts about 500 "
                        "million rows to about 123 million before the data goes into "
                        "memory."
                    ),
                    "`cbd_congestion_fee` becomes a typed null": mo.md(
                        "The column starts in 2025-01. Earlier months get it as a typed "
                        "null, so a glob across all months reads without a schema error."
                    ),
                    "Curb-wait fields stay null, never zero": mo.md(
                        "An earlier version put zero in the hourly-earnings denominator. "
                        "That cut one platform's denominator to trip time alone. It made "
                        "the driver earnings of that platform about 18% too high, and the "
                        "error looked like a result."
                    ),
                    "`secs_engaged` is the only comparable denominator": mo.md(
                        "Request to dropoff. Each licensee reports it for the full "
                        "archive, so it is the one earnings denominator that compares "
                        "across platforms."
                    ),
                    "A trip between two airports is a transfer": mo.md(
                        "Each airport then counts it one time only. A trip that starts and "
                        "ends inside one airport gets the label `internal`, which §5.3 "
                        "shows is most of the JFK bucket."
                    ),
                }
            ),
        ],
        gap=0.9,
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.1 Setup

    The imports and the logging configuration are in the setup cell at the top of
    the file. That cell runs before all other cells. Its names are available
    everywhere. The cell signatures below therefore show data dependencies only.

    The setup cell is also the correct place for a name that two cells share, such as
    `dataclass`. An alias such as `_dataclass` in each cell avoids the marimo
    one-definition rule, but marimo lint MR004 rejects that pattern.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.2 Scope and schema

    Domain constants only. The network and storage values stay with the code that
    uses them.

    `PLATFORMS` is a *label* map, not a filter. A licence number that it does not
    contain keeps its raw code as the platform name. No later cell lists the platforms
    by name. The three thresholds below select the live platforms from the data.
    """)
    return


@app.cell
def _():
    ARCHIVE_START = (2019, 2)
    SAMPLE_MONTH = (2025, 1)
    AIRPORTS = {132: "JFK", 138: "LGA", 1: "EWR"}
    PLATFORMS = {
        "HV0002": "Juno",
        "HV0003": "Uber",
        "HV0004": "Via",
        "HV0005": "Lyft",
    }

    MIN_PLATFORM_SHARE = 0.005
    ACTIVE_WINDOW_MONTHS = 12
    MIN_DISPATCH_RATIO = 0.05
    RECENT_WINDOW_MONTHS = 10
    TRAIL_MONTHS = 12

    TRIP_COLUMNS = [
        "hvfhs_license_num",
        "request_datetime",
        "on_scene_datetime",
        "pickup_datetime",
        "dropoff_datetime",
        "PULocationID",
        "DOLocationID",
        "trip_miles",
        "trip_time",
        "base_passenger_fare",
        "tolls",
        "bcf",
        "sales_tax",
        "congestion_surcharge",
        "airport_fee",
        "tips",
        "driver_pay",
        "shared_request_flag",
        "shared_match_flag",
        "wav_request_flag",
        "wav_match_flag",
    ]
    OPTIONAL_COLUMNS = {"cbd_congestion_fee": pl.Float64}
    MONEY_COLS = [
        "trip_miles",
        "base_passenger_fare",
        "tolls",
        "bcf",
        "sales_tax",
        "congestion_surcharge",
        "airport_fee",
        "tips",
        "driver_pay",
        "cbd_congestion_fee",
    ]

    COVERAGE_THRESHOLD = 0.5
    CENSORING_FRACTION = 0.5
    MIN_VALID_ENGAGED_S = 60
    INCENTIVE_SHARE_THRESHOLD = 1.0
    NON_MARKET_DIRECTIONS = ["transfer", "internal"]

    MONTH_GRAIN = "1mo"
    SEASON_FROM = datetime(2022, 1, 1)
    RECOVERY_BASELINE_MONTH = datetime(2020, 2, 1)
    AGGREGATE_TABLES = (
        "monthly_kpis",
        "market_share",
        "hourly_profile",
        "incentive_breakdown",
        "coverage_timeline",
        "data_quality",
    )
    return (
        ACTIVE_WINDOW_MONTHS,
        AGGREGATE_TABLES,
        AIRPORTS,
        ARCHIVE_START,
        CENSORING_FRACTION,
        COVERAGE_THRESHOLD,
        INCENTIVE_SHARE_THRESHOLD,
        MIN_DISPATCH_RATIO,
        MIN_PLATFORM_SHARE,
        MIN_VALID_ENGAGED_S,
        MONEY_COLS,
        MONTH_GRAIN,
        NON_MARKET_DIRECTIONS,
        OPTIONAL_COLUMNS,
        PLATFORMS,
        RECENT_WINDOW_MONTHS,
        RECOVERY_BASELINE_MONTH,
        SAMPLE_MONTH,
        SEASON_FROM,
        TRAIL_MONTHS,
        TRIP_COLUMNS,
    )


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.3 Where it goes

    One object owns every path, and the filename templates sit next to the only code
    that formats them. Pointing the pipeline at another disk means overriding one root.
    """)
    return


@app.cell
def _():
    @dataclass(frozen=True)
    class Paths:
        """Every path the pipeline reads or writes, derived from one root.

        Attributes:
            root: Directory holding the raw, cache, processed and exports trees.
        """

        root: Path

        @property
        def raw(self) -> Path:
            """Untouched monthly parquet, exactly as downloaded."""
            return self.root / "raw"

        @property
        def cache(self) -> Path:
            """Conditional-GET headers, one JSON file per month."""
            return self.root / "cache"

        @property
        def processed(self) -> Path:
            """Airport-filtered monthly parquet."""
            return self.root / "processed"

        @property
        def exports(self) -> Path:
            """Aggregates the notebook and the site read."""
            return self.root / "exports"

        @property
        def all(self) -> tuple[Path, ...]:
            """Every directory, for creation and disk accounting."""
            return (self.raw, self.cache, self.processed, self.exports)

        def raw_file(self, year: int, month: int) -> Path:
            """Give the path of one downloaded monthly file.

            Returns:
                A path in the raw directory.
            """
            return self.raw / f"fhvhv_{year:04d}-{month:02d}.parquet"

        def out_file(self, year: int, month: int) -> Path:
            """Give the path of one filtered monthly slice.

            Returns:
                A path in the processed directory.
            """
            return self.processed / f"airport_{year:04d}-{month:02d}.parquet"

        def header_file(self, year: int, month: int) -> Path:
            """Give the path of one cached response-header file.

            Returns:
                A path in the cache directory.
            """
            return self.cache / f"fhvhv_{year:04d}-{month:02d}.headers.json"

        def export_file(self, name: str, fmt: str = "parquet") -> Path:
            """Give the path of one exported aggregate table.

            Returns:
                A path in the exports directory.
            """
            return self.exports / f"{name}.{fmt}"

        def ensure(self) -> None:
            """Create each directory that does not exist."""
            for directory in self.all:
                directory.mkdir(parents=True, exist_ok=True)

    PATHS = Paths(Path(os.environ.get("NYC_AIRPORTS_DATA", "data")))
    OUT_GLOB = "airport_[0-9][0-9][0-9][0-9]-[0-9][0-9].parquet"
    return OUT_GLOB, PATHS


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.4 Calendar

    Year-month arithmetic, used by both the fetcher and the build loop.
    """)
    return


@app.cell
def _():
    def month_add(ym: tuple[int, int], n: int) -> tuple[int, int]:
        """Shift a year-month pair by a number of months.

        Args:
            ym: Year and 1-indexed month.
            n: Months to add. A negative value moves backwards.

        Returns:
            The shifted year and month.
        """
        year, month = ym
        index = year * 12 + (month - 1) + n
        return index // 12, index % 12 + 1

    def current_month() -> tuple[int, int]:
        """Give the current year and month in UTC.

        Returns:
            The year and the 1-indexed month.
        """
        now = datetime.now(UTC)
        return now.year, now.month

    def months(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        """List every month between two bounds, inclusive.

        Args:
            start: First year and month.
            end: Last year and month.

        Returns:
            The months in order. The list is empty for an inverted range.
        """
        out: list[tuple[int, int]] = []
        ym = start
        while ym <= end:
            out.append(ym)
            ym = month_add(ym, 1)
        return out

    def parse_ym(text: str) -> tuple[int, int]:
        """Parse a YYYY-MM string from a UI field.

        Args:
            text: User-supplied text.

        Returns:
            The parsed year and month.

        Raises:
            ValueError: If the text is not a plausible YYYY-MM value. The message
                is shown to a person, so it names what was received.
        """
        parts = text.strip().split("-")
        if len(parts) != 2:
            raise ValueError(f"expected YYYY-MM, got {text.strip()!r}")
        try:
            year, month = int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError(f"expected YYYY-MM, got {text.strip()!r}") from None
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 01-12, got {parts[1]!r}")
        if not 2019 <= year <= 2100:
            raise ValueError(f"year looks wrong: {parts[0]!r}")
        return year, month

    return current_month, month_add, months, parse_ym


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.5 Fetch

    One month off the TLC CDN, with retries, resume and a size check. Nothing here
    knows what an airport is.
    """)
    return


@app.cell
def _(PATHS, current_month, month_add):
    CDN = "https://d37ci6vzurychx.cloudfront.net"
    TRIP_URL = CDN + "/trip-data/fhvhv_tripdata_{year:04d}-{month:02d}.parquet"
    USER_AGENT = os.environ.get(
        "NYC_AIRPORTS_USER_AGENT",
        "nyc-airport-analysis/0.1 (set NYC_AIRPORTS_USER_AGENT with your contact)",
    )
    CHUNK = 1 << 20
    PROGRESS_INTERVAL_S = 1.0
    TRIP_TIMEOUT_S = 600
    PROBE_TIMEOUT_S = 30
    DOWNLOAD_RETRIES = 4
    RETRY_BACKOFF_BASE_S = 5
    PUBLICATION_LAG_MONTHS = 2

    @dataclass
    class FetchResult:
        """Outcome of one monthly download.

        Attributes:
            year: Four-digit year.
            month: Month, 1-indexed.
            path: Where the file landed.
            downloaded: False for a complete copy that was on disk.
            n_bytes: Size of the file on disk.
        """

        year: int
        month: int
        path: Path
        downloaded: bool
        n_bytes: int

    def fetch_month(
        year: int,
        month: int,
        timeout: int = TRIP_TIMEOUT_S,
        retries: int = DOWNLOAD_RETRIES,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> FetchResult:
        """Download one monthly parquet, skipping a complete local copy.

        Args:
            year: Four-digit year.
            month: Month, 1-indexed.
            timeout: Per-request timeout in seconds.
            retries: Attempts before giving up.
            on_progress: Callback for the bytes received and the bytes expected.
                The function calls it at most one time each second.

        Returns:
            Where the file is and whether this call fetched it.

        Raises:
            FileNotFoundError: The month is not published yet.
            OSError: Every attempt returned a truncated body.
            requests.RequestException: Every attempt failed at the transport level.
        """
        PATHS.ensure()
        url = TRIP_URL.format(year=year, month=month)
        dest = PATHS.raw_file(year, month)
        headers_path = PATHS.header_file(year, month)

        if dest.exists() and headers_path.exists():
            prior = orjson.loads(headers_path.read_bytes())
            if prior.get("content_length") == dest.stat().st_size:
                return FetchResult(year, month, dest, False, dest.stat().st_size)

        tmp = dest.with_suffix(".parquet.part")
        for attempt in range(retries):
            try:
                with requests.get(
                    url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=True
                ) as response:
                    if response.status_code == 404:
                        raise FileNotFoundError(f"{year}-{month:02d} not published yet: {url}")
                    response.raise_for_status()
                    total = int(response.headers.get("Content-Length") or 0)
                    done = 0
                    last_report = 0.0
                    with tmp.open("wb") as handle:
                        for chunk in response.iter_content(CHUNK):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            done += len(chunk)
                            now = time.monotonic()
                            if on_progress and now - last_report >= PROGRESS_INTERVAL_S:
                                last_report = now
                                on_progress(done, total)
                    got = tmp.stat().st_size
                    if total and got != total:
                        raise OSError(f"truncated: got {got:,} of {total:,} bytes")
                    headers_path.write_bytes(
                        orjson.dumps(
                            {
                                "content_length": total,
                                "etag": response.headers.get("ETag"),
                                "fetched_utc": datetime.now(UTC).isoformat(),
                                "url": url,
                            },
                            option=orjson.OPT_INDENT_2,
                        )
                    )
                break
            except FileNotFoundError:
                tmp.unlink(missing_ok=True)
                raise
            except (requests.RequestException, OSError) as exc:
                tmp.unlink(missing_ok=True)
                if attempt == retries - 1:
                    raise
                wait = RETRY_BACKOFF_BASE_S * 2**attempt
                log.warning(
                    "%d-%02d attempt %d of %d failed (%s). Next try in %ds",
                    year,
                    month,
                    attempt + 1,
                    retries,
                    exc,
                    wait,
                )
                time.sleep(wait)

        tmp.replace(dest)
        return FetchResult(year, month, dest, True, dest.stat().st_size)

    def latest_available_month(
        max_lookback: int = 8, timeout: int = PROBE_TIMEOUT_S
    ) -> tuple[int, int]:
        """Find the newest published month by probing the CDN.

        Args:
            max_lookback: How many months to walk back before giving up.
            timeout: Per-request timeout in seconds.

        Returns:
            The newest month with a 200 response. An unreachable network gives
            the current month minus the nominal lag.
        """
        start = current_month()
        for back in range(max_lookback + 1):
            year, month = month_add(start, -back)
            try:
                response = requests.head(
                    TRIP_URL.format(year=year, month=month),
                    headers={"User-Agent": USER_AGENT},
                    timeout=timeout,
                    allow_redirects=True,
                )
                if response.status_code == 200:
                    return year, month
            except requests.RequestException:
                fallback = month_add(start, -PUBLICATION_LAG_MONTHS)
                log.warning("probe failed. Using %d-%02d", *fallback)
                return fallback
        return month_add(start, -PUBLICATION_LAG_MONTHS)

    return fetch_month, latest_available_month


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.6 Transform

    This is the function that produced every column the notebook reads.

    Look at the platform mapping. `PLATFORMS` gives a label to the four known licence
    numbers. All other codes stay as they are. A fifth licensee therefore appears as
    `HV0006`. It does not go into a shared `Unknown` row with every other unmapped
    code.
    """)
    return


@app.cell
def _(
    AIRPORTS,
    INCENTIVE_SHARE_THRESHOLD,
    MIN_VALID_ENGAGED_S,
    OPTIONAL_COLUMNS,
    PLATFORMS,
    TRIP_COLUMNS,
):
    def airport_expr(col: str) -> pl.Expr:
        """Map a location id column to an airport code.

        Args:
            col: Name of the location id column.

        Returns:
            Expression yielding the airport code, or null off-airport.
        """
        return pl.col(col).replace_strict(AIRPORTS, default=None)

    def platform_expr() -> pl.Expr:
        """Map a licence number to a platform name and keep unknown codes.

        Returns:
            An expression that gives the label from PLATFORMS. A code that
            PLATFORMS does not contain keeps its raw licence number.
        """
        return pl.coalesce(
            pl.col("hvfhs_license_num").replace_strict(PLATFORMS, default=None),
            pl.col("hvfhs_license_num"),
        )

    def scan_airport_trips(path: Path | str) -> pl.LazyFrame:
        """Scan one monthly file, keep airport trips, derive every metric.

        Args:
            path: A monthly HVFHV parquet file.

        Returns:
            Lazy frame of airport trips with derived timing, money and flag columns.
        """
        lf = pl.scan_parquet(path)
        have = set(lf.collect_schema().names())

        lf = lf.select(
            [c for c in TRIP_COLUMNS if c in have] + [c for c in OPTIONAL_COLUMNS if c in have]
        )
        for col, dtype in OPTIONAL_COLUMNS.items():
            if col not in have:
                lf = lf.with_columns(pl.lit(None, dtype=dtype).alias(col))

        ids = list(AIRPORTS)
        lf = lf.filter(pl.col("PULocationID").is_in(ids) | pl.col("DOLocationID").is_in(ids))

        to_scene = (pl.col("on_scene_datetime") - pl.col("request_datetime")).dt.total_seconds()
        at_curb = (pl.col("pickup_datetime") - pl.col("on_scene_datetime")).dt.total_seconds()
        engaged = (pl.col("dropoff_datetime") - pl.col("request_datetime")).dt.total_seconds()

        rider_total = (
            pl.col("base_passenger_fare").fill_null(0.0)
            + pl.col("tolls").fill_null(0.0)
            + pl.col("bcf").fill_null(0.0)
            + pl.col("sales_tax").fill_null(0.0)
            + pl.col("congestion_surcharge").fill_null(0.0)
            + pl.col("airport_fee").fill_null(0.0)
            + pl.col("cbd_congestion_fee").fill_null(0.0)
        )

        return (
            lf.with_columns(
                platform_expr().alias("platform"),
                airport_expr("PULocationID").alias("pu_airport"),
                airport_expr("DOLocationID").alias("do_airport"),
                to_scene.alias("secs_request_to_scene"),
                at_curb.alias("secs_scene_to_pickup"),
                engaged.alias("secs_engaged"),
                pl.col("on_scene_datetime").is_not_null().alias("has_on_scene"),
                rider_total.alias("rider_total_ex_tip"),
            )
            .with_columns(
                pl.when(pl.col("pu_airport") == pl.col("do_airport"))
                .then(pl.lit("internal"))
                .when(pl.col("pu_airport").is_not_null() & pl.col("do_airport").is_not_null())
                .then(pl.lit("transfer"))
                .when(pl.col("pu_airport").is_not_null())
                .then(pl.lit("pickup"))
                .otherwise(pl.lit("dropoff"))
                .alias("direction"),
                pl.coalesce("pu_airport", "do_airport").alias("airport"),
                (pl.col("driver_pay") + pl.col("tips").fill_null(0.0)).alias("driver_gross"),
            )
            .with_columns(
                (pl.col("driver_gross") / pl.col("rider_total_ex_tip").replace(0.0, None)).alias(
                    "driver_share"
                ),
                (pl.col("base_passenger_fare") / pl.col("trip_miles").replace(0.0, None)).alias(
                    "fare_per_mile"
                ),
                (
                    pl.col("driver_gross") / (pl.col("secs_engaged") / 3600.0).replace(0.0, None)
                ).alias("driver_gross_per_engaged_hour"),
                (pl.col("shared_request_flag") == "Y").alias("pool_requested"),
                (pl.col("shared_match_flag") == "Y").alias("pool_matched"),
            )
            .with_columns(
                (pl.col("driver_share") > INCENTIVE_SHARE_THRESHOLD).alias("likely_incentive"),
                (
                    (pl.col("base_passenger_fare") > 0)
                    & (pl.col("trip_miles") > 0)
                    & (pl.col("secs_engaged") > MIN_VALID_ENGAGED_S)
                    & (
                        pl.col("secs_request_to_scene").is_null()
                        | (pl.col("secs_request_to_scene") >= 0)
                    )
                    & (
                        pl.col("secs_scene_to_pickup").is_null()
                        | (pl.col("secs_scene_to_pickup") >= 0)
                    )
                ).alias("is_valid"),
            )
        )

    return (scan_airport_trips,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.7 Store: 111.7 MB to 36.2 MB for each month

    The writer removes each column that the reader can compute again. `add_ratios` is
    the inverse of `DROP_ON_WRITE`. Change the two together.

    Two details in the writer are easy to lose. It sets each datetime to microseconds,
    because the TLC monthly files disagree about the time unit. A glob across a mixed
    set then fails with a schema error. It also sorts by airport and pickup time. The
    sort groups the categorical and time values, and saves about 13% of the file
    size.
    """)
    return


@app.cell
def _(MONEY_COLS):
    ZSTD_LEVEL = 9
    ROW_GROUP = 256_000
    RAW_MB_PER_MONTH = 450
    SLICE_MB_PER_MONTH = 36

    DROP_ON_WRITE = [
        "hvfhs_license_num",
        "pu_airport",
        "do_airport",
        "on_scene_datetime",
        "request_datetime",
        "dropoff_datetime",
        "shared_request_flag",
        "shared_match_flag",
        "wav_request_flag",
        "wav_match_flag",
        "rider_total_ex_tip",
        "driver_gross",
        "driver_share",
        "fare_per_mile",
        "driver_gross_per_engaged_hour",
    ]

    def rider_total_expr() -> pl.Expr:
        """Sum everything the rider paid except the tip.

        Returns:
            Expression yielding the rider total, treating missing fees as zero.
        """
        return (
            pl.col("base_passenger_fare").fill_null(0.0)
            + pl.col("tolls").fill_null(0.0)
            + pl.col("bcf").fill_null(0.0)
            + pl.col("sales_tax").fill_null(0.0)
            + pl.col("congestion_surcharge").fill_null(0.0)
            + pl.col("airport_fee").fill_null(0.0)
            + pl.col("cbd_congestion_fee").fill_null(0.0)
        )

    def slim_for_storage(lf: pl.LazyFrame) -> pl.LazyFrame:
        """Drop derivable columns and downcast for a threefold smaller footprint.

        Args:
            lf: Frame straight out of scan_airport_trips.

        Returns:
            The frame ready to write.
        """
        have = set(lf.collect_schema().names())
        return lf.drop([c for c in DROP_ON_WRITE if c in have]).with_columns(
            pl.col(pl.Datetime).cast(pl.Datetime("us")),
            pl.col("PULocationID").cast(pl.Int16),
            pl.col("DOLocationID").cast(pl.Int16),
            pl.col("trip_time").cast(pl.Int32),
            pl.col("secs_engaged").cast(pl.Int32),
            pl.col("secs_request_to_scene").cast(pl.Int32),
            pl.col("secs_scene_to_pickup").cast(pl.Int32),
            *[pl.col(c).cast(pl.Float32) for c in MONEY_COLS if c in have],
            *[pl.col(c).cast(pl.Categorical) for c in ("platform", "airport", "direction")],
        )

    def add_ratios(lf: pl.LazyFrame) -> pl.LazyFrame:
        """Recompute the ratio columns that slim_for_storage dropped.

        Args:
            lf: Frame read back from a processed monthly file.

        Returns:
            The frame with driver_gross, rider_total_ex_tip and the three ratios.
            A frame that has them stays unchanged.
        """
        if "driver_share" in set(lf.collect_schema().names()):
            return lf
        return lf.with_columns(
            (pl.col("driver_pay") + pl.col("tips").fill_null(0.0)).alias("driver_gross"),
            rider_total_expr().alias("rider_total_ex_tip"),
        ).with_columns(
            (pl.col("driver_gross") / pl.col("rider_total_ex_tip").replace(0.0, None)).alias(
                "driver_share"
            ),
            (pl.col("base_passenger_fare") / pl.col("trip_miles").replace(0.0, None)).alias(
                "fare_per_mile"
            ),
            (pl.col("driver_gross") / (pl.col("secs_engaged") / 3600.0).replace(0.0, None)).alias(
                "driver_gross_per_engaged_hour"
            ),
        )

    def write_slim(lf: pl.LazyFrame, path: Path) -> Path:
        """Sort and write one processed month.

        Args:
            lf: Frame straight out of scan_airport_trips.
            path: Destination parquet file.

        Returns:
            The path written.
        """
        (
            slim_for_storage(lf)
            .sort("airport", "pickup_datetime")
            .sink_parquet(
                path, compression="zstd", compression_level=ZSTD_LEVEL, row_group_size=ROW_GROUP
            )
        )
        return path

    return (
        RAW_MB_PER_MONTH,
        SLICE_MB_PER_MONTH,
        ZSTD_LEVEL,
        add_ratios,
        write_slim,
    )


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.8 Build

    `build_month` builds one month. `build_archive` builds all of them, and is the
    default entry point. The loop skips each month that is on disk. You can stop the
    run at any time, and the next run continues from that point. One raw file is on
    disk at a time: fetch, filter, write, delete.

    Peak disk use is one raw file plus the slices, about 3.2 GB for the full history.
    A month that fails goes to the log, and the loop continues. One bad file cannot
    stop an 89-month run.
    """)
    return


@app.cell
def _(
    ARCHIVE_START,
    OUT_GLOB,
    PATHS,
    add_ratios,
    fetch_month,
    latest_available_month,
    months,
    scan_airport_trips,
    write_slim,
):
    def build_month(
        year: int,
        month: int,
        overwrite: bool = False,
        keep_raw: bool = False,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Fetch, filter and write one month, then delete the source.

        Args:
            year: Four-digit year.
            month: Month, 1-indexed.
            overwrite: Rebuild a month that is on disk.
            keep_raw: Keep the ~450 MB download instead of deleting it.
            on_progress: Callback for the download progress of this month.

        Returns:
            Path of the processed slice.
        """
        out = PATHS.out_file(year, month)
        if out.exists() and not overwrite:
            return out
        result = fetch_month(year, month, on_progress=on_progress)
        write_slim(scan_airport_trips(result.path), out)
        if not keep_raw:
            result.path.unlink(missing_ok=True)
        return out

    def build_archive(
        start: tuple[int, int] = ARCHIVE_START,
        end: tuple[int, int] | None = None,
        keep_raw: bool = False,
        overwrite: bool = False,
        on_month: Callable[[int, int, int, int], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[Path]:
        """Build every month between two bounds, defaulting to the whole archive.

        Args:
            start: First month to build.
            end: Last month, or None to probe the CDN for the newest published.
            keep_raw: Keep each download after filtering.
            overwrite: Rebuild months that are already on disk.
            on_month: Callback after each month, with the year, the month, the
                position in the plan, and the length of the plan.
            on_progress: Callback for the download progress of each month.

        Returns:
            Paths of the slices that exist after the run.
        """
        end = end or latest_available_month()
        plan = months(start, end)
        log.info("building %d month(s): %d-%02d to %d-%02d", len(plan), *plan[0], *plan[-1])

        built: list[Path] = []
        for index, (year, month) in enumerate(plan, start=1):
            try:
                built.append(
                    build_month(
                        year,
                        month,
                        overwrite=overwrite,
                        keep_raw=keep_raw,
                        on_progress=on_progress,
                    )
                )
            except FileNotFoundError as exc:
                log.warning("skip: %s", exc)
            except Exception as exc:
                log.error("FAILED %d-%02d: %s", year, month, exc)
            if on_month:
                on_month(year, month, index, len(plan))
        return built

    def disk_usage() -> dict[str, float]:
        """Measure the current footprint by directory.

        Returns:
            Megabytes held in the raw, processed and exports directories.
        """

        def megabytes(directory: Path) -> float:
            if not directory.exists():
                return 0.0
            return sum(f.stat().st_size for f in directory.glob("*") if f.is_file()) / 1e6

        return {
            "raw_mb": megabytes(PATHS.raw),
            "processed_mb": megabytes(PATHS.processed),
            "exports_mb": megabytes(PATHS.exports),
        }

    def load_all(pattern: str = OUT_GLOB) -> pl.LazyFrame:
        """Scan every processed month, recomputing ratios on the fly.

        Args:
            pattern: Glob matched inside the processed directory.

        Returns:
            Lazy frame over the whole archive.
        """
        cast = pl.ScanCastOptions(
            datetime_cast="microsecond-upcast",
            float_cast="upcast",
            integer_cast="upcast",
        )
        return add_ratios(pl.scan_parquet(str(PATHS.processed / pattern), cast_options=cast))

    return build_archive, disk_usage, load_all


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.9 Aggregates

    The trip table holds 122 million rows and about 3 GB. Do not ship it. These six
    tables hold a few thousand rows each, and §2 loads them.

    They contain **every licensee**, including the two that hold a fraction of one
    percent. Those small columns carry the entries, the exits and the concentration,
    so the duopoly of today reads as a stage rather than a fact.
    """)
    return


@app.cell
def _(AGGREGATE_TABLES, MONTH_GRAIN, PATHS, ZSTD_LEVEL, load_all):
    def coverage_timeline(lf: pl.LazyFrame) -> pl.LazyFrame:
        """Report on-scene reporting coverage by month and platform.

        Args:
            lf: Trip-level frame.

        Returns:
            Trips and the share of them carrying an on-scene timestamp.
        """
        return (
            lf.with_columns(pl.col("pickup_datetime").dt.truncate(MONTH_GRAIN).alias("month"))
            .group_by("month", "platform")
            .agg(
                pl.len().alias("trips"),
                pl.col("has_on_scene").mean().alias("on_scene_coverage"),
            )
            .sort("month", "platform")
        )

    def hourly_profile(
        lf: pl.LazyFrame, direction: str = "pickup", valid_only: bool = True
    ) -> pl.LazyFrame:
        """Summarise trips and economics by hour of day.

        Args:
            lf: Trip-level frame.
            direction: Trip direction to keep, or empty for all.
            valid_only: Drop rows that failed the validity test.

        Returns:
            One row per airport, platform and hour.
        """
        if valid_only:
            lf = lf.filter(pl.col("is_valid"))
        if direction:
            lf = lf.filter(pl.col("direction") == direction)
        return (
            lf.with_columns(pl.col("pickup_datetime").dt.hour().alias("hour"))
            .group_by("airport", "platform", "hour")
            .agg(
                pl.len().alias("trips"),
                pl.col("base_passenger_fare").median().alias("med_fare"),
                pl.col("driver_gross_per_engaged_hour")
                .median()
                .alias("med_gross_per_engaged_hour"),
                pl.col("driver_share").median().alias("med_driver_share"),
                pl.col("likely_incentive").mean().alias("incentive_rate"),
                pl.col("secs_scene_to_pickup").median().alias("med_curb_wait_s"),
                pl.col("has_on_scene").mean().alias("curb_wait_coverage"),
            )
            .with_columns(
                (pl.col("trips") / pl.col("trips").sum().over("airport", "platform")).alias(
                    "share_of_day"
                )
            )
            .sort("airport", "platform", "hour")
        )

    def incentive_breakdown(lf: pl.LazyFrame, valid_only: bool = True) -> pl.LazyFrame:
        """Measure where driver pay exceeds everything the rider paid.

        Args:
            lf: Trip-level frame.
            valid_only: Drop rows that failed the validity test.

        Returns:
            One row per month, airport, platform and direction.
        """
        if valid_only:
            lf = lf.filter(pl.col("is_valid"))
        gap = pl.col("driver_gross") - pl.col("rider_total_ex_tip")
        return (
            lf.with_columns(pl.col("pickup_datetime").dt.truncate(MONTH_GRAIN).alias("month"))
            .group_by("month", "airport", "platform", "direction")
            .agg(
                pl.len().alias("trips"),
                pl.col("likely_incentive").sum().alias("incentive_trips"),
                pl.col("likely_incentive").mean().alias("incentive_rate"),
                gap.filter(pl.col("likely_incentive")).median().alias("med_topup"),
                gap.filter(pl.col("likely_incentive")).sum().alias("total_topup"),
                pl.col("driver_share")
                .filter(pl.col("likely_incentive"))
                .median()
                .alias("med_share_when_incentivised"),
            )
            .with_columns((pl.col("total_topup") / pl.col("trips")).alias("topup_per_trip"))
            .sort("month", "airport", "platform", "direction")
        )

    def monthly_kpis(lf: pl.LazyFrame, valid_only: bool = True) -> pl.LazyFrame:
        """Build the core panel of airport, platform, direction and month.

        Args:
            lf: Trip-level frame.
            valid_only: Drop rows that failed the validity test.

        Returns:
            One row per month, airport, platform and direction.
        """
        if valid_only:
            lf = lf.filter(pl.col("is_valid"))
        return (
            lf.with_columns(pl.col("pickup_datetime").dt.truncate(MONTH_GRAIN).alias("month"))
            .group_by("month", "airport", "platform", "direction")
            .agg(
                pl.len().alias("trips"),
                pl.col("base_passenger_fare").median().alias("med_fare"),
                pl.col("driver_gross").median().alias("med_driver_gross"),
                pl.col("driver_share").median().alias("med_driver_share"),
                pl.col("fare_per_mile").median().alias("med_fare_per_mile"),
                pl.col("driver_gross_per_engaged_hour")
                .median()
                .alias("med_gross_per_engaged_hour"),
                pl.col("secs_engaged").median().alias("med_engaged_s"),
                pl.col("secs_scene_to_pickup").median().alias("med_curb_wait_s"),
                pl.col("has_on_scene").mean().alias("curb_wait_coverage"),
                pl.col("trip_miles").median().alias("med_miles"),
                pl.col("pool_requested").mean().alias("pool_request_rate"),
                (
                    pl.col("pool_matched").sum() / pl.col("pool_requested").sum().replace(0, None)
                ).alias("pool_match_rate"),
                pl.col("likely_incentive").mean().alias("incentive_rate"),
                pl.col("tips").mean().alias("mean_tip"),
            )
            .sort("month", "airport", "platform", "direction")
        )

    def data_quality(lf: pl.LazyFrame) -> pl.LazyFrame:
        """Report per-platform data quality.

        Args:
            lf: Trip-level frame.

        Returns:
            One row per platform, counting the failure modes worth knowing about.
        """
        return (
            lf.group_by("platform")
            .agg(
                pl.len().alias("trips"),
                pl.col("has_on_scene").mean().alias("on_scene_coverage"),
                (~pl.col("is_valid")).sum().alias("invalid_rows"),
                (pl.col("secs_request_to_scene") < 0).sum().alias("neg_to_scene"),
                (pl.col("secs_scene_to_pickup") < 0).sum().alias("neg_curb_wait"),
                (pl.col("base_passenger_fare") <= 0).sum().alias("nonpos_fare"),
                (pl.col("trip_miles") <= 0).sum().alias("nonpos_miles"),
                pl.col("likely_incentive").mean().alias("incentive_rate"),
            )
            .sort("platform")
        )

    def market_share(lf: pl.LazyFrame) -> pl.LazyFrame:
        """Compute each platform's share of airport trips over time.

        Args:
            lf: Trip-level frame.

        Returns:
            Trips and share per month, airport and platform, across all licensees.
        """
        return (
            lf.with_columns(pl.col("pickup_datetime").dt.truncate(MONTH_GRAIN).alias("month"))
            .group_by("month", "airport", "platform")
            .agg(pl.len().alias("trips"))
            .with_columns(
                (pl.col("trips") / pl.col("trips").sum().over("month", "airport")).alias("share")
            )
            .sort("month", "airport", "platform")
        )

    def export_aggregates(
        fmt: str = "parquet",
        on_table: Callable[[str], None] | None = None,
    ) -> dict[str, Path]:
        """Write the analysis-ready tables that §2 loads.

        The six queries collect together. Each one reads the same 122 million rows,
        so one batch replaces six passes over the archive.

        Args:
            fmt: Either parquet, which the site queries directly, or json.
            on_table: Callback with the name of each table before it is written.

        Returns:
            Table name to written path.

        Raises:
            ValueError: The format is not supported.
        """
        if fmt not in ("parquet", "json"):
            raise ValueError(f"fmt must be 'parquet' or 'json', got {fmt!r}")
        PATHS.ensure()
        lf = load_all()

        queries = {
            "monthly_kpis": monthly_kpis(lf),
            "market_share": market_share(lf),
            "hourly_profile": hourly_profile(lf),
            "incentive_breakdown": incentive_breakdown(lf),
            "coverage_timeline": coverage_timeline(lf),
            "data_quality": data_quality(lf),
        }
        assert set(queries) == set(AGGREGATE_TABLES), (
            f"aggregate mismatch: {sorted(set(queries) ^ set(AGGREGATE_TABLES))}"
        )

        if on_table:
            on_table("scanning the archive once for all six tables")
        frames = pl.collect_all(list(queries.values()))

        written: dict[str, Path] = {}
        for label, frame in zip(queries, frames, strict=True):
            if on_table:
                on_table(label)
            path = PATHS.export_file(label, fmt)
            if fmt == "json":
                frame.write_json(path)
            else:
                frame.write_parquet(path, compression="zstd", compression_level=ZSTD_LEVEL)
            written[label] = path
        return written

    return (export_aggregates,)


@app.cell
def _():
    LOG_PANEL_INDEX = 1
    LOG_PANEL_LINES = 14

    class OutputLogHandler(logging.Handler):
        """Write log records into one slot of the cell output.

        Attributes:
            index: Position of the panel in the output of the running cell.
            keep: Number of recent lines to show.
            lines: The captured lines.
        """

        def __init__(self, index: int, keep: int = LOG_PANEL_LINES) -> None:
            super().__init__()
            self.index = index
            self.keep = keep
            self.lines: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            """Add one record to the panel and redraw it.

            Args:
                record: The record to show.
            """
            self.lines.append(self.format(record))
            mo.output.replace_at_index(self.render(), self.index)

        def render(self) -> object:
            """Build the panel.

            Returns:
                A markdown block of the most recent lines.
            """
            recent = "\n".join(self.lines[-self.keep :])
            return mo.md(f"```text\n{recent}\n```")

    @contextmanager
    def log_panel(index: int = LOG_PANEL_INDEX) -> Iterator[OutputLogHandler]:
        """Show the log below the progress bar for the length of one run.

        The progress bar takes the first output slot of the cell and updates
        itself in place. The panel takes the next slot, so the two appear
        together and neither one overwrites the other.

        Args:
            index: Output slot for the panel.

        Yields:
            The handler, for the caller to read the captured lines.
        """
        handler = OutputLogHandler(index)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
        )
        mo.output.append(handler.render())
        log.addHandler(handler)
        try:
            yield handler
        finally:
            log.removeHandler(handler)

    return (log_panel,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 0.10 Run

    The fields default to the **full archive**: blank means "from the beginning" and
    "to the newest month the CDN has". Fill them in only to narrow the scope.
    Equivalent in code, with the same defaults:

    ```python
    build_archive()          # everything
    export_aggregates()      # then rebuild the six tables §2 reads
    ```

    Nothing downloads until the button is pressed. The cell that does the work shows
    two things, one above the other:

    - a **progress bar** in the first output slot, which reports the month, the
      megabytes of the current download, the rate and the estimated time
    - a **log panel** in the second slot, which holds the most recent log lines

    They use separate output slots, so each one updates without a redraw of the other.
    The panel stays after the run, next to the summary.

    This replaces a terminal progress bar. marimo sends terminal output to the console
    panel, away from the control. Two terminal bars also write to one line, one for
    the months and one for the file, and the display then flickers.

    The same lines go to the standard logger, so a run from the command line shows the
    progress in the terminal.
    """)
    return


@app.cell
def _():
    build_from = mo.ui.text(value="", label="From (YYYY-MM, blank = 2019-02)")
    build_to = mo.ui.text(value="", label="To (YYYY-MM, blank = newest published)")
    keep_raw = mo.ui.checkbox(value=False, label="Keep the ~450 MB source files")
    refresh_aggregates = mo.ui.checkbox(value=True, label="Rebuild the aggregates afterwards")
    run_extraction = mo.ui.run_button(
        label="Fetch and build",
        kind="danger",
        tooltip="Downloads from the TLC CDN. Safe to interrupt and resume.",
    )
    mo.vstack([build_from, build_to, keep_raw, refresh_aggregates, run_extraction])
    return build_from, build_to, keep_raw, refresh_aggregates, run_extraction


@app.cell
def _(
    ARCHIVE_START,
    PATHS,
    RAW_MB_PER_MONTH,
    SLICE_MB_PER_MONTH,
    build_from,
    build_to,
    latest_available_month,
    months,
    parse_ym,
):
    plan: list[tuple[int, int]] = []
    plan_error: str | None = None
    try:
        _start = parse_ym(build_from.value) if build_from.value.strip() else ARCHIVE_START
        _end = parse_ym(build_to.value) if build_to.value.strip() else latest_available_month()
        plan = months(_start, _end)
        if not plan:
            plan_error = f"empty range: {_start} is after {_end}"
    except (ValueError, OSError) as exc:
        plan_error = str(exc)

    todo = [ym for ym in plan if not PATHS.out_file(*ym).exists()]

    if plan_error:
        _summary = mo.md(f"Cannot plan: {plan_error}").callout(kind="danger")
    else:
        _summary = mo.md(
            f"""
    **{len(plan)} month(s)** in scope, {plan[0][0]}-{plan[0][1]:02d} to
    {plan[-1][0]}-{plan[-1][1]:02d}. **{len(plan) - len(todo)} already built**,
    **{len(todo)} to fetch**.

    Estimated download **{len(todo) * RAW_MB_PER_MONTH / 1000:.1f} GB**. The processed
    slices come to about **{len(plan) * SLICE_MB_PER_MONTH / 1000:.1f} GB**.
            """
        ).callout(kind="warn" if len(todo) > 12 else "info")
    _summary
    return plan, plan_error, todo


@app.cell
def _(
    build_archive,
    disk_usage,
    export_aggregates,
    keep_raw,
    log_panel,
    plan: list[tuple[int, int]],
    plan_error: str | None,
    refresh_aggregates,
    run_extraction,
    todo,
):
    if run_extraction.value and plan and not plan_error:
        _steps = len(plan) + (1 if refresh_aggregates.value else 0)
        with (
            mo.status.progress_bar(
                total=_steps,
                title="Building the archive",
                subtitle=f"{plan[0][0]}-{plan[0][1]:02d} to {plan[-1][0]}-{plan[-1][1]:02d}",
                completion_title="Extraction finished",
                completion_subtitle="Re-run §2 to load the new tables",
                show_eta=True,
                show_rate=True,
            ) as progress,
            log_panel() as _panel,
        ):

            def month_done(year: int, month: int, index: int, total: int) -> None:
                """Advance the bar by one month and write one log line.

                Args:
                    year: Year just built.
                    month: Month just built.
                    index: Position in the plan.
                    total: Length of the plan.
                """
                stored = disk_usage()["processed_mb"]
                log.info(
                    "%d of %d | %d-%02d done | %s MB stored",
                    index,
                    total,
                    year,
                    month,
                    f"{stored:,.0f}",
                )
                progress.update(subtitle=f"{year}-{month:02d} done, {index} of {total}")

            def bytes_done(done: int, total: int) -> None:
                """Report download progress without advancing the bar.

                Args:
                    done: Bytes received.
                    total: Bytes expected.
                """
                progress.update(
                    increment=0,
                    subtitle=f"downloading {done / 1e6:,.0f} of {total / 1e6:,.0f} MB",
                )

            def table_done(name: str) -> None:
                """Report the aggregate table now being written.

                Args:
                    name: Table name.
                """
                log.info("writing %s", name)
                progress.update(increment=0, subtitle=f"writing {name}")

            _built = build_archive(
                plan[0],
                plan[-1],
                keep_raw=keep_raw.value,
                on_month=month_done,
                on_progress=bytes_done,
            )
            _lines = [f"Built **{len(_built)}** month(s)."]
            if refresh_aggregates.value:
                _written = export_aggregates("parquet", on_table=table_done)
                progress.update(subtitle="aggregates written")
                _lines.append(
                    "Aggregates rebuilt: "
                    + ", ".join(f"`{k}`" for k in _written)
                    + ". Re-run §2 to pick them up."
                )
            log.info(
                "built %d month(s); disk %s",
                len(_built),
                {k: round(v) for k, v in disk_usage().items()},
            )
        extraction_result = mo.vstack(
            [
                _panel.render(),
                mo.md("\n\n".join(_lines)).callout(kind="success"),
            ]
        )
    else:
        extraction_result = mo.md(
            f"Press the button to fetch **{len(todo)} missing month(s)**. You can stop "
            "the run at any time. The next run skips each completed month, so it "
            "continues from that point."
        ).callout(kind="neutral")
    extraction_result
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 1 · Helpers

    Three groups: reading, charts, and the derivations that replace hard-coded
    platform and airport lists.
    """)
    return


@app.cell
def _(PATHS, add_ratios):
    def read_table(name: str, base: Path | None = None) -> pl.DataFrame:
        """Load one exported aggregate table.

        Args:
            name: Table name, without extension.
            base: Directory to read from, defaulting to the exports directory.

        Returns:
            The table.

        Raises:
            FileNotFoundError: The extraction has not been run yet.
        """
        path = (base or PATHS.exports) / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run the extraction in §0.10 first.")
        frame = pl.read_parquet(path)
        log.info("loaded %-22s %8d rows x %2d cols", name, frame.height, frame.width)
        return frame

    def read_month(year: int, month: int) -> pl.DataFrame:
        """Load one processed month at trip level, with ratios restored.

        Args:
            year: Four-digit year.
            month: Month, 1-indexed.

        Returns:
            The month's trips.

        Raises:
            FileNotFoundError: The extraction has not been run yet.
        """
        path = PATHS.out_file(year, month)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run the extraction in §0.10 first.")
        frame = add_ratios(pl.scan_parquet(path)).collect()
        log.info("loaded %-22s %8d rows x %2d cols", path.stem, frame.height, frame.width)
        return frame

    def by_year(df: pl.DataFrame, month_col: str = "month") -> pl.DataFrame:
        """Add a calendar-year column derived from a month timestamp.

        Args:
            df: Any frame with a month column.
            month_col: Name of that column.

        Returns:
            The frame with a year column appended.
        """
        return df.with_columns(pl.col(month_col).dt.year().alias("year"))

    def describe(df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
        """Profile numeric columns as one query.

        Args:
            df: Frame to profile.
            cols: Columns to include.

        Returns:
            One row for each column, with the dtype, the null count and three
            quantiles, in the order the caller gave.
        """
        dtypes = {c: str(df.schema[c]) for c in cols}
        order = {c: i for i, c in enumerate(cols)}
        return (
            df.lazy()
            .select(pl.col(c).cast(pl.Float64) for c in cols)
            .unpivot(variable_name="column", value_name="value")
            .group_by("column")
            .agg(
                pl.col("value").null_count().alias("nulls"),
                pl.col("value").min().alias("min"),
                pl.col("value").median().alias("p50"),
                pl.col("value").max().alias("max"),
            )
            .with_columns(
                pl.col("column").replace_strict(dtypes).alias("dtype"),
                (pl.col("nulls") / max(df.height, 1)).alias("null_pct"),
                pl.col("column").replace_strict(order).alias("rank"),
            )
            .sort("rank")
            .select("column", "dtype", "nulls", "null_pct", "min", "p50", "max")
            .collect()
        )

    return by_year, describe, read_month, read_table


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 1.1 A theme, then four chart functions

    Altair applies a registered theme to every chart at render time, so the styling
    belongs there and not in each call. The theme below follows four rules from the
    data-visualisation literature.

    - **Raise the data-to-ink ratio.** No border around the plot area, no tick marks,
      no vertical gridlines, and a faint horizontal grid.
    - **Keep the text horizontal.** No rotated tick label, and the y-axis title sits
      above the axis instead of on its side.
    - **Use a colourblind-safe palette.** The categories use the Okabe-Ito set, which
      holds its contrast under the three common types of colour blindness.
    - **Follow the page.** The text, the gridlines and the palette come from the
      display mode. The selector above sets it. marimo reports light to Python for
      the system display setting, so a dark page needs the selector.
    - **Give the chart an action title.** The title states the finding and the
      subtitle carries the qualification.

    The five functions below then carry the data, the axis titles and the units. Each
    one pins the colour domain to the platforms in the data. One platform therefore
    keeps one colour in every chart. A new entrant takes the next free colour, and no
    other platform changes.
    """)
    return


@app.cell
def _():
    chart_theme = mo.ui.dropdown(
        options=["Match marimo", "Light", "Dark"],
        value="Match marimo",
        label="Chart colours",
    )
    mo.vstack(
        [
            chart_theme,
            mo.md(
                "The browser does not tell the kernel which mode it chose. marimo "
                "therefore reports **light** to Python for the **system** display "
                "setting. On a dark page that gives dark text on a dark background. Set "
                "this control to **Dark** for a dark page."
            ).callout(kind="neutral"),
        ]
    )
    return (chart_theme,)


@app.cell
def _(GLOSSARY, chart_theme):
    CHART_WIDTH = 680
    CHART_HEIGHT = 300
    FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"
    LIGHT = {
        "ink": "#1b1b1b",
        "muted": "#5f5f5f",
        "grid": "#e6e6e6",
        "faded": "#d6d6d6",
        "lead": "#e4f1e9",
        "behind": "#fdeee4",
        "worst": "#fadfd2",
        "focus": "#eef2f7",
        "palette": [
            "#0072B2",
            "#D55E00",
            "#009E73",
            "#CC79A7",
            "#E69F00",
            "#56B4E9",
            "#7F7F7F",
            "#8B5E00",
        ],
    }
    DARK = {
        "ink": "#ececec",
        "muted": "#a6a6a6",
        "grid": "#3a3a3a",
        "faded": "#4f4f4f",
        "lead": "#16301f",
        "behind": "#33241a",
        "worst": "#452c1d",
        "focus": "#1f242b",
        "palette": [
            "#56B4E9",
            "#E69F00",
            "#00C58F",
            "#F49AC2",
            "#D8D174",
            "#B4A7F5",
            "#B0B0B0",
            "#FF8C61",
        ],
    }

    def display_mode(choice: str) -> str:
        """Decide which set of colours the charts use.

        Args:
            choice: The value of the selector above.

        Returns:
            Either light or dark.
        """
        if choice in ("Light", "Dark"):
            return choice.lower()
        return mo.app_meta().theme

    SKIN = DARK if display_mode(chart_theme.value) == "dark" else LIGHT
    INK = SKIN["ink"]
    MUTED = SKIN["muted"]
    GRID = SKIN["grid"]
    FADED = SKIN["faded"]
    PALETTE = SKIN["palette"]
    ROW_TINTS = {key: SKIN[key] for key in ("lead", "behind", "worst", "focus")}

    @alt.theme.register("airport_minimal", enable=True)
    def airport_minimal() -> alt.theme.ThemeConfig:
        """Register the house style and make it the active theme.

        The colours follow the display mode that marimo reports, so the text and
        the gridlines keep their contrast against a light or a dark page.

        Returns:
            The theme configuration that Altair merges into every chart.
        """
        return {
            "background": "transparent",
            "config": {
                "font": FONT,
                "view": {"strokeWidth": 0, "continuousWidth": CHART_WIDTH},
                "axis": {
                    "labelColor": MUTED,
                    "labelFontSize": 11,
                    "titleColor": INK,
                    "titleFontSize": 12,
                    "titleFontWeight": 500,
                    "domainColor": FADED,
                    "tickColor": FADED,
                    "tickSize": 0,
                    "labelPadding": 8,
                    "gridColor": GRID,
                    "gridDash": [2, 3],
                },
                "axisX": {"grid": False, "labelAngle": 0, "domain": True},
                "axisY": {
                    "grid": True,
                    "domain": False,
                    "titleAngle": 0,
                    "titleAlign": "left",
                    "titleAnchor": "start",
                    "titleY": -14,
                    "titleX": 0,
                },
                "legend": {
                    "orient": "bottom",
                    "direction": "horizontal",
                    "labelColor": INK,
                    "labelFontSize": 11,
                    "titleColor": MUTED,
                    "titleFontSize": 11,
                    "titleFontWeight": 400,
                    "symbolType": "circle",
                    "symbolSize": 90,
                    "offset": 6,
                    "padding": 0,
                },
                "title": {
                    "anchor": "start",
                    "color": INK,
                    "fontSize": 15,
                    "fontWeight": 600,
                    "subtitleColor": MUTED,
                    "subtitleFontSize": 12,
                    "subtitlePadding": 6,
                    "offset": 14,
                },
                "range": {"category": PALETTE},
                "line": {"strokeWidth": 2.5, "strokeCap": "round"},
                "point": {"filled": True, "size": 45},
                "bar": {"cornerRadiusEnd": 2},
                "rect": {"stroke": None},
            },
        }

    def titled(text: str, subtitle: str | None = None) -> alt.TitleParams:
        """Build an action title with an optional qualification below it.

        Args:
            text: The finding, as a short sentence.
            subtitle: The caveat or the unit.

        Returns:
            The title parameters.
        """
        return alt.TitleParams(text, subtitle=[subtitle] if subtitle else [])

    MONTH_ORDER = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    # marimo writes each key into the style attribute as given, so the keys have
    # to be CSS names. A camelCase key is invalid CSS and the browser drops it.
    CARD_STYLE = {
        "border": "1px solid rgba(128, 128, 128, 0.28)",
        "border-radius": "10px",
        "padding": "0.85rem 1rem",
        "background": "rgba(128, 128, 128, 0.06)",
        "min-width": "9rem",
    }

    def stat_card(value: str, label: str, note: str = "") -> mo.Html:
        """Build one figure with a caption under it.

        Args:
            value: The number, already formatted.
            label: What the number counts.
            note: An optional second line.

        Returns:
            The card.
        """
        lines = [
            f"<div style='font-size:1.6rem;font-weight:650;line-height:1.1'>{value}</div>",
            f"<div style='opacity:0.75;font-size:0.82rem;margin-top:0.25rem'>{label}</div>",
        ]
        if note:
            lines.append(f"<div style='opacity:0.55;font-size:0.75rem'>{note}</div>")
        return mo.md("".join(lines)).style(CARD_STYLE)

    def stat_row(cards: list[mo.Html]) -> mo.Html:
        """Lay a set of cards across the page.

        Args:
            cards: The cards, in reading order.

        Returns:
            The row, which wraps on a narrow page.
        """
        return mo.hstack(cards, widths="equal", gap=0.75, wrap=True, align="stretch")

    def link_list(items: list[tuple[str, str, str]]) -> mo.Html:
        """Build a list of links, each with a line that says what it is for.

        Args:
            items: Label, URL and description for each entry.

        Returns:
            The list.
        """
        rows = [
            f"<li style='margin:0 0 0.55rem 0'>"
            f"<a href='{url}' target='_blank' rel='noopener'>{label}</a>"
            f"<div style='opacity:0.7;font-size:0.85rem'>{note}</div></li>"
            for label, url, note in items
        ]
        return mo.md(
            "<ul style='list-style:none;padding-left:0;margin:0'>" + "".join(rows) + "</ul>"
        )

    def heading_anchor(heading: str) -> str:
        """Ask marimo for the id it gives a heading.

        Reading the id back from the rendered markdown keeps the link and the
        heading in step. A hand-written slug goes stale after an edit to a
        heading.

        Args:
            heading: The heading text, without the leading hashes.

        Returns:
            The id. A render without an id gives an empty string.
        """
        match = re.search(r'id="([^"]+)"', mo.md(f"## {heading}").text)
        return match.group(1) if match else ""

    def gloss(text: str) -> str:
        """Wrap the first use of each glossary term so it explains itself.

        A reader who hovers over the term reads the expansion. Code spans, HTML
        tags and links are left alone.

        Args:
            text: Markdown text.

        Returns:
            The text with an abbr element around the first use of each term.
        """
        parts = re.split(r"(`[^`]*`|<[^>]+>|https?://\S+)", text)
        for index in range(0, len(parts), 2):
            for term, expansion, _ in GLOSSARY:
                parts[index] = re.sub(
                    rf"\b{re.escape(term)}\b",
                    f'<abbr title="{expansion}">{term}</abbr>',
                    parts[index],
                    count=1,
                )
        return "".join(parts)

    def glossary_list(items: list[tuple[str, str, str]]) -> mo.Html:
        """Build the glossary, with the expansion on hover and in the text.

        Args:
            items: Term, expansion and note for each entry.

        Returns:
            The list.
        """
        rows = [
            "<li style='margin:0 0 0.7rem 0'>"
            f"<abbr title='{expansion}' "
            "style='font-weight:600;text-decoration:none'>"
            f"{term}</abbr>"
            f"<div style='opacity:0.85'>{expansion}</div>"
            f"<div style='opacity:0.6;font-size:0.85rem'>{note}</div></li>"
            for term, expansion, note in items
        ]
        return mo.md(
            "<ul style='list-style:none;padding-left:0;margin:0'>" + "".join(rows) + "</ul>"
        )

    def contents_list(items: list[tuple[str, str, str]]) -> mo.Html:
        """Build a numbered index that links to each section.

        Args:
            items: Number, title and heading text for each section.

        Returns:
            The index.
        """
        # The anchor carries no style attribute. marimo replaces an in-page anchor
        # with a React link and spreads the raw attributes, so a style string
        # reaches React as a string and raises React error #62.
        rows = [
            f"<li style='margin:0 0 0.4rem 0;display:flex;gap:0.7rem'>"
            f"<span style='opacity:0.55;min-width:2.4rem'>{number}</span>"
            f"<a href='#{heading_anchor(heading)}'>{title}</a></li>"
            for number, title, heading in items
        ]
        return mo.md(
            "<ul style='list-style:none;padding-left:0;margin:0'>" + "".join(rows) + "</ul>"
        )

    def marked_table(
        df: pl.DataFrame,
        mark: "Callable[[int, str], str]",
        *,
        justify: dict[str, str] | None = None,
        bold_columns: tuple[str, ...] = (),
    ) -> mo.ui.table:
        """Render a table whose cells carry a tint that the data decides.

        Args:
            df: The frame to show, already formatted for display.
            mark: Takes the row index and the column name, and gives a key from
                ROW_TINTS or an empty string.
            justify: Column name to one of left, center or right.
            bold_columns: Columns to set in a heavier weight.

        Returns:
            The table.
        """

        def style_cell(row_id: str, column_name: str, value: object) -> dict[str, str]:
            """Build the CSS for one cell.

            Args:
                row_id: Row index, as text.
                column_name: Column name.
                value: The cell value.

            Returns:
                The CSS declarations.
            """
            del value
            style: dict[str, str] = {}
            key = mark(int(row_id), column_name)
            if key:
                style["backgroundColor"] = ROW_TINTS[key]
            if key in ("lead", "worst") or column_name in bold_columns:
                style["fontWeight"] = "600"
            return style

        return mo.ui.table(
            df,
            selection=None,
            pagination=False,
            show_column_summaries=False,
            show_data_types=False,
            show_download=False,
            show_search=False,
            style_cell=style_cell,
            text_justify_columns=justify or {},
        )

    def x_encoding(field: str, kind: str, title: str) -> alt.X:
        """Build an x encoding with readable ticks for the given field type.

        Args:
            field: Column name.
            kind: One of "month", "year" or "hour".
            title: Axis title, written out in words.

        Returns:
            The encoding.

        Raises:
            ValueError: The kind is not recognised.
        """
        if kind == "month":
            return alt.X(
                "month:T",
                title=title,
                axis=alt.Axis(format="%Y", tickCount="year", labelOverlap="greedy"),
            )
        if kind == "year":
            return alt.X(f"{field}:O", title=title)
        if kind == "hour":
            return alt.X(f"{field}:O", title=title, axis=alt.Axis(values=list(range(0, 24, 2))))
        if kind == "calendar":
            return alt.X(f"{field}:O", title=title, sort=MONTH_ORDER)
        raise ValueError(f"unknown x kind {kind!r}")

    def colour(field: str, domain: list[str], title: str) -> alt.Color:
        """Build a colour encoding with a pinned domain and a top legend.

        Args:
            field: Column name.
            domain: Category values, in legend order.
            title: Legend title.

        Returns:
            The encoding.
        """
        return alt.Color(
            f"{field}:N",
            title=title,
            scale=alt.Scale(domain=domain, range=PALETTE[: max(len(domain), 1)]),
            legend=alt.Legend(columns=4),
        )

    def line_chart(
        df: pl.DataFrame,
        *,
        x: str,
        x_kind: str,
        y: str,
        title: str,
        x_title: str,
        y_title: str,
        colour_by: str | None = None,
        domain: list[str] | None = None,
        colour_title: str = "Platform",
        subtitle: str | None = None,
        y_format: str | None = None,
        zero: bool = False,
        height: int = CHART_HEIGHT,
    ) -> alt.Chart:
        """Draw a line chart with points and fully labelled axes.

        Args:
            df: Data to plot.
            x: X column.
            x_kind: One of "month", "year" or "hour".
            y: Y column.
            title: Chart title.
            x_title: X axis title.
            y_title: Y axis title, including units.
            colour_by: Column to colour series by, or None for a single series.
            domain: Category values for the colour scale.
            colour_title: Legend title.
            subtitle: A qualification that sits below the title.
            y_format: D3 format string for the y axis, such as ".0%".
            zero: Force the y axis to include zero.
            height: Plot height in pixels.

        Returns:
            The chart.
        """
        encodings: dict[str, object] = {
            "x": x_encoding(x, x_kind, x_title),
            "y": alt.Y(
                f"{y}:Q",
                title=y_title,
                axis=alt.Axis(format=y_format) if y_format else alt.Axis(),
                scale=alt.Scale(zero=zero),
            ),
        }
        if colour_by:
            encodings["color"] = colour(colour_by, domain or [], colour_title)
        return (
            alt.Chart(df)
            .mark_line(point=alt.OverlayMarkDef(size=45), strokeWidth=2.5)
            .encode(**encodings)
            .properties(width=CHART_WIDTH, height=height, title=titled(title, subtitle))
        )

    def area_chart(
        df: pl.DataFrame,
        *,
        y: str,
        title: str,
        x_title: str,
        y_title: str,
        colour_by: str,
        domain: list[str],
        subtitle: str | None = None,
        y_format: str | None = None,
        stack: str | bool = True,
        height: int = CHART_HEIGHT,
    ) -> alt.Chart:
        """Draw a stacked area chart over months.

        Args:
            df: Data to plot, with a month column.
            y: Y column.
            title: Chart title.
            x_title: X axis title.
            y_title: Y axis title, including units.
            colour_by: Column to stack and colour by.
            domain: Category values for the colour scale.
            subtitle: A qualification that sits below the title.
            y_format: D3 format string for the y axis.
            stack: Altair stack mode, such as "normalize".
            height: Plot height in pixels.

        Returns:
            The chart.
        """
        return (
            alt.Chart(df)
            .mark_area(opacity=0.9)
            .encode(
                x=x_encoding("month", "month", x_title),
                y=alt.Y(
                    f"{y}:Q",
                    title=y_title,
                    stack=stack,
                    axis=alt.Axis(format=y_format) if y_format else alt.Axis(),
                ),
                color=colour(colour_by, domain, "Platform"),
            )
            .properties(width=CHART_WIDTH, height=height, title=titled(title, subtitle))
        )

    def heat_chart(
        df: pl.DataFrame,
        *,
        x: str,
        y: str,
        value: str,
        title: str,
        x_title: str,
        y_title: str,
        legend_title: str,
        value_format: str = ".1%",
        height: int = 160,
    ) -> alt.Chart:
        """Draw a heatmap of one measure across two categorical axes.

        Args:
            df: Data to plot.
            x: X column, treated as hours.
            y: Y column.
            value: Measure driving the colour.
            title: Chart title.
            x_title: X axis title.
            y_title: Y axis title.
            legend_title: Colour legend title.
            value_format: D3 format for the legend labels.
            height: Plot height in pixels.

        Returns:
            The chart.
        """
        return (
            alt.Chart(df)
            .mark_rect()
            .encode(
                x=x_encoding(x, "hour", x_title),
                y=alt.Y(f"{y}:N", title=y_title),
                color=alt.Color(
                    f"{value}:Q",
                    title=legend_title,
                    scale=alt.Scale(scheme="viridis" if SKIN is LIGHT else "cividis"),
                    legend=alt.Legend(
                        orient="bottom",
                        direction="horizontal",
                        format=value_format,
                        gradientLength=CHART_WIDTH / 2,
                    ),
                ),
                tooltip=[f"{y}:N", f"{x}:O", alt.Tooltip(f"{value}:Q", format=value_format)],
            )
            .properties(width=CHART_WIDTH, height=height, title=titled(title))
        )

    def brush_chart(
        df: pl.DataFrame,
        *,
        x: str,
        y: str,
        colour_by: str,
        domain: list[str],
        bar_value: str,
        bar_group: str,
        title: str,
        subtitle: str,
        x_title: str,
        y_title: str,
        bar_title: str,
        bar_y_title: str,
        x_format: str | None = None,
        y_format: str | None = None,
        bar_format: str | None = None,
    ) -> alt.VConcatChart:
        """Draw a scatter plot that filters a bar chart below it.

        Drag a rectangle on the points. The bars then total only the points inside
        it, and the points outside it turn grey.

        Args:
            df: One row for each point.
            x: X column.
            y: Y column.
            colour_by: Column that colours the points.
            domain: Category values for the colour scale.
            bar_value: Column the bars sum.
            bar_group: Column the bars group by.
            title: Action title.
            subtitle: Qualification below the title.
            x_title: X axis title.
            y_title: Y axis title.
            bar_title: X axis title of the bar chart.
            bar_y_title: Y axis title of the bar chart.
            x_format: D3 format for the x axis.
            y_format: D3 format for the y axis.
            bar_format: D3 format for the bar axis.

        Returns:
            The scatter plot above the bar chart, linked by the selection.
        """
        brush = alt.selection_interval(encodings=["x", "y"])
        shared = colour(colour_by, domain, colour_by.title())
        points = (
            alt.Chart(df)
            .mark_circle(size=70, opacity=0.75)
            .encode(
                x=alt.X(
                    f"{x}:Q",
                    title=x_title,
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(format=x_format) if x_format else alt.Axis(),
                ),
                y=alt.Y(
                    f"{y}:Q",
                    title=y_title,
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(format=y_format) if y_format else alt.Axis(),
                ),
                color=alt.when(brush).then(shared).otherwise(alt.value(FADED)),
                tooltip=[
                    alt.Tooltip(f"{colour_by}:N", title=colour_by.title()),
                    alt.Tooltip(f"{bar_group}:N", title=bar_group.title()),
                    alt.Tooltip(f"{x}:Q", title=x_title, format=x_format or ",.2f"),
                    alt.Tooltip(f"{y}:Q", title=y_title, format=y_format or ",.2f"),
                ],
            )
            .add_params(brush)
            .properties(width=CHART_WIDTH, height=320, title=titled(title, subtitle))
        )
        bars = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X(
                    f"sum({bar_value}):Q",
                    title=bar_title,
                    axis=alt.Axis(format=bar_format) if bar_format else alt.Axis(),
                ),
                y=alt.Y(f"{bar_group}:N", title=bar_y_title, sort="-x"),
                color=shared,
                tooltip=[
                    alt.Tooltip(f"{bar_group}:N", title=bar_group.title()),
                    alt.Tooltip(f"sum({bar_value}):Q", title=bar_title, format=","),
                ],
            )
            .transform_filter(brush)
            .properties(width=CHART_WIDTH, height=140)
        )
        return alt.vconcat(points, bars, spacing=24)

    def frame_chart(
        context: pl.DataFrame,
        trail: pl.DataFrame,
        current: pl.DataFrame,
        *,
        x: str,
        y: str,
        colour_by: str,
        domain: list[str],
        x_domain: tuple[float, float],
        y_domain: tuple[float, float],
        title: str,
        subtitle: str,
        x_title: str,
        y_title: str,
        x_format: str | None = None,
        y_format: str | None = None,
    ) -> alt.LayerChart:
        """Draw one frame of an animation over three layers.

        The scales take fixed bounds. A frame that computes its own bounds makes
        the axes jump between frames, which reads as movement in the data.

        Args:
            context: Every point, drawn faint.
            trail: The recent points, drawn with a fading opacity column.
            current: The points for the frame itself.
            x: X column.
            y: Y column.
            colour_by: Column that colours the points.
            domain: Category values for the colour scale.
            x_domain: Fixed lowest and highest x.
            y_domain: Fixed lowest and highest y.
            title: Action title.
            subtitle: Qualification below the title, such as the month.
            x_title: X axis title.
            y_title: Y axis title.
            x_format: D3 format for the x axis.
            y_format: D3 format for the y axis.

        Returns:
            The three layers, in one chart.
        """
        shared = colour(colour_by, domain, colour_by.title())
        position = {
            "x": alt.X(
                f"{x}:Q",
                title=x_title,
                scale=alt.Scale(domain=list(x_domain), nice=False),
                axis=alt.Axis(format=x_format) if x_format else alt.Axis(),
            ),
            "y": alt.Y(
                f"{y}:Q",
                title=y_title,
                scale=alt.Scale(domain=list(y_domain), nice=False),
                axis=alt.Axis(format=y_format) if y_format else alt.Axis(),
            ),
        }
        back = alt.Chart(context).mark_circle(size=22, opacity=0.14, color=FADED).encode(**position)
        fading = (
            alt.Chart(trail)
            .mark_circle(size=45)
            .encode(
                **position,
                color=shared,
                opacity=alt.Opacity("weight:Q", scale=alt.Scale(range=[0.08, 0.6]), legend=None),
            )
        )
        head = (
            alt.Chart(current)
            .mark_point(size=190, filled=True, opacity=0.95, stroke="white", strokeWidth=1)
            .encode(
                **position,
                color=shared,
                tooltip=[
                    alt.Tooltip(f"{colour_by}:N", title=colour_by.title()),
                    alt.Tooltip("platform:N", title="Platform"),
                    alt.Tooltip(f"{x}:Q", title=x_title, format=x_format or ",.2f"),
                    alt.Tooltip(f"{y}:Q", title=y_title, format=y_format or ",.2f"),
                ],
            )
        )
        return (
            alt.layer(back, fading, head)
            .properties(width=CHART_WIDTH, height=340, title=titled(title, subtitle))
            .resolve_scale(color="shared", opacity="independent")
        )

    def span_chart(
        df: pl.DataFrame,
        *,
        title: str,
        x_title: str,
        y_title: str,
        domain: list[str],
        height: int = 200,
    ) -> alt.Chart:
        """Draw one horizontal bar per platform, from first month to last.

        Args:
            df: Frame with platform, first_month and last_month columns.
            title: Chart title.
            x_title: X axis title.
            y_title: Y axis title.
            domain: Platform values for the colour scale.
            height: Plot height in pixels.

        Returns:
            The chart.
        """
        return (
            alt.Chart(df)
            .mark_bar(height=16, cornerRadius=3)
            .encode(
                x=alt.X(
                    "first_month:T",
                    title=x_title,
                    axis=alt.Axis(format="%Y", labelAngle=0, tickCount="year"),
                ),
                x2="last_month:T",
                y=alt.Y("platform:N", title=y_title, sort=domain),
                color=colour("platform", domain, "Platform"),
                tooltip=["platform:N", "first_month:T", "last_month:T", "trips:Q"],
            )
            .properties(width=CHART_WIDTH, height=height, title=titled(title))
        )

    return (
        CHART_WIDTH,
        FADED,
        ROW_TINTS,
        MONTH_ORDER,
        PALETTE,
        area_chart,
        brush_chart,
        colour,
        frame_chart,
        heat_chart,
        contents_list,
        gloss,
        glossary_list,
        heading_anchor,
        link_list,
        marked_table,
        line_chart,
        span_chart,
        stat_card,
        stat_row,
        titled,
        x_encoding,
    )


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 1.2 Derivations instead of constants

    Two questions have to be settled before any comparison starts: which platforms
    are worth comparing, and which airports have a supply market at all.

    Both answers move. Juno and Via each held a real share in 2019 and neither trades
    now. Newark sits in New Jersey. A New York licence can set down there but cannot
    collect a dispatched fare, so its pickup rate sits near zero.

    These four functions read both answers from the data:

    - the platforms above a share threshold in the trailing year
    - the airports above a pickup-to-dropoff ratio
    - the lifetime record of every licensee
    - the share leader in each airport-year
    """)
    return


@app.cell
def _(
    ACTIVE_WINDOW_MONTHS,
    MIN_DISPATCH_RATIO,
    MIN_PLATFORM_SHARE,
    NON_MARKET_DIRECTIONS,
    RECENT_WINDOW_MONTHS,
):
    def platform_census(coverage: pl.DataFrame) -> pl.DataFrame:
        """Summarise every platform that ever appears in the archive.

        Args:
            coverage: The coverage_timeline table, which holds every licensee.

        Returns:
            One row per platform with lifetime trips, share, and first and last
            month, sorted by size.
        """
        return (
            coverage.lazy()
            .group_by("platform")
            .agg(
                pl.col("trips").sum().alias("trips"),
                pl.col("month").min().alias("first_month"),
                pl.col("month").max().alias("last_month"),
                pl.col("month").n_unique().alias("months_active"),
            )
            .with_columns((pl.col("trips") / pl.col("trips").sum()).alias("lifetime_share"))
            .sort("trips", descending=True)
            .collect()
        )

    def active_platforms(
        coverage: pl.DataFrame,
        window: int = ACTIVE_WINDOW_MONTHS,
        min_share: float = MIN_PLATFORM_SHARE,
    ) -> list[str]:
        """Find the platforms trading meaningfully in the recent window.

        Args:
            coverage: The coverage_timeline table, which holds every licensee.
            window: How many trailing months to consider.
            min_share: Minimum share of window trips to count as active.

        Returns:
            Platform names, largest first.
        """
        cutoff = pl.select(pl.lit(coverage["month"].max()).dt.offset_by(f"-{window}mo")).item()
        recent = coverage.lazy().filter(pl.col("month") > cutoff)
        if recent.select(pl.len()).collect().item() == 0:
            recent = coverage.lazy()
        return (
            recent.group_by("platform")
            .agg(pl.col("trips").sum().alias("trips"))
            .with_columns((pl.col("trips") / pl.col("trips").sum()).alias("share"))
            .filter(pl.col("share") >= min_share)
            .sort("trips", descending=True)
            .collect()["platform"]
            .to_list()
        )

    def dispatch_airports(kpis: pl.DataFrame, min_ratio: float = MIN_DISPATCH_RATIO) -> list[str]:
        """Find the airports that actually take dispatched pickups.

        Args:
            kpis: The monthly_kpis table.
            min_ratio: Lowest pickups-to-dropoffs ratio that qualifies.

        Returns:
            Airport codes, alphabetically.
        """
        return (
            kpis.filter(~pl.col("direction").is_in(NON_MARKET_DIRECTIONS))
            .group_by("airport", "direction")
            .agg(pl.col("trips").sum().alias("trips"))
            .pivot(on="direction", index="airport", values="trips")
            .fill_null(0)
            .with_columns((pl.col("pickup") / pl.col("dropoff").replace(0, None)).alias("ratio"))
            .filter(pl.col("ratio") >= min_ratio)
            .sort("airport")
            .get_column("airport")
            .to_list()
        )

    METRICS = (
        ("trips", "Airport pickups", "count", "high"),
        ("med_fare", "Median rider fare", "money", ""),
        ("med_driver_gross", "Median driver gross", "money", "high"),
        ("med_driver_share", "Driver gross / rider payment", "percent", "high"),
        ("med_gross_per_engaged_hour", "Driver gross per engaged hour", "money", "high"),
        ("med_fare_per_mile", "Rider fare per mile", "money", ""),
        ("med_miles", "Median trip distance (miles)", "number", ""),
        ("med_engaged_s", "Median engaged time (minutes)", "minutes", ""),
        ("med_curb_wait_s", "Median curb wait (seconds)", "number", "low"),
        ("mean_tip", "Mean tip", "money", "high"),
        ("incentive_rate", "Minimum-pay binding rate", "percent", ""),
        ("pool_request_rate", "Shared-ride request rate", "percent", ""),
    )

    def compare_platforms(
        kpis: pl.DataFrame,
        platforms: list[str],
        airports: list[str],
        window: int | None = RECENT_WINDOW_MONTHS,
    ) -> pl.DataFrame:
        """Compare any number of platforms on the same measurements.

        Args:
            kpis: The monthly_kpis table.
            platforms: Platform names to report, in column order.
            airports: Airports to report.
            window: Trailing months to include, or None for the whole archive.

        Returns:
            One row for each airport and measurement, with a column for each
            platform. Two platforms also give a difference column.

        Raises:
            ValueError: The caller gave no platform.
        """
        if not platforms:
            raise ValueError("need at least one platform")
        in_window = (
            pl.col("month")
            > pl.select(pl.lit(kpis["month"].max()).dt.offset_by(f"-{window}mo")).item()
            if window is not None
            else pl.lit(True)
        )
        wide = (
            kpis.lazy()
            .filter(
                (pl.col("direction") == "pickup")
                & pl.col("platform").is_in(platforms)
                & pl.col("airport").is_in(airports)
                & in_window
            )
            .group_by("airport", "platform")
            .agg(
                pl.col("trips").sum().alias("trips"),
                *[
                    pl.col(column).median().alias(column)
                    for column, _, _, _ in METRICS
                    if column != "trips"
                ],
            )
            .unpivot(
                index=["airport", "platform"],
                on=[column for column, _, _, _ in METRICS],
                variable_name="metric",
                value_name="value",
            )
            .collect()
            .pivot(on="platform", index=["airport", "metric"], values="value")
        )
        for name in platforms:
            if name not in wide.columns:
                wide = wide.with_columns(pl.lit(None, dtype=pl.Float64).alias(name))
        order = {column: i for i, (column, _, _, _) in enumerate(METRICS)}
        labels = {column: label for column, label, _, _ in METRICS}
        kinds = {column: kind for column, _, kind, _ in METRICS}
        better = {column: side for column, _, _, side in METRICS}
        wide = wide.with_columns(
            pl.col("metric").replace_strict(order).alias("_order"),
            pl.col("metric").replace_strict(kinds).alias("kind"),
            pl.col("metric").replace_strict(labels).alias("label"),
            pl.col("metric").replace_strict(better).alias("better"),
        )
        if len(platforms) == 2:
            wide = wide.with_columns(
                (pl.col(platforms[1]) - pl.col(platforms[0])).alias("difference")
            )
        return wide.sort("airport", "_order").drop("_order")

    def benchmark(comparison: pl.DataFrame, platforms: list[str]) -> pl.DataFrame:
        """Find the best value for each measurement and name the platform that holds it.

        A measurement with no better side, such as the median fare, gives no
        target: a higher fare is neither a win nor a loss without more context.

        Args:
            comparison: Output of compare_platforms.
            platforms: The platform columns to search.

        Returns:
            The comparison with a target column and the platform that sets it.
        """
        best_high = pl.max_horizontal([pl.col(name) for name in platforms])
        best_low = pl.min_horizontal([pl.col(name) for name in platforms])
        target = (
            pl.when(pl.col("better") == "high")
            .then(best_high)
            .when(pl.col("better") == "low")
            .then(best_low)
            .otherwise(None)
        )
        holder = pl.lit(None, dtype=pl.String)
        for name in platforms:
            holder = pl.when(pl.col("target") == pl.col(name)).then(pl.lit(name)).otherwise(holder)
        return comparison.with_columns(target.alias("target")).with_columns(
            holder.alias("target_platform")
        )

    def format_metric(value: float | None, kind: str) -> str:
        """Format one measurement for display.

        Args:
            value: The number, or None.
            kind: One of count, money, percent, minutes or number.

        Returns:
            The formatted text. A missing value gives a short note.
        """
        if value is None:
            return "not reported"
        if kind == "count":
            return f"{value:,.0f}"
        if kind == "money":
            return f"${value:,.2f}"
        if kind == "percent":
            return f"{value:.1%}"
        if kind == "minutes":
            return f"{value / 60:.1f}"
        return f"{value:,.1f}"

    def format_difference(value: float | None, kind: str) -> str:
        """Format a difference between two platforms, with an explicit sign.

        A percent measurement gives percentage points, because the difference
        between two shares is not itself a share.

        Args:
            value: The difference, or None.
            kind: One of count, money, percent, minutes or number.

        Returns:
            The formatted text.
        """
        if value is None:
            return "not comparable"
        sign = "+" if value > 0 else "-"
        size = abs(value)
        if kind == "percent":
            return f"{sign}{size * 100:.1f} pp"
        if kind == "money":
            return f"{sign}${size:,.2f}"
        return f"{sign}{format_metric(size, kind)}"

    def leadership(share_year: pl.DataFrame) -> pl.DataFrame:
        """Identify the share leader in each airport-year and flag handovers.

        Args:
            share_year: Yearly share per airport and platform.

        Returns:
            One row per airport and year with the leader, its share, the runner-up
            gap, and whether leadership changed hands that year.
        """
        return (
            share_year.lazy()
            .sort(["airport", "year", "share"], descending=[False, False, True])
            .group_by("airport", "year", maintain_order=True)
            .agg(
                pl.col("platform").first().alias("leader"),
                pl.col("share").first().alias("leader_share"),
                pl.col("share").slice(1, 1).first().alias("runner_up_share"),
            )
            .sort("airport", "year")
            .with_columns(
                (pl.col("leader_share") - pl.col("runner_up_share").fill_null(0.0)).alias("gap"),
                (pl.col("leader") != pl.col("leader").shift(1).over("airport"))
                .fill_null(False)
                .alias("changed_hands"),
            )
            .collect()
        )

    return (
        active_platforms,
        dispatch_airports,
        benchmark,
        compare_platforms,
        format_difference,
        format_metric,
        leadership,
        platform_census,
    )


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 2 · Loading

    The notebook loads two things. The first is one **raw month** at trip level. It
    shows the effect of uncleaned data on an answer. The second is the six
    **aggregate** tables for the full 89-month history and for every licensee.

    `read_month` sends the raw month through `add_ratios`. The stored file holds no
    `driver_share`, no `fare_per_mile` and no `driver_gross_per_engaged_hour`, because
    `slim_for_storage` removes them. Section 3 reads all three.
    """)
    return


@app.cell
def _(AGGREGATE_TABLES, SAMPLE_MONTH, read_month, read_table):
    tables = {name: read_table(name) for name in AGGREGATE_TABLES}
    kpis, share, hourly = tables["monthly_kpis"], tables["market_share"], tables["hourly_profile"]
    incentive, coverage, quality = (
        tables["incentive_breakdown"],
        tables["coverage_timeline"],
        tables["data_quality"],
    )

    raw = read_month(*SAMPLE_MONTH)
    log.info("raw month spans %s to %s", raw["pickup_datetime"].min(), raw["pickup_datetime"].max())
    return coverage, hourly, incentive, kpis, quality, raw, share, tables


@app.cell(hide_code=True)
def _(census, kpis, live_platforms, pickup_airports, share, stat_card, stat_row, tables):
    mo.vstack(
        [
            stat_row(
                [
                    stat_card(f"{share['trips'].sum() / 1e6:,.1f}M", "Airport trips"),
                    stat_card(
                        f"{share['month'].n_unique()}",
                        "Months",
                        f"{share['month'].min():%b %Y} to {share['month'].max():%b %Y}",
                    ),
                    stat_card(
                        f"{kpis['airport'].n_unique()}",
                        "Airports",
                        f"{', '.join(pickup_airports)} take dispatched pickups",
                    ),
                    stat_card(
                        f"{census.height}",
                        "Licensees",
                        f"{len(live_platforms)} trading now",
                    ),
                    stat_card(
                        f"{sum(t.height for t in tables.values()):,}",
                        "Aggregate rows",
                        f"across {len(tables)} tables",
                    ),
                ]
            ),
            mo.ui.table(
                pl.DataFrame(
                    {
                        "table": list(tables),
                        "rows": [t.height for t in tables.values()],
                        "cols": [t.width for t in tables.values()],
                    }
                ),
                selection=None,
                pagination=False,
                show_column_summaries=False,
                show_data_types=False,
                show_download=False,
                show_search=False,
            ),
        ],
        gap=0.9,
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 3 · Analysis of the loaded data

    Deliberately *before* cleaning. Every number in this section is wrong in some way,
    and section 5 recomputes each one to show by how much.
    """)
    return


@app.cell(hide_code=True)
def _(describe, raw):
    _cols = [
        "base_passenger_fare",
        "driver_pay",
        "tips",
        "trip_miles",
        "secs_engaged",
        "secs_request_to_scene",
        "secs_scene_to_pickup",
        "driver_share",
        "driver_gross_per_engaged_hour",
    ]
    mo.vstack(
        [
            mo.md("**Numeric profile of the raw month**"),
            mo.ui.table(describe(raw, _cols), selection=None, pagination=False),
        ]
    )
    return


@app.cell
def _(raw):
    naive = (
        raw.group_by("airport", "platform")
        .agg(
            pl.len().alias("trips"),
            pl.col("driver_share").median().alias("med_driver_share"),
            pl.col("driver_gross_per_engaged_hour").median().alias("med_gross_per_hr"),
            pl.col("secs_scene_to_pickup").median().alias("med_curb_wait_s"),
        )
        .sort("airport", "platform")
    )
    log.info(
        "naive grouping produced %d rows across %d airports",
        naive.height,
        naive["airport"].n_unique(),
    )
    return (naive,)


@app.cell(hide_code=True)
def _(naive):
    mo.ui.table(naive, selection=None, pagination=False)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    Four problems are already visible, and none of them announce themselves:

    - **Newark rows exist for both directions** even though NYC-licensed pickups
      there are essentially impossible.
    - **Curb wait is reported for platforms that do not report it**, on a handful of
      rows, because the median silently skips nulls rather than refusing to answer.
    - **Airport-to-airport transfers are counted twice**, once under each airport.
    - **Wound-down licensees sit alongside live ones**, so any share denominator
      mixes a live market with a historical one.

    The next cell shows the third one directly.
    """)
    return


@app.cell(hide_code=True)
def _(raw):
    _dir = (
        raw.group_by("airport", "direction")
        .agg(pl.len().alias("trips"))
        .pivot(on="direction", index="airport", values="trips")
        .sort("airport")
    )
    mo.vstack(
        [
            mo.md("**Trips by direction, uncleaned**"),
            mo.ui.table(_dir, selection=None, pagination=False),
        ]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 4 · Preprocessing
    """)
    return


@app.cell
def _(raw):
    _lazy = raw.lazy()
    invalid_by_platform, on_scene = pl.collect_all(
        [
            _lazy.group_by("platform")
            .agg(pl.len().alias("trips"), (~pl.col("is_valid")).sum().alias("invalid"))
            .with_columns((pl.col("invalid") / pl.col("trips")).alias("invalid_rate"))
            .sort("trips", descending=True),
            _lazy.group_by("platform")
            .agg(pl.len().alias("trips"), pl.col("has_on_scene").mean().alias("coverage"))
            .sort("coverage", descending=True),
        ]
    )
    _invalid = invalid_by_platform["invalid"].sum()
    log.info(
        "dropping %d invalid rows of %d (%.2f%%)",
        _invalid,
        raw.height,
        100 * _invalid / raw.height,
    )
    for _row in on_scene.iter_rows(named=True):
        log.info("on_scene coverage %-8s %.4f", _row["platform"], _row["coverage"])
    return invalid_by_platform, on_scene


@app.cell(hide_code=True)
def _(invalid_by_platform, marked_table):
    invalid_worst = (
        invalid_by_platform["invalid_rate"] == invalid_by_platform["invalid_rate"].max()
    ).to_list()
    mo.vstack(
        [
            mo.md("**4.1 Validity, per platform**"),
            marked_table(
                invalid_by_platform.with_columns(pl.col("invalid_rate").round(4)),
                lambda i, c: ("worst" if invalid_worst[i] else "") if c == "invalid_rate" else "",
                justify={"platform": "left"},
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(COVERAGE_THRESHOLD, marked_table, on_scene):
    coverage_below = (on_scene["coverage"] < COVERAGE_THRESHOLD).to_list()
    mo.vstack(
        [
            mo.md("**4.2 On-scene coverage, per platform**"),
            marked_table(
                on_scene.with_columns(pl.col("coverage").round(4)),
                lambda i, c: ("behind" if coverage_below[i] else "lead") if c == "coverage" else "",
                justify={"platform": "left", "trips": "right", "coverage": "right"},
            ),
            mo.md(
                "The coverage in this month is not uniform. A comparison of wait times "
                "between platforms is therefore valid for high-coverage months only. "
                "Section 5.3 gives the date of the change. A rule caused it, not a "
                "product decision."
            ).callout(kind="info"),
        ]
    )
    return


@app.cell(hide_code=True)
def _(COVERAGE_THRESHOLD, marked_table, quality):
    quality_view = (
        quality.with_columns(
            pl.col("on_scene_coverage").round(4), pl.col("incentive_rate").round(4)
        )
        .with_columns((pl.col("invalid_rows") / pl.col("trips")).round(4).alias("invalid_rate"))
        .sort("trips", descending=True)
        .select(
            "platform",
            "trips",
            "on_scene_coverage",
            "invalid_rate",
            "neg_to_scene",
            "neg_curb_wait",
            "nonpos_fare",
            "nonpos_miles",
            "incentive_rate",
        )
    )
    quality_faults = ("neg_to_scene", "neg_curb_wait", "nonpos_fare", "nonpos_miles")
    quality_worst = (quality_view["invalid_rate"] == quality_view["invalid_rate"].max()).to_list()

    def quality_mark(row: int, column: str) -> str:
        """Mark the cells that record a fault or a gap in the filing.

        Args:
            row: Row index.
            column: Column name.

        Returns:
            A key from ROW_TINTS, or an empty string.
        """
        if column in quality_faults and quality_view[column][row] > 0:
            return "behind"
        if column == "invalid_rate" and quality_worst[row]:
            return "worst"
        if column == "on_scene_coverage":
            return "behind" if quality_view[column][row] < COVERAGE_THRESHOLD else "lead"
        return ""

    mo.vstack(
        [
            mo.md("**4.3 Archive-wide quality, every licensee**"),
            marked_table(quality_view, quality_mark, justify={"platform": "left"}),
            mo.md(
                "A licensee with very few trips and a high invalid rate is a rounding "
                "error, not a data problem. The next cell therefore selects the "
                "platforms to compare before any comparison starts."
            ).callout(kind="info"),
        ]
    )
    return


@app.cell
def _(active_platforms, coverage, dispatch_airports, kpis, platform_census):
    census = platform_census(coverage)
    live_platforms = active_platforms(coverage)
    pickup_airports = dispatch_airports(kpis)
    log.info("platforms ever seen: %s", census["platform"].to_list())
    log.info("live platforms: %s", live_platforms)
    log.info("airports with dispatched pickups: %s", pickup_airports)
    return census, live_platforms, pickup_airports


@app.cell(hide_code=True)
def _(census, live_platforms, marked_table, pickup_airports):
    census_live = census["platform"].is_in(live_platforms).to_list()
    mo.vstack(
        [
            mo.md("**4.4 Which platforms and airports, derived rather than declared**"),
            marked_table(
                census.with_columns(pl.col("lifetime_share").round(5)),
                lambda i, c: ("lead" if census_live[i] else "") if c == "platform" else "",
                justify={"platform": "left"},
            ),
            mo.md(
                f"Live platforms, by trailing-year share: **{', '.join(live_platforms)}**. "
                f"Airports that take dispatched pickups: **{', '.join(pickup_airports)}**. "
                "A platform in the census but not in the first list is a very small or "
                "closed licensee. It stays in the data and out of the comparisons."
            ).callout(kind="info"),
        ]
    )
    return


@app.cell
def _(NON_MARKET_DIRECTIONS, live_platforms, pickup_airports, raw):
    clean = raw.filter(
        pl.col("is_valid")
        & pl.col("platform").is_in(live_platforms)
        & ~pl.col("direction").is_in(NON_MARKET_DIRECTIONS)
    )
    clean_pickups = clean.filter(
        (pl.col("direction") == "pickup") & pl.col("airport").is_in(pickup_airports)
    )
    log.info(
        "raw %d -> clean %d (%.1f%% kept) -> pickups %d",
        raw.height,
        clean.height,
        100 * clean.height / raw.height,
        clean_pickups.height,
    )
    return clean, clean_pickups


@app.cell(hide_code=True)
def _(clean, clean_pickups, raw):
    _steps = pl.DataFrame(
        {
            "step": [
                "raw",
                "valid + live platforms + no transfers",
                "pickups at dispatch airports",
            ],
            "rows": [raw.height, clean.height, clean_pickups.height],
        }
    ).with_columns((pl.col("rows") / raw.height).alias("share_of_raw"))
    mo.vstack(
        [mo.md("**4.5 The cleaned frame**"), mo.ui.table(_steps, selection=None, pagination=False)]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 5 · Analysis after preprocessing

    ### 5.1 The same table, recomputed

    Side by side with section 3, on identical inputs.
    """)
    return


@app.cell
def _(clean, naive):
    cleaned = (
        clean.group_by("airport", "platform")
        .agg(
            pl.len().alias("trips"),
            pl.col("driver_share").median().alias("med_driver_share"),
            pl.col("driver_gross_per_engaged_hour").median().alias("med_gross_per_hr"),
            pl.col("secs_scene_to_pickup").median().alias("med_curb_wait_s"),
        )
        .sort("airport", "platform")
    )
    delta = (
        naive.join(cleaned, on=["airport", "platform"], how="inner", suffix="_clean")
        .with_columns(
            (pl.col("trips_clean") - pl.col("trips")).alias("trips_delta"),
            (pl.col("med_gross_per_hr_clean") - pl.col("med_gross_per_hr")).alias(
                "gross_per_hr_delta"
            ),
        )
        .select(
            "airport",
            "platform",
            "trips",
            "trips_clean",
            "trips_delta",
            "med_gross_per_hr",
            "med_gross_per_hr_clean",
            "gross_per_hr_delta",
        )
        .sort("airport", "platform")
    )
    return (delta,)


@app.cell(hide_code=True)
def _(delta):
    mo.vstack(
        [
            mo.md("**Before vs after**"),
            mo.ui.table(
                delta.with_columns(
                    pl.col("med_gross_per_hr").round(2),
                    pl.col("med_gross_per_hr_clean").round(2),
                    pl.col("gross_per_hr_delta").round(2),
                ),
                selection=None,
                pagination=False,
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 5.2 Four ways to explore

    All the work above uses the **manual method**. You write an expression, read a
    table, make a hypothesis, then write the next expression. The method is exact,
    repeatable and open to review. It is also slow, because each question costs one
    cycle.

    Three drag-and-drop views follow, on two different grains.

    - **PyGWalker, chart builder.** The cleaned month at trip level. Drag a field to
      an axis and read the answer.
    - **PyGWalker, data profile.** The same widget on the 89-month panel, opened on
      its data tab. It gives the distribution and the null count for each column.
    - **marimo data explorer.** The panel again, in marimo's own explorer. It needs
      no extra library, and it suggests an encoding for the columns you pick.

    Each one finds a good question faster than code. None keeps a record of the route
    to the answer. Explore with them, then write code for each claim that you intend
    to make.

    The cell below sets PyGWalker to `offline` before it loads the widget. PyGWalker
    can still attempt one call to its telemetry host on first use. Block
    `api.segment.io` to stop it.
    """)
    return


@app.cell
def _(clean):
    explore_cols = [
        "airport",
        "platform",
        "direction",
        "pickup_datetime",
        "base_passenger_fare",
        "driver_pay",
        "tips",
        "trip_miles",
        "secs_engaged",
        "secs_scene_to_pickup",
        "driver_share",
        "driver_gross_per_engaged_hour",
        "likely_incentive",
    ]
    explore = clean.select(explore_cols).with_columns(
        pl.col("pickup_datetime").dt.hour().alias("hour"),
        pl.col("pickup_datetime").dt.weekday().alias("weekday"),
    )
    log.info("exploration frame: %d rows x %d cols", explore.height, explore.width)
    return (explore,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    **Manual:** the hourly incentive question, written out.
    """)
    return


@app.cell
def _(explore, line_chart, pickup_airports):
    manual_hourly = (
        explore.filter(pl.col("direction") == "pickup")
        .group_by("airport", "hour")
        .agg(pl.len().alias("trips"), pl.col("likely_incentive").mean().alias("incentive_rate"))
        .sort("airport", "hour")
    )
    mo.ui.altair_chart(
        line_chart(
            manual_hourly,
            x="hour",
            x_kind="hour",
            y="incentive_rate",
            colour_by="airport",
            domain=[*pickup_airports, "EWR"],
            colour_title="Airport",
            title="Share of airport pickups where driver pay exceeds rider payment",
            x_title="Hour of day (local)",
            y_title="Share of pickups (%)",
            y_format=".0%",
        )
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    **PyGWalker:** the same frame, no expression written.

    Drag `hour` to one axis, a measure to the other axis, and `airport` to the
    colour. The chart above needed a group-by, an aggregation and a sort. This needs
    three drags. It also leaves no artifact for a reviewer.
    """)
    return


@app.cell
def _(chart_theme, explore):
    # The privacy setting comes first. PyGWalker builds its telemetry client when
    # the api module loads, and that client reads the configuration file once.
    from pygwalker.services import config as pyg_config

    if pyg_config.get_config("privacy") != "offline":
        pyg_config.set_config({"privacy": "offline"})
        log.info("pygwalker privacy set to offline")

    from pygwalker.api.marimo import walk

    # media follows the browser. It is the better default here, because marimo
    # reports light to Python for the system display setting.
    walker_appearance = {"Light": "light", "Dark": "dark"}.get(chart_theme.value, "media")

    gwalker = walk(explore, appearance=walker_appearance, default_tab="vis")
    gwalker
    return (walker_appearance,)


@app.cell
def _(NON_MARKET_DIRECTIONS, kpis, live_platforms):
    panel = (
        kpis.lazy()
        .filter(
            pl.col("platform").is_in(live_platforms)
            & ~pl.col("direction").is_in(NON_MARKET_DIRECTIONS)
        )
        .select(
            "month",
            "airport",
            "platform",
            "direction",
            "trips",
            "med_fare",
            "med_driver_gross",
            "med_driver_share",
            "med_fare_per_mile",
            "med_gross_per_engaged_hour",
            "med_miles",
            "med_engaged_s",
            "mean_tip",
            "incentive_rate",
            "pool_request_rate",
        )
        .collect()
    )
    log.info("exploration panel: %d rows x %d cols", panel.height, panel.width)
    return (panel,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    **PyGWalker, data profile.** The same widget, on the 89-month panel, opened on
    its data tab. Each column gets a distribution and a null count. This is the view
    that answers "what is in this table" before any chart.
    """)
    return


@app.cell
def _(panel, walker_appearance):
    from pygwalker.api.marimo import walk as walk_panel

    profiler = walk_panel(
        panel,
        gid="airport-panel",
        appearance=walker_appearance,
        default_tab="data",
    )
    profiler
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    **marimo data explorer.** The panel again, in the explorer that ships with
    marimo. It needs no extra library. Pick the columns and it chooses an encoding.
    """)
    return


@app.cell
def _(panel):
    mo.ui.data_explorer(panel)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 5.3 The whole market, 89 months

    The single month above is a worked example of the method. Everything from here
    uses the full aggregates, and covers every licensee rather than the two obvious
    ones.
    """)
    return


@app.cell
def _(CENSORING_FRACTION, share):
    monthly_volume = (
        share.lazy()
        .group_by("month")
        .agg(pl.col("trips").sum().alias("trips"))
        .sort("month")
        .with_columns(
            (pl.col("trips") < CENSORING_FRACTION * pl.col("trips").median()).alias("thin")
        )
        .with_columns(
            pl.col("thin")
            .cast(pl.Int8)
            .reverse()
            .cum_min()
            .reverse()
            .cast(pl.Boolean)
            .alias("censored")
        )
        .collect()
    )
    MEDIAN_TRIPS = monthly_volume["trips"].median()
    CENSORED_TAIL = monthly_volume.filter("censored")["month"]
    RELIABLE_END = monthly_volume.filter(~pl.col("censored"))["month"].max()

    log.info(
        "window %s to %s (%d months), median %s trips",
        monthly_volume["month"].min().date(),
        monthly_volume["month"].max().date(),
        monthly_volume.height,
        f"{MEDIAN_TRIPS:,.0f}",
    )
    log.info(
        "censored tail: %d month(s); reliable through %s",
        len(CENSORED_TAIL),
        RELIABLE_END.date() if RELIABLE_END is not None else "nothing usable",
    )
    return MEDIAN_TRIPS, monthly_volume


@app.cell(hide_code=True)
def _(MEDIAN_TRIPS, area_chart, monthly_volume):
    _trough = monthly_volume.filter(pl.col("trips") == monthly_volume["trips"].min()).row(
        0, named=True
    )
    _series = "Every licensee"
    _chart = area_chart(
        monthly_volume.with_columns(pl.lit(_series).alias("series")),
        y="trips",
        colour_by="series",
        domain=[_series],
        stack=False,
        title="Airport trips for each month",
        subtitle="Every licensee, and the COVID collapse in the middle",
        x_title="Month",
        y_title="Airport trips in the month",
        y_format="~s",
        height=260,
    )
    mo.vstack(
        [
            mo.ui.altair_chart(_chart),
            mo.md(
                f"The trough is **{_trough['month']:%b %Y}** at **{_trough['trips']:,}** "
                f"trips, or **{_trough['trips'] / MEDIAN_TRIPS:.1%}** of the median. That is "
                "COVID. It is also a check on the pipeline. A series without that drop is "
                "wrong. The months stay in scope."
            ).callout(kind="info"),
        ]
    )
    return


@app.cell
def _(MONTH_ORDER, SEASON_FROM, line_chart, share):
    season = (
        share.filter(pl.col("month") >= SEASON_FROM)
        .group_by("month")
        .agg(pl.col("trips").sum().alias("trips"))
        .with_columns(
            pl.col("month").dt.month().alias("month_number"),
            pl.col("month").dt.year().alias("year"),
        )
        .group_by("month_number")
        .agg(pl.col("trips").mean().alias("mean_trips"))
        .with_columns(
            pl.col("month_number")
            .replace_strict(dict(enumerate(MONTH_ORDER, start=1)), return_dtype=pl.String)
            .alias("calendar_month")
        )
        .sort("month_number")
    )
    _measure = "Mean of the month"
    mo.ui.altair_chart(
        line_chart(
            season.with_columns(pl.lit(_measure).alias("measure")),
            x="calendar_month",
            x_kind="calendar",
            y="mean_trips",
            colour_by="measure",
            domain=[_measure],
            colour_title="Measure",
            title="Airport demand has a season",
            subtitle=f"Mean trips for each calendar month, {SEASON_FROM.year} onwards",
            x_title="Calendar month",
            y_title="Mean trips in the month",
            y_format="~s",
            zero=True,
        )
    )
    return (season,)


@app.cell(hide_code=True)
def _(season):
    _low = season.filter(pl.col("mean_trips") == season["mean_trips"].min()).row(0, named=True)
    _high = season.filter(pl.col("mean_trips") == season["mean_trips"].max()).row(0, named=True)
    mo.md(
        f"The quiet month is **{_low['calendar_month']}** at "
        f"**{_low['mean_trips']:,.0f}** trips. The busy month is "
        f"**{_high['calendar_month']}** at **{_high['mean_trips']:,.0f}**, which is "
        f"**{_high['mean_trips'] / _low['mean_trips'] - 1:.0%}** higher. A target that "
        "compares one month against the month before it reads this pattern as a change "
        "in performance. Compare each month against the same month one year earlier."
    ).callout(kind="info")
    return


@app.cell
def _(RECOVERY_BASELINE_MONTH, monthly_volume):
    baseline_rows = monthly_volume.filter(pl.col("month") == RECOVERY_BASELINE_MONTH)
    BASELINE_TRIPS = baseline_rows["trips"][0] if baseline_rows.height else None
    recovered = monthly_volume.filter(
        (pl.col("month") > RECOVERY_BASELINE_MONTH) & (pl.col("trips") >= BASELINE_TRIPS)
    )
    RECOVERY_MONTH = recovered["month"].min() if recovered.height else None
    if RECOVERY_MONTH is not None:
        RECOVERY_GAP = (RECOVERY_MONTH.year - RECOVERY_BASELINE_MONTH.year) * 12 + (
            RECOVERY_MONTH.month - RECOVERY_BASELINE_MONTH.month
        )
        log.info(
            "volume returned to the %s level in %s, after %d months",
            RECOVERY_BASELINE_MONTH.date(),
            RECOVERY_MONTH.date(),
            RECOVERY_GAP,
        )
    else:
        RECOVERY_GAP = None
        log.info("volume has not returned to the %s level", RECOVERY_BASELINE_MONTH.date())
    return BASELINE_TRIPS, RECOVERY_GAP, RECOVERY_MONTH


@app.cell(hide_code=True)
def _(BASELINE_TRIPS, RECOVERY_BASELINE_MONTH, RECOVERY_GAP, RECOVERY_MONTH):
    mo.md(
        (
            f"Volume reached **{BASELINE_TRIPS:,}** trips in "
            f"**{RECOVERY_BASELINE_MONTH:%b %Y}**, the last month before the collapse. It "
            f"returned to that level in **{RECOVERY_MONTH:%b %Y}**, after "
            f"**{RECOVERY_GAP}** months."
        )
        if RECOVERY_MONTH is not None
        else "Volume has not returned to the level of the last month before the collapse."
    ).callout(kind="info")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### Who has ever operated here

    The entry-and-exit picture is the first thing a two-platform analysis throws away.
    """)
    return


@app.cell(hide_code=True)
def _(census, span_chart):
    _domain = census["platform"].to_list()
    mo.vstack(
        [
            mo.ui.altair_chart(
                span_chart(
                    census,
                    domain=_domain,
                    title="Platform lifespan at NYC airports, first to last month traded",
                    x_title="Year",
                    y_title="Platform",
                )
            ),
            mo.md(
                "A bar that stops before the right edge is an exit. "
                + ". ".join(
                    f"{row['platform']} ends in {row['last_month']:%B %Y}"
                    for row in census.filter(
                        pl.col("last_month") < census["last_month"].max()
                    ).iter_rows(named=True)
                )
                + ". A bar that starts late is an entrant, and a bare `HV####` label is "
                "a licence number issued after this archive was documented."
            ).callout(kind="info"),
        ]
    )
    return


@app.cell
def _(area_chart, census, share):
    share_domain = census["platform"].to_list()
    share_all = share.group_by("month", "platform").agg(pl.col("trips").sum().alias("trips"))
    mo.ui.altair_chart(
        area_chart(
            share_all,
            y="trips",
            colour_by="platform",
            domain=share_domain,
            stack="normalize",
            title="Share of all NYC airport trips, every licensee",
            x_title="Month",
            y_title="Share of trips (%)",
            y_format=".0%",
        )
    )
    return (share_domain,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### Concentration

    Share charts show who is winning. The Herfindahl-Hirschman index shows whether the
    market is a contest at all: it is the sum of squared percentage shares, so 10,000
    is a monopoly and the US merger guidelines treat anything above 2,500 as highly
    concentrated. Computing it needs every licensee, which is why the aggregates keep
    them.
    """)
    return


@app.cell
def _(line_chart, share):
    hhi = (
        share.group_by("month", "airport")
        .agg((pl.col("share").pow(2).sum() * 10_000).alias("hhi"))
        .sort("month", "airport")
    )
    hhi_domain = hhi.get_column("airport").unique().sort().to_list()
    mo.ui.altair_chart(
        line_chart(
            hhi,
            x="month",
            x_kind="month",
            y="hhi",
            colour_by="airport",
            domain=hhi_domain,
            colour_title="Airport",
            title="Market concentration at each airport (Herfindahl-Hirschman index)",
            x_title="Month",
            y_title="HHI (10,000 = one platform takes every trip)",
            y_format=",.0f",
        )
    )
    return (hhi_domain,)


@app.cell
def _(by_year, leadership, share):
    share_year = (
        by_year(share)
        .group_by("year", "airport", "platform")
        .agg(pl.col("trips").sum().alias("trips"))
        .with_columns(
            (pl.col("trips") / pl.col("trips").sum().over("year", "airport")).alias("share")
        )
        .sort("year", "airport", "platform")
    )
    leaders = leadership(share_year)
    handovers = leaders.filter(pl.col("changed_hands"))
    log.info("leadership changed hands %d time(s)", handovers.height)
    return handovers, leaders, share_year


@app.cell(hide_code=True)
def _(handovers, leaders):
    mo.vstack(
        [
            mo.md("**Share leader by airport and year, with the runner-up gap**"),
            mo.ui.table(
                leaders.with_columns(
                    pl.col("leader_share").round(3),
                    pl.col("runner_up_share").round(3),
                    pl.col("gap").round(3),
                ),
                selection=None,
                pagination=True,
            ),
            mo.md(
                "Leadership changed hands "
                f"**{handovers.height}** time(s): "
                + (
                    ", ".join(
                        f"{r['airport']} in {r['year']} (to {r['leader']})"
                        for r in handovers.iter_rows(named=True)
                    )
                    or "never"
                )
                + ". A narrowing gap with no handover is the more common pattern, and it "
                "is the one a two-platform crossover test misses entirely."
            ).callout(kind="info"),
        ]
    )
    return


@app.cell
def _(COVERAGE_THRESHOLD, coverage, line_chart, share_domain):
    coverage_starts = (
        coverage.lazy()
        .group_by("platform")
        .agg(
            pl.col("month")
            .filter(pl.col("on_scene_coverage") > COVERAGE_THRESHOLD)
            .min()
            .alias("first_month")
        )
        .sort("platform")
        .collect()
    )
    COMPARABLE_FROM = coverage_starts["first_month"].max()
    for _row in coverage_starts.iter_rows(named=True):
        log.info(
            "on_scene %d%% coverage %-8s %s",
            100 * COVERAGE_THRESHOLD,
            _row["platform"],
            _row["first_month"].date() if _row["first_month"] else "never",
        )
    log.info("curb wait comparable from %s", COMPARABLE_FROM.date())

    mo.ui.altair_chart(
        line_chart(
            coverage,
            x="month",
            x_kind="month",
            y="on_scene_coverage",
            colour_by="platform",
            domain=share_domain,
            title="Share of trips reporting driver-arrival time",
            x_title="Month",
            y_title="Trips with an on-scene timestamp (%)",
            y_format=".0%",
        )
    )
    return COMPARABLE_FROM, coverage_starts


@app.cell(hide_code=True)
def _(COMPARABLE_FROM, coverage_starts):
    _late = (
        coverage_starts.filter(pl.col("first_month") == COMPARABLE_FROM)
        .sort("platform")
        .get_column("platform")
        .to_list()
    )
    mo.md(
        f"The last platform started to report in **{COMPARABLE_FROM:%b %Y}** "
        f"({', '.join(_late)}). Curb wait is comparable between platforms from that month "
        "only. A rule caused the change, not a commercial decision. See §6."
    ).callout(kind="warn")
    return


@app.cell
def _(kpis, live_platforms, pickup_airports):
    pickups = kpis.filter(
        (pl.col("direction") == "pickup")
        & pl.col("platform").is_in(live_platforms)
        & pl.col("airport").is_in(pickup_airports)
    )
    return (pickups,)


@app.cell
def _(by_year, line_chart, live_platforms, pickup_airports, pickups):
    econ_year = (
        by_year(pickups)
        .group_by("year", "airport", "platform")
        .agg(
            pl.col("med_driver_share").median().alias("payout_share"),
            pl.col("med_gross_per_engaged_hour").median().alias("gross_per_hour"),
            pl.col("med_fare").median().alias("median_fare"),
        )
        .sort("year", "airport", "platform")
    )
    mo.vstack(
        [
            mo.ui.altair_chart(
                line_chart(
                    econ_year.filter(pl.col("airport") == airport),
                    x="year",
                    x_kind="year",
                    y="payout_share",
                    colour_by="platform",
                    domain=live_platforms,
                    title=f"Driver gross as a share of rider payment — {airport} pickups",
                    x_title="Year",
                    y_title="Driver gross ÷ rider payment (%)",
                    y_format=".0%",
                    height=260,
                )
            )
            for airport in pickup_airports
        ]
    )
    return (econ_year,)


@app.cell(hide_code=True)
def _(econ_year, line_chart, live_platforms, pickup_airports):
    mo.vstack(
        [
            mo.ui.altair_chart(
                line_chart(
                    econ_year.filter(pl.col("airport") == airport),
                    x="year",
                    x_kind="year",
                    y="gross_per_hour",
                    colour_by="platform",
                    domain=live_platforms,
                    title=f"Driver gross per engaged hour — {airport} pickups",
                    x_title="Year",
                    y_title="Dollars per engaged hour (request → dropoff)",
                    y_format="$,.0f",
                    height=260,
                )
            )
            for airport in pickup_airports
        ]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### One month, one point

    Every chart so far reduces the archive to a line. This one keeps the months
    apart. Each point is one airport, one platform and one month: the median fare
    against the driver gross for each engaged hour.

    **Drag a rectangle across the points.** The bars below then total the pickups
    inside the selection. A region of the fare and earnings space resolves into the
    platforms that occupy it. To clear the selection, click once outside the
    rectangle.
    """)
    return


@app.cell
def _(brush_chart, kpis, live_platforms, pickup_airports):
    fare_earnings = (
        kpis.lazy()
        .filter(
            (pl.col("direction") == "pickup")
            & pl.col("airport").is_in(pickup_airports)
            & pl.col("platform").is_in(live_platforms)
            & pl.col("med_gross_per_engaged_hour").is_not_null()
        )
        .select(
            "month",
            "airport",
            "platform",
            "trips",
            "med_fare",
            "med_gross_per_engaged_hour",
        )
        .collect()
    )
    mo.ui.altair_chart(
        brush_chart(
            fare_earnings,
            x="med_fare",
            y="med_gross_per_engaged_hour",
            colour_by="airport",
            domain=pickup_airports,
            bar_value="trips",
            bar_group="platform",
            title="A higher fare does not carry a higher hourly wage",
            subtitle=(
                "One point for each airport, platform and month. Drag to filter the bars below."
            ),
            x_title="Median rider fare",
            y_title="Driver gross for each engaged hour",
            x_format="$,.0f",
            y_format="$,.0f",
            bar_title="Airport pickups in the selection",
            bar_y_title="Platform",
            bar_format="~s",
        ),
        chart_selection=False,
        legend_selection=False,
    )
    return (fare_earnings,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### The same points, played over time

    The chart above holds all 89 months at once. This one plays them in order. The
    faint points are the whole archive, so the axes never move. The coloured trail
    is the last year, and the ringed points are the month in the caption.

    Press **play**. The market drifts up and to the right. The vertical drift then
    stops while the horizontal drift continues. That is the fare rising faster than
    the driver gross.
    """)
    return


@app.cell
def _():
    get_frame, set_frame = mo.state(0)
    return get_frame, set_frame


@app.cell
def _(fare_earnings):
    frame_months = fare_earnings["month"].unique().sort().to_list()
    player = mo.ui.refresh(
        options=["0.25s", "0.5s", "1s", "2s"],
        default_interval="0.5s",
        label="Play the archive",
    )
    player
    return frame_months, player


@app.cell
def _(frame_months, player, set_frame):
    player
    set_frame(lambda index: (index + 1) % len(frame_months))
    return


@app.cell
def _(TRAIL_MONTHS, fare_earnings, frame_chart, frame_months, get_frame, pickup_airports):
    frame_index = get_frame() % len(frame_months)
    frame_month = frame_months[frame_index]
    trail_start = frame_months[max(0, frame_index - TRAIL_MONTHS)]

    frame_trail = (
        fare_earnings.lazy()
        .filter(pl.col("month").is_between(trail_start, frame_month))
        .with_columns(
            (1.0 - (frame_month - pl.col("month")).dt.total_days() / (31.0 * TRAIL_MONTHS)).alias(
                "weight"
            )
        )
        .collect()
    )
    frame_now = fare_earnings.filter(pl.col("month") == frame_month)

    mo.ui.altair_chart(
        frame_chart(
            fare_earnings,
            frame_trail,
            frame_now,
            x="med_fare",
            y="med_gross_per_engaged_hour",
            colour_by="airport",
            domain=pickup_airports,
            x_domain=(
                fare_earnings["med_fare"].min() * 0.95,
                fare_earnings["med_fare"].max() * 1.05,
            ),
            y_domain=(
                fare_earnings["med_gross_per_engaged_hour"].min() * 0.95,
                fare_earnings["med_gross_per_engaged_hour"].max() * 1.05,
            ),
            title="Where the market sat in each month",
            subtitle=(
                f"{frame_month:%B %Y}, month {frame_index + 1} of {len(frame_months)}. "
                f"The trail covers the previous {TRAIL_MONTHS} months."
            ),
            x_title="Median rider fare",
            y_title="Driver gross for each engaged hour",
            x_format="$,.0f",
            y_format="$,.0f",
        ),
        chart_selection=False,
        legend_selection=False,
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### An airport pickup is a different job from an airport dropoff

    The direction column carries a structural difference that a pickup-only view
    hides. A pickup starts in a queue, so it holds the driver for longer before the
    meter earns anything. The minimum-pay floor therefore binds more often, the
    payout share is higher, and the rider tips more.
    """)
    return


@app.cell
def _(NON_MARKET_DIRECTIONS, kpis, live_platforms, pickup_airports):
    direction_economics = (
        kpis.filter(
            pl.col("platform").is_in(live_platforms)
            & pl.col("airport").is_in(pickup_airports)
            & ~pl.col("direction").is_in(NON_MARKET_DIRECTIONS)
        )
        .group_by("airport", "direction")
        .agg(
            pl.col("trips").sum().alias("trips"),
            pl.col("med_fare").median().alias("median_fare"),
            pl.col("med_driver_share").median().alias("payout_share"),
            pl.col("med_engaged_s").median().alias("engaged_s"),
            pl.col("mean_tip").mean().alias("mean_tip"),
            pl.col("incentive_rate").mean().alias("binding_rate"),
        )
        .with_columns(
            (pl.col("mean_tip") / pl.col("median_fare")).alias("tip_rate"),
            (pl.col("engaged_s") / 60).alias("engaged_min"),
        )
        .sort("airport", "direction")
    )
    mo.ui.table(
        direction_economics.select(
            "airport",
            "direction",
            "trips",
            pl.col("median_fare").round(2),
            pl.col("payout_share").round(3),
            pl.col("engaged_min").round(1),
            pl.col("mean_tip").round(2),
            pl.col("tip_rate").round(4),
            pl.col("binding_rate").round(4),
        ),
        selection=None,
        pagination=False,
    )
    return (direction_economics,)


@app.cell(hide_code=True)
def _(direction_economics, pickup_airports):
    _wide = direction_economics.pivot(
        on="direction", index="airport", values=["payout_share", "engaged_min", "tip_rate"]
    )
    _lines = []
    for _row in _wide.iter_rows(named=True):
        _lines.append(
            f"At **{_row['airport']}** the pickup holds the driver "
            f"{_row['engaged_min_pickup'] - _row['engaged_min_dropoff']:.1f} minutes longer "
            f"than the dropoff, pays "
            f"{100 * (_row['payout_share_pickup'] - _row['payout_share_dropoff']):.1f} points "
            f"more of the rider payment, and tips at "
            f"{_row['tip_rate_pickup']:.1%} against {_row['tip_rate_dropoff']:.1%}."
        )
    mo.md("\n\n".join(_lines)).callout(kind="info")
    return


@app.cell(hide_code=True)
def _(kpis):
    _internal = kpis.filter(pl.col("direction") == "internal")
    _label = "internal" if _internal.height else "transfer"
    _same = (
        kpis.filter(pl.col("direction") == _label)
        .group_by("airport")
        .agg(
            pl.col("trips").sum().alias("trips"),
            pl.col("med_miles").median().alias("median_miles"),
            pl.col("med_fare").median().alias("median_fare"),
        )
        .sort("trips", descending=True)
    )
    mo.vstack(
        [
            mo.md(f"**Trips with the label `{_label}`**"),
            mo.ui.table(_same, selection=None, pagination=False),
            mo.md(
                "JFK to LaGuardia is about 11 road miles. A median near 3.5 miles in the "
                "JFK row means that most of those trips start and end inside one airport. "
                "They are terminal-to-terminal moves, not a transfer between airports. "
                "§0.6 gives them the label `internal`, and no market measurement uses "
                "them. An export from an earlier version of the extractor puts both kinds "
                "under `transfer`."
            ).callout(kind="warn"),
        ]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### How much ground a driver covers in an hour

    Median distance divided by median engaged time gives an effective speed for the
    whole job, from the request to the dropoff. It is not a road speed, because the
    engaged time includes the approach and the queue. It is the measurement that
    decides how many airport trips one driver can complete in an hour.
    """)
    return


@app.cell
def _(by_year, kpis, line_chart, live_platforms, pickup_airports):
    speed_year = (
        by_year(
            kpis.filter(
                (pl.col("direction") == "pickup")
                & pl.col("airport").is_in(pickup_airports)
                & pl.col("platform").is_in(live_platforms)
            )
        )
        .group_by("year", "airport")
        .agg(
            (pl.col("med_miles").median() / (pl.col("med_engaged_s").median() / 3600)).alias("mph")
        )
        .sort("year", "airport")
    )
    mo.ui.altair_chart(
        line_chart(
            speed_year,
            x="year",
            x_kind="year",
            y="mph",
            colour_by="airport",
            domain=pickup_airports,
            colour_title="Airport",
            title="Effective speed of an airport pickup, request to dropoff",
            x_title="Year",
            y_title="Miles for each engaged hour",
            y_format=",.1f",
        )
    )
    return (speed_year,)


@app.cell(hide_code=True)
def _(speed_year):
    _wide = speed_year.pivot(on="airport", index="year", values="mph").sort("year")
    _first = _wide.row(0, named=True)
    _last = _wide.row(-1, named=True)
    _peak = _wide.row(1, named=True)
    _lines = []
    for _airport in [c for c in _wide.columns if c != "year"]:
        _change = _last[_airport] / _first[_airport] - 1
        _word = "slower" if _change < 0 else "faster"
        _lines.append(
            f"**{_airport}**: {_first[_airport]:.1f} in {_first['year']}, "
            f"{_last[_airport]:.1f} in {_last['year']}, "
            f"{abs(_change):.1%} {_word}."
        )
    mo.md(
        "\n\n".join(_lines)
        + f"\n\nThe spike in {_peak['year']} is COVID and the empty streets. Measured "
        "against the first year the two airports part company again. One of them slowed "
        "and the other did not. A network-wide claim about congestion is therefore wrong "
        "for one of the two."
    ).callout(kind="info")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### The rider pays more, the driver keeps less

    The two lines start together in 2019 and separate. The median trip distance
    stays near 13.5 miles across the archive, so a change in trip mix does not
    explain the gap.
    """)
    return


@app.cell
def _(by_year, line_chart, live_platforms, pickup_airports, kpis):
    money_year = (
        by_year(
            kpis.filter(
                (pl.col("direction") == "pickup")
                & pl.col("airport").is_in(pickup_airports)
                & pl.col("platform").is_in(live_platforms)
            )
        )
        .group_by("year")
        .agg(
            pl.col("med_fare").median().alias("Median rider fare"),
            pl.col("med_driver_gross").median().alias("Median driver gross"),
        )
        .sort("year")
    )
    divergence = (
        money_year.unpivot(index="year", variable_name="measure", value_name="dollars")
        .with_columns(
            (100 * pl.col("dollars") / pl.col("dollars").first().over("measure")).alias("index")
        )
        .sort("year", "measure")
    )
    mo.ui.altair_chart(
        line_chart(
            divergence,
            x="year",
            x_kind="year",
            y="index",
            colour_by="measure",
            domain=["Median rider fare", "Median driver gross"],
            colour_title="Measure",
            title="Rider fare and driver gross, indexed to the first year",
            x_title="Year",
            y_title="Index (first year = 100)",
            y_format=",.0f",
        )
    )
    return (money_year,)


@app.cell(hide_code=True)
def _(money_year):
    _first = money_year.row(0, named=True)
    _last = money_year.row(-1, named=True)
    _fare = _last["Median rider fare"] / _first["Median rider fare"] - 1
    _gross = _last["Median driver gross"] / _first["Median driver gross"] - 1
    mo.md(
        f"""
    Between {money_year["year"].min()} and {money_year["year"].max()} the median
    airport fare moved from ${_first["Median rider fare"]:,.2f} to
    ${_last["Median rider fare"]:,.2f}, a rise of {_fare:.1%}. The median driver
    gross moved from ${_first["Median driver gross"]:,.2f} to
    ${_last["Median driver gross"]:,.2f}, a rise of {_gross:.1%}. The difference is
    the payout share, and it falls across the same period.
    """
    ).callout(kind="info")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### Newark is a one-way airport

    §4.4 removes Newark from the pickup analysis by ratio, not by name. This table
    gives the ratio that the rule reads.
    """)
    return


@app.cell(hide_code=True)
def _(MIN_DISPATCH_RATIO, NON_MARKET_DIRECTIONS, kpis, marked_table):
    direction_ratio = (
        kpis.filter(~pl.col("direction").is_in(NON_MARKET_DIRECTIONS))
        .group_by("airport", "direction")
        .agg(pl.col("trips").sum().alias("trips"))
        .pivot(on="direction", index="airport", values="trips")
        .fill_null(0)
        .with_columns(
            (pl.col("pickup") / pl.col("dropoff").replace(0, None)).alias("pickups_per_dropoff")
        )
        .sort("pickups_per_dropoff", descending=True)
    )
    dispatch_fails = (direction_ratio["pickups_per_dropoff"] < MIN_DISPATCH_RATIO).to_list()
    mo.vstack(
        [
            marked_table(
                direction_ratio.with_columns(pl.col("pickups_per_dropoff").round(6)),
                lambda i, c: (
                    ("behind" if dispatch_fails[i] else "lead")
                    if c == "pickups_per_dropoff"
                    else ""
                ),
                justify={"airport": "left"},
            ),
            mo.md(
                "A New York licence lets a vehicle set down in New Jersey. It does not "
                "let the vehicle take a dispatched pickup there. The Newark ratio shows "
                "the effect, and no airport sits between the two groups."
            ).callout(kind="info"),
        ]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    #### When the airport actually works

    The chart gives trip counts for each hour, as a share of the day at that airport.
    This is the supply question. It shows the hours at which a platform must attract
    drivers to the airport. It separates the airports better than any money
    measurement.
    """)
    return


@app.cell
def _(heat_chart, hourly):
    hour_shape = (
        hourly.group_by("airport", "hour")
        .agg(pl.col("trips").sum().alias("trips"))
        .with_columns((pl.col("trips") / pl.col("trips").sum().over("airport")).alias("share"))
        .sort("airport", "hour")
    )
    mo.ui.altair_chart(
        heat_chart(
            hour_shape,
            x="hour",
            y="airport",
            value="share",
            title="When airport pickups happen, as a share of each airport's day",
            x_title="Hour of day (local)",
            y_title="Airport",
            legend_title="Share of that airport's pickups",
        )
    )
    return


@app.cell
def _(kpis, line_chart, live_platforms):
    pool = (
        kpis.filter(pl.col("platform").is_in(live_platforms))
        .group_by("month", "platform")
        .agg(
            (
                (pl.col("pool_request_rate") * pl.col("trips")).sum()
                / pl.col("trips").sum().replace(0, None)
            ).alias("pool_request_rate")
        )
        .sort("month", "platform")
    )
    mo.ui.altair_chart(
        line_chart(
            pool,
            x="month",
            x_kind="month",
            y="pool_request_rate",
            colour_by="platform",
            domain=live_platforms,
            title="Shared-ride requests as a share of airport trips",
            x_title="Month",
            y_title="Trips requesting a shared ride (%)",
            y_format=".1%",
            zero=True,
        )
    )
    return


@app.cell
def _(incentive, line_chart, live_platforms):
    binding = (
        incentive.filter(
            (pl.col("direction") == "pickup") & pl.col("platform").is_in(live_platforms)
        )
        .group_by("month", "platform")
        .agg(
            (pl.col("incentive_trips").sum() / pl.col("trips").sum().replace(0, None)).alias(
                "binding_rate"
            )
        )
        .sort("month", "platform")
    )
    mo.ui.altair_chart(
        line_chart(
            binding,
            x="month",
            x_kind="month",
            y="binding_rate",
            colour_by="platform",
            domain=live_platforms,
            title="How often driver pay exceeds everything the rider paid",
            x_title="Month",
            y_title="Share of airport pickups (%)",
            y_format=".0%",
            zero=True,
        )
    )
    return


@app.cell
def _(COMPARABLE_FROM, pickups):
    wait = (
        pickups.filter((pl.col("month") >= COMPARABLE_FROM) & (pl.col("curb_wait_coverage") > 0.8))
        .group_by("airport", "platform")
        .agg(
            pl.col("med_curb_wait_s").median().alias("median_wait_s"),
            pl.len().alias("months"),
        )
        .sort("airport", "platform")
    )
    ROUNDING_SUSPECT = wait.filter(pl.col("median_wait_s") % 60 == 0).height > 0
    if ROUNDING_SUSPECT:
        log.warning(
            "curb-wait medians land on an exact minute for %d of %d airport and platform "
            "pair(s). Read the direction of the difference, not the size.",
            wait.filter(pl.col("median_wait_s") % 60 == 0).height,
            wait.height,
        )
    return ROUNDING_SUSPECT, wait


@app.cell(hide_code=True)
def _(ROUNDING_SUSPECT, marked_table, wait):
    wait_rounded = (wait["median_wait_s"] % 60 == 0).to_list()
    mo.vstack(
        [
            mo.md("**Median curb wait, comparable months only**"),
            marked_table(
                wait,
                lambda i, c: ("worst" if wait_rounded[i] else "") if c == "median_wait_s" else "",
                justify={"airport": "left", "platform": "left"},
            ),
            mo.md(
                "One median or more is an exact multiple of 60 seconds. This is a sign "
                "of minute-level rounding on one platform. The direction of the "
                "difference can be correct. The size of it is not reliable."
            ).callout(kind="warn")
            if ROUNDING_SUSPECT
            else mo.md("No rounding artifact."),
        ]
    )
    return


@app.cell
def _(incentive, live_platforms):
    inc_by_airport = (
        incentive.filter(
            (pl.col("direction") == "pickup") & pl.col("platform").is_in(live_platforms)
        )
        .group_by("airport", "platform")
        .agg(
            pl.col("incentive_trips").sum().alias("topped_up"),
            pl.col("trips").sum().alias("trips"),
            pl.col("total_topup").sum().alias("total_topup"),
            pl.col("med_topup").median().alias("median_topup"),
        )
        .with_columns(
            (pl.col("topped_up") / pl.col("trips")).alias("rate"),
            (pl.col("total_topup") / pl.col("trips")).alias("topup_per_trip"),
        )
        .sort("airport", "platform")
    )
    return (inc_by_airport,)


@app.cell(hide_code=True)
def _(inc_by_airport, pickup_airports):
    mo.vstack(
        [
            mo.md("**Minimum-pay binding rate and top-up size, dispatch airports**"),
            mo.ui.table(
                inc_by_airport.filter(pl.col("airport").is_in(pickup_airports))
                .select("airport", "platform", "trips", "rate", "median_topup", "topup_per_trip")
                .with_columns(
                    pl.col("rate").round(4),
                    pl.col("median_topup").round(2),
                    pl.col("topup_per_trip").round(3),
                ),
                selection=None,
                pagination=False,
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 6 · Conclusions
    """)
    return


@app.cell(hide_code=True)
def _(COMPARABLE_FROM):
    mo.vstack(
        [
            mo.md(
                f"""
    #### The on-scene jump ({COMPARABLE_FROM:%b %Y}) is a reporting rule, not a product change

    TLC adopted the *Wait Time Restrictions for FHVs* rule on 29 January 2025. The
    rule took effect on 6 March 2025. It tells each high-volume service to report the
    time at which the dispatched vehicle reached the pickup point. Before that date
    the documentation gave the field for accessible vehicles only. Coverage for the
    other licensees therefore stayed near zero. TLC re-dated the HVFHV data dictionary
    on 18 March 2025.
            """
            ).callout(kind="danger"),
            mo.md(
                """
    #### Driver pay above rider payment is the minimum-pay formula, not incentive spend

    The NYC minimum pay standard computes the pay for each trip as
    *(per-mile rate x miles + per-minute rate x minutes) / `utilization rate`*. The
    fare has no part in it. A `utilization rate` below 1 increases the pay. On an
    airport trip with a low fare and a long empty approach, the floor goes above the
    rider payment. Measure how often the minimum applies. Do not read it as the spend
    of each platform.
            """
            ).callout(kind="danger"),
        ]
    )
    return


@app.cell
def _(econ_year, inc_by_airport, share_year):
    latest_year = econ_year["year"].max()
    summary = (
        econ_year.filter(pl.col("year") == latest_year)
        .join(
            share_year.filter(pl.col("year") == latest_year).select("airport", "platform", "share"),
            on=["airport", "platform"],
            how="left",
        )
        .join(
            inc_by_airport.select("airport", "platform", "rate"),
            on=["airport", "platform"],
            how="left",
        )
        .select(
            "airport",
            "platform",
            pl.col("share").round(3).alias("share_of_airport"),
            pl.col("payout_share").round(3),
            pl.col("gross_per_hour").round(2),
            pl.col("rate").round(4).alias("min_pay_binding_rate"),
        )
        .sort("airport", "share_of_airport", descending=[False, True])
    )
    log.info(
        "summary covers %d platform(s) at %d airport(s) in %s",
        summary["platform"].n_unique(),
        summary["airport"].n_unique(),
        latest_year,
    )
    return latest_year, summary


@app.cell(hide_code=True)
def _(census, hhi_domain, latest_year, leaders, live_platforms, summary):
    _dormant = census.filter(~pl.col("platform").is_in(live_platforms))["platform"].to_list()
    _final = leaders.filter(pl.col("year") == leaders["year"].max())
    mo.vstack(
        [
            mo.md(f"**Where every live platform stands in {latest_year}**"),
            mo.ui.table(summary, selection=None, pagination=False),
            mo.md(
                f"""
    Across **{len(hhi_domain)}** airports the archive contains
    **{census.height}** licensees, of which **{len(live_platforms)}** are live
    (**{", ".join(live_platforms)}**) and
    **{len(_dormant)}** are dormant (**{", ".join(_dormant) or "none"}**). The current
    leaders are
    {", ".join(f"{r['airport']}: {r['leader']} at {r['leader_share']:.1%}" for r in _final.iter_rows(named=True))}.
                """
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(census, handovers, hhi_domain, live_platforms):
    mo.md(f"""
    ### The headline finding

    The headline is a tension, not a number. The payout share and the share of trips
    move independently. A larger slice for the driver does not buy position. That
    result points away from pay as the binding constraint. It points towards matching,
    dispatch and curb operations. The public data can frame that product question. It
    cannot settle it.

    Three cautions go with the result. The leader changed **{handovers.height}** time(s)
    across **{len(hhi_domain)}** airports, so watch the concentration and not the rank.
    The 2024 app-lockout period and the August 2025 change to the `utilization rate`
    both distort a per-hour earnings comparison. Read the months after August 2025 for
    the cleanest picture. Each share figure comes from the trip records. No third party
    publishes airport share for each licensee, so no external source confirms it. That
    absence is the reason to do the work, and the reason the method stays open to
    inspection.

    The archive holds **{census.height}** licensees and **{len(live_platforms)}** of
    them trade today. The two that left took a pooling product and the most generous
    payout share in the record with them. That is the part of the history a
    two-platform view cannot show.
    """)
    return


@app.cell(hide_code=True)
def _(RECENT_WINDOW_MONTHS, kpis):
    mo.md(f"""
    ## 7 · Platform against platform

    Sections 5 and 6 measure the market. This section measures the competitors, on
    one set of numbers, at each dispatch airport.

    §7.1 holds **every licensee in the archive** across the full history. §7.2 puts
    the **two live platforms** side by side over a recent window, with a difference
    column.

    The columns run in order of size, largest first.

    The window in §7.2 is the last **{RECENT_WINDOW_MONTHS}** months, to
    **{kpis["month"].max():%b %Y}**. Two events make the earlier months a poor
    comparison: the 2024 app-lockout period, and the August 2025 change that split
    the `utilization rate` into a time part and a distance part. Airport pickups only.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 7.1 Every licensee, across the whole archive

    The window here is the full archive, not the recent months. Two of the licensees
    stopped trading years ago, so a recent window gives them empty columns.

    Read a closed platform as history. Each one ran a different airport product, and
    the numbers below are the record of it.
    """)
    return


@app.cell
def _(census, compare_platforms, format_metric, kpis, marked_table, pickup_airports):
    all_platforms = census["platform"].to_list()
    lifetime = compare_platforms(kpis, all_platforms, pickup_airports, window=None)

    def lifetime_table(airport: str) -> mo.ui.table:
        """Render one airport's lifetime numbers, marking the best of each row.

        Args:
            airport: Airport code.

        Returns:
            The table.
        """
        frame = (
            lifetime.lazy()
            .filter(pl.col("airport") == airport)
            .with_columns(
                pl.when(pl.col("better") == "high")
                .then(pl.max_horizontal([pl.col(name) for name in all_platforms]))
                .when(pl.col("better") == "low")
                .then(pl.min_horizontal([pl.col(name) for name in all_platforms]))
                .otherwise(None)
                .alias("best")
            )
            .collect()
        )
        winners = [
            next(
                (
                    name
                    for name in all_platforms
                    if row["best"] is not None and row[name] == row["best"]
                ),
                "",
            )
            for row in frame.iter_rows(named=True)
        ]
        shown = pl.DataFrame(
            {"Measurement": frame["label"]}
            | {
                name: [format_metric(v, k) for v, k in zip(frame[name], frame["kind"], strict=True)]
                for name in all_platforms
            }
        )
        return marked_table(
            shown,
            lambda i, c: "lead" if c and c == winners[i] else "",
            justify={"Measurement": "left"} | {name: "right" for name in all_platforms},
        )

    mo.vstack(
        [
            mo.vstack(
                [
                    mo.md(
                        f"#### {airport} pickups, {kpis['month'].min():%b %Y} "
                        f"to {kpis['month'].max():%b %Y}"
                    ),
                    lifetime_table(airport),
                ]
            )
            for airport in pickup_airports
        ]
    )
    return all_platforms, lifetime


@app.cell(hide_code=True)
def _(census, lifetime, live_platforms):
    _closed = census.filter(~pl.col("platform").is_in(live_platforms))
    _rows = []
    for _row in _closed.iter_rows(named=True):
        _rows.append(
            f"**{_row['platform']}** ran for {_row['months_active']} months and ended in "
            f"{_row['last_month']:%b %Y} with {_row['trips']:,} airport trips, "
            f"{_row['lifetime_share']:.2%} of the archive."
        )
    mo.md(
        "\n\n".join(_rows)
        + "\n\nA column of blanks means the platform never ran at that airport, or "
        "never filed the field. Compare a closed platform against the others on the "
        "measurements it did file, and read the rest as absent rather than as zero."
    ).callout(kind="info")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### 7.2 The two live platforms, head to head
    """)
    return


@app.cell
def _(census, compare_platforms, kpis, live_platforms, pickup_airports):
    duo = (
        census.lazy()
        .filter(pl.col("platform").is_in(live_platforms))
        .sort("trips", descending=True)
        .head(2)
        .collect()
        .get_column("platform")
        .to_list()
    )
    scorecard = compare_platforms(kpis, duo, pickup_airports)
    log.info("head to head: %s at %s", " against ".join(duo), ", ".join(pickup_airports))
    return duo, scorecard


@app.cell(hide_code=True)
def _(duo, format_difference, format_metric, marked_table, pickup_airports, scorecard):
    def scorecard_table(airport: str) -> mo.ui.table:
        """Render one airport's head-to-head numbers with the leader marked.

        A measurement with a better side tints the cell of the platform that
        holds it. A measurement with no better side, such as the median fare,
        stays plain.

        Args:
            airport: Airport code.

        Returns:
            The table.
        """
        frame = (
            scorecard.lazy()
            .filter(pl.col("airport") == airport)
            .with_columns(
                pl.when(pl.col("better") == "")
                .then(pl.lit(""))
                .when(
                    ((pl.col("better") == "high") & (pl.col(duo[0]) >= pl.col(duo[1])))
                    | ((pl.col("better") == "low") & (pl.col(duo[0]) <= pl.col(duo[1])))
                )
                .then(pl.lit(duo[0]))
                .otherwise(pl.lit(duo[1]))
                .alias("leader")
            )
            .collect()
        )
        leaders = frame["leader"].to_list()
        shown = pl.DataFrame(
            {
                "Measurement": frame["label"],
                duo[0]: [
                    format_metric(v, k) for v, k in zip(frame[duo[0]], frame["kind"], strict=True)
                ],
                duo[1]: [
                    format_metric(v, k) for v, k in zip(frame[duo[1]], frame["kind"], strict=True)
                ],
                "Difference": [
                    format_difference(v, k)
                    for v, k in zip(frame["difference"], frame["kind"], strict=True)
                ],
            }
        )

        return marked_table(
            shown,
            lambda i, c: "lead" if c and c == leaders[i] else "",
            justify={
                "Measurement": "left",
                duo[0]: "right",
                duo[1]: "right",
                "Difference": "right",
            },
        )

    mo.vstack(
        [
            mo.vstack([mo.md(f"### {airport} pickups"), scorecard_table(airport)])
            for airport in pickup_airports
        ]
    )
    return (scorecard_table,)


@app.cell(hide_code=True)
def _(duo):
    mo.md(
        f"The difference column is **{duo[1]} minus {duo[0]}**. A positive driver-side "
        "row means the second platform gives the driver more. A positive fare row means "
        "the second platform charges the rider more. The **green** cell in each row "
        "holds the better value. A row with no green cell has no better side: a higher "
        "median fare is neither a win nor a loss on its own."
    ).callout(kind="neutral")
    return


@app.cell
def _(by_year, duo, kpis, line_chart, pickup_airports, share):
    duo_payout = (
        by_year(
            kpis.filter(
                (pl.col("direction") == "pickup")
                & pl.col("platform").is_in(duo)
                & pl.col("airport").is_in(pickup_airports)
            )
        )
        .group_by("year", "platform")
        .agg(pl.col("med_driver_share").median().alias("payout_share"))
        .sort("year", "platform")
    )
    duo_share = (
        by_year(share.filter(pl.col("airport").is_in(pickup_airports)))
        .group_by("year", "platform")
        .agg(pl.col("trips").sum().alias("trips"))
        .with_columns((pl.col("trips") / pl.col("trips").sum().over("year")).alias("share"))
        .filter(pl.col("platform").is_in(duo))
        .sort("year", "platform")
    )
    mo.vstack(
        [
            mo.ui.altair_chart(
                line_chart(
                    duo_payout,
                    x="year",
                    x_kind="year",
                    y="payout_share",
                    colour_by="platform",
                    domain=duo,
                    title="Driver gross as a share of rider payment, dispatch airports",
                    x_title="Year",
                    y_title="Driver gross / rider payment (%)",
                    y_format=".0%",
                    height=250,
                )
            ),
            mo.ui.altair_chart(
                line_chart(
                    duo_share,
                    x="year",
                    x_kind="year",
                    y="share",
                    colour_by="platform",
                    domain=duo,
                    title="Share of airport trips, dispatch airports",
                    x_title="Year",
                    y_title="Share of trips (%)",
                    y_format=".0%",
                    height=250,
                )
            ),
        ]
    )
    return duo_payout, duo_share


@app.cell
def _(duo, duo_payout, duo_share):
    payout_wide = duo_payout.pivot(on="platform", index="year", values="payout_share").sort("year")
    share_wide = duo_share.pivot(on="platform", index="year", values="share").sort("year")
    ahead = payout_wide.filter(pl.col(duo[1]) > pl.col(duo[0]))
    PAYOUT_LEAD_FROM = ahead["year"].min() if ahead.height else None
    SHARE_START = share_wide.row(0, named=True)
    SHARE_END = share_wide.row(-1, named=True)
    log.info("payout lead for %s from %s", duo[1], PAYOUT_LEAD_FROM)
    return PAYOUT_LEAD_FROM, SHARE_END, SHARE_START, payout_wide


@app.cell(hide_code=True)
def _(PAYOUT_LEAD_FROM, SHARE_END, SHARE_START, duo, payout_wide, scorecard):
    _latest = payout_wide.row(-1, named=True)
    _curb = scorecard.filter(pl.col("metric") == "med_curb_wait_s")
    _pool = scorecard.filter(pl.col("metric") == "pool_request_rate")
    mo.md(f"""
    ### The result

    #### {duo[1]} pays the larger share and holds the smaller market

    The payout share of {duo[1]} went above the payout share of {duo[0]} in
    {PAYOUT_LEAD_FROM}, and it stays above. In {_latest["year"]} the two figures are
    **{_latest[duo[1]]:.1%}** and **{_latest[duo[0]]:.1%}**. Over the same archive the
    share of trips for {duo[1]} moved from **{SHARE_START[duo[1]]:.1%}** to
    **{SHARE_END[duo[1]]:.1%}**.

    A larger slice for the driver therefore did not buy position. That result points
    away from pay, and towards the parts of the product that this data can only
    describe: matching, dispatch, and the curb.

    #### The two airports are two different products

    Read the tables above one at a time. The fare, the fare for each mile and the tip differ between the airports by
    more than they differ between the platforms. One network-wide target reads both
    airports wrong.

    #### Two rows are not a service measurement

    The curb wait for one platform sits on an exact minute, which is a sign of minute-level rounding. Read the direction, not
    the size. The shared-ride request rate is near zero for one platform, so the pool
    rows compare a live product against a closed one.
    """)
    return


@app.cell(hide_code=True)
def _(duo, quality):
    _q = quality.filter(pl.col("platform").is_in(duo)).with_columns(
        (pl.col("invalid_rows") / pl.col("trips")).alias("invalid_rate")
    )
    mo.vstack(
        [
            mo.md("### The same two platforms, as data sources"),
            mo.ui.table(
                _q.select(
                    "platform",
                    "trips",
                    pl.col("on_scene_coverage").round(4),
                    pl.col("invalid_rate").round(4),
                    "neg_to_scene",
                    "neg_curb_wait",
                    "nonpos_fare",
                    "nonpos_miles",
                ).sort("trips", descending=True),
                selection=None,
                pagination=False,
            ),
            mo.md(
                "A comparison of the two platforms is also a comparison of two reporting "
                "practices. One reports the driver-arrival time for the full archive. The "
                "other started in 2025. One files rows with a negative curb wait. The "
                "other files none, because it files no curb wait at all. Read the "
                "difference in the invalid rate as a property of the filing, not of the "
                "service."
            ).callout(kind="warn"),
        ]
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 8 · The five questions

    These are the questions the work exists to answer. Each answer below is computed
    for the platform in the selector, from the same tables, by the same method. Change
    the selector and every number changes with it.

    Two of the five have no answer in this data. The section says so and names the
    field that is missing, because a proxy that resembles an answer is worse than a
    gap.
    """)
    return


@app.cell
def _(live_platforms):
    subject = mo.ui.dropdown(
        options=live_platforms,
        value=live_platforms[0],
        label="Answer the questions for",
    )
    subject
    return (subject,)


@app.cell
def _(
    benchmark,
    compare_platforms,
    hourly,
    kpis,
    live_platforms,
    pickup_airports,
    subject,
):
    focus = subject.value
    scoreboard = benchmark(compare_platforms(kpis, live_platforms, pickup_airports), live_platforms)
    focus_hours = (
        hourly.filter((pl.col("platform") == focus) & pl.col("airport").is_in(pickup_airports))
        .select("airport", "hour", "trips", "share_of_day", "incentive_rate")
        .sort("airport", "hour")
    )
    log.info("answering for %s across %s", focus, ", ".join(pickup_airports))
    return focus, focus_hours, scoreboard


@app.cell(hide_code=True)
def _(focus, format_metric, live_platforms, marked_table, pickup_airports, scoreboard):
    def target_rows(airport: str) -> tuple[pl.DataFrame, list[str]]:
        """Build one airport's target table and mark each row.

        A row is a lead where the selected platform already sets the target, and
        behind where it does not. The largest relative gap becomes the worst row.

        Args:
            airport: Airport code.

        Returns:
            The table, and the mark for each row in the same order.
        """
        frame = (
            scoreboard.lazy()
            .filter((pl.col("airport") == airport) & (pl.col("better") != ""))
            .with_columns(
                pl.when(pl.col("better") == "high")
                .then(pl.col("target") - pl.col(focus))
                .otherwise(pl.col(focus) - pl.col("target"))
                .alias("gap")
            )
            .with_columns(
                (pl.col("gap").abs() / pl.col("target").abs().replace(0, None)).alias("relative")
            )
            .with_columns(
                pl.when(pl.col("gap").abs() < 1e-9)
                .then(pl.lit("lead"))
                .when(pl.col("relative") == pl.col("relative").max())
                .then(pl.lit("worst"))
                .otherwise(pl.lit("behind"))
                .alias("mark")
            )
            .collect()
        )
        shown = pl.DataFrame(
            {
                "Measurement": frame["label"],
                focus: [
                    format_metric(v, k) for v, k in zip(frame[focus], frame["kind"], strict=True)
                ],
                "Best": [
                    format_metric(v, k) for v, k in zip(frame["target"], frame["kind"], strict=True)
                ],
                "Held by": frame["target_platform"].fill_null(""),
                "Gap": [
                    format_metric(v, k) for v, k in zip(frame["gap"], frame["kind"], strict=True)
                ],
            }
        )
        return shown, frame["mark"].to_list()

    def target_table(airport: str) -> mo.ui.table:
        """Render one airport's target table with the rows marked by colour.

        Args:
            airport: Airport code.

        Returns:
            The table.
        """
        shown, marks = target_rows(airport)
        return marked_table(
            shown,
            lambda i, c: marks[i],
            justify={
                "Measurement": "left",
                focus: "right",
                "Best": "right",
                "Held by": "left",
                "Gap": "right",
            },
            bold_columns=(focus,),
        )

    mo.vstack(
        [
            mo.md(f"### Targets for {focus}"),
            mo.md(
                "The target is the best value that any live platform reaches now, at "
                f"that airport, over the same window. A gap of zero means {focus} sets "
                "the target. Only the measurements with a better side appear here. A "
                "higher median fare is neither a win nor a loss on its own, so the table "
                "leaves it out."
            ),
            mo.md(
                f"A **green** row means {focus} holds the target. An **amber** row means "
                "another platform holds it. The **deepest** row is the largest gap, "
                "measured against the size of the target. Change the platform in the "
                "selector and the colours follow it."
            ).callout(kind="neutral"),
            *[
                mo.vstack([mo.md(f"#### {airport}"), target_table(airport)])
                for airport in pickup_airports
            ],
            mo.md(f"Compared platforms: {', '.join(live_platforms)}.").callout(kind="neutral"),
        ]
    )
    return target_rows, target_table


@app.cell(hide_code=True)
def _(COMPARABLE_FROM, focus, focus_hours, format_metric, pickup_airports, scoreboard):
    def value(airport: str, metric: str) -> str:
        """Read one measurement for the selected platform.

        Args:
            airport: Airport code.
            metric: Column name from METRICS.

        Returns:
            The formatted value.
        """
        row = scoreboard.filter((pl.col("airport") == airport) & (pl.col("metric") == metric))
        if not row.height:
            return "not reported"
        return format_metric(row[focus][0], row["kind"][0])

    _night = (
        focus_hours.filter(pl.col("hour").is_in([0, 1, 2, 3, 4]))
        .group_by("airport")
        .agg(pl.col("share_of_day").sum().alias("night"))
        .sort("airport")
    )
    _peak_bind = focus_hours.sort("incentive_rate", descending=True).row(0, named=True)
    _night_text = ", ".join(
        f"{r['airport']} {r['night']:.1%}" for r in _night.iter_rows(named=True)
    )
    _pricing = "\n".join(
        f"- **{a}**: fare {value(a, 'med_fare')}, fare for each mile "
        f"{value(a, 'med_fare_per_mile')}, driver gross {value(a, 'med_driver_gross')}, "
        f"payout share {value(a, 'med_driver_share')}, "
        f"{value(a, 'med_gross_per_engaged_hour')} for each engaged hour, "
        f"minimum-pay binding rate {value(a, 'incentive_rate')}"
        for a in pickup_airports
    )
    _modes = "\n".join(
        f"- **{a}**: shared-ride requests {value(a, 'pool_request_rate')}, "
        f"curb wait {value(a, 'med_curb_wait_s')}"
        for a in pickup_airports
    )

    mo.accordion(
        {
            "1 · How to determine pricing and earnings for airport rides": mo.md(f"""
    **What the data gives for {focus}**

    {_pricing}

    **How to read it.** The platform does not set the driver side alone. The NYC
    minimum-pay formula fixes a floor for each trip from the miles, the minutes and the
    `utilization rate`. The fare has no part in that floor. The binding rate above is
    the share of pickups where the floor pays more than the rider paid.
    A high binding rate means the regulation sets the price of supply at that airport,
    not the pricing team.

    The fare for each mile separates the airports more than it separates the platforms,
    so price each airport as its own market. §5.3 shows the fare rising faster than the
    driver gross across the archive, which is the trend any pricing change lands on top
    of.

    **What the data cannot give.** No surge multiplier, no rider-side test, no bonus
    ledger, and no cost line. Inside a platform, model the difference between the
    fare-derived pay and the formula floor for each trip. Then measure the share of
    airport supply that the floor holds.
        """),
            "2 · Which driver segment grows airport supply, and how bonuses interact": mo.md(f"""
    **Not answerable from this data.** The file has no driver identifier. It gives no
    tenure, no home borough, no trip history and no bonus record. Any segment described
    from this dataset is an invention.

    **What the data gives instead.** Supply in total, by hour and by airport. For
    {focus}, the hours from midnight to 05:00 hold {_night_text} of the pickups at each
    airport. The binding rate peaks at {_peak_bind["airport"]} in hour
    {_peak_bind["hour"]}, at {_peak_bind["incentive_rate"]:.1%}. Supply is hardest to
    hold in those hours, so a bonus lands there.

    **The bonus point.** A bonus and the minimum-pay floor pay for the same thing, and
    this data cannot separate them. A trip where the driver gross exceeds the rider
    payment can be either one. Read the binding rate as the floor, because §6 shows the
    formula produces that result without any bonus.

    **What to instrument.** Driver identifier, tenure band, acceptance rate, and bonus
    payments as a separate field. With those, segment on airport share of a driver's
    week, then test a bonus against the hours above.
        """),
            "3 · Which airports underperform, on which measurements, and against what targets": mo.md(f"""
    **The measurements.** The table above the accordion is the answer. It holds the
    value for {focus}, the best value any live platform reaches now, and the gap.

    **The targets.** Set each target at the current best, not at a round number.
    Another operator reaches that value at the same airport, in the same window, under
    the same regulation and the same weather. The target is therefore demonstrated.

    **Classification.** Rank the airports by the size of the gaps, not by the level of
    the measurements. §5.3 shows the airports differ by more than the platforms do, so
    a network-wide target reads one airport wrong.

    **Monitoring.** The censoring rule in §5.3 matters more than the measurements. The
    last months of the archive are thin, because the filings still arrive. A dashboard
    that reads the last two months as a trend reports publication lag. Compare each
    month against the same month one year earlier. The seasonal swing is larger than
    most of the gaps in the table.
        """),
            "4 · What drives cancellations, who cancels, and what reduces them": mo.md("""
    **Not answerable at all.** Every public trip file holds completed trips only. There
    is no cancelled-trip record, no rider identifier and no driver identifier. Nothing
    in this dataset separates a cancellation from a trip that never appears.

    **The nearest legal signal.** Unmet demand. The request-to-pickup delay is in the
    file, and an arrival bank with no rise in pickups is visible in the hourly profile.
    Both indicate friction. Neither is a cancellation rate.

    **What to instrument.** Record a cancellation event with five fields: the
    timestamp, the side that cancelled, the seconds from the request, the stated
    reason, and the queue position at the airport. The queue position then shows
    whether a cancellation follows the wait or the fare.
        """),
            "5 · How riders and drivers use ride modes at airports": mo.md(f"""
    **What the data gives for {focus}**

    {_modes}

    **The finding.** Shared rides have gone from airport pickups for the live
    platforms. The rate is near zero and the trend chart in §5.3 shows it fall rather
    than assert it. The archive also holds the counterexample: a closed licensee ran a
    pooling-first product and reached a request rate above 60% at JFK, in §7.1. The
    behaviour is therefore a product decision, not a limit on rider demand.

    **Curb wait.** The reporting rule took effect in {COMPARABLE_FROM:%b %Y}. The value
    above is comparable between platforms from that month only. A median that sits on
    an exact minute is a sign of minute-level rounding, so read the direction and not
    the size.

    **What the data cannot give.** The public schema holds no premium tier, no vehicle
    class beyond the wheelchair flag, and no seat count. A mode analysis past shared
    against standard needs the product tier on each trip.
        """),
        }
    )
    return


@app.cell(hide_code=True)
def _(SOURCES, TOOLS, link_list):
    mo.vstack(
        [
            mo.md("## 9 · Sources and tools"),
            mo.md(
                "Every figure in this notebook comes from the first item below. The "
                "rules in §6 come from the two TLC rule pages."
            ),
            mo.md("### Data"),
            link_list(SOURCES),
            mo.md("### Libraries"),
            link_list(TOOLS),
        ],
        gap=0.7,
    )
    return


if __name__ == "__main__":
    app.run()