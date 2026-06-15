import urllib.request, urllib.parse, time

print("Testing with urllib directly...")
params = urllib.parse.urlencode({"q": "工具", "limit": "3", "offset": "0", "time_range": "30d", "sort_filter": "default"})
url = "https://api.xiaoheihe.cn/bbs/app/api/general/search/v1?" + params
print("URL:", url[:80])
start = time.time()
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = urllib.request.urlopen(req, timeout=15)
    print(f"OK {time.time()-start:.1f}s, status={r.status}")
except Exception as e:
    print(f"Failed {time.time()-start:.1f}s: {type(e).__name__}: {e}")
