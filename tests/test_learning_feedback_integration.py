import pytest
import json
import agent.controller as controller_module

from agent.controller import run_simple_runtime
from agent.state import AgentState
from memory.service import MemoryService
from memory.store import MemoryStore


pytestmark = pytest.mark.integration


def test_learning_feedback_updates_skill_through_simple_runtime(monkeypatch):
    import agent.controller as controller_module

    store = MemoryStore()
    memory_service = MemoryService(store)

    memory_service.remember(
        memory_type="skill",
        memory_key="Python",
        content='{"level": 60}',
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "success",
            "content": """
            <tool_call>
            {
                "name": "save_learning_feedback",
                "arguments": {
                    "topic": "Python",
                    "understanding": 80,
                    "evidence": "测验8/10",
                    "evidence_type": "quiz"
                }
            }
            </tool_call>
            """,
        }

    monkeypatch.setattr(
        controller_module,
        "call_llm",
        fake_call_llm,
    )

    state = AgentState(
        "今天学习Python函数，理解80%，完成了一次测验，得分8/10。",
        memory_service=memory_service,
    )

    _, status = run_simple_runtime(
        state.user_message,
        state=state,
    )

    learning_memories = store.list_by_type("learning")

    assert len(learning_memories) == 1


def test_second_strong_learning_feedback_updates_skill(monkeypatch):

    store = MemoryStore()
    memory_service = MemoryService(store)

    # 先建立一个已有 Skill。
    # confidence 故意低于后面的 quiz evaluation，
    # 这样新的高质量证据有资格更新它。
    memory_service.remember(
        memory_type="skill",
        memory_key="Python",
        content='{"level": 50}',
        importance=0.9,
        confidence=0.5,
        source="agent_inference",
    )

    responses = iter(
        [
            # 第一次学习反馈
            {
                "status": "success",
                "content": """
                <tool_call>
                {
                    "name": "save_learning_feedback",
                    "arguments": {
                        "topic": "Python",
                        "understanding": 60,
                        "evidence": "完成了一次练习",
                        "evidence_type": "practice"
                    }
                }
                </tool_call>
                """,
            },
            # 第一次 Tool 执行后的最终回答
            {
                "status": "success",
                "content": "已记录第一次学习反馈。",
            },
            # 第二次学习反馈
            {
                "status": "success",
                "content": """
                <tool_call>
                {
                    "name": "save_learning_feedback",
                    "arguments": {
                        "topic": "Python",
                        "understanding": 80,
                        "evidence": "测验得分8/10",
                        "evidence_type": "quiz"
                    }
                }
                </tool_call>
                """,
            },
            # 第二次 Tool 执行后的最终回答
            {
                "status": "success",
                "content": "已记录第二次学习反馈。",
            },
        ]
    )

    def fake_call_llm(system_prompt, user_message):
        return next(responses)

    monkeypatch.setattr(
        controller_module,
        "call_llm",
        fake_call_llm,
    )

    # ---------- 第一次 ----------
    first_message = "今天学习Python，理解60%，完成了一次练习。"

    first_state = AgentState(
        first_message,
        memory_service=memory_service,
    )

    _, first_status = run_simple_runtime(
        first_message,
        state=first_state,
    )

    assert first_status == "success"

    # 只有一条 Learning Record 时应为 insufficient_data，
    # 所以 Skill 暂时不能更新。
    skill_after_first = memory_service.get_by_key(
        "skill",
        "Python",
    )

    skill_data_after_first = json.loads(skill_after_first.content)

    assert skill_data_after_first["level"] == 50

    # ---------- 第二次 ----------
    second_message = "今天继续学习Python，理解80%，完成了一次测验，得分8/10。"

    second_state = AgentState(
        second_message,
        memory_service=memory_service,
    )

    _, second_status = run_simple_runtime(
        second_message,
        state=second_state,
    )

    assert second_status == "success"

    # 应已有两条历史记录
    learning_memories = store.list_by_type("learning")

    assert len(learning_memories) == 2

    # 第二次相对第一次：
    # 60 → 80
    # status = improving
    # quiz confidence = 0.85
    # 应允许 Skill Update
    updated_skill = memory_service.get_by_key(
        "skill",
        "Python",
    )

    updated_skill_data = json.loads(updated_skill.content)

    assert updated_skill_data["level"] == 80
    assert updated_skill_data["evaluation_status"] == "improving"
    assert updated_skill_data["evaluation_confidence"] == 0.85
