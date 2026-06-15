import base64
import hashlib
import hmac
import random
from urllib.parse import quote_plus, urlparse
import requests as pure_requests

TAPTAP_CLIENT_USER_AGENT = "TapTap/2.96.2-rel#100200 (com.taptap; build:296021002; Android 11) Okhttp/3.12.1"
TAPTAP_XUA = "V=1&PN=TapTap&VN=2.96.2-rel.100200&VN_CODE=296021002&LOC=CN&LANG=zh_CN&CH=seo-google_mobile_d20260604--260604B8QTgMTVSwY7&UID=463a281d-a90a-45ab-b0e3-476a81e9d4db&VID=518119982&NT=1&SR=1080x1920&DEB=Xiaomi&DEM=Mi+Note+3&OSV=11"

def generate_random_xua():
    import uuid
    random_uid = str(uuid.uuid4())
    random_vid = f"{random.randint(100000000, 999999999)}"
    xua_template = "V=1&PN=TapTap&VN=2.96.2-rel.100200&VN_CODE=296021002&LOC=CN&LANG=zh_CN&CH=seo-google_mobile_d20260604--260604B8QTgMTVSwY7&UID={uid}&VID={vid}&NT=1&SR=1080x1920&DEB=Xiaomi&DEM=Mi+Note+3&OSV=11"
    return xua_template.format(uid=random_uid, vid=random_vid)

TAPTAP_APP_PLUGIN_VERSION = "app_plugin-39401"
TAPTAP_DEVICE_ID = "566b4a0cdd2b7521"

TAPTAP_USER_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsInYiOjF9.eyJhdWQiOiI0Y2RiZjFhNjE1ZmNkNTViNzUiLCJqdGkiOiIwaWxlckNReTRQckMzYlVNT2JFZ2hZTGJuckJlYnpqdjdtNk5PdVB0IiwiaWF0IjoxNzc2MzQzMDA0LCJpc3MiOiJvYXV0aDI6VXNlciIsInN1YiI6IjUxODExOTk4MiJ9.jagIT0kAmCpSbJ9LUw3Z0Ny89jb0ciTD187li_PRybh2dBcdGn5zWWV0qkRHObKPObKsvAYgIfDYCMS1MAK8854v7xEboWcAUpYxERfrJug3ec6m_iqaPMVsw-vupTH8OHwSsXygU06K1LwJPo_GW5agEJhwWR_T_KHmjoxN1WI"
TAPTAP_DEVICE_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsInYiOjF9.eyJhdWQiOiI0Y2RiZjFhNjE1ZmNkNTViNzUiLCJqdGkiOiI5ZUlDUWlOeXVCT1dRZmhXS3ZCS3o0djRycUl6VUtpdDdxY01mRlVvIiwiaWF0IjoxNzc1MjcyNDUzLCJpc3MiOiJvYXV0aDI6RGV2aWNlIiwic3ViIjoiMjI3Nzg4MTI2MCIsInV1aWQiOiI0NjNhMjgxZC1hOTBhLTQ1YWItYjBlMy00NzZhODFlOWQ0ZGIifQ.RRCLCYSxk-zPLZnGVRITHbyWgWf4fYZe2IOQe385K-CPlUvPVFAujS8gmQfRR8iTu1U23eNF2ipr37c0S20CYmfObbVm_xqQvepi6_GVKv_bwCZa3shc3fe55gqkM_-JjsDdNXStCJGp21-LUHuQ6gBRY4XHFrpIb2VIwgsbXis"

SIGN_URL = "http://autotest.3839.com/appCrawler/taptap/sign"

NONCE_CHARACTER = "abcdefghijklmnopqrstuvwxyz0123456789"
MAC_NONCE_CHARACTER = "abcdefghijklmnopqrstuvwxyz"

TAPTAP_SIGN_KID = "0ilerCQy4PrC3bUMObEghYLbnrBebzjv7m6NOuPt"
TAPTAP_SIGN_KEY = "TBlerCQy1l8gvrDKARCnD1U2rikpqJrwJGwaZTd9"


def get_request_nonce():
    return "".join(random.choices(NONCE_CHARACTER, k=5))


def get_mac_nonce():
    return "".join(random.choices(MAC_NONCE_CHARACTER, k=5))


def http_head_encryption(key: str, value: str) -> str | None:
    if not key or not value:
        return None
    return f'{key}="{value}"'


def sort_https_params(time_value: str, nonce: str, method: str, path: str, host: str, port: str, rest: str) -> str | None:
    if not time_value or not nonce or not method or not host or not port:
        return None

    params = f"{time_value}\n{nonce}\n{method}\n{path}\n{host}\n{port}\n"
    append = "\n" if not rest else f"{rest}\n"
    return params + append


def hmac_encode(data: str, key: str) -> str | None:
    if not data or not key:
        return None

    digest = hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def get_mac(request_method: str, request_url: str, xua: str, kid: str, key: str, time_value: str, fix_nonce: str = None) -> str:
    try:
        url_str = f"{request_url}X-UA={quote_plus(xua)}"
        header_id = http_head_encryption("id", kid)
        mac_nonce = fix_nonce if fix_nonce else get_mac_nonce()

        parsed_url = urlparse(url_str)
        host = parsed_url.hostname
        if not host:
            raise ValueError("Invalid request URL")

        host_index = url_str.index(host)
        path = url_str[host_index + len(host):]
        port = "443" if url_str.startswith("https") else "80"

        sorted_param = sort_https_params(time_value, mac_nonce, request_method, path, host, port, "")
        hmac_value = hmac_encode(sorted_param, key)
        mac_parts = [
            "MAC ",
            f"{header_id},",
            f'{http_head_encryption("ts", time_value)},',
            f'{http_head_encryption("nonce", mac_nonce)},',
            http_head_encryption("mac", hmac_value),
        ]
        return "".join(mac_parts)
    except Exception as exc:
        raise Exception(f"Failed to get mac: {exc}") from exc


def request_sign(sign_payload: dict) -> str:
    sign_resp = pure_requests.post(SIGN_URL, json=sign_payload, timeout=10)
    sign_resp.raise_for_status()
    sign_resp_data = sign_resp.json()
    return sign_resp_data["sign"]
