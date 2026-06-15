import os
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

import httpx

print("=== 健康检查 ===")
r = httpx.get("http://127.0.0.1:8001/api/monitor/health", timeout=15, follow_redirects=True)
print(f"Status: {r.status_code}")
print(r.text)

print()
print("=== 小黑盒采集测试 ===")
r2 = httpx.post("http://127.0.0.1:8001/api/monitor/heybox", json={
    "keyword": "工具", "count": 10, "time_range": "30d", "sort": "default"
}, timeout=120, follow_redirects=True)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    data = r2.json()
    print(f"ok={data['ok']}, count={data['count']}")
    for item in data["items"][:3]:
        title = item.get("title", "")[:60] if item.get("title") else "N/A"
        url = item.get("share_url", "N/A")
        if url and len(url) > 80:
            url = url[:80] + "..."
        print(f"  - title={title}")
        print(f"    url={url}")
else:
    print(f"Error: {r2.text[:500]}")
