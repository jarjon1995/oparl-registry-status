#!/usr/bin/env python3
"""OParl endpoint capability probe.

Given one OParl entry URL (a System object or its root), report what the
server can actually do, measured rather than assumed:

  - which collections answer at the top level, and which only under a body
  - whether limit / offset / page / since / modified-since are honoured
    (a server that silently ignores a parameter is the failure mode that
    makes naive scraping wrong: measured on mandari 23 Nov, every filter
    except page returned the same 100 items)
  - the licence the server itself declares
  - total item counts where the server reports them

Output is JSON on stdout. Nothing is written anywhere; all requests are
read-only GETs.

Usage: python3 probe.py <entry-url> [<entry-url> ...]
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "oparl-capability-probe/0.1 (read-only survey; contact: anselm@posteo.de)"
TIMEOUT = 20
COLLECTIONS = ("organizations", "people", "locations", "meetings",
               "agendas", "papers", "drafts", "files", "committees",
               "participations", "elections")


def get(url):
    """Return (status, parsed_json_or_None, raw_head, elapsed)."""
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(400_000)
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read(4000) if e.fp else b""
        status, parsed = e.code, None
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        return status, parsed, raw[:200].decode("utf-8", "replace"), time.time() - t0
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}", time.time() - t0
    try:
        return status, json.loads(raw), raw[:200].decode("utf-8", "replace"), time.time() - t0
    except Exception:
        return status, None, raw[:200].decode("utf-8", "replace"), time.time() - t0


def collection_of(payload):
    """Normalise the two shapes OParl servers use for a collection."""
    if not isinstance(payload, dict):
        return None
    if str(payload.get("type", "")).endswith("/Error"):
        # KISA measured 23 Nov answers EVERY path with HTTP 200 and an OParl
        # Error object; counting it as an empty collection made a dead server
        # look like it had all eleven collections.
        return None
    if "data" in payload and isinstance(payload["data"], list):
        items = payload["data"]
    elif "items" in payload and isinstance(payload["items"], list):
        items = payload["items"]
    elif "type" in payload and str(payload.get("type", "")).endswith("System"):
        return None
    else:
        return None
    paging = {}
    for k in ("pagination", "page", "total", "totalElements", "numberOfElements"):
        if k in payload:
            paging[k] = payload[k]
    return {"count": len(items), "paging": paging,
            "sample_id": (items[0].get("id") if items and isinstance(items[0], dict) else None)}


def probe(entry):
    out = {"entry": entry, "steps": []}
    st, sysobj, head, el = get(entry)
    out["system_status"] = st
    out["system_elapsed_s"] = round(el, 2)
    if not isinstance(sysobj, dict):
        out["fatal"] = f"no System object: {head[:160]}"
        return out
    # KISA trap measured 23 Nov: zv-kisa answers HTTP 200 with an ERROR
    # object {"debug","message","type"} that parses as JSON. A 200 status
    # and valid JSON do NOT make it a System object.
    typ = str(sysobj.get("type", ""))
    if not typ.endswith("/System") and "oparlVersion" not in sysobj:
        out["fatal"] = ("HTTP %s but body is not an OParl System object "
                        "(type=%r, keys=%s): %s" % (st, typ, sorted(sysobj)[:8],
                                                    head[:160]))
        return out
    out["system"] = {
        "name": sysobj.get("name"),
        "oparl_version": sysobj.get("oparlVersion"),
        "vendor": sysobj.get("vendor"),
        "product": (sysobj.get("product") or "")[:80],
        "license": sysobj.get("license"),
        "contact": sysobj.get("contactName"),
    }
    body_url = sysobj.get("body") or sysobj.get("bodies")
    # measured 24 Nov: SOMACOS writes the link as /oparl/Body with a capital B,
    # Session Online as /oparl/bodies. Any test on the literal string "bodies"
    # silently skipped the whole under-body leg for the 75 SOMACOS systems.
    if body_url:
        body_url = body_url.rstrip("/")
    out["system_keys"] = sorted(sysobj.keys())
    bodies = []
    if body_url:
        st2, b, _, _ = get(body_url)
        col = collection_of(b)
        if col:
            bodies = [i.get("id") for i in (b.get("data") or b.get("items") or [])
                      if isinstance(i, dict)]
        out["bodies_status"] = st2
        out["bodies_count"] = len(bodies)

    # --- top level vs under-body availability -----------------------------
    # base for collection paths. Measured 24 Nov: many vendors (SOMACOS,
    # more! Rubin, Session Online) omit the System object's "system" key
    # entirely, so falling back to the entry URL produced ".../oparl/system/
    # organizations" -> 404 and made every system look body-scoped. Strip the
    # trailing /system instead.
    base = sysobj.get("system") or entry
    base = base.rstrip("/")
    if base.endswith("/system"):
        base = base[: -len("/system")]
    avail, only_body = {}, {}
    for c in COLLECTIONS:
        st3, p, _, _ = get(f"{base}/{c}?limit=1")
        col = collection_of(p) if st3 == 200 else None
        if col:
            avail[c] = col["count"]
        else:
            only_body[c] = st3
    out["top_level_collections"] = avail
    out["top_level_missing_status"] = only_body

    # --- parameter honesty on one collection that does answer -------------
    # Many vendors (SOMACOS Session/SessionNet measured 23 Nov) answer
    # collections ONLY under a body: top level is 404 for all eleven.
    target = None
    for c in COLLECTIONS:
        if avail.get(c):
            target, url = c, f"{base}/{c}"
            break
    if target is None and bodies:
        # Measured 24 Nov again: the plural path under a body id is NOT how
        # more! Rubin and SOMACOS expose collections. The Body OBJECT itself
        # advertises singular links (meeting, paper, organization). Guessing
        # the plural path made 92 of 98 live systems look empty.
        stb, bobj, _, _ = get(bodies[0])
        links = {}
        if stb == 200 and isinstance(bobj, dict):
            for k, v in bobj.items():
                if isinstance(v, str) and v.startswith("http"):
                    links[k] = v
        out["body_advertised_links"] = sorted(links)
        for c in COLLECTIONS:
            for cand in (links.get(c.rstrip("s")), links.get(c),
                         f"{bodies[0].rstrip('/')}/{c}"):
                if not cand:
                    continue
                stx, px, _, _ = get(cand)
                colx = collection_of(px) if stx == 200 else None
                if colx:
                    target, url = c, cand
                    out["scoped_under_body"] = c
                    break
            if target:
                break
    if False:
        for c in COLLECTIONS:
            stx, px, _, _ = get(f"{bodies[0]}/{c}?limit=1")
            colx = collection_of(px) if stx == 200 else None
            if colx:
                target, url = c, f"{bodies[0]}/{c}"
                out["scoped_under_body"] = c
                break
    if target:
        tests = {}
        st_a, pa, _, _ = get(f"{url}?limit=1")
        st_b, pb, _, _ = get(f"{url}?limit=1&offset=1")
        st_c, pc, _, _ = get(f"{url}?limit=2")
        st_d, pd_, _, _ = get(f"{url}?limit=5&modified_since=2999-01-01T00:00:00Z")
        st_e, pe, _, _ = get(f"{url}?limit=5&created_since=2999-01-01T00:00:00Z")
        st_f, pf, _, _ = get(f"{url}?limit=1&page=2")
        ida = collection_of(pa) or {}
        idb = collection_of(pb) or {}
        idc = collection_of(pc) or {}
        idd = collection_of(pd_) or {}
        ide = collection_of(pe) or {}
        idf = collection_of(pf) or {}
        # Measured 24 Nov: a None count means no collection was read at all,
        # which is NOT the same as a parameter being ignored. Lumping them
        # together produced a flattering-looking "77 servers ignore limit".
        def tri(cond):
            return True if cond else ("unmeasurable" if ida.get("count") is None
                                      or idc.get("count") is None else False)
        tests["limit"] = {"limit1": ida.get("count"), "limit2": idc.get("count"),
                          "honoured": tri(ida.get("count") == 1 and idc.get("count") == 2)}
        tests["offset"] = {"id_limit1": ida.get("sample_id"),
                           "id_offset1": idb.get("sample_id"),
                           "honoured": (ida.get("sample_id") != idb.get("sample_id")
                                        if ida.get("sample_id") and idb.get("sample_id")
                                        else "unmeasurable")}
        # decisive: a filter set in the FUTURE must return zero items if the
        # server honours it; items coming back means the parameter was ignored.
        def verdict(st, col, base_count):
            if st in (400, 401, 403, 405):
                return "rejected_http_%s" % st
            if col is None:
                return "no_collection"
            if col.get("count") == 0:
                return "honoured"
            if col.get("count") == base_count:
                return "silently_ignored"
            return "unclear"
        base_c = (collection_of(pa) or {}).get("count")
        tests["modified_since"] = {"status": st_d,
                                   "count_with_future_filter": idd.get("count"),
                                   "verdict": verdict(st_d, idd, base_c)}
        tests["created_since"] = {"status": st_e,
                                  "count_with_future_filter": ide.get("count"),
                                  "verdict": verdict(st_e, ide, base_c)}
        tests["page"] = {"page2_count": idf.get("count"), "status": st_f,
                         "page2_id": idf.get("sample_id"),
                         "differs_from_page1": idf.get("sample_id") != ida.get("sample_id")}
        out["param_tests"] = {"collection": target, "tests": tests,
                              "paging_seen": ida.get("paging")}
    if bodies:
        st4, bp, _, _ = get(f"{bodies[0]}/meetings?limit=1")
        out["body_meetings_status"] = st4
        out["body_meetings_count"] = (collection_of(bp) or {}).get("count")
    return out


def main():
    entries = sys.argv[1:] or ["https://ratsinformation.stadt-koeln.de/oparl/system"]
    results = [probe(e) for e in entries]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
