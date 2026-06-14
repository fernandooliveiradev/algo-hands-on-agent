from pathlib import Path

from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind


def evaluation(kind: EvidenceKind) -> EvaluationResult:
    return EvaluationResult(
        result=AttemptResult.CORRECT,
        score=0.9,
        used_hint=False,
        module_id=0,
        competency_key="diagnostico-inicial",
        evidence_kind=kind,
        concepts_demonstrated=["raciocinio"],
        feedback="Bom trabalho.",
    )


def test_five_independent_evidences_advance_module(tmp_path: Path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("fernando", "Fernando")

    for kind in EvidenceKind:
        repository.record_evaluation(
            student_id="fernando",
            session_id="test-session",
            evaluation=evaluation(kind),
        )

    snapshot = repository.get_progress_snapshot("fernando")
    assert snapshot["modules"][0]["status"] == "mastered"
    assert snapshot["current"]["current_module"] == 1


def test_hint_does_not_satisfy_evidence(tmp_path: Path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("aluno", "Aluno")
    item = evaluation(EvidenceKind.DIRECT)
    item.result = AttemptResult.CORRECT_WITH_HINT
    item.used_hint = True
    repository.record_evaluation(
        student_id="aluno",
        session_id="test",
        evaluation=item,
    )
    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 0
    assert snapshot["evidence"][0]["satisfied"] == 0
