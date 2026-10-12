from agent.controller import run_agent, run_simple_runtime
from agent.state import AgentState


def test_run_agent_should_store_conversation_context_in_state(
    monkeypatch,
):
    conversation_context = [
        {
            "role": "user",
            "content": "Memory 有哪两种读取模式？",
        },
        {
            "role": "assistant",
            "content": "第一种是隐式注入，第二种是显式工具调用。",
        },
    ]

    monkeypatch.setattr(
        "agent.controller.route_task",
        lambda user_message: "simple",
    )

    monkeypatch.setattr(
        "agent.controller.run_simple_agent",
        lambda user_message, state=None: "Coach response",
    )

    state, response = run_agent(
        "那第二种呢？",
        conversation_context=conversation_context,
        return_state=True,
    )

    assert response == "Coach response"
    assert state.conversation_context == conversation_context


def test_run_simple_runtime_should_inject_conversation_context_into_initial_prompt(
    monkeypatch,
):
    state = AgentState("那第二种呢？")

    state.set_conversation_context(
        [
            {
                "role": "user",
                "content": "Memory 有哪两种读取模式？",
            },
            {
                "role": "assistant",
                "content": "第一种是隐式注入，第二种是显式工具调用。",
            },
        ]
    )

    captured = {}

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt
        captured["user_message"] = user_message

        return {
            "status": "success",
            "content": "第二种是显式工具调用。",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    _, status = run_simple_runtime(
        "那第二种呢？",
        state=state,
    )

    assert status == "success"

    system_prompt = captured["system_prompt"]

    assert "最近对话历史" in system_prompt
    assert "Memory 有哪两种读取模式？" in system_prompt
    assert "第一种是隐式注入，第二种是显式工具调用。" in system_prompt
    assert '"role": "user"' in system_prompt
    assert '"role": "assistant"' in system_prompt


def test_run_simple_runtime_should_inject_conversation_context_into_final_prompt(
    monkeypatch,
):
    state = AgentState("那第二种呢？")

    state.set_conversation_context(
        [
            {
                "role": "user",
                "content": "Memory 有哪两种读取模式？",
            },
            {
                "role": "assistant",
                "content": "第一种是隐式注入，第二种是显式工具调用。",
            },
        ]
    )

    captured_prompts = []

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured_prompts.append(system_prompt)

        if len(captured_prompts) == 1:
            return {
                "status": "success",
                "content": """
<tool_call>
{
    "name": "test_tool",
    "arguments": {}
}
</tool_call>
""",
            }

        return {
            "status": "success",
            "content": "第二种是显式工具调用。",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: ["test_tool"],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [
            {
                "name": "test_tool",
                "description": "test",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            }
        ],
    )

    monkeypatch.setattr(
        "agent.controller.execute_tool",
        lambda name, arguments, **kwargs: {
            "status": "success",
            "result": "ok",
        },
    )

    _, status = run_simple_runtime(
        "那第二种呢？",
        state=state,
    )

    assert status == "success"
    assert len(captured_prompts) == 2

    final_system_prompt = captured_prompts[1]

    assert "最近对话历史" in final_system_prompt
    assert "Memory 有哪两种读取模式？" in final_system_prompt
    assert "第一种是隐式注入，第二种是显式工具调用。" in final_system_prompt
