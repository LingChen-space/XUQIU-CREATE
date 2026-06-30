from __future__ import annotations

import time
from hashlib import md5
from urllib.parse import urlencode


# Keep the current standalone crawler behavior: the source project pins the
# July 2025 WBI mixin key instead of requesting nav keys for every call.
RID_KEY = "ea1db124af3c7062474693fa704f4ff8"


def get_w_rid(query_params: dict) -> tuple[str, str]:
    params = dict(sorted(query_params.items()))
    query_string = urlencode(params, doseq=True)
    wts = str(int(time.time()))
    source = f"{query_string}&wts={wts}"
    return md5((source + RID_KEY).encode("utf-8")).hexdigest(), wts
