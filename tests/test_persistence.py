import sqlite3
import time
from collections.abc import Callable

import pytest
from agno.db.sqlite import SqliteDb

from algo_hands_on.db.agno_tables import AGNO_TABLE_NAMES
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


def test_partial_coverage_does_not_advance_even_with_high_average(
    repository: ProgressRepository,
    make_evaluation: Callable[..., EvaluationResult],
) -> None:
    repository.create_student("aluno", "Aluno")

    for kind in (
        EvidenceKind.DIRECT,
        EvidenceKind.INDEPENDENT,
        EvidenceKind.INTEGRATION,
        EvidenceKind.DIAGNOSIS,
    ):
        repository.record_evaluation(
            student_id="aluno",
            session_id="test",
            evaluation=make_evaluation(kind, score=1.0),
        )

    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 0
    assert snapshot["current"]["evidence_coverage_count"] == 4
    assert snapshot["modules"][0]["mastery_score"] == pytest.approx(0.8)


def test_full_coverage_below_seventy_does_not_advance(
    repository: ProgressRepository,
    make_evaluation: Callable[..., EvaluationResult],
) -> None:
    repository.create_student("aluno", "Aluno")
    scores = {
        EvidenceKind.DIRECT: 0.9,
        EvidenceKind.INDEPENDENT: 0.7,
        EvidenceKind.INTEGRATION: 0.7,
        EvidenceKind.DIAGNOSIS: 0.6,
        EvidenceKind.EXPLANATION_TRANSFER: 0.4,
    }

    for kind, score in scores.items():
        repository.record_evaluation(
            student_id="aluno",
            session_id="test",
            evaluation=make_evaluation(kind, score=score),
        )

    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["current"]["current_module"] == 0
    assert snapshot["current"]["evidence_coverage_count"] == 5
    assert snapshot["modules"][0]["mastery_score"] == pytest.approx(0.66, abs=1e-6)


def test_low_scores_do_not_put_evidence_on_target(
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
            score=0.6,
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


def test_high_score_with_hint_counts_toward_module_average(
    repository: ProgressRepository,
    make_evaluation: Callable[..., EvaluationResult],
) -> None:
    repository.create_student("aluno", "Aluno")

    for kind in EvidenceKind:
        repository.record_evaluation(
            student_id="aluno",
            session_id="test",
            evaluation=make_evaluation(
                kind,
                result=AttemptResult.CORRECT_WITH_HINT,
                used_hint=True,
                score=0.9,
            ),
        )

    snapshot = repository.get_progress_snapshot("aluno")
    assert snapshot["modules"][0]["status"] == "mastered"
    assert snapshot["modules"][0]["mastery_score"] == pytest.approx(0.9)
    assert snapshot["current"]["current_module"] == 1


def test_record_evaluation_rejects_competency_outside_module(
    repository: ProgressRepository,
) -> None:
    repository.create_student("aluno", "Aluno")
    evaluation = EvaluationResult(
        result=AttemptResult.CORRECT,
        score=0.9,
        used_hint=False,
        module_id=0,
        competency_key="decomposicao",
        evidence_kind=EvidenceKind.DIRECT,
    )

    with pytest.raises(ValueError, match="Competência inválida"):
        repository.record_evaluation(
            student_id="aluno",
            session_id="test",
            evaluation=evaluation,
        )

    assert repository.get_progress_snapshot("aluno")["recent_attempts"] == []


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


def test_module_skip_does_not_mark_mastery_without_evidence(
    repository: ProgressRepository,
) -> None:
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


def test_clear_all_data_cleans_future_agno_schedule_tables(tmp_path) -> None:
    db_path = tmp_path / "aho.db"
    repository = ProgressRepository(db_path)
    repository.initialize()
    repository.create_student("fernando", "Fernando")

    now = int(time.time())
    agno_db = SqliteDb(db_file=str(db_path), **AGNO_TABLE_NAMES)
    try:
        agno_db.create_schedule(
            {
                "id": "schedule-1",
                "name": "practice-reminder",
                "description": "Lembrete de prática futura.",
                "method": "POST",
                "endpoint": "/api/v1/tutor/turn",
                "payload": {"student_id": "fernando"},
                "cron_expr": "0 9 * * *",
                "timezone": "America/Sao_Paulo",
                "timeout_seconds": 30,
                "max_retries": 2,
                "retry_delay_seconds": 60,
                "enabled": True,
                "next_run_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        agno_db.create_schedule_run(
            {
                "id": "schedule-run-1",
                "schedule_id": "schedule-1",
                "attempt": 1,
                "triggered_at": now,
                "completed_at": now,
                "status": "success",
                "created_at": now,
            }
        )
    finally:
        agno_db.close()

    repository.clear_all_data()

    with sqlite3.connect(db_path) as connection:
        schedule_rows = connection.execute("SELECT COUNT(*) FROM agno_schedules").fetchone()[0]
        run_rows = connection.execute("SELECT COUNT(*) FROM agno_schedule_runs").fetchone()[0]

    assert schedule_rows == 0
    assert run_rows == 0
