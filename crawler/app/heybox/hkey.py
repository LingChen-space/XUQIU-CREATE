import requests

XIAOHEIHE_KEY_CRACK_ENDPOINT = 'http://autotest.3839.com/appCrawler/heybox/query'

def fetch_hkey(query_path: str):

    try:
        resp = requests.post(url=XIAOHEIHE_KEY_CRACK_ENDPOINT,
                             json={
                                 "path": query_path,
                                 "headers": {
                                     "Accept": "application/json",
                                     "Accept-Encoding": ""
                                 }
                             })
    except:
        raise Exception("Unable to connect crack endpoint")
    
    if resp.status_code != 200:
        raise Exception(f"Crack endpoint returned {resp.status_code}")
    
    resp_data = None
    try:
        resp_data = resp.json()
    except:
        raise Exception("Failed to parse crack response!")

    if 'hkey' not in resp_data:
        raise Exception("Crack response: missing hkey!")
    if 'nonce' not in resp_data:
        raise Exception("Crack response: missing nonce!")
    if '_time' not in resp_data:
        raise Exception("Crack response: missing _time!")
    
    hkey = resp_data['hkey']
    nonce = resp_data['nonce']
    _time = resp_data['_time']

    return hkey, nonce, _time
    