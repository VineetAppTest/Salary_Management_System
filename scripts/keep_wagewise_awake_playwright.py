"""Keep WageWise Streamlit app awake using Playwright.

This script is intended to run from GitHub Actions. It opens the public
Streamlit app URL and waits long enough for the app to initialise.

Required environment variable:
  WAGEWISE_APP_URL - full Streamlit app URL, e.g. https://your-app.streamlit.app

Optional environment variables:
  KEEP_AWAKE_TIMEOUT_MS - page load timeout in milliseconds, default 60000
  KEEP_AWAKE_SETTLE_SECONDS - seconds to keep page open after load, default 20
"""

from __future__ import annotations

import os
import sys
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def _get_app_url() -> str:
    url = (os.getenv("WAGEWISE_APP_URL") or "").strip()
    if not url:
        raise ValueError("Missing required secret/env var: WAGEWISE_APP_URL")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("WAGEWISE_APP_URL must be a full URL, for example https://your-app.streamlit.app")

    return url


def main() -> int:
    app_url = _get_app_url()
    timeout_ms = int(os.getenv("KEEP_AWAKE_TIMEOUT_MS", "60000"))
    settle_seconds = int(os.getenv("KEEP_AWAKE_SETTLE_SECONDS", "20"))

    print(f"Opening WageWise app: {app_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WageWiseKeepAwake/1.0"
            ),
        )

        try:
            page.goto(app_url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except PlaywrightTimeoutError:
                print("Network did not become fully idle; continuing because the page DOM loaded.")

            # Streamlit may continue hydrating after domcontentloaded. Keep the page open briefly.
            time.sleep(settle_seconds)
            title = page.title()
            print(f"WageWise keep-awake completed. Page title: {title!r}")
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # GitHub Actions should show the exact operational error.
        print(f"WageWise keep-awake failed: {exc}", file=sys.stderr)
        raise
