"""Test final quality gate rules."""
from src.scan import check_prompt_residue


def test_prompt_residue_is_error():
    issues = check_prompt_residue("正文\n\n【原文段落 #245】\n内容")
    assert issues
    assert issues[0]["type"] == "prompt_residue"
    assert issues[0]["severity"] == "error"
