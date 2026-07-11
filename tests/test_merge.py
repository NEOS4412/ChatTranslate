"""Test paragraph merging logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.merge import is_mergable, merge_paragraphs

def test_sentence_end_not_merged():
    """段落以句号结尾，不应和下一段合并"""
    assert not is_mergable("这是第一段。", "这是第二段。")

def test_broken_paragraph_merged():
    """跨页断裂的段落应该合并"""
    assert is_mergable("这是第一段的内容，还没有", "结束，这里继续")

def test_title_not_merged():
    """标题行不应被合并"""
    assert not is_mergable("## 章节标题", "正文内容")
    assert not is_mergable("正文内容", "## 章节标题")

def test_merge_basic():
    text = "这是第一句还没有\n\n结束继续。\n\n新段落。"
    result, n = merge_paragraphs(text)
    assert n == 1, f"Expected 1 merge, got {n}"

def test_no_change_for_complete():
    text = "完整的段落。\n\n另一个完整段落。"
    result, n = merge_paragraphs(text)
    assert n == 0, f"Expected 0 merges, got {n}"

if __name__ == "__main__":
    test_sentence_end_not_merged()
    test_broken_paragraph_merged()
    test_title_not_merged()
    test_merge_basic()
    test_no_change_for_complete()
    print("✅ tests: all merge tests passed")
