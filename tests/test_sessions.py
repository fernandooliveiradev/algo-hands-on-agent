from pathlib import Path

from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind


def evaluation(kind: EvidenceKind, module_id: int = 0, student_id: str = "aluno") -> EvaluationResult:
    return EvaluationResult(
        result=AttemptResult.CORRECT,
        score=0.9,
        used_hint=False,
        module_id=module_id,
        competency_key="diagnostico-inicial",
        evidence_kind=kind,
        concepts_demonstrated=["raciocinio"],
        feedback="Bom trabalho.",
    )


def test_sessions_isolated_by_student(tmp_path: Path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("fernando", "Fernando")
    repository.create_student("maria", "Maria")

    eval_data = evaluation(EvidenceKind.DIRECT, module_id=0)
    repository.record_evaluation(student_id="fernando", session_id="sessao-f1", evaluation=eval_data)
    repository.record_evaluation(student_id="fernando", session_id="sessao-f2", evaluation=eval_data)
    repository.record_evaluation(student_id="maria", session_id="sessao-m1", evaluation=eval_data)

    fernando_sessions = repository.list_sessions("fernando")
    maria_sessions = repository.list_sessions("maria")

    fernando_ids = {s["session_id"] for s in fernando_sessions}
    maria_ids = {s["session_id"] for s in maria_sessions}

    assert "sessao-f1" in fernando_ids
    assert "sessao-f2" in fernando_ids
    assert "sessao-m1" not in fernando_ids
    assert "sessao-m1" in maria_ids
    assert "sessao-f1" not in maria_ids


def test_list_sessions_empty_for_new_student(tmp_path: Path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("novo", "Novo")
    sessions = repository.list_sessions("novo")
    assert sessions == []


def test_recent_events_capped(tmp_path: Path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("aluno", "Aluno")
    # Record events without session
    for i in range(5):
        repository.record_event("aluno", None, "test_event", {"index": i})
    events = repository.get_recent_events("aluno", limit=3)
    assert len(events) == 3


def test_module_skip_preserves_mastered_status(tmp_path: Path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("aluno", "Aluno")

    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 0

    repository.set_current_module("aluno", 3, reason="test_skip")
    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 3
    assert snapshot["modules"][0]["status"] != "mastered"


def test_progress_reset_isolation(tmp_path: Path) -> None:
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("a", "Aluno A")
    repository.create_student("b", "Aluno B")

    eval_data = evaluation(EvidenceKind.DIRECT, module_id=0)
    repository.record_evaluation(student_id="a", session_id="s1", evaluation=eval_data)
    repository.record_evaluation(student_id="b", session_id="s1", evaluation=eval_data)

    repository.reset_student("a")

    snapshot_a = repository.get_progress_snapshot("a")
    snapshot_b = repository.get_progress_snapshot("b")

    assert snapshot_a["current"]["current_module"] == 0
    assert len(snapshot_a["evidence"]) == 0
    assert snapshot_b["current"]["current_module"] == 0
    assert len(snapshot_b["evidence"]) >= 1
