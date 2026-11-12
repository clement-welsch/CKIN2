# Cloud inventory snapshots

CKIN2 can publish processed data into a folder synchronized by Google Drive,
Dropbox, OneDrive or another desktop cloud client. Configure that client first;
CKIN2 does not authenticate to a provider or upload through its API. A local
folder alone does not provide cloud storage. No provider credentials are stored
in CKIN2. At M2I you can also download the ZIP through the provider's website,
without installing its sync client.

## At home

Finish inventory edits and price collection first. Do not edit data or run
collectors during publication: this command does not lock other writers.
Publish after each update you want to share:

```powershell
python src/cloud_inventory.py publish --folder "C:\Users\Clement\Dropbox\CKIN2"
```

Replace the example with your actual synchronized folder. The source defaults
to this repository; `--root PATH` selects another root containing
`data/processed`. All processed CSVs are included recursively: inventory, prices,
transactions, historical snapshots and forecast CSVs. Raw exports, settings,
logs, credentials and code are excluded. Archives contain personal data; keep
the destination private.

Publication creates a unique dated ZIP without replacing previous versions.
Only completed ZIPs are ready for use; ignore `.partial` files. Wait for the
cloud client's upload confirmation before leaving. CKIN2 cannot confirm that
the remote upload completed. Old archives can be removed manually when no
longer needed; there is no automatic retention or two-way merge.

## At M2I

Download the latest completed `ckin2-*.zip` (UTC publication time in its name).
Use a new destination for each snapshot:

```powershell
python src/cloud_inventory.py restore "C:\Users\Clement\Downloads\ckin2-EXAMPLE.zip" --destination "D:\CKIN2-cloud\2026-11-12"
python src/dashboard.py --root "D:\CKIN2-cloud\2026-11-12"
python src/update_portfolio.py school --root "D:\CKIN2-cloud\2026-11-12"
```

Replace the archive and destination paths with your own. Restore verifies file
checksums and rejects existing destinations, so it cannot silently overwrite
local changes. `cloud_manifest.json` records the UTC publication time. This is
the copy's publication time, not the time of its last inventory or price update;
check the price dates and snapshot dates in the dashboard too.

The project and its Python dependencies must also be available at M2I. The
dashboard and school report use the restored copy locally and require no Steam
connection. Repeat download/restore to see subsequent publications. Edit and
publish from one main computer to avoid competing inventories. This feature
shares snapshots; it does not continuously synchronize edits or run collection
when the home computer is off.
