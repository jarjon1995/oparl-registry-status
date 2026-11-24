# OParl endpoint registry: live status, measured 2026-11-24

Input: OParl/resources `endpoints.yml` (repo last pushed 2024-02-11); 127 unique URLs behind 141 `url:` lines.
Method: `probe.py` read-only GETs, 10 workers, wall 103.3 s. A server counts as alive only if the body is an actual OParl System object (`type` ends with `/System`, or `oparlVersion` is present). HTTP 200 plus valid JSON is not enough - several vendors answer 200 with an Error object.

## Headline
- **95 of 127 endpoints answer today; 32 are broken.**
  - 9: host gone (DNS)
  - 6: other
  - 5: HTTP 200 with an Error body
  - 4: HTTP 404
  - 4: timeout
  - 2: HTTP 500
  - 1: ASP database error
  - 1: TLS failure
- OParl version declared by the server: 75 x https://schema.oparl.org/1.1/, 20 x https://schema.oparl.org/1.0/.
- Licence declared by the server itself: 6 of 95 (89 declare none).
- Vendors (by System `vendor` URL): 75 x https://www.sitzungsdienst.net/; 10 x https://www.more-rubin.de/; 2 x https://www.somacos.de?oparl=v1.6.1; 2 x https://www.somacos.de?oparl=v1.5.4

## How collections are actually reached - the part that costs people weeks
- **0** of 95 expose any collection at the system root.
- **86** answer only through the singular links the **Body object itself advertises** (e.g. `.../oparl/body/EUV/meeting`, not `.../meetings`).
- **9** returned a System object but no collection on the routes tried.
- Plural paths under a body id (`/body/1/meetings`) give 400/404 or an error body on SOMACOS, SD.NET RIM and more! Rubin alike. The spec's own example paths are not what the installed products do.

## Parameter honesty, measured on the one collection each live server answered
- Systems with a parameter test run: 86.
  - created_since_honoured: 1
  - created_since_rejected_http_400: 64
  - created_since_rejected_http_401: 3
  - created_since_rejected_http_403: 2
  - created_since_silently_ignored: 13
  - created_since_unclear: 3
  - limit_IGNORED: 11
  - limit_ok: 6
  - limit_unmeasurable: 69
  - modified_since_honoured: 1
  - modified_since_rejected_http_400: 65
  - modified_since_rejected_http_401: 3
  - modified_since_rejected_http_403: 2
  - modified_since_silently_ignored: 12
  - modified_since_unclear: 3
  - offset_IGNORED: 17
  - offset_unmeasurable: 69
  - page2_differs: 7
  - page2_same_or_unmeasurable: 79

## What I refuse to claim
- `unmeasurable` means no collection was read at all on that route - NOT that the server ignores the parameter. My first pass lumped the two together and printed '77 servers ignore limit', which was an artifact of my own path resolution.
- `page2_same_or_unmeasurable` is not proof of broken paging: a one-page collection returns the same items by definition.
- One probe per server, one collection per server. Behaviour varies per installation, and a single 20 s timeout can look like a dead server.
- The 2024 list is not the population: endpoints that exist but were never registered (more! Rubin on gremien.info, RIM hostings) are absent from it entirely.

Files: `endpoints.yml` (input), `probe.py` (probe), `registry_check.py` (driver), `registry_status.json` (full per-URL record).
