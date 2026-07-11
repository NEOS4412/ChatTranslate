# 📚 书籍翻译流水线 — 项目总结

把 zlib 下载的外文 PDF（作者原本语言版）翻译成中文 EPUB，一行命令跑通。

**首个实战书籍**: Le Droit à la Ville (Henri Lefebvre) → `output/Le_Droit_A_La_Ville_I_Henri_Lefebvre.epub`（法语→简体中文，约 300 页）

---

## 📋 整体流程

```
PDF ──► PaddleOCR ──► 法/英 md（按页）──► DeepSeek 逐章翻译 ──► 中文 md
                                           │
                                           ▼
         AI 过滤无关章节（出版社广告等） + 格式清理 + 段落合并
                                           │
                                           ▼
         按 ## 切分章节 → 生成 .book 配置 → crowbook → EPUB
                                           │
                                           ▼
                            验证脚本检查格式问题
```

## 📁 目录结构约定

```
books/
├── _inbox/                  # 待处理 PDF
└── <书名_作者姓_作者名>/
    ├── raw/                 # 原始 PDF 软链（自动）
    ├── ocr/
    │   ├── doc_N.md         # 每页 OCR 原始 md
    │   ├── images/imgs/     # 提取的图片
    │   ├── _result.jsonl    # PaddleOCR 原始返回
    │   └── full_raw.md      # 按页合并（<!-- page:N --> 分隔）
    ├── translated/
    │   ├── _glossary.json   # 术语表（首跑自动生成，全书复用）
    │   └── chapters/
    │       └── ch_NNN_标题.md  # 逐章翻译结果
    ├── proofread/
    │   ├── full_zh.md       # 翻译合并 + 清理后的中文成品
    │   └── suggestions.json  # AI 校对建议（人工审阅）
    ├── chapters/             # 最终分章文件（手动微调后给 crowbook）
    │   ├── ch_000_front.md  # 前置内容（封面/版权声明）
    │   ├── ch_NNN.md        # 正文章节
    │   └── front/           # 前置图片等
    ├── cover.jpg            # 封面（自动从 PDF 首页截取）
    ├── style.css            # EPUB CSS 样式
    ├── images/ -> ocr/images # 图片软链
    ├── KNOWN_ISSUES.md      # 已知问题跟踪
    └── <书名>.book           # crowbook 配置文件
output/                      # 最终 EPUB 输出目录
bin/                         # 流水线脚本
```

## 🔧 脚本清单

| 脚本 | 作用 | 关键参数 |
|------|------|----------|
| `bin/ocr_paddle.py` | PaddleOCR 识别 PDF → 按页 md + 图片 | `--lang fr/en`, `--resume` |
| `bin/translate.py` | DeepSeek 逐章翻译（v2，推荐） | `--src-lang fr/en`, `--resume`, `--workers 5` |
| `bin/clean_md.py` | LaTeX 清理 / 标题降级 / 图片转换 | `--titles`, `--superscripts` |
| `bin/split_chapters.py` | 按 `##` 切分章节 + 自动生成 `.book` | `--front N`, `--protect` |
| `bin/proofread.py` | AI 整本校对 → suggestions.json | — |
| `bin/merge_paragraphs.py` | 合并跨页断行 | — |
| `bin/scan_untranslated.py` | 扫描未翻译的外文残留 | — |
| `bin/batch_retranslate.py` | 批量重新翻译低质量段落 | — |
| `bin/scan_final.py` | 最终质量扫描（格式/翻译/段落） | `--workers`, `--fix-merge` |
| `bin/verify_epub.py` | 验证 EPUB 完整性 | — |
| `bin/crowbook_build.sh` | crowbook 构建 EPUB（方案 A/B） | — |
| `bin/build_book.sh` | 一键全自动流水线（1→5） | `--lang fr/en` |

## 🚀 快速开始

### 一次性配置

```bash
export DEEPSEEK_API_KEY="sk-..."
export PADDLEOCR_TOKEN="..."
cargo install crowbook
```

### 端到端（一键跑通）

```bash
bin/build_book.sh books/<书名_作者> books/_inbox/原著.pdf --lang=fr
```

自动执行：OCR → 翻译 → 清理 → 校对 → EPUB。任何一步失败可加 `--resume` 续跑。

### 分步调试（灵活可控）

```bash
# 1) OCR
python3 bin/ocr_paddle.py books/_inbox/xxx.pdf books/<书名> --lang fr

# 2) 翻译（关键：按章节保持上下文）
python3 bin/translate.py books/<书名> --src-lang fr

# 3) 清理合并
python3 bin/clean_md.py books/<书名> --titles --superscripts
python3 bin/merge_paragraphs.py books/<书名> --fix-merge

# 4) 切分 + .book 配置
python3 bin/split_chapters.py books/<书名> --front 8 --protect

# 5) 构建 EPUB
bash bin/crowbook_build.sh books/<书名>/<书名>.book

# 6) 验证
python3 bin/verify_epub.py output/xxx.epub
```

## 🧠 实战踩坑记录

### 1. OCR 阶段

**PaddleOCR 输出特点**:
- 按页输出 `<img src="imgs/xxx.jpg">`，需改路径为 `images/imgs/`
- 有时输出 `<img... />` 自闭合 → 转成标准 `![alt](path)`
- 图片可能包在双层 `<div style="text-align:center">` 里
- 每天 2w 页配额限制

### 2. 翻译阶段（v1 → v2 演进）

**逐页翻译的坑（v1）**:
- 跨页句子断裂（如「将\n\n财富」变两段）
- 缺上下文导致术语不一致

**逐章翻译（v2，当前方案）**:
- 合并所有 OCR 页 → 按 `# ` 标题切分为章节 → 整章提交翻译
- `filter_chapters()` 用 DeepSeek 自动屏蔽出版社广告页等无关内容

**翻译参数**: `deepseek-v4-flash`, `temperature=0.3`, `max_tokens=8000`, 5 线程并发

### 3. 格式清理（PaddleOCR 常见残留）

| 问题 | 清理方式 |
|------|----------|
| `$^{e}$`, `$^{*}$`, `$^{x}$` LaTeX 上标 | clean_md.py 正则清理 |
| `<!-- page:203 -->` 页分隔符 | clean_md.py → 删掉 |
| `<sup>20</sup>` 日期上标 | 手动删除 |
| `<table>` 渲染失败 | 手动替换为文字 |
| 双层居中 div | clean_md.py 去嵌套 |

### 4. 段落合并（核心难点）

**规则**: 自然段结尾一定有 `。？！；：」】…`，没有的就是跨页断裂，需和下一段合并。章节标题和 `<25字` 副标题除外。

### 5. EPUB 构建

**crowbook 方案对比**:

| 方案 | 命令 | 适用 |
|------|------|------|
| A | `crowbook -s 单文件` | 简单书籍 |
| B | `crowbook .book 配置文件` | 复杂书籍，可控制章节顺序/前置/后置 |

**当前** 用方案 B。关键经验：
- crowbook 会转义所有行内 HTML（`<div>` → `&lt;div&gt;`）
- **样式必须通过外部 `epub.css` 文件注入**（`style.css`）
- 封面图片从 PDF 首页用 `pdftoppm` 截取

### 6. 最终 QC

`scan_final.py` 自动检查：未翻译残留、页分隔符、孤立 LaTeX、段落断裂。生成报告逐章扫描。

## ⚙️ API / 工具选型

| 组件 | 选型 | 理由 |
|------|------|------|
| OCR | PaddleOCR API | 免费 2w 页/天，法文+英文效果好 |
| 翻译 | DeepSeek (deepseek-v4-flash) | 性价比高，法→中质量不错 |
| EPUB 构建 | crowbook (Rust) | 轻量，CSS 灵活，配置简单 |
| 语言 | Python 3.14 + requests | 标准库够用 |

## 📐 书籍目录名规范

```
<书名_作者姓_作者名>
例：Le_Droit_A_La_Ville_Lefebvre_Henri
```

各部分下划线分隔，`split_chapters.py` 会自动从目录名解析书名和作者，用于 `.book` 配置。

## 📌 实操 checklist（扩展新书用）

- [ ] PDF 放进 `books/_inbox/`
- [ ] 运行 OCR（检查配额）
- [ ] 运行翻译（检查术语表是否合理）
- [ ] 手动审查 `proofread/full_zh.md`：段落断裂、格式残留
- [ ] 运行段落合并脚本
- [ ] 运行 `split_chapters.py` 切分章节
- [ ] 检查生成的 `.book`：章节顺序、前置/后置标记
- [ ] 手动修复特殊问题（表格、引文、目录干扰项）
- [ ] 运行 `crowbook_build.sh`
- [ ] 用 EPUB 阅读器实测
- [ ] 运行 `verify_epub.py` + 手动扫描
