from dataclasses import dataclass


@dataclass
class RetrievalBenchmarkItem:
    query: str
    expected_chunk_id: str


def build_python_baseline_benchmark():
    return [
        RetrievalBenchmarkItem(
            query="Python函数有什么作用？",
            expected_chunk_id="function-chunk",
        ),
        RetrievalBenchmarkItem(
            query="Python变量是干什么的？",
            expected_chunk_id="variable-chunk",
        ),
        RetrievalBenchmarkItem(
            query="Python循环有什么作用？",
            expected_chunk_id="loop-chunk",
        ),
        RetrievalBenchmarkItem(
            query="如何把重复逻辑封装起来？",
            expected_chunk_id="function-chunk",
        ),
        RetrievalBenchmarkItem(
            query="程序里的数据一般保存在哪里？",
            expected_chunk_id="variable-chunk",
        ),
        RetrievalBenchmarkItem(
            query="怎样重复执行一段代码？",
            expected_chunk_id="loop-chunk",
        ),
    ]
