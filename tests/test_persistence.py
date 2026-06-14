from collections.abc import Callable

from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind


def test_five_independent_evidences_advance_module(
    repository: ProgressRepository,
    make_evaluation: Callable[..., EvaluationResult],
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


def test_hint_and_incorrect_attempts_do_not_satisfy_evidence(
    repository: ProgressRepository,
    make_evaluation: Callable[..., EvaluationResult],
) -> None:
    repository.create_student("aluno", "Aluno")
    repository.create_student("aluno-incorreto", "Aluno Incorreto")

    repository.record_evaluation(
        student_id="aluno",
        session_id="test",
        evaluation=make_evaluation(
            EvidenceKind.DIRECT,
            result=AttemptResult.CORRECT_WITH_HINT,
            used_hint=True,
        ),
    )
    repository.record_evaluation(
        student_id="aluno",
        session_id="test",
        evaluation=make_evaluation(
            EvidenceKind.DIAGNOSIS,
            result=AttemptResult.INCORRECT,
            used_hint=True,
            score=0.2,
        ),
    )

    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 0
    assert snapshot["evidence"][0]["satisfied"] == 0

    repository.record_evaluation(
        student_id="aluno-incorreto",
        session_id="test",
        evaluation=make_evaluation(
            EvidenceKind.DIRECT,
            result=AttemptResult.INCORRECT,
            used_hint=True,
            score=0.2,
        ),
    )
    incorrect_snapshot = repository.get_progress_snapshot("aluno-incorreto")
    assert incorrect_snapshot["competencies"][0]["hinted_successes"] == 0
    assert incorrect_snapshot["competencies"][0]["failed_attempts"] == 1


def test_sessions_and_reset_are_isolated_by_student(
    repository: ProgressRepository,
    make_evaluation: Callable[..., EvaluationResult],
) -> None:
    repository.create_student("fernando", "Fernando")
    repository.create_student("maria", "Maria")
    evaluation = make_evaluation(EvidenceKind.DIRECT, module_id=0)

    repository.record_evaluation(
        student_id="fernando",
        session_id="sessao-f1",
        evaluation=evaluation,
    )
    repository.record_evaluation(
        student_id="fernando",
        session_id="sessao-f2",
        evaluation=evaluation,
    )
    repository.record_evaluation(
        student_id="maria",
        session_id="sessao-m1",
        evaluation=evaluation,
    )

    fernando_ids = {s["session_id"] for s in repository.list_sessions("fernando")}
    maria_ids = {s["session_id"] for s in repository.list_sessions("maria")}

    assert {"sessao-f1", "sessao-f2"} <= fernando_ids
    assert "sessao-m1" not in fernando_ids
    assert maria_ids == {"sessao-m1"}

    repository.reset_student("fernando")
    assert repository.get_progress_snapshot("fernando")["evidence"] == []
    assert len(repository.get_progress_snapshot("maria")["evidence"]) == 1


def test_module_skip_does_not_fake_mastery(repository: ProgressRepository) -> None:
    repository.create_student("aluno", "Aluno")
    repository.set_current_module("aluno", 3, reason="test_skip")

    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 3
    assert snapshot["modules"][0]["status"] != "mastered"


def test_clear_all_data_ignores_missing_agno_tables(tmp_path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("fernando", "Fernando")

    repository.clear_all_data()

    assert repository.list_students() == []
