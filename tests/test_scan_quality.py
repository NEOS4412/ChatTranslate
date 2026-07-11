"""Test final quality gate rules."""
from pathlib import Path
from src.scan import check_prompt_residue


def test_prompt_residue_is_error():
    issues = check_prompt_residue("正文\n\n【原文段落 #245】\n内容")
    assert issues
    assert issues[0]["type"] == "prompt_residue"
    assert issues[0]["severity"] == "error"


def test_clean_strips_prompt_label():
    """clean.py 必须删除 LLM 未脱壳的 【原文段落 #N】 行级残留。"""
    from src.clean import clean_file
    import tempfile, os
    bad_text = "上文段落一。\n\n【原文段落 #245】\n\n下文段落二。\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(bad_text)
        path = f.name
    try:
        n = clean_file(Path(path), fix_titles=False, fix_superscripts=False)
        result = Path(path).read_text(encoding="utf-8")
        assert "【原文段落" not in result, f"残留未清: {result!r}"
        assert n == 1, f"应标记为有变更, got {n}"
        # 上文/下文必须保留
        assert "上文段落一。" in result
        assert "下文段落二。" in result
    finally:
        os.unlink(path)
