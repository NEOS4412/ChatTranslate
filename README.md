# 📚 书籍翻译流水线

> 外文 PDF → OCR → AI 翻译 → 格式清理 → EPUB

## 快速开始

```bash
# 1. 配置 API 密钥
export DEEPSEEK_API_KEY="sk-..."
export PADDLEOCR_TOKEN="..."

# 2. 一键跑通
bash scripts/build-book.sh books/城市权利-列斐伏尔 books/_inbox/原著.pdf --lang fr

# 或分步执行：
python3 scripts/run-ocr.py books/_inbox/xxx.pdf books/城市权利-列斐伏尔 --lang fr
python3 scripts/run-translate.py books/城市权利-列斐伏尔 --src-lang fr
python3 scripts/run-clean.py books/城市权利-列斐伏尔 --titles
python3 scripts/run-merge.py books/城市权利-列斐伏尔
python3 scripts/run-split.py books/城市权利-列斐伏尔 --front 8 --protect
bash scripts/build-book.sh books/城市权利-列斐伏尔
python3 scripts/run-scan.py books/城市权利-列斐伏尔 --workers 10
```

## 项目结构

```
├── src/                    # 可导入的 Python 核心模块
│   ├── config.py          # 共享配置（API URL / 模型名）
│   ├── ocr.py             # PaddleOCR 封装
│   ├── translate.py       # DeepSeek 翻译引擎
│   ├── clean.py           # 格式清理（LaTeX / 标题 / 脚注）
│   ├── merge.py           # 跨页段落合并
│   ├── split.py           # 按标题切分章节
│   ├── proofread.py       # AI 全文校对
│   ├── scan.py            # 最终质量扫描 + 自动修复
│   └── epub.py            # EPUB 构建（crowbook 封装）
│
├── scripts/                # CLI 入口（薄层，委托 src/）
│   ├── run-ocr.py
│   ├── run-translate.py
│   └── build-book.sh      # 一键流水线
│
├── bin/                    # 向后兼容的包装器
│
├── books/
│   ├── _inbox/            # 待处理 PDF
│   └── 城市权利-列斐伏尔/  # 单书目录
│       ├── meta.yaml      # 元数据（书名/作者/语言）
│       ├── assets/        # 资源（封面 / CSS）
│       ├── stages/        # 流水线中间数据
│       │   ├── 01-ocr/
│       │   ├── 02-translated/
│       │   ├── 03-merged/
│       │   └── 04-proofread/
│       └── final/         # 最终分章文件
│
├── tests/                  # 单元测试
│   ├── test_merge.py
│   ├── test_split.py
│   └── fixtures/
│
├── output/                 # 最终 EPUB
├── pyproject.toml          # 项目元数据
└── .env.example            # API 密钥模板
```

## API 配置

| 变量 | 用途 | 获取方式 |
|------|------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek 翻译+校对 | [platform.deepseek.com](https://platform.deepseek.com) |
| `PADDLEOCR_TOKEN` | PaddleOCR 文字识别 | [aistudio.baidu.com](https://aistudio.baidu.com) |

## 关键设计

- **逐章翻译**：合并 OCR 页面 → 按 `#` 标题切分为章节 → 整章提交翻译，保持上下文连贯
- **断点续传**：所有脚本支持 `--resume`，中断后从上次进度继续
- **并行翻译**：默认 5 线程并发，`--workers N` 调整
- **术语表**：首跑时 AI 自动抽取术语 → `_glossary.json`，全书复用

## 已知局限

- PaddleOCR 每天 2 万页免费配额
- crowbook 不支持行内 HTML（`<div>` → `&lt;div&gt;`），样式需外部 CSS
- 表格和复杂排版需人工干预

## Acknowledgements

本项目重度依赖以下开源工具：

- [crowdagger/crowbook](https://github.com/crowdagger/crowbook) — Rust 编写的轻量 EPUB 生成器，支撑了从 Markdown 到 ePub 的构建链路
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — 百度 OCR 引擎，提供多语言文字识别能力
- [DeepSeek](https://deepseek.com) — 高效经济的大语言模型翻译引擎
- [zlib](https://z-lib.io) — 提供原始外文 PDF 资源
