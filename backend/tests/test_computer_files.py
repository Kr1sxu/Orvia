from pathlib import Path

import pytest

from orvia_backend.computer.files import FileTools
from orvia_backend.computer.paths import PathPolicy, ToolError


def make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "readme.md").write_text("第一行\n第二行\n", encoding="utf-8")
    (root / "data.csv").write_text("a,b\n", encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "large.log").write_text("x" * 20, encoding="utf-8")
    return root


def test_files_scan_search_metadata_and_space(tmp_path: Path):
    root = make_tree(tmp_path)
    tools = FileTools(PathPolicy(str(root)))
    assert len(tools.list_directory()["data"]["entries"]) == 3
    assert tools.search_files(query="read")["data"]["entries"][0]["name"] == "readme.md"
    assert tools.get_file_metadata("readme.md")["data"]["name"] == "readme.md"
    assert tools.analyze_directory_space()["data"]["file_count"] == 3


def test_text_is_utf8_and_bounded(tmp_path: Path):
    root = make_tree(tmp_path)
    tools = FileTools(PathPolicy(str(root)))
    result = tools.read_text_file("readme.md", start_line=2)
    assert result["data"]["text"].splitlines() == ["第二行"]
    (root / "binary.txt").write_bytes(b"\xff")
    with pytest.raises(ToolError) as exc:
        tools.read_text_file("binary.txt")
    assert exc.value.code == "encoding_invalid"


def test_path_escape_and_symlink_are_rejected(tmp_path: Path):
    root = make_tree(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    tools = FileTools(PathPolicy(str(root)))
    with pytest.raises(ToolError):
        tools.get_file_metadata("../outside.txt")
    link = root / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("当前系统不允许创建测试符号链接")
    with pytest.raises(ToolError):
        tools.get_file_metadata("link.txt")
