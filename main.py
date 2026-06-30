"""
留学新闻聚合器 (StudyAbroad News Aggregator) -- 主入口

用法:
    python main.py                           # 一次运行
    python main.py --schedule                # 定时运行（每天早 8 点）
    python main.py --no-llm                  # 跳过 LLM 步骤（仅抓取+清洗）
    python main.py --dry-run                 # 仅读取来源和规则，不抓取
    python main.py --test-scraper            # 测试所有来源的爬虫规则
    python main.py --test-scraper https://example.com/news  # 测试特定 URL
"""

import argparse
import logging
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from src.scraper import SourceReader, Fetcher, Parser, WeChatScraper
from src.processor import Cleaner, Deduplicator
from src.llm import LLMClient, ArticleComposer, SummaryExtractor
from src.output import DirManager, Writer, HtmlWriter

# -- 路径常量 ----------------------------------------------
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后，exe 所在目录
    EXE_DIR = Path(sys.executable).resolve().parent
    # 如果 config/ 在 exe 旁边就用 exe 目录，否则向上找（项目根目录）
    if (EXE_DIR / "config").exists():
        BASE_DIR = EXE_DIR
    else:
        BASE_DIR = EXE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
PROMPTS_DIR = CONFIG_DIR / "prompts"

SOURCES_PATH = CONFIG_DIR / "sources.md"
RULES_PATH = CONFIG_DIR / "scraping_rules.yaml"
COMPOSE_PROMPT_PATH = PROMPTS_DIR / "compose_article.txt"
SUMMARY_PROMPT_PATH = PROMPTS_DIR / "generate_summary.txt"



# -- 日志配置 ----------------------------------------------
def setup_logging(level: str = "INFO"):
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"edusnap_{datetime.now():%Y-%m-%d}.log"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


# -- 配置加载 ----------------------------------------------
def load_env() -> dict:
    load_dotenv(BASE_DIR / ".env")
    import os

    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "api_base": os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1"),
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.8")),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
        "timeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
        "delay": float(os.getenv("REQUEST_DELAY", "2")),
        "use_playwright": os.getenv("USE_PLAYWRIGHT", "false").lower() == "true",
        "playwright_headless": os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


def load_rules() -> dict:
    if not RULES_PATH.exists():
        logging.warning("规则文件不存在: %s", RULES_PATH)
        return {}
    with open(RULES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_domain(url: str) -> str:
    """从 URL 提取域名（用于匹配规则）"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    # 去掉 www. 前缀
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.split(":")[0]  # 去掉端口


# -- 站点抓取报告 ------------------------------------------
def _write_site_report(site_results: list[dict]) -> None:
    """将每个站点的抓取结果写入 logs/site_report_YYYY-MM-DD.log"""
    from datetime import date
    report_file = LOGS_DIR / f"site_report_{date.today():%Y-%m-%d}.log"
    succeeded = [r for r in site_results if r["status"] == "成功"]
    failed = [r for r in site_results if r["status"] != "成功"]

    lines = [
        f"站点抓取报告 ({date.today():%Y-%m-%d})",
        f"{'=' * 60}",
        f"总计: {len(site_results)} 个站点 | 成功: {len(succeeded)} | 失败/无匹配: {len(failed)}",
        "",
    ]
    if failed:
        lines.append("--- 失败/无匹配站点 ---")
        for r in failed:
            lines.append(f"  [{r['status']}] {r['domain']}")
            lines.append(f"    URL: {r['url']}")
            if r["reason"]:
                lines.append(f"    原因: {r['reason']}")
        lines.append("")
    if succeeded:
        lines.append("--- 成功站点 ---")
        for r in succeeded:
            lines.append(f"  [OK] {r['domain']} ({r['articles']} 篇文章)")

    report_file.write_text("\n".join(lines), encoding="utf-8")
    logger = logging.getLogger("edusnap")
    logger.info("站点报告已写入: %s", report_file)


# -- 主流程 ------------------------------------------------
def run_pipeline(
    env: dict,
    rules: dict,
    skip_llm: bool = False,
    dry_run: bool = False,
    allow_undated: bool = False,
):
    logger = logging.getLogger("edusnap")

    # 1. 读取来源
    source_reader = SourceReader(SOURCES_PATH)
    urls = source_reader.read()
    wechat_accounts = source_reader.read_wechat_accounts()

    total_sources = len(urls) + len(wechat_accounts)
    if total_sources == 0:
        logger.error("没有有效的来源，请检查 %s", SOURCES_PATH)
        return

    logger.info(
        "来源统计: %d 个网站, %d 个公众号名称",
        len(urls), len(wechat_accounts),
    )

    if dry_run:
        logger.info("Dry-run 模式，仅输出来源列表。")
        return

    # 2. 初始化抓取、解析、清洗、去重
    fetcher = Fetcher(
        timeout=env["timeout"],
        delay=env["delay"],
        use_playwright=env["use_playwright"],
        playwright_headless=env["playwright_headless"],
    )
    wechat_scraper = WeChatScraper()
    parser = Parser(rules)
    cleaner = Cleaner()
    dedup = Deduplicator()

    all_articles = []
    site_results: list[dict] = []

    # 3a. 普通网站抓取 -> 解析 -> 清洗
    for url in urls:
        domain = extract_domain(url)
        result = fetcher.fetch(url)
        if result is None:
            site_results.append({
                "url": url, "domain": domain, "status": "失败",
                "reason": fetcher.last_failure_reason or "未知错误",
                "articles": 0,
            })
            continue

        articles = parser.parse(result, domain)
        for art in articles:
            art.content_text = cleaner.clean_article_text(art.content_text)
            if art.content_html:
                art.content_html = cleaner.clean_html(art.content_html)
        all_articles.extend(articles)

        status = "成功" if articles else "无匹配"
        site_results.append({
            "url": url, "domain": domain, "status": status,
            "reason": "" if articles else "CSS 选择器未匹配到文章",
            "articles": len(articles),
        })

    # 3b. 公众号名称搜索（通过搜狗搜索）
    for account_name in wechat_accounts:
        logger.info("正在搜索公众号: %s", account_name)
        wechat_articles = wechat_scraper.search_account_articles(account_name)

        for art in wechat_articles:
            art.content_text = cleaner.clean_article_text(art.content_text)
            if art.content_html:
                art.content_html = cleaner.clean_html(art.content_html)
        all_articles.extend(wechat_articles)

        site_results.append({
            "url": f"wechat:{account_name}",
            "domain": f"公众号:{account_name}",
            "status": "成功" if wechat_articles else "无匹配/搜索失败",
            "reason": "" if wechat_articles else "未搜索到文章",
            "articles": len(wechat_articles),
        })

    # 公众号问题汇总
    problematic_accounts = [
        r["domain"] for r in site_results
        if r["domain"].startswith("公众号:") and r["status"] != "成功"
    ]
    if problematic_accounts:
        logger.warning("=" * 60)
        logger.warning("  以下公众号可能存在问题，请确认名称是否正确:")
        for acc in problematic_accounts:
            logger.warning("    - %s", acc.replace("公众号:", ""))
        logger.warning("=" * 60)

    logger.info("抓取完成，共 %d 篇原始文章", len(all_articles))

    # 写入站点抓取报告
    _write_site_report(site_results)

    if not all_articles:
        logger.warning("没有抓取到任何文章")
        return

    # 4. 去重
    all_articles = dedup.deduplicate(all_articles)
    logger.info("去重后剩余 %d 篇文章", len(all_articles))

    # 5. 日期过滤 — 只保留今明两天文章（缓解时差问题）
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=1)
    before = len(all_articles)
    kept = []
    dropped_no_date = 0
    dropped_old = 0
    dropped_no_date_articles: list[str] = []
    dropped_old_articles: list[str] = []
    for art in all_articles:
        if art.date_parsed is not None:
            if art.date_parsed.date() >= cutoff:
                kept.append(art)
            else:
                dropped_old += 1
                dropped_old_articles.append(f"  {art.url} ({art.date})")
        elif art.date:
            kept.append(art)
        elif allow_undated:
            kept.append(art)
        else:
            dropped_no_date += 1
            dropped_no_date_articles.append(f"  {art.url} ({art.title[:30]})")
    all_articles = kept
    if dropped_no_date:
        logger.warning("无日期丢弃 %d 篇:", dropped_no_date)
        for line in dropped_no_date_articles:
            logger.warning("%s", line)
    if dropped_old:
        logger.info("超出2天丢弃 %d 篇:", dropped_old)
        for line in dropped_old_articles:
            logger.info("%s", line)
    if dropped_no_date or dropped_old:
        logger.info(
            "日期过滤: 保留 %d 篇 (无日期丢弃 %d, 超出2天丢弃 %d)",
            len(all_articles), dropped_no_date, dropped_old,
        )
    if not all_articles:
        logger.warning("没有近 2 天的文章，跳过输出")
        return

    # 6. 输出目录
    dir_mgr = DirManager(DATA_DIR)
    article_dir, summary_dir = dir_mgr.ensure_dated_dirs()
    writer = Writer(article_dir, summary_dir)
    html_writer = HtmlWriter(DATA_DIR / "daily_html")

    # 7. LLM 处理（可选）
    if skip_llm or not LLMClient("").is_configured:
        # 检查是否有有效 LLM 配置
        llm_check = LLMClient(env["api_key"], env["api_base"], env["model"])
        if skip_llm or not llm_check.is_configured:
            logger.info("LLM 未配置或已跳过，使用纯文本摘要")
            summaries = [SummaryExtractor._fallback_summary(art) for art in all_articles]
            writer.write_summaries(summaries, all_articles)
            html_writer.write_page(None, summaries, all_articles)
            return

    llm = LLMClient(
        api_key=env["api_key"],
        api_base=env["api_base"],
        model=env["model"],
        temperature=env["temperature"],
        max_tokens=env["max_tokens"],
    )

    # 7. 生成综合文章
    composer = ArticleComposer(llm, COMPOSE_PROMPT_PATH)
    daily_article = composer.compose(all_articles)
    if daily_article:
        writer.write_daily_article(daily_article)

    # 8. 生成单篇摘要
    summarizer = SummaryExtractor(llm, SUMMARY_PROMPT_PATH)
    summaries = [summarizer.extract(art) for art in all_articles]
    writer.write_summaries(summaries, all_articles)

    # 9. 生成 HTML 日报
    html_writer.write_page(daily_article, summaries, all_articles)

    logger.info("=" * 50)
    logger.info("运行完成！输出目录: data/")
    logger.info("  综合文章: %s", article_dir)
    logger.info("  单篇摘要: %s", summary_dir)
    logger.info("  HTML 日报: %s", DATA_DIR / "daily_html")


# -- 定时任务 ----------------------------------------------
def run_scheduled(env: dict, rules: dict):
    import time
    import schedule

    logger = logging.getLogger("edusnap.scheduler")
    logger.info("定时模式已启动，每天 08:00 运行")

    schedule.every().day.at("08:00").do(
        run_pipeline, env=env, rules=rules,
    )

    # 首次立即运行
    run_pipeline(env, rules)

    while True:
        schedule.run_pending()
        time.sleep(60)


# -- 爬虫规则测试器 -----------------------------------------
class ScraperTester:
    """
    测试 config/scraping_rules.yaml 中的 CSS 选择器是否有效。

    用法:
        tester = ScraperTester(env, rules)
        tester.test_all()                         # 测试 sources.md 所有来源
        tester.test_single("https://example.com")  # 测试单个 URL
    """

    def __init__(self, env: dict, rules: dict):
        self.env = env
        self.rules = rules
        self.generic_rule = rules.get("generic_list_rule", {})
        self.fetcher = Fetcher(
            timeout=env["timeout"],
            delay=env["delay"],
            use_playwright=env["use_playwright"],
            playwright_headless=env["playwright_headless"],
        )
        self.cleaner = Cleaner()

    # -- 公开入口 ------------------------------------------

    def test_all(self, urls: list[str]) -> None:
        """测试 sources.md 中的所有来源，最后汇总无日期的文章"""
        all_undated: list[tuple[str, str, str]] = []  # (domain, title, url)
        for url in urls:
            domain = extract_domain(url)
            print()
            print("=" * 72)
            print(f"  [SITE] {domain}")
            print(f"  [URL]  {url}")
            print("=" * 72)
            undated = self._test_url(url, domain)
            all_undated.extend((domain, a.title, a.url) for a in undated)

        # 汇总所有无日期的文章
        if all_undated:
            print()
            print("=" * 72)
            print("  [WARN] 以下文章未匹配到日期，请检查 date_css 选择器")
            print("=" * 72)
            for domain, title, url in all_undated:
                t = self._safe(title, 50)
                print(f"  {domain}: \"{t}\"")
                print(f"          {url}")
            print(f"  共 {len(all_undated)} 篇无日期文章")

    def test_single(self, url: str) -> None:
        """测试单个 URL"""
        domain = extract_domain(url)
        print()
        print("=" * 72)
        print(f"  [TEST] 测试单个 URL: {url}")
        print("=" * 72)
        self._test_url(url, domain)

    # -- 单 URL 测试 ---------------------------------------

    def _test_url(self, url: str, domain: str) -> list:
        """测试单个 URL，返回无日期的文章列表"""
        site_rule = self.rules.get(domain, {})

        # 1. 抓取
        print(f"\n  >> 第1步: 抓取页面...")
        result = self.fetcher.fetch(url)

        if result is None:
            print(f"  [FAIL] 抓取失败 -- 无法访问该 URL")
            self._print_raw_hint(url)
            return []

        print(f"  [OK] 抓取成功 (HTTP {result.status_code})"
              f"{' [Playwright 兜底]' if result.fallback_used else ''}")
        print(f"     页面大小: {len(result.html):,} 字符")

        # 2. 测试规则
        print(f"\n  >> 第2步: 测试 CSS 选择器...")

        if site_rule:
            print(f"\n  -- 站点特定规则 [{domain}] --")
            self._test_selectors(result.soup, site_rule, domain)
        else:
            print(f"\n  [WARN] 未找到 {domain} 的特定规则，使用通用规则 --")

        print(f"\n  -- 通用规则 (generic_list_rule) --")
        self._test_selectors(result.soup, self.generic_rule, domain)

        # 3. 尝试用最匹配的规则解析文章
        print(f"\n  >> 第3步: 尝试解析文章...")
        parser = Parser(self.rules)
        articles = parser.parse(result, domain)
        self._print_articles(articles)

        # 4. 暴露原始 HTML 片段辅助调试
        print(f"\n  >> 第4步: 调试信息")
        self._print_debug_hints(result.soup, domain)

        # 返回无日期的文章供汇总
        return [a for a in articles if not a.date]

    # -- 选择器测试 ----------------------------------------

    def _test_selectors(self, soup: BeautifulSoup, rule: dict, domain: str) -> None:
        """测试单个规则集中的所有 CSS 选择器"""
        selectors = [
            ("[1] 文章容器 (article_list_css)", rule.get("article_list_css", self.generic_rule.get("article_list_css", "article"))),
            ("[2] 标题 (title_css)", rule.get("title_css", self.generic_rule.get("title_css", "h2 a, h3 a"))),
            ("[3] 链接 (link_css)", rule.get("link_css", self.generic_rule.get("link_css", "a"))),
            ("[4] 日期 (date_css)", rule.get("date_css", self.generic_rule.get("date_css", ".date, time"))),
            ("[5] 正文 (content_css)", rule.get("content_css", self.generic_rule.get("content_css", ".content, .body"))),
        ]

        for label, css in selectors:
            if not css:
                print(f"  {label}: (未配置)")
                continue
            elements = soup.select(css)
            status = "[OK]" if elements else "[FAIL]"
            print(f"  {status} {label}")
            print(f"     selector: {css}")
            print(f"     匹配数量: {len(elements)}")
            if elements:
                # 显示前 3 个匹配项的预览
                for i, el in enumerate(elements[:3], 1):
                    text = el.get_text(strip=True)
                    preview = self._safe(text, 80)
                    print(f"       [{i}] {preview}")

    # -- 文章展示 ------------------------------------------

    @staticmethod
    def _safe(text: str, maxlen: int = 0) -> str:
        """安全输出，过滤非 ASCII 字符避免 GBK 终端报错"""
        s = text.encode("ascii", "ignore").decode()
        if maxlen and len(s) > maxlen:
            s = s[:maxlen] + "..."
        return s

    def _print_articles(self, articles: list) -> None:
        if not articles:
            print(f"  [FAIL] 未解析到任何文章")
            return
        print(f"  [OK] 成功解析 {len(articles)} 篇文章:")
        for i, art in enumerate(articles, 1):
            print(f"    [{i}] {self._safe(art.title, 60)}")
            print(f"        +- 链接: {art.url}")
            print(f"        +- 日期: {art.date or '未知'}")
            content_preview = self.cleaner.clean_article_text(art.content_text)
            if content_preview:
                preview = self._safe(content_preview, 100)
                print(f"        L- 正文预览: {preview}")

    # -- 调试辅助 ------------------------------------------

    def _print_debug_hints(self, soup: BeautifulSoup, domain: str) -> None:
        """当选择器匹配为 0 时，暴露页面结构帮助调试"""
        # 展示页面中实际的标签结构
        print(f"  页面标签统计:")
        for tag in ["article", "a", "h2", "h3", "h4", "time", "img"]:
            count = len(soup.find_all(tag))
            if count > 0:
                print(f"    <{tag}> x {count}")

        # 展示前 5 个含链接的标题 (辅助发现正确的选择器)
        print(f"  页面中带链接的标题:")
        seen = set()
        for tag in ["h2", "h3", "h4"]:
            for heading in soup.find_all(tag):
                link = heading.find("a")
                if link:
                    text = heading.get_text(strip=True)
                    if text and text not in seen:
                        seen.add(text)
                        preview = self._safe(text, 80)
                        print(f"    <{tag}> -> <a href=\"{link.get('href', '')}\"> {preview}")

    def _print_raw_hint(self, url: str) -> None:
        """URL 不可达时的建议"""
        print(f"  [TIP] 建议:")
        print(f"    1. 检查 URL 是否正确: {url}")
        print(f"    2. 该网站可能屏蔽了爬虫，尝试在 .env 中设置 USE_PLAYWRIGHT=true")
        print(f"    3. 或手动在浏览器中打开确认")


# -- CLI ---------------------------------------------------
def _preflight_check(env: dict, args) -> bool:
    """启动前检查：确保环境就绪，对非技术用户友好提示"""
    ok = True

    # 1. 检查 sources.md
    if not SOURCES_PATH.exists():
        print()
        print("=" * 60)
        print("  [X] 缺少新闻来源文件")
        print()
        print("  请在以下文件中添加你要追踪的网站和公众号:")
        print(f"    {SOURCES_PATH}")
        print()
        print("  格式示例:")
        print("    - https://www.cam.ac.uk/latest-news")
        print("    - wechat:公众号名称")
        print("=" * 60)
        ok = False

    # 2. 检查 prompts 文件
    for prompt_file in [COMPOSE_PROMPT_PATH, SUMMARY_PROMPT_PATH]:
        if not prompt_file.exists():
            print()
            print("=" * 60)
            print(f"  [X] 缺少提示词模板: {prompt_file.name}")
            print(f"  请确保 config/prompts/ 目录下有该文件")
            print("=" * 60)
            ok = False

    # 3. 检查 LLM 密钥（仅 --no-llm 时不阻塞，其他情况提示）
    if not args.no_llm and not env.get("api_key"):
        print()
        print("=" * 60)
        print("  [!] 未配置 LLM API 密钥")
        print()
        print("  如需 AI 自动合成新闻，请在 .env 文件中设置:")
        print("    LLM_API_KEY=你的API密钥")
        print()
        print("  或者运行时加上 --no-llm 跳过 AI 步骤（仅抓取+输出到 HTML）")
        print("=" * 60)

    return ok


def main():
    env = load_env()
    setup_logging(env["log_level"])
    rules = load_rules()

    parser = argparse.ArgumentParser(
        description="留学新闻聚合器 -- 抓取留学新闻并生成综合文章",
    )
    parser.add_argument("--schedule", action="store_true", help="启用定时任务模式（每天 08:00）")
    parser.add_argument("--no-llm", action="store_true", help="跳过 LLM 步骤，仅抓取+清洗+输出")
    parser.add_argument("--dry-run", action="store_true", help="仅读取来源和规则，不执行抓取")
    parser.add_argument("--allow-undated", action="store_true",
                        help="允许储存无日期的文章（默认只保留当天文章）")
    parser.add_argument("--test-scraper", nargs="?", const=True, default=False,
                        help="测试爬虫规则是否有效；可附带具体 URL")

    args = parser.parse_args()

    # 启动前检查（非技术用户友好提示）
    if not _preflight_check(env, args):
        sys.exit(1)

    if args.test_scraper:
        tester = ScraperTester(env, rules)
        if isinstance(args.test_scraper, str):
            # 测试单个 URL
            tester.test_single(args.test_scraper)
        else:
            # 测试所有来源
            source_reader = SourceReader(SOURCES_PATH)
            urls = source_reader.read()
            if urls:
                tester.test_all(urls)
            else:
                print("[X] sources.md 中没有有效 URL，请先配置来源")
        return

    if args.schedule:
        run_scheduled(env, rules)
    else:
        run_pipeline(env, rules, skip_llm=args.no_llm, dry_run=args.dry_run,
                     allow_undated=args.allow_undated)


if __name__ == "__main__":
    main()
