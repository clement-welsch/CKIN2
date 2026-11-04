# ByMykel source register and review procedure (#51)

| Field | Reviewed value |
|---|---|
| Source / author | ByMykel / CSGO-API |
| Repository | https://github.com/ByMykel/CSGO-API |
| Reference revision | b014e92bc37f4143ead2cb1af26aa85f2c3d6688 |
| License reviewed | MIT, Copyright (c) 2023 ByMykel |
| Review date | 2026-11-04 |
| Intended inputs | English item identities / exact market listing metadata; skins_not_grouped.json or category-specific JSON selected and reviewed locally |
| Current integration | Optional reviewed local releases, not an automatic API call; no upstream catalog, code or images bundled |
| Local provenance | data/market/releases/*.json: source_url, source_revision, source_updated_at, collected_at, scope, source_id and exact variant metadata |
| Local adaptation | Human-reviewed conversion to CKIN2 category/name-based identities and listing schema; no upstream source-code adaptation |
| Notices | THIRD_PARTY_NOTICES.md and licenses/ByMykel-CSGO-API-MIT.txt |

The reference commit pins the license review; it must not be substituted for the
actual dataset revision in a release. No imported release was present in the
local environment inspected for this implementation. Other installations can
have different releases. The dashboard lists their declared source/revision
without exposing item names or quantities and marks unreviewed revisions.

## Usage scenarios

- Personal/training use: retain source/revision information and the notice with
  local covered copies. Being noncommercial does not remove license conditions.
- Public repository or packaged local application: include notices/full MIT
  text when distributing covered code/data or substantial portions. Do not
  commit private exports; check the exact files to be redistributed.
- Hosted dashboard: keep visible attribution and distribute notices with any
  downloadable covered portions. API access terms and rights for other assets
  still require separate review; MIT is not a service availability guarantee.
- Commercial use: the reviewed MIT software text permits commercial use under
  its conditions. This review does not clear Valve assets/trademarks, other
  sources or a future redistribution dataset. Review the actual release and
  usage before expanding scope.

## Review checklist for a new import, version or publication

1. Pin the upstream commit and exact source files; record retrieval date and
   transformations in local provenance. Do not use an unversioned main URL as
   the only reproducibility reference.
2. Read that revision's license and check whether it covers the selected
   materials. Recheck upstream notices for third-party content.
3. Keep the author/copyright and full required license text with covered copies;
   update the register and dashboard reference when the review changes.
4. Separately assess images, descriptions and other Valve-origin materials.
   Do not import/display them merely because their URLs occur in a catalog.
5. Review intended personal, public, hosted or commercial distribution. Record
   uncertainties before publishing; a link alone does not satisfy all licenses.
6. Check the Sources and licenses page works offline and still displays the
   correct upstream author and reference. Source changes require this check in
   PR review. This is an engineering record, not blanket legal clearance.
