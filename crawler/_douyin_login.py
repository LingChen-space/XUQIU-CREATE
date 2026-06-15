"""抖音登录 - 使用原生 Playwright 打开浏览器进行手动登录，保存 Cookie。
启动方式: cd 监控脚本 && .venv\Scripts\python.exe _douyin_login.py
"""
import json
import os
import sys
from pathlib import Path

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
COOKIE_PATH = SCRIPT_DIR / ".cloakbrowser" / "douyin-cookies.json"


def main():
    print("[抖音登录] 正在启动浏览器...")
    print("[抖音登录] 请在浏览器中完成登录（扫码或手机号），登录完成后回到此处按 Enter")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # 隐藏 webdriver 特征
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
        """)

        page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        print(f"[抖音登录] 页面标题: {page.title()}")

        # 等待用户手动登录
        input("\n[抖音登录] 登录完成后按 Enter 保存 Cookie...")

        cookies = context.cookies()
        print(f"[抖音登录] 获取到 {len(cookies)} 个 Cookie")

        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_PATH.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[抖音登录] Cookie 已保存到 {COOKIE_PATH}")

        browser.close()
        print("[抖音登录] 完成")


if __name__ == "__main__":
    main()
