"""
Markdown 文件输出
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from src.scraper.parser import Article

logger = logging.getLogger(__name__)


class Writer:
    """写入 Markdown 格式的输出文件"""

    def __init__(self, article_dir: Path, summary_dir: Path):
        self.article_dir = article_dir
        self.summary_dir = summary_dir

    def write_daily_article(self, content: str, date: datetime | None = None) -> Path:
        """写入综合文章到 data/daily_articles/YYYY-MM-DD.md"""
        date = date or datetime.now()
        filepath = self.article_dir / f"{date.strftime('%Y-%m-%d')}.md"
        filepath.write_text(content, encoding="utf-8")
        logger.info("综合文章已写入: %s", filepath)
        return filepath

    def write_summaries(self, summaries: List[str], articles: List[Article]) -> List[Path]:
        """写入每篇新闻的摘要到 data/daily_summaries/YYYY-MM-DD/"""
        paths = []
        for i, (summary, article) in enumerate(zip(summaries, articles), 1):
            safe_title = "".join(c for c in article.title[:30] if c.isalnum() or c in " _-").strip()
            if not safe_title:
                safe_title = f"news_{i}"
            filepath = self.summary_dir / f"{safe_title}.md"
            filepath.write_text(summary, encoding="utf-8")
            paths.append(filepath)
        logger.info("已写入 %d 篇摘要到 %s", len(paths), self.summary_dir)
        return paths
