"""
综合文章生成 — 调用 LLM 将多篇新闻合成为一篇完整文章
"""

import logging
from pathlib import Path
from typing import List

from src.scraper.parser import Article
from src.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ArticleComposer:
    """将多篇文章合成为一篇综合新闻稿"""

    def __init__(self, llm: LLMClient, prompt_path: str | Path):
        self.llm = llm
        self.prompt_template = Path(prompt_path).read_text(encoding="utf-8")

    def compose(self, articles: List[Article]) -> str:
        if not articles:
            logger.warning("没有文章可合成")
            return ""

        articles_text = self._format_articles(articles)
        prompt = self.prompt_template.replace("{articles_text}", articles_text)

        logger.info("正在生成综合文章 (%d 篇素材)...", len(articles))
        result = self.llm.invoke(prompt)
        if result:
            logger.info("综合文章生成完成 (%d 字符)", len(result))
        else:
            logger.warning("综合文章生成为空")
        return result

    @staticmethod
    def _format_articles(articles: List[Article]) -> str:
        parts = []
        for i, art in enumerate(articles, 1):
            text = art.content_text or "(无正文内容)"
            parts.append(
                f"===== 文章 {i} =====\n"
                f"标题: {art.title}\n"
                f"来源: {art.source_name}\n"
                f"原文链接: {art.url}\n"
                f"日期: {art.date or '未知'}\n"
                f"内容:\n{text}\n"
            )
        return "\n\n".join(parts)
