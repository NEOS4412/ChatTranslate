# 《城市权利》(Le Droit à la Ville) — 已知问题清单

> 本文档列出自动化流程无法 100% 解决、需人工复核/修复的问题。
> 最后更新: 2026-07-11

## 1. 翻译质量类（需人工阅读）

### 1.1 ch_019 长段完整性
- **状态**: 已修复 ✅
- **操作**: 重新翻译了全书 17 个低质量页面（doc_100-107 等），ch_019 从 8889 字扩展为 5508 字（去除了页分隔符和重复内容后实际内容更紧凑）

### 1.2 ch_020 章节完整性
- **状态**: 已修复 ✅
- **操作**: 重翻后 ch_020 从 1300 字扩展为 9533 字，章节内容完整

### 1.3 翻译腔残留
- **状态**: 部分修复
- **位置**: 全本
- **说明**: 重翻的 17 页使用 max_tokens=8000 完整翻译，已消除截断问题。仍可能有少量直译痕迹
- **建议**: 校对阶段（proofread.py）的 suggestions.json 包含 105 条建议，可参考

### 1.4 术语一致性
- **状态**: 保留
- **位置**: 全本
- **说明**: 术语表目前 47 条，术语一致性取决于翻译阶段

## 2. 格式类（已全部修复）

### 2.1 页分隔符残留
- **状态**: 已修复 ✅
- **操作**: clean_md.py 规则 3.1 + scan_final.py 双重清理

### 2.2 LaTeX 残留
- **状态**: 已修复 ✅
- **操作**: clean_md.py 清理 $^{X}$ $^{*}$ $^{e}$ 等

### 2.3 段间断行
- **状态**: 已修复 ✅
- **操作**: scan_final.py --fix-merge 合并了 44 个章节的句间断行

### 2.4 未翻译段落
- **状态**: 已修复 ✅
- **操作**: batch_retranslate.py 重翻 17 页 + 手动修复 ch_031.md 1 处法语残留

### 2.5 图片路径
- **状态**: 正常
- **位置**: ch_000_front（封面）、ch_043（封底）
- **说明**: 图片引用为 `images/imgs/xxx.jpg`，epub 中正常显示

## 3. 结构性类

### 3.1 章节切分
- **状态**: 正常
- **数量**: 44 章节（1 front + 8 前置 + 35 正文 + 1 封底）

### 3.2 标题层级
- **状态**: 正常
- **说明**: 所有章节使用 `## ` 二级标题

## 4. EPUB 输出类

### 4.1 文件名
- **当前**: `Le_Droit_A_La_Ville_I_Henri_Lefebvre.epub`
- **位置**: `output/Le_Droit_A_La_Ville_I_Henri_Lefebvre.epub`

### 4.2 验证
- **verify_epub.py**: ✅ 全部通过

## 5. 建议

### 5.1 校对建议未应用
- **位置**: `proofread/suggestions.json`（105 条建议）
- **状态**: 仅生成未应用
- **建议**: 若需应用，使用 `sed` 或自定义脚本

### 5.2 工具链
```bash
# 重新扫描全部章节
python3 bin/scan_final.py books/Le_Droit_A_La_Ville_I_Henri_Lefebvre --workers 10

# 重新构建 epub
bash bin/crowbook_build.sh books/Le_Droit_A_La_Ville_I_Henri_Lefebvre/Le_Droit_A_La_Ville_I_Henri_Lefebvre.book

# 验证 epub
python3 bin/verify_epub.py output/Le_Droit_A_La_Ville_I_Henri_Lefebvre.epub
```
