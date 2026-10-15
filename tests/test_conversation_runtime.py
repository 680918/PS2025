from agent.controller import run_agent, run_simple_runtime
from agent.state import AgentState
from agent.context_assembly import assemble_context


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


def test_run_agent_should_store_assembled_context_in_state(
    monkeypatch,
):
    monkeypatch.setattr(
        "agent.controller.route_task",
        lambda user_message: "simple",
    )

    assembled_context = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    state, _ = run_agent(
        "继续学习",
        assembled_context=assembled_context,
        return_state=True,
    )

    assert state.assembled_context is assembled_context


def test_run_agent_should_assemble_runtime_context_when_not_provided(
    monkeypatch,
):
    monkeypatch.setattr(
        "agent.controller.route_task",
        lambda user_message: "simple",
    )

    conversation_context = [
        {
            "role": "user",
            "content": "那第二种呢？",
        }
    ]

    learning_continuity_context = {
        "topic": "Tool Calling",
        "understanding_score": 80,
    }

    state, _ = run_agent(
        "继续学习",
        conversation_context=conversation_context,
        learning_continuity_context=learning_continuity_context,
        return_state=True,
    )

    assert state.assembled_context is not None

    assert state.assembled_context.conversation_context == conversation_context

    assert state.assembled_context.learning_continuity == learning_continuity_context


def test_run_simple_runtime_should_include_assembled_context_in_initial_prompt(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    assembled_context = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    state.set_assembled_context(
        assembled_context,
    )

    captured = {}

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: [],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [],
    )

    monkeypatch.setattr(
        "agent.controller.format_assembled_context",
        lambda context: (
            "ASSEMBLED_CONTEXT_SENTINEL" if context is assembled_context else ""
        ),
        raising=False,
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "测试回答",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    assert "ASSEMBLED_CONTEXT_SENTINEL" in captured["system_prompt"]


def test_run_simple_runtime_should_include_assembled_context_in_final_prompt(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    assembled_context = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    state.set_assembled_context(
        assembled_context,
    )

    captured_prompts = []

    monkeypatch.setattr(
        "agent.controller.format_assembled_context",
        lambda context: (
            "ASSEMBLED_CONTEXT_FINAL_SENTINEL" if context is assembled_context else ""
        ),
    )

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
            "content": "工具调用后的最终回答",
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
        "继续学习",
        state=state,
    )

    assert status == "success"
    assert len(captured_prompts) == 2

    final_system_prompt = captured_prompts[1]

    assert "ASSEMBLED_CONTEXT_FINAL_SENTINEL" in final_system_prompt


def test_run_simple_runtime_should_not_duplicate_assembled_context_sources(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    conversation_context = [
        {
            "role": "user",
            "content": "CONVERSATION_UNIQUE_MARKER",
        }
    ]

    learning_continuity_context = {
        "topic": "LEARNING_UNIQUE_MARKER",
    }

    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "test",
                "content": "MEMORY_UNIQUE_MARKER",
            }
        ],
        "project": [],
        "experience": [],
    }

    state.set_conversation_context(
        conversation_context,
    )

    state.set_learning_continuity_context(
        learning_continuity_context,
    )

    state.set_memory_context(
        memory_context,
    )

    state.set_assembled_context(
        assemble_context(
            conversation_context=conversation_context,
            learning_continuity=learning_continuity_context,
            memory_context=memory_context,
        )
    )

    captured = {}

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: [],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [],
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "测试回答",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    system_prompt = captured["system_prompt"]

    assert system_prompt.count("CONVERSATION_UNIQUE_MARKER") == 1

    assert system_prompt.count("LEARNING_UNIQUE_MARKER") == 1

    assert system_prompt.count("MEMORY_UNIQUE_MARKER") == 1


def test_run_simple_runtime_final_prompt_should_not_duplicate_assembled_context_sources(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    conversation_context = [
        {
            "role": "user",
            "content": "FINAL_CONVERSATION_UNIQUE_MARKER",
        }
    ]

    learning_continuity_context = {
        "topic": "FINAL_LEARNING_UNIQUE_MARKER",
    }

    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "test",
                "content": "FINAL_MEMORY_UNIQUE_MARKER",
            }
        ],
        "project": [],
        "experience": [],
    }

    state.set_conversation_context(
        conversation_context,
    )

    state.set_learning_continuity_context(
        learning_continuity_context,
    )

    state.set_memory_context(
        memory_context,
    )

    state.set_assembled_context(
        assemble_context(
            conversation_context=conversation_context,
            learning_continuity=learning_continuity_context,
            memory_context=memory_context,
        )
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
            "content": "最终回答",
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

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    assert len(captured_prompts) == 2

    final_system_prompt = captured_prompts[1]

    assert final_system_prompt.count("FINAL_CONVERSATION_UNIQUE_MARKER") == 1

    assert final_system_prompt.count("FINAL_LEARNING_UNIQUE_MARKER") == 1

    assert final_system_prompt.count("FINAL_MEMORY_UNIQUE_MARKER") == 1


def test_run_simple_runtime_should_hide_legacy_context_sections_when_assembled(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    state.set_assembled_context(
        assemble_context(
            conversation_context=[],
            learning_continuity={},
            memory_context={},
        )
    )

    captured = {}

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: [],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [],
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "测试回答",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    system_prompt = captured["system_prompt"]

    assert "当前 Journey 的最近对话历史" not in system_prompt

    assert "与当前用户有关的长期记忆" not in system_prompt

    assert "用户当前学习连续性状态" not in system_prompt


def test_run_simple_runtime_should_keep_legacy_context_sections_without_assembled(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    state.set_conversation_context(
        [
            {
                "role": "user",
                "content": "LEGACY_CONVERSATION_MARKER",
            }
        ]
    )

    state.set_learning_continuity_context(
        {
            "topic": "LEGACY_LEARNING_MARKER",
        }
    )

    state.set_memory_context(
        {
            "profile": [],
            "skill": [],
            "learning": [
                {
                    "memory_key": "test",
                    "content": "LEGACY_MEMORY_MARKER",
                }
            ],
            "project": [],
            "experience": [],
        }
    )

    captured = {}

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: [],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [],
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "测试回答",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    system_prompt = captured["system_prompt"]

    assert "当前 Journey 的最近对话历史" in system_prompt
    assert "LEGACY_CONVERSATION_MARKER" in system_prompt

    assert "与当前用户有关的长期记忆" in system_prompt
    assert "LEGACY_MEMORY_MARKER" in system_prompt

    assert "用户当前学习连续性状态" in system_prompt
    assert "LEGACY_LEARNING_MARKER" in system_prompt


def test_run_simple_runtime_should_include_assembled_context_policy_in_initial_prompt(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    assembled_context = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    state.set_assembled_context(
        assembled_context,
    )

    captured = {}

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: [],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [],
    )

    monkeypatch.setattr(
        "agent.controller.format_assembled_context_policy",
        lambda context: (
            "ASSEMBLED_CONTEXT_POLICY_SENTINEL" if context is assembled_context else ""
        ),
        raising=False,
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "测试回答",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    assert "ASSEMBLED_CONTEXT_POLICY_SENTINEL" in captured["system_prompt"]


def test_run_simple_runtime_should_include_assembled_context_policy_in_final_prompt(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    assembled_context = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    state.set_assembled_context(
        assembled_context,
    )

    captured_prompts = []

    monkeypatch.setattr(
        "agent.controller.format_assembled_context_policy",
        lambda context: (
            "ASSEMBLED_CONTEXT_POLICY_FINAL_SENTINEL"
            if context is assembled_context
            else ""
        ),
    )

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
            "content": "最终回答",
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

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    assert len(captured_prompts) == 2

    final_system_prompt = captured_prompts[1]

    assert "ASSEMBLED_CONTEXT_POLICY_FINAL_SENTINEL" in final_system_prompt


def test_run_simple_runtime_should_not_duplicate_legacy_context_rules_when_assembled(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    state.set_assembled_context(
        assemble_context(
            conversation_context=[],
            learning_continuity={},
            memory_context={},
        )
    )

    captured = {}

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: [],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [],
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "测试回答",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    system_prompt = captured["system_prompt"]

    assert system_prompt.count("使用最近对话历史时必须遵守") == 0

    assert system_prompt.count("使用学习连续性状态时必须遵守") == 0

    assert system_prompt.count("使用这些记忆时必须遵守") == 0


def test_run_simple_runtime_should_keep_legacy_context_rules_without_assembled(
    monkeypatch,
):
    state = AgentState(
        "继续学习",
    )

    captured = {}

    monkeypatch.setattr(
        "agent.controller.route_tools",
        lambda user_message: [],
    )

    monkeypatch.setattr(
        "agent.controller.filter_tool_schemas",
        lambda candidate_tools: [],
    )

    def fake_call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=None,
    ):
        captured["system_prompt"] = system_prompt

        return {
            "status": "success",
            "content": "测试回答",
        }

    monkeypatch.setattr(
        "agent.controller.call_llm_with_retry",
        fake_call_llm_with_retry,
    )

    run_simple_runtime(
        "继续学习",
        state=state,
    )

    system_prompt = captured["system_prompt"]

    assert "使用最近对话历史时必须遵守" in system_prompt
    assert "使用学习连续性状态时必须遵守" in system_prompt
    assert "使用这些记忆时必须遵守" in system_prompt
