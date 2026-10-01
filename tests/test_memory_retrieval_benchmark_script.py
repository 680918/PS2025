from scripts.run_memory_retrieval_benchmark import (
    build_benchmark_output,
)


def test_build_benchmark_output_should_return_report_text():

    output = build_benchmark_output()

    assert "Memory Retrieval Benchmark" in output
