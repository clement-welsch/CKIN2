# Project contact and planned Free website

Tracking: [issue #103](https://github.com/clement-welsch/CKIN2/issues/103).

- Project contact email: `ckin2@free.fr` (created by the owner).
- Planned website: `ckin2.free.fr`, pending activation and hosting verification.
- Current dashboard: local Python server, bound to loopback.
- Current Google integration: desktop authorization and private snapshot upload,
  implemented for review in [PR #102](https://github.com/clement-welsch/CKIN2/pull/102).

The website is not deployed. A Free email address does not itself establish a
Google account or grant access to an existing private Drive folder. Contact
details in Google must be configured using options Google permits for the
account; OAuth ownership and support-email verification remain separate.

## Migration work

First verify the activated Free account's supported languages, HTTPS, Python
processes, background tasks, deployment method, storage and secret isolation.
Then select an architecture supported by those findings. Do not upload the
existing local Python server and assume it will run unchanged. A separate
backend or an explicitly limited static consultation interface may be needed.

The target experience distinguishes Steam identity verification from Google
authorization for storage. Before any private inventory is hosted, enforce
authorization for viewing data and triggering writes. Web OAuth redirects,
sessions, logout and cross-account isolation must be designed for the chosen
site; the current Desktop client and its account-bound local credentials must
not be copied to public hosting.

Keep the private Drive destination, tokens, client configuration, inventory
archives and Free account/deployment credentials out of Git and publicly served
directories. The public contact address and planned hostname above are project
information explicitly provided for documentation; they are not login secrets.

Validate with a test deployment, unauthorized-account checks, mobile display,
freshness indicators, backup and rollback. Issue #103 tracks delivery of the
deployment tutorial. The current French Google setup guide is already available
through **Configurer Google Drive** in the local dashboard (`/cloud-setup`) or
by opening `src/cloud_setup.html` offline.
