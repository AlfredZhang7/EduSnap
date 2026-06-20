"""
文章去重 — URL 精确去重 + 标题 Jaccard 相似度去重
"""

import logging
from typing import List, Set

from src.scraper.parser import Article
from src.processor.cleaner import Cleaner

logger = logging.getLogger(__name__)


class Deduplicator:
    """文章去重"""

    def __init__(self, title_similarity_threshold: float = 0.85):
        self.threshold = title_similarity_threshold

    def deduplicate(self, articles: List[Article]) -> List[Article]:
        seen_urls: Set[str] = set()
        seen_titles: List[str] = []

        result: List[Article] = []
        for art in articles:
            if art.url in seen_urls:
                logger.debug("URL 重复，跳过: %s", art.url)
                continue
            seen_urls.add(art.url)

            if self._is_duplicate_title(art.title, seen_titles):
                logger.debug("标题相似，跳过: %s", art.title)
                continue
            seen_titles.append(art.title)
            result.append(art)

        removed = len(articles) - len(result)
        if removed:
            logger.info("去重移除 %d 篇文章", removed)
        return result

    @staticmethod
    def _is_duplicate_title(title: str, titles: List[str]) -> bool:
        if not title:
            return True
        clean = Cleaner.clean_article_text(title)
        words_a = set(clean.lower().split())
        if not words_a:
            return True
        for existing in titles:
            words_b = set(existing.lower().split())
            intersection = words_a & words_b
            union = words_a | words_b
            if not union:
                continue
            jaccard = len(intersection) / len(union)
            if jaccard > 0.85:
                return True
        return False
