def get_retrieval_benchmark_cases():

    return [
        {
            "name": "python_tool_calling",
            "query": "继续学习 Python Tool Calling",
            "memories": [
                {
                    "memory_key": "learning_feedback:python-tool-calling",
                    "content": "Python Tool Calling practice",
                },
                {
                    "memory_key": "learning_feedback:python-basics",
                    "content": "Python basics",
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English vocabulary review",
                },
                {
                    "memory_key": "learning_feedback:stock",
                    "content": "A stock strategy research",
                },
            ],
            "relevant_keys": {
                "learning_feedback:python-tool-calling",
                "learning_feedback:python-basics",
            },
        },
        {
            "name": "agent_memory",
            "query": "继续优化 AI Agent Memory",
            "memories": [
                {
                    "memory_key": "learning_feedback:agent-memory",
                    "content": "AI Agent memory architecture",
                },
                {
                    "memory_key": "learning_feedback:tool-calling",
                    "content": "Tool Calling design",
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English practice",
                },
            ],
            "relevant_keys": {
                "learning_feedback:agent-memory",
                "learning_feedback:tool-calling",
            },
        },
        {
            "name": "stock_strategy",
            "query": "继续优化股票策略系统",
            "memories": [
                {
                    "memory_key": "learning_feedback:stock-strategy",
                    "content": "A股 strategy optimization",
                },
                {
                    "memory_key": "learning_feedback:factor-model",
                    "content": "Factor model research",
                },
                {
                    "memory_key": "learning_feedback:reading",
                    "content": "Reading notes",
                },
            ],
            "relevant_keys": {
                "learning_feedback:stock-strategy",
                "learning_feedback:factor-model",
            },
        },
        {
            "name": "reading_system",
            "query": "继续培养阅读习惯",
            "memories": [
                {
                    "memory_key": "learning_feedback:reading-system",
                    "content": "Build long term reading habit",
                },
                {
                    "memory_key": "learning_feedback:book-notes",
                    "content": "Book notes and reflection",
                },
                {
                    "memory_key": "learning_feedback:stock",
                    "content": "Stock analysis",
                },
            ],
            "relevant_keys": {
                "learning_feedback:reading-system",
                "learning_feedback:book-notes",
            },
        },
        {
            "name": "agent_memory_semantic_hard",
            "query": "继续设计 AI Agent Memory",
            "memories": [
                {
                    "memory_key": "learning_feedback:agent-memory",
                    "content": "智能体长期记忆架构设计与 Memory 系统优化",
                },
                {
                    "memory_key": "learning_feedback:tool-calling",
                    "content": "Tool Calling 接口设计与 Agent 工具调用",
                },
                {
                    "memory_key": "learning_feedback:python",
                    "content": "Python 基础语法和编程练习",
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English vocabulary learning",
                },
            ],
            "relevant_keys": {
                "learning_feedback:agent-memory",
                "learning_feedback:tool-calling",
            },
        },
    ]
