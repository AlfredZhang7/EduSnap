"""
LLM 调用封装 — 基于 LangChain 的 ChatOpenAI（兼容 DeepSeek / OpenAI）
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """封装对 LLM 的调用，支持 OpenAI / DeepSeek 等兼容 API"""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.deepseek.com/",
        model: str = "deepseek-v4-flash",
        temperature: float = 0.8,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm: Optional["ChatOpenAI"] = None
        logger.info(
            "LLM 初始化: model=%s, base=%s, temperature=%.1f",
            model, api_base, temperature,
        )

    @property
    def llm(self) -> "ChatOpenAI":
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.model,
                openai_api_key=self.api_key,
                openai_api_base=self.api_base,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        return self._llm

    def invoke(self, prompt: str) -> str:
        """调用 LLM 并返回文本输出"""
        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as e:
            logger.error("LLM 调用失败: %s", e, exc_info=True)
            return ""

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your-api-key-here"
