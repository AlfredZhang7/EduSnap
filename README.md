# EduSnap — 留学新闻聚合器 v1.0

自动抓取全球各大院校和留学资讯网站的新闻，通过 LLM 整合为每日综合文章和单篇摘要，输出 Markdown 文件。

## 功能

- **多源抓取** — 支持剑桥、华威、KCL、爱丁堡、港科大、理工大、LSE 等 7+ 站点
- **智能解析** — 依据 CSS 选择器精准提取标题、日期、正文
- **自动去重** — URL 精确去重 + 标题相似度去重
- **日期过滤** — 只保留今明两天的文章，避免历史数据混入
- **LLM 合成** — 调用 DeepSeek / OpenAI 将多篇新闻合成为一篇综合文章
- **单篇摘要** — 为每篇文章生成结构化摘要，便于快速浏览
- **站点报告** — 每次运行自动记录各站点的抓取成功/失败状态
- **爬虫测试** — `--test-scraper` 快速验证规则是否生效

## 快速开始

```bash
# 1. 克隆仓库
git clone <repo-url> && cd EduSnap

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY

# 4. 试运行（仅读取来源列表）
python main.py --dry-run

# 5. 运行
python main.py
```

## 使用方式

```bash
python main.py                           # 完整运行（抓取 + LLM 合成）
python main.py --no-llm                  # 仅抓取，跳过 LLM
python main.py --dry-run                 # 仅读取来源列表
python main.py --test-scraper            # 测试所有爬虫规则
python main.py --test-scraper https://example.com/news  # 测试单个 URL
python main.py --allow-undated           # 保留无日期的文章
python main.py --schedule                # 定时模式（每天 08:00）
```

## 目录结构

```
EduSnap/
├── main.py                      # 主入口
├── config/
│   ├── sources.md               # 新闻来源 URL 列表
│   ├── scraping_rules.yaml      # 各站点的 CSS 选择器规则
│   └── prompts/
│       ├── compose_article.txt  # 综合文章提示词
│       └── generate_summary.txt # 单篇摘要提示词
├── src/
│   ├── scraper/                 # 网页抓取与解析
│   ├── processor/               # 文本清洗与去重
│   ├── llm/                     # LLM 调用与文章合成
│   └── output/                  # Markdown 文件输出
├── data/                        # 生成的文章（自动创建）
├── logs/                        # 运行日志与站点报告（自动创建）
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

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller --onefile --console \
  --name EduSnap \
  --hidden-import bs4 --hidden-import lxml \
  --hidden-import yaml --hidden-import dotenv \
  --hidden-import requests \
  --hidden-import langchain_openai --hidden-import openai \
  --hidden-import src.scraper --hidden-import src.processor \
  --hidden-import src.llm --hidden-import src.output \
  --collect-data bs4 --collect-data lxml \
  --collect-all langchain_openai \
  main.py
```

将 `dist/EduSnap.exe` 连同 `config/` 目录和 `.env` 放在同一目录即可运行。

## 技术栈

- **Python 3.10+**
- **爬虫**: requests + BeautifulSoup4 + lxml
- **LLM**: LangChain + DeepSeek / OpenAI 兼容 API
- **配置**: pyyaml + python-dotenv
- **打包**: PyInstaller

## License

MIT
