from collections.abc import Callable

from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind


def test_five_independent_evidences_advance_module(
    repository: ProgressRepository, make_evaluation: Callable[..., EvaluationResult]
) -> None:
    repository.create_student("fernando", "Fernando")

    for kind in EvidenceKind:
        repository.record_evaluation(
            student_id="fernando",
            session_id="test-session",
            evaluation=make_evaluation(kind),
        )

    snapshot = repository.get_progress_snapshot("fernando")
    assert snapshot["modules"][0]["status"] == "mastered"
    assert snapshot["current"]["current_module"] == 1


def test_hint_does_not_satisfy_evidence(
    repository: ProgressRepository, make_evaluation: Callable[..., EvaluationResult]
) -> None:
    repository.create_student("aluno", "Aluno")
    item = make_evaluation(
        EvidenceKind.DIRECT,
        result=AttemptResult.CORRECT_WITH_HINT,
        used_hint=True,
    )
    repository.record_evaluation(
        student_id="aluno",
        session_id="test",
        evaluation=item,
    )
    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 0
    assert snapshot["evidence"][0]["satisfied"] == 0
