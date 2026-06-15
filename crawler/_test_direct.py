import sys, time
sys.path.insert(0, ".")
from app.heybox.api import api_search

print("Testing heybox API directly...", flush=True)
start = time.time()
resp = api_search(keyword="工具", limit=5, offset=0, time_range="30d", sort_filter="default")
elapsed = time.time() - start
if resp:
    items = resp.get("result", {}).get("items", [])
    print(f"Got {len(items)} items in {elapsed:.1f}s")
else:
    print(f"Failed after {elapsed:.1f}s")
