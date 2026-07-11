# 🧪 测试样例生成器 — 计划书 v0.2

> 状态：**草案 v0.2 · 待评审**
> 上一版：v0.1（备份于 `/tmp/PLAN_v0.1.md`）
> 目标：把不同图书的 PDF 喂入流水线，让 LLM 找出真实缺陷，人工筛选后固化为回归测试样本，持续提升流水线稳定性。

---

## 🚨 零、本轮最重要的发现（**13 天倒计时**）

| 事项 | 详情 |
|------|------|
| **DeepSeek-V4-Flash** | ✅ 已发布（2026-04-24），284B 总参 / 13B 激活，1M 上下文，定位"快速 + 经济" |
| **DeepSeek-V4-Pro** | ✅ 同日发布，1.6T 总参 / 49B 激活，"性能对标顶级闭源" |
| ⚠️ **旧模型弃用** | `deepseek-chat` / `deepseek-reasoner` **将于 2026-07-24 15:59 UTC 弃用**（距今 13 天） |
| **价格对比（V4-Flash / V4-Pro，每 1M token）** | 输入缓存命中：$0.0028 / $0.003625；输入缓存未命中：$0.14 / $0.435；输出：$0.28 / $0.87；并发上限：2500 / 500 |
| **本项目影响** | `src/config.py` 当前用 `deepseek-chat`，13 天后会报 404，必须立刻迁到 `deepseek-v4-flash` |

**🔴 这是阻塞任务，优先级 > 测试样例生成器本身。** 建议本周末前完成迁移。

---

## 🎯 一、目标与边界

### 1.1 目标
- 用 **真实图书**（非手工造数据）作为输入，暴露当前流水线在 OCR / 翻译 / 清理 / 校对 / EPUB 各环节的盲区。
- 缺陷 → 经人工筛选 → 沉淀为可回归的 **测试样本**（业内称 **Golden Dataset** / **Regression Test Set**），让 `pytest` 越跑越能锁住质量底线。

### 1.2 非目标
- ❌ 不替代人工终审
- ❌ 不重写流水线
- ❌ 不做模型微调 / fine-tune

### 1.3 范围 — 首期 4 类问题（你确认的）
| 类型 | 描述 | 检测手段 |
|------|------|---------|
| **OCR 漏字** | 字符 ⌈⌋→□、多栏漏合、注脚丢失 | quote grep + 字符白名单校验 |
| **格式残留** | LaTeX `$..$`、`<div>`、HTML 实体未清 | 正则黑名单扫描 |
| **术语不一致** | 同一概念全书译名漂移 | `_glossary.json` 引用计数 + 编辑距离 |
| **prompt 残留** | `<think>...</think>`、`<|...|>`、英文 prompt 段 | 正则黑名单扫描 |

> 架构必须可扩展：你后续发现的"其他问题"通过新增 `IssueType` 枚举 + 检测器插件接入，**不改核心流程**。


---

## 🧬 二、整体流程（5 步闭环）

```
[PDF] → ① 跑流水线 → [final/*.md]
                       ↓
              ② LLM 缺陷扫描（deepseek-v4-flash）
                       ↓
              [扫描报告：缺陷候选清单]
                       ↓
              ③ 自动分级（critical/warn/info）
                       ↓
              [待审报告]
                       ↓
              ④ 人工审核（Argilla UI）
                       ↓
              [Golden Sample]
                       ↓
              ⑤ 写入 tests/fixtures/samples/ + 标注
```

### 步骤详解

#### ① 跑流水线
- 复用现有 `bash scripts/build-book.sh books/<书名> books/_inbox/<pdf> --lang <xx> --resume`
- 输出：`books/<书名>/final/*.md`

#### ② LLM 缺陷扫描
- 模型：**`deepseek-v4-flash`**（fast + cheap + 1M ctx 装得下整章）
- Prompt：新增 `src/prompts/defect_scan.md`，强制 JSON 输出
- Schema：

```json
{
  "issues": [
    {
      "id": "ocr-001",
      "type": "ocr_missing|format_residue|term_inconsistent|prompt_residue",
      "severity": "critical|warn|info",
      "quote": "原文片段（≤30 字）",
      "location": "chapter-XX.md:行号",
      "explanation": "一句话说明",
      "suggested_fix": "建议修复方向"
    }
  ]
}
```

- **强制校验**：
  - JSON 必须合法（schema 校验）
  - `quote` 必须在原文中 `grep` 命中（防 LLM 幻觉）
  - 每章最多 5 条（防刷屏）

#### ③ 自动分级
- `severity` 排序 → critical 直送人工，info 仅入档

#### ④ 人工审核 — **采用 Argilla 方案（详见第五节）**

#### ⑤ 沉淀 Golden Sample
- 文件结构（采用 **Inspect AI 的 Sample 风格**）：

```
tests/fixtures/samples/
├── corpus.jsonl              # 主索引（每行一个 sample）
├── <书名>/<sample_id>/
│   ├── input.md              # 触发缺陷的最小输入
│   ├── expected.md           # 期望修复后输出
│   └── meta.yaml             # 缺陷类型、来源 PDF、首次发现日期、严重度
```


---

## 🏗️ 三、新增模块设计

### 3.1 `src/sample_generator.py`（新）
CLI 入口：`yt-scan-defects`

```python
def scan_chapter(md_path: str, *, model: str = "deepseek-v4-flash") -> list[Issue]:
    """对单章 Markdown 跑缺陷扫描，返回结构化 issue 列表"""

def scan_book(book_dir: str, *, workers: int = 10) -> ScanReport:
    """批量扫整本书，写入 books/<书名>/defects_report.json"""

# 检测器插件（首期 4 类 + 未来扩展）
class IssueDetector(Protocol):
    name: str
    def detect(self, chapter_md: str) -> list[Issue]: ...

REGISTRY: dict[str, IssueDetector] = {
    "ocr_missing":        OCRMissingDetector(),
    "format_residue":     FormatResidueDetector(),
    "term_inconsistent":  TermInconsistencyDetector(glossary=load_glossary()),
    "prompt_residue":     PromptResidueDetector(),
}
```

**关键设计**：
- 双轨检测：**LLM 自由扫描** + **规则检测器**（LLM 擅长语义，规则擅长已知模式）
- 两路结果合并去重

### 3.2 `src/sample_curator.py`（新）
CLI 入口：`yt-curate-samples` — 导出审核结果到 fixtures + pytest 骨架

```python
def load_report(book_dir) -> ScanReport
def export_to_fixtures(report, selected_ids: list[str], target: str)
def emit_pytest_stub(fixture_dir, test_id) -> str
```

### 3.3 Prompt 设计
- 新增 `src/prompts/defect_scan.md`
- 关键约束：
  - 必须输出合法 JSON
  - `quote` 必须能在原文中 `grep` 命中
  - 限制每类问题最多报 3 条（避免模型刷屏同类）
  - 必须从 `IssueType` 枚举中选 type（防自由发挥）

---

## 📦 四、交付物 Checklist

- [ ] **P0 阻塞**：迁移 `src/config.py` 至 `deepseek-v4-flash`（含 `.env.example`）
- [ ] `src/sample_generator.py` + CLI `yt-scan-defects`
- [ ] `src/sample_curator.py` + CLI `yt-curate-samples`
- [ ] `src/prompts/defect_scan.md`
- [ ] `src/detectors/` 目录 + 4 个内置检测器
- [ ] `tests/fixtures/samples/` 目录约定 + corpus.jsonl schema
- [ ] `tests/test_sample_generator.py`（10 个单测，覆盖 4 类检测 + JSON 解析 + quote 校验）
- [ ] `docs/TEST_SAMPLE_GENERATOR.md`（使用手册）
- [ ] README 同步：新增两 CLI + 模型迁移说明


---

## 🎯 五、人工审核 UI 方案 — Argilla 调研结论

### 5.1 调研对象

| 方案 | 类型 | 适配度 | 备注 |
|------|------|--------|------|
| **Argilla** ⭐ | 开源数据标注平台（HuggingFace 生态） | ★★★★★ | 专治 LLM 输出审核；Python SDK 直连；支持人工+LLM 混合标注 |
| Label Studio | 开源标注工具（HumanSignal） | ★★★ | 通用标注，配置 JSON schema 略繁琐 |
| Doccano | 开源文本标注 | ★★ | 老牌但维护节奏慢，UI 偏老 |
| Promptfoo | LLM 红队 + eval | ★★ | 偏 eval，不擅长大规模人工审核 |
| DeepEval | LLM 单测框架 | ★★★ | pytest 友好，但人工审核 UI 弱 |
| Inspect AI (UK AISI) | LLM eval 框架 | ★★★ | sample dataset 设计值得借鉴，但 UI 不是重点 |
| 自研 Streamlit | 内部工具 | ★★ | 控制力强但要自己写很多 |

### 5.2 推荐：**Argilla**

**为什么选 Argilla**：
1. **专为 LLM 输出设计** — 字段直接对应 issue schema（type / severity / quote / explanation）
2. **Python SDK** — `argilla_sdk.log(...)` 一行上传 issue
3. **支持 suggestion** — LLM 提建议 + 人工 accept/reject，正好对应你的需求
4. **HF 生态** — 与 transformers / datasets 无缝，未来易集成
5. **自部署简单** — `docker run -p 6900:6900 argilla/argilla` 一行起

**最小化集成代码草图**：

```python
# src/sample_curator.py
import argilla as rg

def upload_to_argilla(report: ScanReport, book_name: str):
    dataset = rg.FeedbackDataset(
        fields=[
            rg.TextField(name="quote", title="原文片段"),
            rg.TextField(name="context", title="上下文 ±100字", use_markdown=False),
        ],
        questions=[
            rg.LabelQuestion(name="issue_type", labels=["ocr_missing", "format_residue", "term_inconsistent", "prompt_residue", "false_positive"]),
            rg.LabelQuestion(name="severity", labels=["critical", "warn", "info"]),
            rg.TextQuestion(name="fix_suggestion", required=False),
        ],
    )
    samples = []
    for issue in report.issues:
        samples.append({
            "fields": {
                "quote": issue.quote,
                "context": extract_context(issue.location, ±100),
            },
            "suggestions": [{"question_name": "issue_type", "value": issue.type},
                            {"question_name": "severity", "value": issue.severity}],
        })
    dataset.add_records(samples)
    dataset.push_to_argilla(name=f"{book_name}-defects")
```

**你的审核工作流**：
1. 浏览器打开 `http://localhost:6900`
2. 看 LLM 给的 issue（带 suggestion）
3. 三选一：✅ accept / ❌ reject / ✏️ modify
4. 点 export → JSONL → 落入 `tests/fixtures/samples/corpus.jsonl`

### 5.3 备选：纯 CLI（如果你不想跑 Docker）
- `yt-curate-samples books/<书名>` → 终端交互（fzf 多选 + vi 编辑）
- 优点：零依赖；缺点：体验差，量大时会哭

---

## 📅 六、里程碑（建议）

| 阶段 | 内容 | 估时 | 阻塞？ |
|------|------|------|--------|
| **M0** | 迁移 `deepseek-v4-flash` + 跑通一次 `yt-translate` | 0.5 天 | 🔴 必做 |
| M1 | `sample_generator.py` + 4 个 detector + JSON prompt + 单测 | 1.5 天 | - |
| M2 | 用《城市权利》`final/` 跑通首轮扫描 | 0.5 天 | - |
| M3 | `sample_curator.py` + Argilla 集成 + pytest 骨架生成 | 1 天 | - |
| M4 | 首批 Golden Sample 入库 + 接入 CI（命中 KNOWN_GAPS G1+G2） | 0.5 天 | - |


---

## 🔗 七、与 KNOWN_GAPS.md 的关系

直接命中并推进：
- **G1 CI/CD 缺失** → 接入 GitHub Actions 后 Golden Sample 自动回归
- **G2 测试覆盖率不足** → 本项目直接产出真实样本
- **G3 可观测性** → 扫描报告 JSON + Argilla dataset 都是结构化数据
- **G4 错误处理粗糙** → 强制 JSON schema 校验 + quote grep 校验
- **G5 状态管理脆弱** → corpus.jsonl 是显式状态机，替代 `glob("doc_*.md")` 魔数
- **G7 文档对齐** → 新增 `docs/TEST_SAMPLE_GENERATOR.md` + README 同步
- **G10 prompt 注入** → 检测器 `prompt_residue` 直接捕获此类问题

---

## 🛡️ 八、风险与对策

| 风险 | 对策 |
|------|------|
| 🔴 旧模型 13 天后不可用 | 本周末完成 V4-Flash 迁移（独立 PR，优先级最高） |
| LLM 漏报（false negative） | 规则检测器兜底 + 抽样人工比对监控 recall |
| LLM 幻觉（quote 不存在） | 强制 quote 在原文 grep 命中，否则丢弃 |
| 不同语种 prompt 不通用 | prompt 抽出语言变量，按 src-lang 切换 |
| 测试样本爆炸导致 CI 变慢 | corpus.jsonl 抽样回归 + 每类 ≤5 条 |
| Argilla 部署成本 | 先 CLI 兜底，按需切 Docker |
| 4 类问题定义边界模糊 | IssueType 枚举强制收敛，允许 `false_positive` |

---

## 🎬 九、立即可执行的下一步

1. ✅ 你确认 Argilla 方案 vs 纯 CLI 方案
2. 🔴 **先做 M0**（模型迁移，13 天倒计时）
3. 我开始 M1：`sample_generator.py` + 4 个 detector 骨架
4. 跑通后用《城市权利》生成首批 Golden Sample

---

## 📚 附录 A：检索证据

### A.1 DeepSeek-V4-Flash 来源
- 官方公告：https://api-docs.deepseek.com/news/news260424/
- 价格页：https://api-docs.deepseek.com/quick_start/pricing/
- HuggingFace：https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash
- NVIDIA NIM：https://build.nvidia.com/deepseek-ai/deepseek-v4-flash/modelcard
- arxiv：https://arxiv.org/abs/2606.19348

### A.2 Golden Dataset 行业参考
- Maxim AI "Building a Golden Dataset for AI Evaluation"
- FieldGuideToAI "Evaluations 201: Golden Sets & Rubrics"
- TeachYou Academy "Building a Golden Dataset for LLM Evaluation"

### A.3 开源人工审核工具
- **Argilla**：https://github.com/argilla-io/argilla（HuggingFace 生态）
- **Label Studio**：https://github.com/HumanSignal/label-studio
- **Doccano**：https://github.com/doccano/doccano
- **Promptfoo**：https://github.com/promptfoo/promptfoo
- **DeepEval**：https://github.com/confident-ai/deepeval
- **Inspect AI**：https://github.com/UKGovernmentBEIS/inspect_ai

---

## 📝 附录 B：相比 v0.1 的变更

| 变更 | 原因 |
|------|------|
| + 🚨 零节：13 天模型弃用倒计时 | 你说"项目数据太老"，实际比这更紧急——是真弃用 |
| 模型 `deepseek-chat` → `deepseek-v4-flash` | V4-Flash 专为快速+经济场景，与扫描器场景契合 |
| 锁定 4 类问题（首期）+ 插件化扩展 | 你确认了 OCR 漏字 / 格式残留 / 术语不一致 / prompt 残留 |
| 引入 Argilla 作为人工审核 UI | 你说"不懂，找其他人方案"——Argilla 是 LLM 输出审核的事实标准 |
| 引入 Golden Dataset 术语 | 业内标准叫法，避免"测试样例"歧义 |
| 文件结构改为 corpus.jsonl + meta.yaml | 借鉴 Inspect AI sample dataset 设计 |
| 新增双轨检测（LLM + 规则） | 规则检测器可以兜底 LLM 漏报，且能直接覆盖 4 类已知问题 |

