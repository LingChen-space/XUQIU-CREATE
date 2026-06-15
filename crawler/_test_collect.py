import urllib.request, json

body = json.dumps({"keyword":"工具","count":5,"time_range":"30d","sort":"default"}).encode()
req = urllib.request.Request("http://127.0.0.1:8001/api/monitor/heybox", data=body,
    headers={"Content-Type":"application/json"}, method="POST")
try:
    r = urllib.request.urlopen(req, timeout=120)
    data = json.loads(r.read())
    print("Heybox: ok=", data["ok"], "items=", data["count"])
    for item in data["items"][:3]:
        t = item.get("title","N/A")
        if t and len(t) > 60: t = t[:60]
        u = item.get("share_url","N/A")
        print("  title:", t)
        print("  url:", u[:80] if u else "N/A")
except Exception as e:
    print("Failed:", type(e).__name__, str(e)[:200])
