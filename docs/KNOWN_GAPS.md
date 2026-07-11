# 📋 KNOWN GAPS — 距离生产级别的差距清单

> **本文件作用**：本轮重构已落地 P0（双轨制收敛、配置归一、CLI 入口标准化）。
> 下列项目是 *尚未* 解决的问题，按优先级排列。详见上轮对话诊断。
> 最后更新: 2026-07-11

---

## 🟠 P1 — 必须补的工程基础设施

### G1. CI/CD 缺失
- 没有 `.github/workflows/`、`pyproject.toml` 无 ruff/mypy/pytest 配置
- 没有 lock 文件（uv.lock / poetry.lock / requirements.txt）
- 任何一次 push 都没有自动跑测试

### G2. 测试覆盖率结构性不足
- 12 测试，全在字符串层（split/merge）
- **核心 LLM 模块 0 测试**：OCR / translate / proofread / scan 四个流水线命门
- 没有 LLM mock → CI 跑就要密钥 → CI 永远跑不起来
- `tests/fixtures/` 是空目录

### G3. 日志与可观测性
- 全是 `print()`，失败仅 stdout
- 无 token 用量统计（成本/重试次数无法复盘）
- 无结构化错误报告，CI parse 不出 exit code 语义

### G4. 错误处理粗糙
- `call_llm` 不区分 4xx / 5xx / 429，不读 `Retry-After`
- LLM 返回非 JSON 时各模块静默吞（`proofread.py` `re.search` 失败 → 用户看不到"建议被吞了"）
- `sys.exit("ERROR: ...") exit code 全是 1，吞语义

---

## 🟡 P2 — 架构债

### G5. 数据/状态管理基于文件系统魔数
- 断点续传靠 `glob("doc_*.md")` + 文件名匹配数字 → 脆弱
- `meta.yaml` 仅被 README 提及，运行时无人解析
- `_glossary.json` 无版本、无冲突解决
- 书籍作者名 `run_epub.py` 和 `split.py` 解析规则不一致（一个 `rsplit` 后两段、一个 `split` 后两段）

### G6. 配置仍较分散
- CLI 参数全靠位置参数 + 模块顶部 hardcode 常量（`CONCURRENCY=5`、`MAX_TOKENS=8000`）
- `.env` 文档承诺自动加载但代码没装 `python-dotenv`
- 想 override 须改源码或 env var

### G7. 包元信息残缺
- 无 `LICENSE`
- 无 `CHANGELOG.md`
- 项目名 `yishu-translate` ≠ CLI 前缀 `yt-` ≠ import path `src`（历史包袱，暂无歧义但易混）

### G8. 安全与可恢复性
- 用 `mktemp` 已修并行封面冲突 ✅（本轮顺手）
- 仍无回滚：翻译文件被覆盖后无 auto-snapshot
- prompt 注入面未审计（`SYSTEM_PROMPT` 中允许保留 `<think>`、可被 prompt 攻击用作侧信道）

---

## 🟢 P3 — 可持续性 / 体验

### G9. 文档与实际不完全对齐
- README"先 export 或在 .env 中填入"，但**未实现 .env 读取**（缺 python-dotenv）
- README 里项目结构图还显示 `bin/` 子树（已删除，但 README 未同步）
- 没有 `CONTRIBUTING.md` / `docs/architecture.md`

### G10. 边角瑕疵
- `src/scan.py` 仍 import `time` 但无调用
- `src/batch_retranslate.py` 在 `__main__` 里重新 import argparse（应统一在 CLI 层）
- `tests/test_cli_entrypoints.py` 是烟雾测试，断言 `callable(main)`，CI 跑过等于什么也没验

---

## ✅ 已落地（本轮重构）

- [x] 删除 `bin/` 目录全部 13 个 stub/旧实现文件
- [x] 删除 `scripts/run-*.py`（连字符 wrapper）
- [x] 删除 `scripts/__init__.py`，scripts 不再是 package
- [x] `bin/verify_epub.py` → `src/verify_epub.py` + 新 `scripts/run_verify_epub.py` + `yt-verify-epub` CLI
- [x] 新增 `yt-proofread`、`yt-verify-epub` 到 pyproject.toml `[project.scripts]`
- [x] 统一配置源：`src/config.py` 单点 `DEEPSEEK_API_URL/MODEL/TIMEOUT/MAX_RETRIES`
- [x] 替换 `src/translate.py` / `src/ocr.py` / `src/batch_retranslate.py` 中 hardcode `timeout=300` → `DEFAULT_API_TIMEOUT`
- [x] 修 src/*.py 中重复 `import sys`（translate/proofread/scan/batch_retranslate）
- [x] `scripts/build-book.sh` 重写：调 yt-* CLI、修正步骤顺序（clean → split → merge → proofread → scan → epub）、原子化封面提取
- [x] `tests/test_cli_entrypoints.py` 改用 importlib.util，不再依赖 scripts.* 包结构；新增两项冒烟（pyproject 覆盖、bin/wrapper 残留检测）

---

## 🔧 下一轮路线建议（按 ROI）

| # | 任务 | 估时 | 影响的 Gap |
|---|------|------|----------|
| 1 | 加 ruff + pytest GitHub Actions；用 `responses` mock 所有 `requests` 调用 | 半天 | G1+G2+G4 |
| 2 | `src/{ocr,translate,proofread,scan}.py` 各加 5-10 单测 + golden fixture | 1 天 | G2 |
| 3 | 引入 `python-dotenv` + 真正的 Settings（pydantic-settings 或 dataclass） | 2h | G6+G9 |
| 4 | `logging` 替 print + token 计数 + 结构化 error report JSON | 3h | G3+G4 |
| 5 | LICENSE（MIT/Apache-2.0）+ CHANGELOG.md + 同步 README 删除 bin/ 残留 | 1h | G7+G9 |
