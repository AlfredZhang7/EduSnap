"""
config/sources.md 读取与验证
"""

import re
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


WECHAT_PREFIX = "wechat:"


class SourceReader:
    """读取 sources.md 中的 URL 列表并做基本校验"""

    def __init__(self, sources_path: str | Path):
        self.sources_path = Path(sources_path)

    def read(self) -> List[str]:
        """解析 Markdown 无序列表，返回有效 URL 列表（排除 wechat: 条目）"""
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
                # 跳过 wechat: 条目（由 read_wechat_accounts 处理）
                if candidate.lower().startswith(WECHAT_PREFIX):
                    continue
                if URL_PATTERN.match(candidate):
                    urls.append(candidate)
                else:
                    logger.warning("跳过无效 URL: %s", candidate)
        logger.info("从 sources.md 读取到 %d 个有效来源", len(urls))
        return urls

    def read_wechat_accounts(self) -> List[str]:
        """读取 sources.md 中的 wechat: 公众号条目

        格式:   - wechat:公众号名称

        Returns:
            公众号名称列表
        """
        if not self.sources_path.exists():
            logger.warning("来源文件不存在: %s", self.sources_path)
            return []

        text = self.sources_path.read_text(encoding="utf-8")
        accounts: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            match = re.match(r"^[-*]\s+" + re.escape(WECHAT_PREFIX) + r"\s*(.+)$", line, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name:
                    accounts.append(name)
                else:
                    logger.warning("跳过空的公众号名称: %s", line)

        if accounts:
            logger.info("从 sources.md 读取到 %d 个公众号: %s", len(accounts), accounts)
        return accounts
