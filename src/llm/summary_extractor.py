"""
单篇新闻概要生成 — 调用 LLM 为每篇文章生成结构化摘要
"""

import logging
from pathlib import Path

from src.scraper.parser import Article
from src.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SummaryExtractor:
    """为单篇新闻生成 Markdown 格式的摘要"""

    def __init__(self, llm: LLMClient, prompt_path: str | Path):
        self.llm = llm
        self.prompt_template = Path(prompt_path).read_text(encoding="utf-8")

    def extract(self, article: Article) -> str:
        prompt = (
            self.prompt_template
            .replace("{article_text}", article.content_text or article.title)
            .replace("{source_url}", article.url)
            .replace("{source_name}", article.source_name)
        )

        logger.info("正在生成摘要: %s", article.title[:50])
        result = self.llm.invoke(prompt)
        if result:
            logger.info("摘要生成完成 (%d 字符)", len(result))
        else:
            logger.warning("摘要为空: %s", article.title[:50])
            result = self._fallback_summary(article)
        return result

    @staticmethod
    def _fallback_summary(article: Article) -> str:
        text = article.content_text or ""
        preview = text[:200] + "..." if len(text) > 200 else text
        return (
            f"## {article.title}\n\n"
            f"**来源**: {article.source_name}\n"
            f"**原文链接**: {article.url}\n"
            f"**日期**: {article.date or '未知'}\n\n"
            f"**内容预览**:\n{preview}\n"
        )
