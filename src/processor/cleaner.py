"""
HTML 文本清洗 — 去标签、去脚本、规范化空白
"""

import re
import logging
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class Cleaner:
    """清洗 HTML 内容为纯净文本"""

    @staticmethod
    def clean_html(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        return Cleaner._normalize(text)

    @staticmethod
    def clean_article_text(text: Optional[str]) -> str:
        if not text:
            return ""
        return Cleaner._normalize(text)

    @staticmethod
    def _normalize(text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)
        text = re.sub(r" +", " ", text)
        return text.strip()
