#!/usr/bin/env python3
"""Live-status check of the OParl endpoint registry.

Reads endpoints.yml (the OParl/resources list, last touched 2024-02-11),
deduplicates it, and probes every entry with probe.py's probe() to record
what the server answers TODAY. Output: registry_status.json with one record
per unique URL plus a summary. Read-only GETs only.
"""
import json, re, sys, time, concurrent.futures as cf
import probe

BUDGET_S = 210

def load():
    t = open("endpoints.yml").read()
    # entries are "- title: ... url: ..." blocks; split on list items
    blocks = re.split(r"\n- ", t)
    out = {}
    for b in blocks:
        m = re.search(r"^\s*url:\s*(\S+)", b, re.M)
        if not m:
            continue
        url = m.group(1).strip().strip('"\'')
        ti = re.search(r"^\s*title:\s*(.+)$", b, re.M)
        title = ti.group(1).strip() if ti else ""
        out.setdefault(url, title)
    return out

def main():
    urls = load()
    print(f"unique urls: {len(urls)}", file=sys.stderr)
    results = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(probe.probe, u): u for u in urls}
        for f in cf.as_completed(futs, timeout=BUDGET_S):
            u = futs[f]
            try:
                results[u] = f.result()
            except Exception as e:
                results[u] = {"entry": u, "fatal": f"probe raised {type(e).__name__}: {e}"}
    done = time.time() - t0
    missing = [u for u in urls if u not in results]
    json.dump({"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "wall_seconds": round(done, 1),
               "unique_urls": len(urls), "probed": len(results),
               "not_probed": missing,
               "results": results},
              open("registry_status.json", "w"), indent=1, ensure_ascii=False)

    # summary
    alive, dead, weird = [], [], []
    for u, r in results.items():
        if r.get("fatal"):
            (dead if "no System object" in str(r.get("fatal")) else weird).append((u, r["fatal"][:90]))
        else:
            alive.append(u)
    print(f"wall {done:.0f}s  alive {len(alive)}  dead {len(dead)}  other {len(weird)}  unprobed {len(missing)}")
    print("--- DEAD ---")
    for u, f in sorted(dead): print(f"  {u}\n    {f}")
    print("--- OTHER ---")
    for u, f in sorted(weird): print(f"  {u}\n    {f}")

main()
