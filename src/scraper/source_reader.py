"""
config/sources.md 读取与验证
"""

import re
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


class SourceReader:
    """读取 sources.md 中的 URL 列表并做基本校验"""

    def __init__(self, sources_path: str | Path):
        self.sources_path = Path(sources_path)

    def read(self) -> List[str]:
        """解析 Markdown 无序列表，返回有效 URL 列表"""
        if not self.sources_path.exists():
            logger.warning("来源文件不存在: %s", self.sources_path)
            return []

        text = self.sources_path.read_text(encoding="utf-8")
        urls = []
        for line in text.splitlines():
            line = line.strip()
            match = re.match(r"^[-*]\s+(.+)$", line)
            if match:
                candidate = match.group(1).strip()
                if URL_PATTERN.match(candidate):
                    urls.append(candidate)
                else:
                    logger.warning("跳过无效 URL: %s", candidate)
        logger.info("从 sources.md 读取到 %d 个有效来源", len(urls))
        return urls
