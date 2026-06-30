"""
微信公众号文章爬取模块 — 通过搜狗微信搜索按公众号名称查找文章
"""

import re
import time
import random
import logging
from datetime import datetime, timedelta
from typing import List
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from src.scraper.parser import Article

logger = logging.getLogger(__name__)

SOGOU_DOMAIN = "weixin.sogou.com"
SOGOU_ARTICLE_SEARCH = "https://weixin.sogou.com/weixin"
SOGOU_BLOCKED_KEYWORDS = ["请输入验证码", "antispider", "访问过于频繁"]


def _rand_delay(min_s=2.0, max_s=5.0):
    time.sleep(random.uniform(min_s, max_s))


class WeChatScraper:
    """通过搜狗微信搜索查找公众号最新文章"""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def search_account_articles(self, account_name: str, max_articles: int = 2):
        """
        搜索指定公众号近 2 天的文章

        公众号通常每天最多发 1 篇，所以近 2 天最多 2 篇。
        搜到 2 篇后立即停止，节省时间。

        Args:
            account_name: 公众号名称
            max_articles: 最多返回多少篇（默认 2）

        Returns:
            Article 列表
        """
        logger.info("正在搜狗搜索: %s", account_name)

        cutoff = datetime.now() - timedelta(days=2)
        articles: list[Article] = []

        for page in range(1, 101):
            if page > 1:
                _rand_delay(6, 12)

            url = f"{SOGOU_ARTICLE_SEARCH}?type=2&query={quote(account_name)}&page={page}"
            try:
                resp = self._session.get(url, timeout=30)
                resp.raise_for_status()
                resp.encoding = "utf-8"
            except requests.RequestException:
                break

            if any(kw in resp.text for kw in SOGOU_BLOCKED_KEYWORDS):
                logger.warning("搜狗搜索被反爬")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select("ul.news-list > li")

            # 第1页为空 → 搜狗没搜到这个公众号的任何结果
            if page == 1 and not items:
                logger.warning("╔════════════════════════════════════════════╗")
                logger.warning("║  [!] 公众号可能存在问题: %s", account_name)
                logger.warning("║     搜狗搜索第1页无任何结果")
                logger.warning("║     可能原因: 名称错误 / 未收录 / 已注销")
                logger.warning("╚════════════════════════════════════════════╝")
                break

            if not items:
                logger.info("  第%d页为空,结束翻页", page)
                break

            page_hits = 0
            for li in items:
                # 校验来源公众号
                src_el = li.select_one(".all-time-y2")
                src_name = src_el.get_text(strip=True) if src_el else ""
                if account_name not in src_name and src_name not in account_name:
                    continue

                # 提取时间戳 (格式: timeConvert('1769079926'))
                s2 = li.select_one(".s2")
                script = s2.find("script") if s2 else None
                if not script:
                    continue
                m = re.search(r"""timeConvert\(['"]?(\d+)['"]?\)""", str(script))
                if not m:
                    continue

                pub_time = datetime.fromtimestamp(int(m.group(1)))
                if pub_time < cutoff:
                    continue

                # 提取搜狗跳转链接
                link_el = li.select_one("h3 a")
                if not link_el:
                    continue
                href = link_el.get("href", "")
                if not href or "link?url=" not in href:
                    continue
                if href.startswith("/"):
                    href = "https://weixin.sogou.com" + href

                # 解析跳转并抓取全文（mp.weixin.qq.com 与搜狗不同域,延迟可短些）
                _rand_delay(1, 2)
                real_url = self._resolve_sogou_redirect(href)
                if not real_url:
                    continue

                article = self._fetch_and_parse_article(real_url, account_name, pub_time)
                if article:
                    articles.append(article)
                    logger.info("  [%d/%d] %s (%s)", len(articles), max_articles,
                               article.title, pub_time.date())

                page_hits += 1

                if len(articles) >= max_articles:
                    break

            logger.info("  第%d页: %d篇, 命中%d篇, 累计%d篇",
                       page, len(items), page_hits, len(articles))

            if len(articles) >= max_articles:
                logger.info("已找到 %d 篇,结束搜索", len(articles))
                break

        if not articles:
            logger.info("近2天内无新文章")

        return articles

    def _fetch_and_parse_article(self, url: str, account_name: str,
                                 pub_time: datetime) -> Article | None:
        """抓取单篇微信文章并解析"""
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        if self._is_blocked_page(soup):
            return None

        title = self._extract_title(soup) or "未知标题"
        content_html, content_text = self._extract_content(soup)

        return Article(
            title=title, url=url, source_name=f"{account_name} (公众号)",
            source_url=url, date=pub_time.strftime("%Y-%m-%d"),
            date_parsed=pub_time, content_html=content_html,
            content_text=content_text or "",
        )

    def _resolve_sogou_redirect(self, sogou_url: str) -> str | None:
        """解析搜狗跳转链接为真实文章 URL"""
        try:
            resp = self._session.get(sogou_url, timeout=30, allow_redirects=True)
            resp.encoding = "utf-8"
            final_url = resp.url
            if SOGOU_DOMAIN in final_url:
                fragments = re.findall(r"""url\s*\+=\s*[']([^']+)[']""", resp.text)
                if fragments:
                    return "".join(fragments)
                return None
            return final_url
        except requests.RequestException:
            return None

    # ── 页面解析 ──────────────────────────────────────

    @staticmethod
    def _extract_title(soup) -> str | None:
        for sel in ["#activity-name", ".rich_media_title", "h1.rich_media_title", "h1"]:
            el = soup.select_one(sel)
            if el and (text := el.get_text(strip=True)):
                return " ".join(text.split())
        return None

    @staticmethod
    def _extract_content(soup) -> tuple[str | None, str | None]:
        content_div = soup.find(id="js_content")
        if not content_div:
            content_div = soup.select_one(".rich_media_content, #article-content")
        if not content_div:
            return None, None
        return str(content_div), content_div.get_text(separator="\n", strip=True)

    @staticmethod
    def _is_blocked_page(soup) -> bool:
        if soup.find(id="js_content") or soup.select_one(".rich_media_content"):
            return False
        for kw in ["请在微信客户端打开", "环境异常", "非微信客户端"]:
            if kw in soup.get_text():
                return True
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if len(soup.get_text().strip()) < 100 and ("验证" in title or "verify" in title.lower()):
            return True
        return False
