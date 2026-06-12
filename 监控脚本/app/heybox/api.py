from app.heybox.hkey import fetch_hkey

import requests

HEYBOX_SEARCH_URL = "https://api.xiaoheihe.cn/bbs/app/api/general/search/v1"


def build_proxies(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {
        "http": proxy_url,
        "https": proxy_url,
    }

def normalize_heybox_response(response):
    try:
        return response.json()
    except ValueError:
        print("Failed to parse response as JSON. Response text:")
        print(response.text)
        return None
    
def check_heybox_response(response_data):
    if response_data is None:
        print("No response data to check.")
        return False
    
    if "status" in response_data and response_data["status"] != "ok":
        print(f"Heybox API error - Status: {response_data.get('status')}, Message: {response_data.get('msg')}")
        return False
    
    return True

def safe_get(url, params=None, headers=None, proxy_url: str | None = None):
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            proxies=build_proxies(proxy_url),
        )
        response.raise_for_status()
        
        response_data = normalize_heybox_response(response)

        if check_heybox_response(response_data):
            return response_data
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"HTTP GET request failed: {e}")
        return None
    
def safe_post(url, data=None, headers=None, proxy_url: str | None = None):
    try:
        response = requests.post(
            url,
            data=data,
            headers=headers,
            proxies=build_proxies(proxy_url),
        )
        response.raise_for_status()
        
        response_data = normalize_heybox_response(response)

        if check_heybox_response(response_data):
            return response_data
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"HTTP POST request failed: {e}")
        return None
    
def safe_post_json(url, json=None, headers=None, proxy_url: str | None = None):
    try:
        response = requests.post(
            url,
            json=json,
            headers=headers,
            proxies=build_proxies(proxy_url),
        )
        response.raise_for_status()
        
        response_data = normalize_heybox_response(response)

        if check_heybox_response(response_data):
            return response_data
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"HTTP POST request failed: {e}")
        return None


def api_search(
    keyword: str,
    limit: int = 30,
    offset: int = 0,
    time_range: str = "30d",
    sort_filter: str = "default",
    proxy_url: str | None = None,
):

    req_data = {
        "q": keyword,
        "search_type": "general",
        "limit": limit,
        "link_content_type": "",
        "offset": offset,
        "time_range": time_range,
        "sort_filter": sort_filter,
        "heybox_id": "",
        "imei": "",
        "device_info": "Mi Note 3"
    }

    ext_params = {
        "os_type": "Android",
        "x_os_type": "Android",
        "x_client_type": "mobile",
        "os_version": "11",
        "version": "1.3.248",
        # "build": "947",
        "dw": 411,
        "channel": "heybox",
        "x_app": "heybox",
        "time_zone": "Asia/Shanghai"
    }

    hkey, nonce, _time = fetch_hkey("/bbs/app/api/general/search/v1/")

    final_params = {
        **req_data,
        "hkey": hkey,
        "nonce": nonce,
        "_time": _time,
        **ext_params,
    }

    search_resp = safe_get(HEYBOX_SEARCH_URL, params=final_params, proxy_url=proxy_url)
    return search_resp
