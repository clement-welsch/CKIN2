# Optional local collection scheduling (#34)

No task is installed by importing modules, running tests or merging this feature.
Use the existing project virtual environment. Keep all settings and runtime files
under ignored `data/`; never commit personal exports or task histories.

## Prepare and run manually

```powershell
New-Item -ItemType Directory -Force data/runtime
Copy-Item config/collection.example.json data/runtime/collection.json
.\.venv\Scripts\python.exe src/scheduled_collection.py home --config data/runtime/collection.json --due
.\.venv\Scripts\python.exe src/scheduled_collection.py school
```

The first home command above performs a **real** collection if due. Review the
catalog and configuration first. School uses the unified read-only report: no
Steam, lock file, runtime journal, notification state or CSV writes.

Configuration fields:

| Field | Default | Meaning |
| --- | --- | --- |
| interval_minutes | 1440 | Minimum elapsed time between completed attempts |
| timezone | Europe/Paris | IANA timezone for readable journal timestamps |
| attempts | 3 | Maximum requests per listing, including the initial attempt (limit 10) |
| base_delay_seconds | 2 | Exponential wait before another temporary-error attempt |
| max_wait_seconds | 120 | Maximum individual wait inside a run; longer requests are deferred |
| stale_days | 2 | Age above which saved prices trigger a stale-data condition |
| persistent_failures | 3 | Consecutive non-successful runs before a persistent alert |
| notification | console | `console` or `none`; no external messaging connection |

Cadence uses elapsed UTC time, not a fixed local hour. A daily interval therefore
stays 24 hours across daylight-saving changes. `timezone` changes journal labels,
not the timestamps in existing market CSVs, which retain machine-local semantics.
Keep the machine timezone correct. The example is a polling cadence, not a promise
to run at midnight. Windows requires IANA timezone data; `tzdata` is included with
the project's pandas environment. Check `ZoneInfo('Europe/Paris')` when setting up.

`--due` skips work until the saved next-due instant. Omitting it explicitly forces
one attempt. A missed polling interval does not generate synthetic market rows:
the next invocation makes at most one current collection, not a replay of missed
days. Retry-After can move the next due time later than the normal interval.

## Install, disable or remove on Windows (manual, opt-in)

After preparing the local settings, run this yourself from PowerShell:

```powershell
.\scripts\register-collection-task.ps1
Get-ScheduledTask -TaskName "CKIN2 collection"
Disable-ScheduledTask -TaskName "CKIN2 collection"
# Re-enable explicitly when wanted:
Enable-ScheduledTask -TaskName "CKIN2 collection"
# Remove the task if no longer wanted:
Unregister-ScheduledTask -TaskName "CKIN2 collection" -Confirm
```

The registration script polls every 15 minutes while the current user is logged
on, using the existing environment and local config. It does not store passwords,
request elevation or overwrite an existing task. Task Scheduler settings avoid
overlap, allow a missed start when available and limit execution to two hours.
The kernel lock also protects manual `update_portfolio.py home` invocations.
Use these two entry points for writes; legacy low-level collector scripts are
not scheduling entry points and must not be launched concurrently.

If the PC is off, asleep or logged out, collection cannot happen. The task does
not wake the PC. Catch-up occurs at a later available poll; no historical price
is invented. Battery policies may delay or stop tasks according to Windows
defaults. If the run is stopped, the next invocation detects its active marker.
Offline runs make bounded attempts and record the failure once executed.

## Locks, retries and persistence

Both supported home entry points hold a kernel lock in
`data/runtime/collection.lock`. Its file stays in place intentionally; an old
file does not mean a live owner. Process exit, including a crash, releases the
OS lock automatically. A live process cannot be displaced just because it is
slow. If it is stuck, inspect and stop that process before retrying; do not
delete the lock file while a process is active.

The scheduled adapter uses Python's standard HTTPS client with a 12-second
request timeout and the shared Steam price parser. Connection failures, HTTP
408/429/5xx and invalid JSON responses get bounded exponential retries.
Other HTTP failures and valid responses without a usable price are not retried
in the same run. Catalog validation stops invalid mappings before collection.
Failed listings may be tried again at the next scheduled run to detect recovery.

Retry-After supports seconds and HTTP dates. The wait is never shortened to fit
the budget: a long wait defers the request and remaining listings for this run.
After the retry budget is exhausted, a short global cooldown also prevents
immediate requests for the next listing. Partial observations retain the shared
collector's existing per-file atomic persistence; reporting or snapshot failure
does not roll back successfully written prices. An interrupted batch is retried
on the next run; it is not resumed at the exact failed listing.

## Journal and notifications

- `collection-active.json`: start marker, allowing detection of an interrupted run.
- `collection-state.json`: last complete success, failure streak and next due time.
- `runs/*.json`: one atomic event per finished run, with start/end, updated/failed
  counts, price age/missing conditions, classified outcomes, failed stage names
  and planned next attempt. Retain or clean old event files manually while idle.

No raw HTTP payloads, full script output, exception messages, URLs, item names,
quantities or credentials are copied into this journal. Regular command output
can contain private portfolio details; do not publish captured terminal logs.
If state or config is malformed, the CLI reports a generic failure rather than
silently resetting the cadence. Restore it from a backup or inspect it locally.

Console alerts occur when status/stale/missing/persistent-failure conditions
change, including recovery. Repeated unchanged failures stay quiet apart from
the compact run summary. `notification=none` disables alerts, not the private
event journal. No email, webhook, chat or desktop notification is configured.
Scheduler exit codes remain 0/1/2; an active-lock skip returns 1. A polling skip
before the due time returns 0 and leaves the existing state unchanged.

The manual unified command keeps its existing 24-hour stale-price exit rule.
The scheduler's `stale_days` setting is an additional alert threshold; it does
not reclassify incomplete reports as successful.
