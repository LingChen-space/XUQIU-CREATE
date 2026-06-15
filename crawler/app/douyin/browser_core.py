# -*- coding: utf-8 -*-
"""抖音浏览器核心 — 使用 cloakbrowser（已下载专用 Chromium）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from cloakbrowser import launch_context_async, launch_persistent_context
from playwright.async_api import BrowserContext as AsyncBrowserContext
from playwright.sync_api import BrowserContext, Page

DOUYIN_CLOAK_HUMANIZE = True
DOUYIN_CLOAK_HEADLESS = False
DOUYIN_CLOAK_PROXY = ""
DOUYIN_CLOAK_GEOIP = False
DOUYIN_CLOAK_PROFILE_DIR = "./.cloakbrowser/douyin-www-profile"

DOUYIN_WWW_URL = "https://www.douyin.com/"
DOUYIN_CONTEXT_LOCALE = "zh-CN"
DOUYIN_SCREEN = {"width": 1920, "height": 1080}

ContextConfigurator = Callable[[BrowserContext], None]
PageCallback = Callable[[Page, BrowserContext], None]


class ManagedDouyinBrowserSession:
    def __init__(self, context: BrowserContext, page: Page) -> None:
        self.context = context
        self.page = page

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def get_cookies(self):
        return self.context.cookies()

    def close(self) -> None:
        try:
            if not self.page.is_closed():
                self.page.close()
        except Exception:
            pass
        try:
            self.context.close()
        except Exception:
            pass


def build_cookie_seed_urls(target_url: str) -> list[str]:
    seed_urls: list[str] = []

    def add_url(url: str):
        if url and url not in seed_urls:
            seed_urls.append(url)

    parsed = urlsplit(target_url)
    if parsed.scheme and parsed.netloc:
        add_url(f"{parsed.scheme}://{parsed.netloc}")

    add_url(DOUYIN_WWW_URL.rstrip("/"))
    add_url("https://douyin.com")
    add_url("https://www-hj.douyin.com")
    add_url("https://douhot.douyin.com")
    return seed_urls


def normalize_context_cookies(cookie_data: Any, target_url: str) -> list[dict[str, Any]]:
    if not cookie_data:
        return []
    if isinstance(cookie_data, list):
        return cookie_data
    if isinstance(cookie_data, str):
        result: list[dict[str, Any]] = []
        for cookie_item in cookie_data.split(";"):
            cookie_item = cookie_item.strip()
            if not cookie_item or "=" not in cookie_item:
                continue
            name, value = cookie_item.split("=", 1)
            name = name.strip()
            if not name:
                continue
            for seed_url in build_cookie_seed_urls(target_url=target_url):
                result.append({"name": name, "value": value.strip(), "url": seed_url})
        return result
    raise TypeError("Unsupported cookie data type, must be list or str")


def build_douyin_cloak_launch_options(*, headless: bool | None = None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "headless": DOUYIN_CLOAK_HEADLESS if headless is None else bool(headless),
        "humanize": bool(DOUYIN_CLOAK_HUMANIZE),
    }
    proxy = DOUYIN_CLOAK_PROXY.strip()
    if proxy:
        options["proxy"] = proxy
        if DOUYIN_CLOAK_GEOIP:
            options["geoip"] = True
    return options


def build_douyin_profile_dir() -> str:
    return str(Path(DOUYIN_CLOAK_PROFILE_DIR).resolve())


async def start_douyin_transient_context(
    target_url: str,
    *,
    initial_cookies: Any = None,
    headless: bool | None = None,
    context_kwargs: dict[str, Any] | None = None,
) -> AsyncBrowserContext:
    merged_context_kwargs = {
        "locale": DOUYIN_CONTEXT_LOCALE,
        **(context_kwargs or {}),
    }
    context = await launch_context_async(
        **build_douyin_cloak_launch_options(headless=headless),
        **merged_context_kwargs,
    )
    context_cookies = normalize_context_cookies(
        cookie_data=initial_cookies,
        target_url=target_url,
    )
    if context_cookies:
        await context.add_cookies(context_cookies)
    return context


def start_douyin_browser_session(
    target_url: str,
    *,
    initial_cookies: Any = None,
    headless: bool = False,
    configure_context: ContextConfigurator | None = None,
    on_page_ready: PageCallback | None = None,
    context_kwargs: dict[str, Any] | None = None,
) -> ManagedDouyinBrowserSession:
    merged_context_kwargs = {
        "locale": DOUYIN_CONTEXT_LOCALE,
        **(context_kwargs or {}),
    }
    context = None
    page = None
    try:
        context = launch_persistent_context(
            build_douyin_profile_dir(),
            **build_douyin_cloak_launch_options(headless=headless),
            **merged_context_kwargs,
        )
        if configure_context is not None:
            configure_context(context)
        context_cookies = normalize_context_cookies(
            cookie_data=initial_cookies,
            target_url=target_url,
        )
        if context_cookies:
            context.add_cookies(context_cookies)
        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded")
        page.bring_to_front()
        if on_page_ready is not None:
            on_page_ready(page, context)
        return ManagedDouyinBrowserSession(context=context, page=page)
    except Exception:
        if page is not None:
            try:
                if not page.is_closed():
                    page.close()
            except Exception:
                pass
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        raise
