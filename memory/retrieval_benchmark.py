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
    ]
