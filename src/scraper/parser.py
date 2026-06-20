"""
基于规则的 HTML 解析 — 提取文章列表及标题/链接/日期
"""

import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from src.scraper.fetcher import FetchResult

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    url: str
    source_name: str
    source_url: str
    date: Optional[str] = None
    date_parsed: Optional[datetime] = None
    content_html: Optional[str] = None
    content_text: Optional[str] = None


class Parser:
    """根据 scraping_rules.yaml 规则解析 HTML"""

    def __init__(self, rules: Dict[str, Any]):
        self.generic_rule = rules.get("generic_list_rule", {})
        self.site_rules: Dict[str, Dict[str, Any]] = {}
        for domain, rule in rules.items():
            if domain == "generic_list_rule":
                continue
            if isinstance(rule, dict) and "base_url" in rule:
                self.site_rules[domain] = rule

    def parse(self, result: FetchResult, domain: str) -> List[Article]:
        """从 FetchResult 中提取文章列表"""
        rule = self.site_rules.get(domain) or {}
        articles = self._extract_articles(result.soup, result.url, domain, rule)
        logger.info("从 %s 解析到 %d 篇文章", domain, len(articles))
        return articles

    def _extract_articles(
        self, soup: BeautifulSoup, source_url: str,
        source_name: str, rule: Dict[str, Any],
    ) -> List[Article]:
        list_css = rule.get("article_list_css") or self.generic_rule.get("article_list_css", "article")
        title_css = rule.get("title_css") or self.generic_rule.get("title_css", "h2 a, h3 a")
        link_css = rule.get("link_css") or self.generic_rule.get("link_css", "a")
        date_css = rule.get("date_css") or self.generic_rule.get("date_css", ".date, time")
        content_css = rule.get("content_css") or self.generic_rule.get("content_css", ".content, .body")
        date_format = rule.get("date_format")

        containers = soup.select(list_css)
        if not containers:
            containers = soup.find_all("article")
        if not containers:
            logger.warning("未找到文章容器 (selector=%s)", list_css)
            return []

        articles = []
        seen_urls: set = set()
        base_url = rule.get("base_url", "")

        for container in containers:
            article = self._parse_single(
                container, title_css, link_css, date_css, content_css,
                date_format, source_url, source_name, base_url, seen_urls,
            )
            if article:
                articles.append(article)
                seen_urls.add(article.url)

        return articles

    def _parse_single(
        self, container: Tag, title_css: str, link_css: str,
        date_css: str, content_css: str, date_format: Optional[str],
        source_url: str, source_name: str, base_url: str, seen_urls: set,
    ) -> Optional[Article]:
        title_el = container.select_one(title_css) if title_css else None
        if not title_el:
            title_el = container.find(["h2", "h3", "h4"])
        if not title_el and container.name == "a":
            title_el = container
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            title = title_el.get("aria-label", "").strip()
            for suffix in (" news link", " link"):
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
        if not title:
            return None

        link_el = container.select_one(link_css) if link_css else title_el
        href = link_el.get("href") if isinstance(link_el, Tag) else None
        if not href:
            href = title_el.get("href") if isinstance(title_el, Tag) else None
        if not href and container.name == "a":
            href = container.get("href")
        url = self._resolve_url(href, base_url or source_url)

        if url in seen_urls:
            return None

        date_el = container.select_one(date_css) if date_css else None
        date_text = date_el.get_text(strip=True) if date_el else None
        date_parsed = self._parse_date(date_text, date_format) if date_text else None

        content_el = container.select_one(content_css) if content_css else None
        content_html = str(content_el) if content_el else None
        content_text = content_el.get_text(strip=True) if content_el else None

        return Article(
            title=title, url=url, source_name=source_name,
            source_url=source_url, date=date_text, date_parsed=date_parsed,
            content_html=content_html, content_text=content_text,
        )

    @staticmethod
    def _resolve_url(href: Any, base: str) -> str:
        if not href or not isinstance(href, str):
            return base
        href = href.strip()
        if href.startswith("http://") or href.startswith("https://"):
            return href
        base = base.rstrip("/")
        if href.startswith("/"):
            match = re.match(r"(https?://[^/]+)", base)
            if match:
                return match.group(1) + href
            return base + href
        return base + "/" + href.lstrip("/")

    @staticmethod
    def _parse_date(date_text: str, fmt: Optional[str]) -> Optional[datetime]:
        if not date_text:
            return None
        date_text = date_text.strip()
        if fmt:
            try:
                return datetime.strptime(date_text, fmt)
            except (ValueError, TypeError):
                pass
        # 从文本中提取日期部分，尝试多种格式
        for pattern in (
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{2}/\d{2}/\d{4})",
            r"(\d{1,2}\s+\w+\s+\d{4})",
        ):
            match = re.search(pattern, date_text)
            if match:
                raw = match.group(1)
                for guess_fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d %B, %Y", "%d %b, %Y"):
                    try:
                        return datetime.strptime(raw, guess_fmt)
                    except (ValueError, TypeError):
                        continue
        return None
