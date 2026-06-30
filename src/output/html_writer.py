"""
HTML 输出 — 生成带样式的新闻日报页面
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from src.scraper.parser import Article

logger = logging.getLogger(__name__)

_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --bg: #f8f9fa;
    --card-bg: #ffffff;
    --text: #1a1a2e;
    --text-secondary: #555;
    --accent: #2563eb;
    --accent-light: #eff6ff;
    --border: #e5e7eb;
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #e2e8f0;
      --text-secondary: #94a3b8;
      --accent: #60a5fa;
      --accent-light: #1e293b;
      --border: #334155;
      --shadow: 0 1px 3px rgba(0,0,0,0.3);
    }}
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC",
                 "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
    padding: 2rem 1rem;
  }}
  .container {{ max-width: 800px; margin: 0 auto; }}

  /* Header */
  header {{
    text-align: center;
    padding: 2rem 0 1.5rem;
    border-bottom: 2px solid var(--border);
    margin-bottom: 2rem;
  }}
  header h1 {{ font-size: 1.6rem; font-weight: 700; }}
  header .date {{ color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.3rem; }}
  header .stats {{ color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.2rem; }}

  /* Daily Article */
  .daily-article {{
    background: var(--card-bg);
    border-radius: 12px;
    padding: 1.8rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
  }}
  .daily-article h2 {{
    font-size: 1.2rem;
    margin-bottom: 1rem;
    color: var(--accent);
  }}
  .daily-article p {{ margin-bottom: 0.8rem; text-indent: 2em; }}
  .daily-article p:last-child {{ margin-bottom: 0; }}

  /* Summary list */
  .summary-list {{ display: flex; flex-direction: column; gap: 1rem; }}

  .summary-card {{
    background: var(--card-bg);
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    transition: border-color 0.15s;
  }}
  .summary-card:hover {{ border-color: var(--accent); }}

  .summary-card h3 {{
    font-size: 1.05rem;
    margin-bottom: 0.3rem;
  }}
  .summary-card h3 a {{
    color: var(--text);
    text-decoration: none;
  }}
  .summary-card h3 a:hover {{ color: var(--accent); }}

  .summary-card .meta {{
    font-size: 0.82rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
  }}
  .summary-card .meta .source {{ font-weight: 500; }}
  .summary-card .meta .sep {{ margin: 0 0.4em; }}

  .summary-card .content {{ font-size: 0.92rem; line-height: 1.7; }}

  .summary-card .read-more {{
    display: inline-block;
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: var(--accent);
    text-decoration: none;
    font-weight: 500;
  }}
  .summary-card .read-more:hover {{ text-decoration: underline; }}

  /* Footer */
  footer {{
    text-align: center;
    padding: 2rem 0 0.5rem;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }}

  /* Empty state */
  .empty {{
    text-align: center;
    padding: 3rem;
    color: var(--text-secondary);
  }}

  @media (max-width: 600px) {{
    body {{ padding: 1rem 0.5rem; }}
    .daily-article {{ padding: 1.2rem; }}
    .summary-card {{ padding: 1rem 1.2rem; }}
    header h1 {{ font-size: 1.3rem; }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>{header_title}</h1>
    <div class="date">{date_str}</div>
    <div class="stats">{stats}</div>
  </header>

  {daily_section}

  <section>
    <h2 style="font-size:1.1rem;margin-bottom:1rem;color:var(--text-secondary);">
      📌 单篇摘要 <span style="font-weight:400;font-size:0.85rem;">({article_count} 篇)</span>
    </h2>
    <div class="summary-list">
      {summaries_html}
    </div>
  </section>

  <footer>
    <p>由 EduSnap 自动生成 · {date_str}</p>
  </footer>
</div>
</body>
</html>
"""

_SUMMARY_TEMPLATE = """\
      <article class="summary-card">
        <h3><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
        <div class="meta">
          <span class="source">{source}</span>
          <span class="sep">·</span>
          <span>{date}</span>
        </div>
        <div class="content">
          {summary_html}
        </div>
        <a class="read-more" href="{url}" target="_blank" rel="noopener">阅读原文 →</a>
      </article>"""


def _md_to_html(text: str) -> str:
    """极简 Markdown → HTML 转换（只处理段落、链接、加粗）"""
    import re
    # 转义 HTML 特殊字符
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    # **加粗**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 行内链接 [text](url)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    # 段落（双换行分割）
    paragraphs = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        # 单行内的换行转空格
        block = block.replace("\n", " ")
        paragraphs.append(f"<p>{block}</p>")
    return "\n          ".join(paragraphs) if paragraphs else f"<p>{text}</p>"


class HtmlWriter:
    """将抓取结果渲染为带样式的 HTML 页面"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def write_page(
        self,
        daily_article: str | None,
        summaries: List[str],
        articles: List[Article],
        date: datetime | None = None,
    ) -> Path:
        """
        生成 HTML 日报页面

        Args:
            daily_article: LLM 合成的综合文章（Markdown 原文）
            summaries: 每篇文章的摘要（Markdown 原文）
            articles: 对应的 Article 列表
            date: 日期

        Returns:
            HTML 文件路径
        """
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        # 标题
        weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][date.weekday()]
        title = f"EduSnap · 留学新闻日报 · {date_str} 周{weekday_cn}"

        # 统计
        sources = set(a.source_name for a in articles)
        stats = f"共 {len(articles)} 篇新闻 · 来自 {len(sources)} 个来源"

        # — 综合文章 —
        if daily_article:
            daily_html = _md_to_html(daily_article)
            daily_section = f"""\
  <section class="daily-article">
    <h2>📰 综合新闻</h2>
    {daily_html}
  </section>"""
        else:
            daily_section = """\
  <section class="daily-article">
    <h2>📰 综合新闻</h2>
    <p style="color:var(--text-secondary)">（LLM 未配置，跳过综合生成）</p>
  </section>"""

        # — 单篇摘要 —
        summaries_html = ""
        for summary, article in zip(summaries, articles):
            safe_title = article.title or "未知标题"
            safe_source = article.source_name or "未知来源"
            safe_date = article.date or "未知日期"
            safe_url = article.url or "#"

            summary_html = _md_to_html(summary)

            summaries_html += _SUMMARY_TEMPLATE.format(
                title=safe_title,
                source=safe_source,
                date=safe_date,
                url=safe_url,
                summary_html=summary_html,
            )

        if not summaries_html:
            summaries_html = '<div class="empty">暂无新闻摘要</div>'

        # — 拼装 —
        html = _PAGE_TEMPLATE.format(
            title=title,
            header_title="📰 留学新闻日报",
            date_str=date_str,
            stats=stats,
            daily_section=daily_section,
            summaries_html=summaries_html,
            article_count=len(articles),
        )

        # — 输出 —
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.output_dir / f"{date_str}.html"
        filepath.write_text(html, encoding="utf-8")
        logger.info("HTML 日报已生成: %s", filepath)
        return filepath
