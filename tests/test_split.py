"""Test chapter splitting logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.split import split, safe_name

def test_split_basic():
    text = "# 书名\n\n扉页内容\n\n## 第一章\n\n正文内容\n\n## 第二章\n\n更多正文"
    title, front, sections = split(text)
    assert title == "书名"
    assert len(sections) == 2
    assert sections[0][0] == "第一章"
    assert sections[1][0] == "第二章"

def test_split_no_title():
    text = "## 直接开始\n\n没有一级标题"
    title, front, sections = split(text)
    assert title == "未命名"

def test_split_front_matter():
    text = "# 书\n\n版权页\n\n前言\n\n## 第一章\n\n正文"
    title, front, sections = split(text)
    assert "版权页" in front

if __name__ == "__main__":
    test_split_basic()
    test_split_no_title()
    test_split_front_matter()
    print("✅ tests: all split tests passed")
