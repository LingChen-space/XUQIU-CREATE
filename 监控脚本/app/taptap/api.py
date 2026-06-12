from app.taptap.sign import (
    get_mac,
    TAPTAP_SIGN_KEY,
    TAPTAP_SIGN_KID,
    TAPTAP_XUA,
    generate_random_xua,
    get_request_nonce,
    request_sign
)
import time
import requests


class TapTapAPIError(Exception):
    """Custom exception for TapTap API errors."""
    pass


class TapTapRiskControlError(TapTapAPIError):
    """TapTap returned 405, which usually indicates risk control."""
    pass


def build_proxies(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def check_taptap_response(response_data):
    if response_data is None:
        print("No response data to check.")
        return False
    
    # if "success": false, taptap API indicates an error
    if response_data.get("success") is False:
        # try parse error entity
        # "data": {
        #     "code": -1,
        #     "msg": "signature invalid",
        #     "error": "invalid_request",
        #     "error_description": "Parameter error, Check the \"sign\" parameter."
        # }
        error_info = response_data.get("data", {})
        code = error_info.get("code")
        msg = error_info.get("msg")
        error = error_info.get("error")
        error_description = error_info.get("error_description")

        print(f"TapTap API error - Code: {code}, Message: {msg}, Error: {error}, Description: {error_description}")
        raise TapTapAPIError(f"TapTap API error - Code: {code}, Message: {msg}, Error: {error}, Description: {error_description}")

    return True

def normalize_taptap_response(response):
    if response is None:
        return None
    try:
        return response.json()
    except ValueError as e:
        print(f"Failed to parse JSON response: {e}")
        return None

def safe_post(url, data=None, headers=None, params=None, proxy_url: str | None = None):
    try:
        response = requests.post(
            url,
            data=data,
            headers=headers,
            params=params,
            proxies=build_proxies(proxy_url),
        )
        response.raise_for_status()
        
        response_data = normalize_taptap_response(response)

        if check_taptap_response(response_data):
            return response_data
        else:
            return None
    except requests.exceptions.RequestException as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        if status_code == 405:
            current_proxy = proxy_url or "\u672a\u8bbe\u7f6e"
            raise TapTapRiskControlError(
                f"TapTap \u906d\u9047\u98ce\u63a7\uff08HTTP 405\uff09\uff0c"
                f"\u8bf7\u5207\u6362\u4ee3\u7406\u540e\u91cd\u8bd5\u3002"
                f"\u5f53\u524d\u4ee3\u7406\uff1a{current_proxy}"
            ) from e
        print(f"HTTP POST request failed: {e}")
        return None
    


# POST
TAPTAP_AGG_SEARCH = "https://api.taptapdada.com/search/v6/agg-search"


def api_agg_search(
    keyword: str,
    types: str = "community",
    scene: str = "history",
    sort: str | None = None,
    limit: int = 10,
    from_: int = 0,
    session_id: str | None = None,
    proxy_url: str | None = None,
):

    x_ua = generate_random_xua()

    ts = str(int(time.time()))
    nonce = get_request_nonce()

    req_data = {
        "types": types,
        "kw": keyword,
        "scene": scene,
        "limit": str(limit),
        "from": str(from_) if from_ > 0 else "",
    }
    if sort:
        req_data["sort"] = sort
    if session_id:
        req_data["session_id"] = session_id

    req_sign_data = {
        "taptap_method": "POST",
        "taptap_request_url": TAPTAP_AGG_SEARCH + "?",
        "X-UA": x_ua,
        "taptap_kid": TAPTAP_SIGN_KID,
        "taptap_key": TAPTAP_SIGN_KEY,
        "time": ts,
        "nonce": nonce,
    }
    req_sign_data.update(req_data)
    mac = get_mac(
        request_method=req_sign_data["taptap_method"],
        request_url=req_sign_data["taptap_request_url"],
        xua=req_sign_data["X-UA"],
        kid=req_sign_data["taptap_kid"],
        key=req_sign_data["taptap_key"],
        time_value=req_sign_data["time"],
    )
    sign = request_sign(req_sign_data)

    req_data["sign"] = sign
    req_data["time"] = ts
    req_data["nonce"] = nonce
    
    req_params = {
        "X-UA": x_ua
    }

    agg_search_resp = safe_post(
        TAPTAP_AGG_SEARCH,
        data=req_data,
        headers={"Authorization": mac},
        params=req_params,
        proxy_url=proxy_url,
    )
    
    return agg_search_resp
