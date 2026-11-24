# OParl endpoint registry: what the servers actually do

Measured 2026-11-24, read-only. The OParl community keeps a registry of German
municipal council-data endpoints (`OParl/resources`, `endpoints.yml`, last pushed
2024-02-11). Nobody has checked in years whether those endpoints still answer, or
whether they do what the specification says. This does.

**127 unique URLs behind 141 `url:` lines. 95 answer today, 32 are broken.**

This is not a judgement about OParl adoption — it is a measurement of the installed
base, and it is the reason a generic OParl client is harder to write than the spec
suggests.

## Method

`probe.py` fetches each entry URL (10 workers, 103 s wall) and counts a server as
alive **only if the body is an actual OParl System object** (`type` ending in
`/System`, or an `oparlVersion` field). HTTP 200 plus valid JSON is not enough:
five servers answer 200 with an OParl `Error` object.

Why the registry is not the population: endpoints that exist but were never
registered are absent from it entirely (e.g. more! Rubin hostings on gremien.info,
several SD.NET RIM hostings). So "95 alive" is a floor on the live OParl base, not
a count of it.

## Headline findings

| Measured | Consequence |
|---|---|
| **0 of 95** expose any collection at the system root | The spec's own example paths are not what the installed products do. |
| **86 of 95** answer only through the singular links the **Body object itself advertises** (`.../oparl/body/EUV/meeting`, not `.../meetings`) | A client must read the links the vendor publishes, not guess plural paths. |
| `created_since` honoured by **1** server; rejected with 400 by 64, by 401 by 3, by 403 by 2; **silently ignored** by 13 | Incremental sync by date is not available on almost any server. A server that silently ignores a filter and returns everything is the dangerous case: it looks like success. |
| `modified_since` honoured by **1** | Same. |
| `limit` ok on 6, ignored on 11, unmeasurable on 69 | Page size cannot be assumed. |
| `offset` ignored on 17 | Offset paging re-delivers page one forever on those servers. |
| `page2` differs on 7, same-or-unmeasurable on 79 | Paging mode must be probed per endpoint, not configured per vendor. |
| Licence declared by the server itself: **6 of 95** | 89 servers say nothing about rights. Silence is not permission. |
| Vendors: 75 SD.NET RIM, 10 more! Rubin, 5 SOMACOS (three versions), 2 CC e-gov | The "every vendor behaves differently" problem is mostly one vendor's behaviour, measured. |

Of the 32 broken: 9 host gone (DNS), 6 other, 5 HTTP 200 with an Error body, 4 404,
4 timeout, 2 HTTP 500, 1 ASP database error, 1 TLS failure.

## What this file refuses to claim

- `unmeasurable` means **no collection was read at all on that route** — not that the
  server ignores the parameter. An earlier pass lumped the two together and printed
  "77 servers ignore `limit`", which was an artifact of my own path resolution.
- `page2_same_or_unmeasurable` is not proof of broken paging: a one-page collection
  returns the same items by definition.
- One probe per server, one collection per server. Behaviour varies per installation,
  and a single 20 s timeout can look like a dead server.
- The 2024 registry is not the population (above).

## Files

- `endpoints.yml` — the input, from the OParl community registry (their data, not mine)
- `probe.py` — the capability probe; read-only GETs, identifying User-Agent
- `registry_check.py` — driver over the registry file
- `registry_status.json` — full per-URL record, machine-readable
- `REGISTRY_STATUS_2026-11-24.md` — the same findings as prose

Reproduce: `python3 registry_check.py` (fetches `endpoints.yml` and probes it).
Everything here is a measurement of public servers, made with GET requests.
