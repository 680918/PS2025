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
    ]
