# EduSnap — 留学新闻聚合器 v2.0

自动抓取全球各大院校官网新闻和微信公众号文章，通过 LLM 整合为每日综合文章，输出 **Markdown + HTML** 双格式，非技术用户也能直接打开浏览。

## 功能

- **🌐 网站新闻** — 支持剑桥、华威、KCL、爱丁堡、港科大、理工大、LSE 等 7+ 站点
- **📱 公众号新闻** — 通过搜狗微信搜索按公众号名称查找最新文章，自动过滤近 2 天内容
- **🤖 LLM 合成** — 调用 DeepSeek / OpenAI 将多篇新闻合成为一篇综合文章
- **📄 双格式输出** — Markdown（开发者友好）+ HTML（带样式，浏览器直接打开）
- **🧹 智能处理** — CSS 选择器精准解析、URL+标题去重、日期过滤
- **📊 站点报告** — 每次运行自动记录各站点抓取状态
- **🔍 爬虫测试** — `--test-scraper` 快速验证规则是否生效
- **🛡 异常检测** — 自动识别可能失效的公众号并汇总提醒

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY

# 3. 查看新闻来源
python main.py --dry-run

# 4. 运行（跳过 LLM，仅抓取 + 输出 HTML）
python main.py --no-llm

# 5. 完整运行（含 LLM 合成）
python main.py
```

运行后直接用浏览器打开 `data/daily_html/YYYY-MM-DD.html` 即可查看日报。

## 使用方式

```bash
python main.py                           # 完整运行（抓取 + LLM 合成）
python main.py --no-llm                  # 仅抓取，跳过 LLM（适合测试）
python main.py --dry-run                 # 仅查看来源列表
python main.py --test-scraper            # 测试所有爬虫规则
python main.py --test-scraper https://example.com/news  # 测试单个 URL
python main.py --allow-undated           # 保留无日期的文章
python main.py --schedule                # 定时模式（每天 08:00）
```

## 公众号配置

在 `config/sources.md` 中添加 `- wechat:` 开头的行即可追踪公众号：

```markdown
## 公众号来源

- wechat:魔都选校指南
- wechat:英国留学中心
- wechat:国际择校圈
```

爬虫会自动通过搜狗微信搜索查找这些公众号近 2 天发布的文章。如第 1 页无搜索结果，会提示可能存在名称错误或账号已注销。

## 目录结构

```
EduSnap/
├── main.py                      # 主入口
├── config/
│   ├── sources.md               # 新闻来源（网站 + 公众号）
│   ├── scraping_rules.yaml      # 各站点的 CSS 选择器规则
│   └── prompts/
│       ├── compose_article.txt  # 综合文章提示词
│       └── generate_summary.txt # 单篇摘要提示词
├── src/
│   ├── scraper/                 # 网页抓取与解析
│   │   ├── wechat_scraper.py    # 搜狗微信搜索（公众号）
│   │   ├── source_reader.py     # 来源列表读取
│   │   ├── fetcher.py           # 网页下载
│   │   └── parser.py            # HTML 解析
│   ├── processor/               # 文本清洗与去重
│   ├── llm/                     # LLM 调用与文章合成
│   └── output/                  # 输出（Markdown + HTML）
├── data/                        # 运行生成的日报（自动创建）
│   ├── daily_articles/          # 综合文章 .md
│   ├── daily_summaries/         # 单篇摘要 .md
│   └── daily_html/              # HTML 日报（浏览器直接打开）
├── logs/                        # 运行日志与站点报告
└── requirements.txt
```

## 已支持的站点

| 站点 | 文章 | 日期 | 备注 |
|---|---|---|---|
| cam.ac.uk | ✅ | ✅ | 剑桥大学 |
| warwick.ac.uk | ✅ | ✅ | 华威大学新闻稿 |
| ed.ac.uk | ✅ | ✅ | 爱丁堡大学 |
| polyu.edu.hk | ✅ | ✅ | 香港理工大学 |
| hkust.edu.hk | ✅ | ✅ | 香港科技大学（中文） |
| kcl.ac.uk | ✅ | ✅ | 伦敦国王学院 |
| lse.ac.uk | ✅ | ⚠️ | 部分卡片无日期 |
| 微信公众号 | ✅ | ✅ | 通过搜狗搜索，近 2 天 |

## 技术栈

- **Python 3.10+**
- **爬虫**: requests + BeautifulSoup4 + lxml
- **LLM**: LangChain + DeepSeek / OpenAI 兼容 API
- **配置**: pyyaml + python-dotenv
- **输出**: Markdown + 自包含 HTML（暗色模式自适应）

## License

MIT
