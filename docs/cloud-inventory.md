# Cloud inventory snapshots

French step-by-step instructions are available from **Configurer Google Drive**
in the dashboard (`/cloud-setup`), or by opening `src/cloud_setup.html` directly.
The guide contains no private settings and does not require inventory files.
The project email and planned website migration are documented in the
[Free hosting plan](free-hosting-plan.md), tracked by issue #103. The current
desktop Google connection does not depend on the future website.

## Automatic publication

Once configured, publication runs after `update_portfolio.py home` (including
the dashboard's Steam refresh and scheduled collection), an applied Steam owner
import or visible capture, a Steam override rollback, and `process_categories.py`.
School mode and previews never publish. Manual edits in an editor are not
watched: run the home update afterwards. Failed validation never publishes.
Completed partial price collections publish the successfully updated data with
the existing coverage indicators. A failed cloud publication preserves local
updates, reports failure, and makes the home workflow return partial status.
It retries at the next update; manual retry is also available.

The archive includes processed CSVs and the two specific Steam state JSONs
`steam_inventory_override.json` and `steam_inventory_visible.json`. These are
needed to reproduce effective owner quantities and visible captures at M2I.
Other JSON files, import rollback backups, runtime settings and credentials are
excluded. Restored copies are intended for consultation; rollback of an import
requires its original local backup.

### Direct Google Drive connection

This mode uploads through the Drive API; a local Drive folder is not required.
The folder link alone does not grant access. Initial setup requires a Google
Cloud project with the Drive API and Google Picker API enabled, an OAuth consent
configuration, and a downloaded **Desktop app** OAuth client JSON. If the app is
in testing, add your Google account as a test user. Google's testing-mode token
lifetime can require reconnection; use an appropriate production configuration
for unattended long-term use. Do not bypass Google's consent screen.

1. Follow Google's [desktop OAuth setup](https://developers.google.com/identity/protocols/oauth2/native-app)
   and [desktop folder picker](https://developers.google.com/workspace/drive/picker/guides/desktop-mobile-picker).
2. Keep the downloaded client JSON under `.secrets/` or outside the repository.
3. Install optional dependencies and connect:

```powershell
python -m pip install -r requirements-cloud.txt
python src/google_drive_cloud.py connect --client-secrets ".secrets/client_secret.json"
```

Enter your folder link in the masked prompt, then authorize Google in your
browser and select that same folder. If a private target has already been set
locally, no prompt is needed. The flow uses OAuth state, PKCE, a loopback callback
and only `drive.file` access to explicitly granted files. CKIN2 verifies that the
selected folder accepts uploads before enabling automatic publication.

No link, folder ID or token belongs in code, README examples, PR descriptions or
GitHub secrets. Runtime files live under Git-ignored `data/runtime/`; the folder
ID and authorization are protected with account-bound DPAPI on Windows (mode
0600 on POSIX). The private target is likewise excluded. Do not copy runtime
files to M2I or enable HTTP/OAuth debug logging. This protects local credential
storage; it does not provide a multi-user login or encrypt the uploaded ZIP.

Drive uploads are confirmed only after Google returns matching size and MD5
checksum. Failure messages omit raw Google responses, folder IDs and tokens.
Local `data/runtime/cloud-publication.json` records attempt time and outcome.
There is no background retry loop, automatic archive deletion or two-way merge.
An ambiguous timeout may leave an uploaded archive; a later retry can create a
second dated copy. Existing archives are never overwritten or made public.

```powershell
python src/google_drive_cloud.py publish
python src/google_drive_cloud.py disconnect
```

Disconnect disables publication and removes the locally stored authorization.
To revoke Google access completely, remove CKIN2 from your Google account's
third-party connections. Steam login is a separate feature: it identifies a
Steam account and cannot grant access to Drive. No Steam login is added here.

### Existing synchronized folder

Alternatively, configure a local folder already synchronized by any provider:

```powershell
python src/cloud_inventory.py configure --folder "C:\path\to\synced\CKIN2"
python src/cloud_inventory.py configure --disable
```

Use an existing absolute folder path. If the drive disappears, publication fails
instead of silently creating an unsynchronized replacement. This mode reports
`ready_for_sync`, not confirmed remote upload. The client must finish syncing.

## Manual publication and retrieval

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
`data/processed`. All processed CSVs and the two Steam state JSONs described above
are included: inventory, prices, transactions, historical snapshots and forecast
CSVs. Raw exports, settings,
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
