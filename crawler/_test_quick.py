import sys; sys.path.insert(0, '.')
from app.heybox.api import api_search
resp = api_search('工具', limit=3, offset=0, time_range='7d', sort_filter='default')
if resp:
    items = resp.get('result', {}).get('items', [])
    print(f'OK: {len(items)} items')
    for item in items[:3]:
        print(f"  - {str(item.get('subject',''))[:60]}")
else:
    print('FAIL: no response')
