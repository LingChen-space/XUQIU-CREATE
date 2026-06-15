import urllib.request, json

body = json.dumps({"keyword":"工具","count":10,"time_range":"30d","sort":"default"}).encode()
req = urllib.request.Request("http://127.0.0.1:8001/api/monitor/heybox", data=body,
    headers={"Content-Type":"application/json"}, method="POST")
try:
    r = urllib.request.urlopen(req, timeout=60)
    data = json.loads(r.read())
    print("Heybox OK:", data["ok"], "items:", data["count"])
    for item in data["items"][:3]:
        t = item.get("title","N/A")
        if t and len(t) > 60: t = t[:60]
        u = item.get("share_url","N/A")
        if u and len(u) > 80: u = u[:80]
        print(" ", t)
        print("   url:", u)
except Exception as e:
    print("Heybox failed:", e)
