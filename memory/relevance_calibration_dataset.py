def get_calibration_cases():
    return [
        {
            "name": "python_tool_calling",
            "query": "继续学习 Python Tool Calling",
            "items": [
                {
                    "memory_key": "learning_feedback:python-tool-calling",
                    "content": "Python Tool Calling practice",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:python-basics",
                    "content": "Python basics",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English vocabulary review",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "agent_memory",
            "query": "继续优化 AI Agent Memory",
            "items": [
                {
                    "memory_key": "learning_feedback:agent-memory",
                    "content": "AI Agent memory architecture",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:memory-retrieval",
                    "content": "Memory retrieval design",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English vocabulary review",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "stock_strategy",
            "query": "继续优化股票策略系统",
            "items": [
                {
                    "memory_key": "learning_feedback:stock-strategy",
                    "content": "A股 strategy optimization",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:factor-model",
                    "content": "Factor model research",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English vocabulary review",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "reading_system",
            "query": "继续培养阅读习惯",
            "items": [
                {
                    "memory_key": "learning_feedback:reading-system",
                    "content": "Build long term reading habit",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:book-notes",
                    "content": "Book notes and reflection",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:stock",
                    "content": "Stock analysis",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "tool_calling_keyword_distractor",
            "query": "继续学习 Python Tool Calling",
            "items": [
                {
                    "memory_key": "learning_feedback:python-tool-calling",
                    "content": "Python Tool Calling practice",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:python-basics",
                    "content": "Python basics",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:english-tool",
                    "content": "English lesson about the words tool and calling",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "tool_calling_semantic_hard",
            "query": "继续学习工具调用",
            "items": [
                {
                    "memory_key": "learning_feedback:tool-calling",
                    "content": "Tool Calling design and practice",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:agent-tools",
                    "content": "AI Agent tool integration",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:english-tool",
                    "content": "English vocabulary lesson about the word tool",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "memory_overload",
            "query": "继续优化 Agent Memory 工具调用能力",
            "items": [
                {
                    "memory_key": "learning_feedback:agent-memory",
                    "content": "Agent Memory architecture and retrieval",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:tool-calling",
                    "content": "Tool Calling design and practice",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:python-basics",
                    "content": "Python basics",
                    "relevance": 0,
                },
                {
                    "memory_key": "learning_feedback:reading-system",
                    "content": "Build long term reading habit",
                    "relevance": 0,
                },
                {
                    "memory_key": "learning_feedback:stock-strategy",
                    "content": "A股 strategy optimization",
                    "relevance": 0,
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English vocabulary review",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "agent_memory_semantic_distractor",
            "query": "继续优化 Agent Memory retrieval",
            "items": [
                {
                    "memory_key": "learning_feedback:agent-memory-retrieval",
                    "content": "Agent Memory retrieval architecture",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:memory-ranking",
                    "content": "Memory retrieval ranking and top-k selection",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:knowledge-retrieval",
                    "content": "Knowledge retrieval search ranking",
                    "relevance": 0,
                },
            ],
        },
    ]
