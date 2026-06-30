from __future__ import annotations

import random
import re

import requests


USER_AGENT_TEMPLATE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{}.0.0.0 Safari/537.36"
)


def _random_user_agent() -> str:
    return USER_AGENT_TEMPLATE.format(random.randint(96, 138))


def get_buvid_from_spi(proxy_url: str | None = None) -> tuple[str, str]:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    response = requests.get(
        "https://api.bilibili.com/x/frontend/finger/spi",
        headers={"User-Agent": _random_user_agent()},
        proxies=proxies,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili buvid spi failed: {payload.get('message')}")

    data = payload.get("data", {})
    return data.get("b_3", ""), data.get("b_4", "")


def get_buvid_from_homepage(proxy_url: str | None = None) -> tuple[str, str]:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    response = requests.get(
        "https://www.bilibili.com",
        headers={"User-Agent": _random_user_agent()},
        proxies=proxies,
        timeout=15,
    )
    response.raise_for_status()
    set_cookie_header = response.headers.get("set-cookie", "")

    buvid3_match = re.search(r"buvid3=([^;]+)", set_cookie_header)
    b_nut_match = re.search(r"b_nut=([^;]+)", set_cookie_header)

    return (
        buvid3_match.group(1) if buvid3_match else "",
        b_nut_match.group(1) if b_nut_match else "",
    )
