import pytest
from pydantic import ValidationError

from packages.graph.schemas import EditorDecision


def test_editor_decision_valid() -> None:
    decision = EditorDecision(is_approved=True, feedback=[])
    assert decision.is_approved is True
    assert decision.feedback == []


def test_editor_decision_reject_requires_feedback() -> None:
    with pytest.raises(ValidationError):
        EditorDecision(is_approved=False, feedback=[])


def test_editor_decision_feedback_must_be_list() -> None:
    with pytest.raises(ValidationError):
        EditorDecision(is_approved=False, feedback="needs fixes")  # type: ignore[arg-type]
