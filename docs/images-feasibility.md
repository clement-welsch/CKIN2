# Item-image feasibility decision (#86)

## Decision on 2026-11-09: no-go for automatic third-party image integration

The bounded review examined the actual ByMykel pinned weapon-skin metadata
used in [the catalog study](studies/2026-11-09-catalog-live.md). It contains image
URLs hosted by Valve's economy CDN. Those URLs are references, not a transfer
of rights, proof of exact wear/StatTrak imagery, cache permission or a guaranteed
stable asset API. No image was requested, cached, rendered or redistributed.

The source metadata's MIT text matches CKIN2's retained ByMykel notice. It does
not independently clear Valve-origin art. Primary documents reviewed:

- [Valve site terms](https://www.valvesoftware.com/en/legal), which distinguish
  limited personal downloads from redistribution;
- [Steam Subscriber Agreement, sections 2.D–G](https://store.steampowered.com/subscriber_agreement/),
  which addresses fan works, ownership and restrictions; it does not establish
  that this dashboard's asset extraction/cache/distribution is a qualifying work;
- [Valve video policy](https://store.steampowered.com/video_policy), which concerns
  videos and does not generally authorize distributing isolated game assets.

These documents are not treated as a ban on every conceivable personal use.
They also do not establish the intended application's caching/distribution rights
or exact-image contract. No authenticated asset export or separate permission
was provided. Cache headers, MIME/decoding safety and long-term URL availability
were therefore not asserted or measured by downloading assets.

| Category | Source/identity finding in this study | Cleared image coverage |
|---|---|---|
| Skins | Exact metadata variants have CDN URL candidates; exact visual variant and reuse/cache scope unverified | 0 integrated |
| Souvenir packages | Not established by the reviewed weapon-skin file | 0 integrated |
| Cases | No reviewed image source in this study | 0 integrated |
| Stickers | No reviewed image source in this study | 0 integrated |
| Charms | No reviewed image source in this study | 0 integrated |
| Agents | No reviewed image source in this study | 0 integrated |

The existing text identity, quantity, coverage and exact-item links remain fully
offline. #86 explicitly permits a documented no-go instead of an unauthorized
integration; there is no hidden page-load download or cache side effect.

A future go requires an identified authorized source/usage scope, dated cache and
attribution terms, exact variant mapping and measured category coverage. Only
then should an explicit preparation command populate an ignored local cache,
validate image format/size and expose fixed-size accessible thumbnails with a
fallback. That future implementation must test variant mismatch, missing or
corrupt cache, request failure, mobile layout and keyboard/accessibility behavior.
