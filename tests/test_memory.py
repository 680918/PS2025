import pytest

import memory.memory as memory_module

from memory.memory import (
    get_memory_context,
    update_memory,
    get_user_profile_structured,
    get_skill_map_structured
)


pytestmark = pytest.mark.unit


# 测试未知 memory_type
def test_memory_unknown_type():

    result = get_memory_context(
        "abc_not_exist"
    )

    assert result["status"] == "error"

    assert (
        result["message"]
        == "Unknown memory type: abc_not_exist"
    )


# 测试文件不存在
def test_memory_file_not_found(
    tmp_path,
    monkeypatch
):

    monkeypatch.setattr(
        memory_module,
        "MEMORY_PATH",
        str(tmp_path)
    )

    result = get_memory_context(
        "profile"
    )

    assert result["status"] == "error"

    assert (
        result["message"]
        == "Memory file not found: user_profile.md"
    )


# 测试正常读取
def test_memory_read_success(
    tmp_path,
    monkeypatch
):

    test_file = (
        tmp_path / "user_profile.md"
    )

    test_file.write_text(
        "这是测试用户画像",
        encoding="utf-8"
    )

    monkeypatch.setattr(
        memory_module,
        "MEMORY_PATH",
        str(tmp_path)
    )

    result = get_memory_context(
        "profile"
    )

    assert result["status"] == "success"

    assert result["memory_type"] == "profile"

    assert (
        result["content"]
        == "这是测试用户画像"
    )


#测试 update_memory() 追加写入
def test_update_memory_append(
    tmp_path,
    monkeypatch
):

    monkeypatch.setattr(
        memory_module,
        "MEMORY_PATH",
        str(tmp_path)
    )

    result_1 = update_memory(
        "learning_log.md",
        "第一次学习\n"
    )

    result_2 = update_memory(
        "learning_log.md",
        "第二次学习\n"
    )

    content = (
        tmp_path / "learning_log.md"
    ).read_text(
        encoding="utf-8"
    )

    assert result_1["status"] == "success"

    assert result_2["status"] == "success"

    assert (
        content
        == "第一次学习\n第二次学习\n"
    )


# 测试 User Profile Structured Output
def test_user_profile_structured():

    result = get_user_profile_structured()

    assert result["status"] == "success"

    assert (
        result["tool_name"]
        == "get_user_profile"
    )

    assert "data" in result

    assert "goal" in result["data"]

    assert (
        result["data"]
        ["daily_learning_time"]
        == "1小时"
    )


# 测试 Skill Map Structured Output
def test_skill_map_structured():

    result = get_skill_map_structured()

    assert result["status"] == "success"

    assert (
        result["tool_name"]
        == "get_skill_map"
    )

    assert (
        result["data"]
        ["AI Agent"]
        ["level"]
        == 90
    )

    assert (
        result["data"]
        ["Python"]
        ["level"]
        == 15
    )