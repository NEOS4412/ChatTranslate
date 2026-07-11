"""CLI 入口烟雾测试：保证所有 yt-* 子命令文件存在且 main() 可调用。

不依赖 scripts.* 包式 import（避免把 scripts 当成可导入包污染目录结构）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

CLI_MODULES = [
    "run_ocr",
    "run_translate",
    "run_clean",
    "run_merge",
    "run_split",
    "run_proofread",
    "run_scan",
    "run_epub",
    "run_batch_retranslate",
    "run_verify_epub",
]


def _load(module_name: str):
    """从 scripts/ 目录 import 模块（不依赖 scripts 包）。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        f"yt_entry_{module_name}", SCRIPTS / f"{module_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_entrypoints_exist_and_callable():
    for name in CLI_MODULES:
        path = SCRIPTS / f"{name}.py"
        assert path.exists(), f"missing CLI file: {path}"
        mod = _load(name)
        assert callable(getattr(mod, "main", None)), f"main() missing in {name}"


def test_pyproject_declares_all_cli_scripts():
    """pyproject.toml 中的 [project.scripts] 必须覆盖所有 CLI 模块。"""
    import tomllib
    py = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {entry.split("=")[0].strip() for entry in py["project"]["scripts"]}
    expected = {f"yt-{name.removeprefix('run_')}".replace("_", "-") for name in CLI_MODULES}
    missing = expected - declared
    assert not missing, f"yt-* entries missing in pyproject.toml: {missing}"


def test_no_compat_wrappers_left():
    """不应存在 bin/ 目录或 scripts/run-*.py 连字符版 wrapper。"""
    assert not (ROOT / "bin").exists(), "bin/ 目录应已被完全移除"
    leftover = list((ROOT / "scripts").glob("run-*.py"))
    assert not leftover, f"应删除连字符版 wrapper: {leftover}"
    assert not (ROOT / "scripts" / "__init__.py").exists(), "scripts 不应是 Python 包"
