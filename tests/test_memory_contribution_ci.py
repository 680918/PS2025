from pathlib import Path

import pytest


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "tests.yml"
)


@pytest.mark.unit
def test_tests_workflow_should_include_memory_contribution_regression_gate():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "memory-contribution-regression:" in workflow

    assert "python -m scripts.check_memory_contribution_regression" in workflow

    assert "- memory-contribution-regression" in workflow
