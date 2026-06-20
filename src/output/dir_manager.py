"""
日期化输出目录管理
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DirManager:
    """管理按日期组织的输出目录"""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def ensure_dated_dirs(self, date: datetime | None = None) -> tuple[Path, Path]:
        """
        创建并返回 (article_dir, summary_dir) 两个日期子目录。
        - data/daily_articles/  (综合文章目录)
        - data/daily_summaries/YYYY-MM-DD/  (单篇摘要目录)
        """
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        article_dir = self.base_dir / "daily_articles"
        summary_dir = self.base_dir / "daily_summaries" / date_str

        article_dir.mkdir(parents=True, exist_ok=True)
        summary_dir.mkdir(parents=True, exist_ok=True)

        logger.info("输出目录已就绪: %s, %s", article_dir, summary_dir)
        return article_dir, summary_dir
