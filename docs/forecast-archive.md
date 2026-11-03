# Forecast archive and realized accuracy (#36)

Forecasts displayed in an experimental notebook are not automatically evidence
of what was predicted at the time. This feature explicitly archives issued
forecasts, then evaluates them against their own frozen baskets once the target
month is closed. It reuses the existing persistence, trend and Ridge experiment.

## Explicit issuance and read-only evaluation

```powershell
.\.venv\Scripts\python.exe src/forecast_archive.py issue
.\.venv\Scripts\python.exe src/forecast_archive.py evaluate
.\.venv\Scripts\python.exe src/forecast_archive.py evaluate --target-start 2026-01-01 --target-end 2026-12-31
```

`--root` selects a data root. Issuance creates private JSON files under
`data/processed/forecast_archive/`, which is covered by the existing Git ignore.
Evaluation reads them without changing forecasts or source CSVs. No live price
collection, scheduling, trading or notification is triggered by these commands.
The prediction notebook's archive section is also strictly read-only.

Issuance uses the actual local clock and excludes future-dated observations.
It trains on completed months only. The origin is the last completed month-end,
and the target is the following calendar month-end (one-month horizon). A current
forecast is archived only while its target month has not closed. Insufficient
recent data yields no archive file; Ridge can remain unavailable while both
simple methods are saved. Defaults are 12 training pairs and a 45-day freshness
limit, configurable with `--min-train` and `--max-age-days`.

## Contents and immutable revisions

One record contains all three method values for one category, origin and revision:

- Actual emission time, information cutoff, origin, target and horizon.
- Category and complete frozen item identities, equal-item weights and positive
  unit prices at the exact common observed base date.
- Training-pair count and last training target, method parameters and library versions.
- Hashes of relevant source files and the available price/identity inputs.
- Persistence/trend values and Ridge when trainable; missing model values remain
  explicit JSON nulls. The fitted model itself is not serialized.
- A logical archive ID and payload-integrity hash.

Origin, category, issue kind and revision form the logical key. Repeating the
same calculation with unchanged inputs/code/settings reuses the original record
and emission timestamp. A later invocation without new data does not rewrite it.
Changing data, basket, settings, dependencies or relevant code at that same key
raises an error: explicitly use `--revision 2` (then 3, etc.) to keep a revised
forecast alongside its original. Revisions are never silently pooled in scores.
Adding genuinely available observations can require a revision even when the
numerical forecast happens to remain the same.

Writes publish a completed temporary file exclusively (non-replacing rename on
Windows; exclusive hard link on other platforms). Concurrent identical writers
reuse the existing record; conflicting writers cannot overwrite it. Each record
is atomic independently: a failed batch may leave earlier category records saved,
and a retry reuses those records. Temporary files are not read as forecasts.
Existing files with integrity errors are rejected, not repaired automatically.
These checks protect workflow immutability and accidental corruption, not against
a person deliberately editing files and recomputing hashes.

To explicitly simulate historical information:

```powershell
.\.venv\Scripts\python.exe src/forecast_archive.py issue --retrospective-as-of 2025-06-15
```

The actual emission timestamp is still recorded, but the record is labeled
`retrospective` with its historical information cutoff. It is never counted as
a real forecast emitted in 2025. Future simulation cutoffs are rejected. The
current tracked basket may introduce retrospective selection bias, just as in
the original experiment; simulations cannot establish live forecasting accuracy.

## Target observation and coverage

The stored target date labels the month-end day; its close is the final instant
of that day in machine-local time. As in the experiment, the current month is
never treated as completed, including on its final afternoon. The realized value
is computed only after that close, using the **archived basket and base**, not
today's quantities or basket. No price after the target close is substituted.

For each frozen item, take the latest non-estimated valid price at or before
the close. All items must satisfy the archived freshness limit measured at the
close. Sum their normalized indices with the stored weights. Zero realized prices
are valid; absent or stale prices remain unavailable and do not become zero.
Removed items remain represented through archived identities, including legacy
others-price classification in the command-line evaluator.

States are `pending` (target not closed or issue not yet emitted at the evaluation
cutoff), `evaluated`, and `unavailable` (target closed but required prices missing
or stale). An unavailable target can become evaluable if a valid historical
observation is later supplied; evaluation is recomputed read-only, never a cached
rewrite of the forecast. Correcting historical prices may change realized errors.
The source schema has observation timestamps, not ingestion timestamps: later
backfills/corrections cannot prove what an external observer could have known at
the time. The archive records the exact issuance input hash, but does not claim
an independent audit of upstream data provenance.

## Comparing errors

Detail rows expose issue kind, revision, basket hash, code hash, parameter/software
hash, dates and availability. MAE and RMSE are in index points and support zero
targets. `baseline_common` uses dates where both simple methods and the target
are available; `model_common` uses only dates where Ridge is also available, and
compares all three methods on precisely those same rows.

Results are grouped by issue kind, category, revision, basket, code and settings
version. They are not pooled across incompatible baskets/versions or duplicate
revisions. Tables include sample counts and first/last target dates. The optional
target-period filter applies identically to every method. A small sample remains
experimental; these errors are not a promise of future performance.
