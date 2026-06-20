"""
网页下载模块 — requests 为主，playwright 兜底
"""

import time
import logging
from typing import Optional
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    html: str
    soup: BeautifulSoup
    status_code: int
    fallback_used: bool = False


class Fetcher:
    """支持静态（requests）和动态（playwright）两种抓取模式"""

    def __init__(
        self,
        timeout: int = 30,
        delay: float = 1.0,
        user_agent: Optional[str] = None,
        use_playwright: bool = False,
        playwright_headless: bool = True,
    ):
        self.timeout = timeout
        self.delay = delay
        self.use_playwright = use_playwright
        self.playwright_headless = playwright_headless
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        })
        # 失败记录 — 每次 fetch 前清空，统一收集供外部读取
        self.last_failure_reason: Optional[str] = None

    def fetch(self, url: str) -> Optional[FetchResult]:
        """下载单个页面，返回 FetchResult 或 None"""
        time.sleep(self.delay)
        logger.info("正在抓取: %s", url)
        self.last_failure_reason = None

        html, status, ok = self._fetch_requests(url)
        fallback = False

        if not ok and self.use_playwright:
            logger.info("requests 失败，尝试 playwright: %s", url)
            html, status, ok = self._fetch_playwright(url)
            fallback = True

        if not ok or html is None:
            reason = self.last_failure_reason or f"HTTP {status}"
            logger.error("抓取失败: %s (reason=%s)", url, reason)
            return None

        soup = BeautifulSoup(html, "lxml")
        return FetchResult(
            url=url,
            html=html,
            soup=soup,
            status_code=status or 0,
            fallback_used=fallback,
        )

    def _fetch_requests(self, url: str):
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or resp.encoding
            return resp.text, resp.status_code, True
        except requests.RequestException as e:
            logger.warning("requests 请求异常 [%s]: %s", url, e)
            self.last_failure_reason = str(e)
            return None, None, False

    def _fetch_playwright(self, url: str):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.last_failure_reason = "playwright 未安装"
            logger.error("playwright 未安装: pip install playwright && playwright install")
            return None, None, False

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.playwright_headless)
                page = browser.new_page()
                page.goto(url, timeout=self.timeout * 1000, wait_until="networkidle")
                html = page.content()
                browser.close()
            return html, 200, True
        except Exception as e:
            logger.warning("playwright 抓取异常 [%s]: %s", url, e)
            self.last_failure_reason = f"playwright: {e}"
            return None, None, False
