# -*- coding: utf-8 -*-
"""抖音浏览器核心 — 使用 cloakbrowser（已下载专用 Chromium）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext as AsyncBrowserContext
    from playwright.sync_api import BrowserContext, Page
else:
    AsyncBrowserContext = Any
    BrowserContext = Any
    Page = Any

DOUYIN_CLOAK_HUMANIZE = True
DOUYIN_CLOAK_HEADLESS = False
DOUYIN_CLOAK_PROXY = ""
DOUYIN_CLOAK_GEOIP = False
DOUYIN_CLOAK_PROFILE_DIR = "./.cloakbrowser/douyin-www-profile"
DOUYIN_PLAYWRIGHT_PROFILE_DIR = "./.playwright/douyin-www-profile"
DOUYIN_BROWSER_METHOD_CLOAK = "cloak"
DOUYIN_BROWSER_METHOD_PLAYWRIGHT = "playwright"
DOUYIN_BROWSER_METHOD_ALIASES = {
    None: DOUYIN_BROWSER_METHOD_CLOAK,
    "": DOUYIN_BROWSER_METHOD_CLOAK,
    "method1": DOUYIN_BROWSER_METHOD_CLOAK,
    "cloak": DOUYIN_BROWSER_METHOD_CLOAK,
    "method2": DOUYIN_BROWSER_METHOD_PLAYWRIGHT,
    "playwright": DOUYIN_BROWSER_METHOD_PLAYWRIGHT,
}

DOUYIN_WWW_URL = "https://www.douyin.com/"
DOUYIN_CONTEXT_LOCALE = "zh-CN"
DOUYIN_SCREEN = {"width": 1920, "height": 1080}
DOUYIN_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
DOUYIN_PLAYWRIGHT_INSTALL_HINT = (
    "\u65b9\u6cd5\u4e8c\u9700\u8981\u5b89\u88c5 Playwright \u548c Chromium "
    "\u6d4f\u89c8\u5668\u5185\u6838\u3002"
    "\u8bf7\u5728 crawler \u76ee\u5f55\u6267\u884c: "
    "python -m playwright install chromium\u3002"
    "\u5982\u679c\u63d0\u793a\u6ca1\u6709 playwright \u6a21\u5757\uff0c"
    "\u8bf7\u5148\u6267\u884c: pip install playwright\u3002"
)

ContextConfigurator = Callable[[BrowserContext], None]
PageCallback = Callable[[Page, BrowserContext], None]


class ManagedDouyinBrowserSession:
    def __init__(self, context: BrowserContext, page: Page, cleanup: Callable[[], None] | None = None) -> None:
        self.context = context
        self.page = page
        self._cleanup = cleanup

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
        if self._cleanup is not None:
            try:
                self._cleanup()
            except Exception:
                pass


def normalize_douyin_browser_method(browser_method: str | None = None) -> str:
    method = DOUYIN_BROWSER_METHOD_ALIASES.get(browser_method)
    if method is None:
        raise ValueError("browser_method must be one of: method1, method2")
    return method


def is_playwright_install_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "No module named 'playwright'" in message
        or "Executable doesn't exist" in message
        or "playwright install" in message
        or "BrowserType.launch" in message and "install" in message.lower()
    )


def raise_playwright_install_hint(exc: Exception) -> None:
    if is_playwright_install_error(exc):
        raise RuntimeError(DOUYIN_PLAYWRIGHT_INSTALL_HINT) from exc
    raise exc


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


def build_douyin_playwright_launch_options(*, headless: bool | None = None) -> dict[str, Any]:
    return {
        "headless": DOUYIN_CLOAK_HEADLESS if headless is None else bool(headless),
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ],
    }


def build_douyin_context_kwargs(context_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "locale": DOUYIN_CONTEXT_LOCALE,
        "user_agent": DOUYIN_USER_AGENT,
        **(context_kwargs or {}),
    }


def build_douyin_profile_dir() -> str:
    return str(Path(DOUYIN_CLOAK_PROFILE_DIR).resolve())


def build_douyin_playwright_profile_dir() -> str:
    return str(Path(DOUYIN_PLAYWRIGHT_PROFILE_DIR).resolve())


async def start_douyin_transient_context(
    target_url: str,
    *,
    initial_cookies: Any = None,
    headless: bool | None = None,
    browser_method: str | None = None,
    context_kwargs: dict[str, Any] | None = None,
) -> AsyncBrowserContext:
    merged_context_kwargs = build_douyin_context_kwargs(context_kwargs)
    method = normalize_douyin_browser_method(browser_method)
    if method == DOUYIN_BROWSER_METHOD_CLOAK:
        from cloakbrowser import launch_context_async

        context = await launch_context_async(
            **build_douyin_cloak_launch_options(headless=headless),
            **merged_context_kwargs,
        )
    else:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(DOUYIN_PLAYWRIGHT_INSTALL_HINT) from exc

        playwright = None
        browser = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                **build_douyin_playwright_launch_options(headless=headless),
            )
        except Exception as exc:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception:
                    pass
            raise_playwright_install_hint(exc)
        context = await browser.new_context(**merged_context_kwargs)
        original_close = context.close

        async def close_with_browser(*args, **kwargs):
            try:
                await original_close(*args, **kwargs)
            finally:
                try:
                    await browser.close()
                finally:
                    await playwright.stop()

        context.close = close_with_browser  # type: ignore[method-assign]
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
    browser_method: str | None = None,
    configure_context: ContextConfigurator | None = None,
    on_page_ready: PageCallback | None = None,
    context_kwargs: dict[str, Any] | None = None,
) -> ManagedDouyinBrowserSession:
    merged_context_kwargs = build_douyin_context_kwargs(context_kwargs)
    method = normalize_douyin_browser_method(browser_method)
    context = None
    page = None
    cleanup = None
    try:
        if method == DOUYIN_BROWSER_METHOD_CLOAK:
            from cloakbrowser import launch_persistent_context

            context = launch_persistent_context(
                build_douyin_profile_dir(),
                **build_douyin_cloak_launch_options(headless=headless),
                **merged_context_kwargs,
            )
        else:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:
                raise RuntimeError(DOUYIN_PLAYWRIGHT_INSTALL_HINT) from exc

            playwright = None
            try:
                playwright = sync_playwright().start()
                cleanup = playwright.stop
                context = playwright.chromium.launch_persistent_context(
                    build_douyin_playwright_profile_dir(),
                    **build_douyin_playwright_launch_options(headless=headless),
                    **merged_context_kwargs,
                )
            except Exception as exc:
                if cleanup is not None:
                    try:
                        cleanup()
                    except Exception:
                        pass
                    cleanup = None
                elif playwright is not None:
                    try:
                        playwright.stop()
                    except Exception:
                        pass
                raise_playwright_install_hint(exc)
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
        return ManagedDouyinBrowserSession(context=context, page=page, cleanup=cleanup)
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
        if cleanup is not None:
            try:
                cleanup()
            except Exception:
                pass
        raise
