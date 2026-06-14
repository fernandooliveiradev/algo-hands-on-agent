from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from algo_hands_on.curriculum import MODULES, get_module, next_module_id
from algo_hands_on.db.connection import SQLiteConnectionFactory
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind


class StudentNotFoundError(LookupError):
    """Aluno não encontrado no repositório de progresso."""


class ProgressRepository:
    """Repositório transacional do domínio pedagógico do AHO."""

    REQUIRED_EVIDENCE = tuple(item.value for item in EvidenceKind)

    def __init__(self, db_path: Path) -> None:
        self.factory = SQLiteConnectionFactory(db_path)
        self.schema_path = Path(__file__).with_name("schema.sql")

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self.factory.transaction(write=True) as connection:
            connection.executescript(schema)
            connection.execute(
                "INSERT OR IGNORE INTO aho_schema_migrations(version, name) VALUES (?, ?)",
                (1, "initial_progress_schema"),
            )

    def create_student(self, student_id: str, display_name: str) -> dict[str, Any]:
        with self.factory.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO aho_students(student_id, display_name)
                VALUES (?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (student_id, display_name.strip()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO aho_student_progress(student_id) VALUES (?)",
                (student_id,),
            )
            for module in MODULES:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO aho_module_progress(student_id, module_id)
                    VALUES (?, ?)
                    """,
                    (student_id, module.id),
                )
            connection.execute(
                """
                UPDATE aho_module_progress
                SET status = CASE WHEN module_id = 0 THEN 'in_progress' ELSE status END,
                    started_at = CASE WHEN module_id = 0 AND started_at IS NULL
                        THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now') ELSE started_at END
                WHERE student_id = ?
                """,
                (student_id,),
            )
        self.record_event(student_id, None, "student_upserted", {"display_name": display_name})
        return self.get_student(student_id)

    def get_student(self, student_id: str) -> dict[str, Any]:
        with self.factory.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM aho_students WHERE student_id = ?", (student_id,)
            ).fetchone()
        if row is None:
            raise StudentNotFoundError(student_id)
        result = dict(row)
        result["preferences"] = json.loads(result.pop("preferences_json"))
        return result

    def get_progress_snapshot(self, student_id: str) -> dict[str, Any]:
        self.get_student(student_id)
        with self.factory.transaction() as connection:
            progress = connection.execute(
                "SELECT * FROM aho_student_progress WHERE student_id = ?", (student_id,)
            ).fetchone()
            module_rows = connection.execute(
                "SELECT * FROM aho_module_progress WHERE student_id = ? ORDER BY module_id",
                (student_id,),
            ).fetchall()
            competency_rows = connection.execute(
                """
                SELECT * FROM aho_competency_progress
                WHERE student_id = ? AND module_id = ?
                ORDER BY competency_key
                """,
                (student_id, progress["current_module"]),
            ).fetchall()
            evidence_rows = connection.execute(
                """
                SELECT evidence_kind, best_score, satisfied
                FROM aho_module_evidence
                WHERE student_id = ? AND module_id = ?
                ORDER BY evidence_kind
                """,
                (student_id, progress["current_module"]),
            ).fetchall()
            recent_attempts = connection.execute(
                """
                SELECT module_id, competency_key, evidence_kind, result, score, used_hint, created_at
                FROM aho_exercise_attempts
                WHERE student_id = ?
                ORDER BY created_at DESC LIMIT 10
                """,
                (student_id,),
            ).fetchall()

        current = dict(progress)
        module = get_module(current["current_module"])
        return {
            "student": self.get_student(student_id),
            "current": {
                **current,
                "module_title": module.title,
                "module_slug": module.slug,
                "domain_skill": module.domain_skill,
                "module_competencies": list(module.competencies),
            },
            "modules": [
                {
                    **dict(row),
                    "title": get_module(row["module_id"]).title,
                    "slug": get_module(row["module_id"]).slug,
                }
                for row in module_rows
            ],
            "competencies": [dict(row) for row in competency_rows],
            "evidence": [dict(row) for row in evidence_rows],
            "recent_attempts": [dict(row) for row in recent_attempts],
        }

    def record_evaluation(
        self,
        *,
        student_id: str,
        session_id: str,
        evaluation: EvaluationResult,
        exercise_statement: str | None = None,
    ) -> dict[str, Any]:
        self.get_student(student_id)
        attempt_id = str(uuid.uuid4())
        prompt_hash = (
            hashlib.sha256(exercise_statement.encode("utf-8")).hexdigest()
            if exercise_statement
            else None
        )
        evidence_kind = evaluation.evidence_kind.value if evaluation.evidence_kind else None
        independent_success = (
            evaluation.result == AttemptResult.CORRECT
            and not evaluation.used_hint
            and evaluation.score >= 0.8
        )

        with self.factory.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO aho_exercise_attempts(
                    attempt_id, student_id, session_id, module_id, competency_key,
                    evidence_kind, result, score, used_hint, prompt_hash, evaluation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    student_id,
                    session_id,
                    evaluation.module_id,
                    evaluation.competency_key,
                    evidence_kind,
                    evaluation.result.value,
                    evaluation.score,
                    int(evaluation.used_hint),
                    prompt_hash,
                    evaluation.model_dump_json(),
                ),
            )

            status = self._competency_status(evaluation)
            connection.execute(
                """
                INSERT INTO aho_competency_progress(
                    student_id, module_id, competency_key, status, evidence_count,
                    independent_successes, hinted_successes, failed_attempts,
                    mastery_score, last_attempt_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                ON CONFLICT(student_id, module_id, competency_key) DO UPDATE SET
                    status = excluded.status,
                    evidence_count = aho_competency_progress.evidence_count + 1,
                    independent_successes = aho_competency_progress.independent_successes + excluded.independent_successes,
                    hinted_successes = aho_competency_progress.hinted_successes + excluded.hinted_successes,
                    failed_attempts = aho_competency_progress.failed_attempts + excluded.failed_attempts,
                    mastery_score = MAX(aho_competency_progress.mastery_score, excluded.mastery_score),
                    last_attempt_at = excluded.last_attempt_at,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (
                    student_id,
                    evaluation.module_id,
                    evaluation.competency_key,
                    status,
                    int(independent_success),
                    int(evaluation.result == AttemptResult.CORRECT_WITH_HINT or evaluation.used_hint),
                    int(evaluation.result in {AttemptResult.INCORRECT, AttemptResult.INCOMPLETE}),
                    evaluation.score,
                ),
            )

            if evidence_kind:
                connection.execute(
                    """
                    INSERT INTO aho_module_evidence(
                        student_id, module_id, evidence_kind, best_score, satisfied, source_attempt_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, module_id, evidence_kind) DO UPDATE SET
                        best_score = MAX(aho_module_evidence.best_score, excluded.best_score),
                        satisfied = MAX(aho_module_evidence.satisfied, excluded.satisfied),
                        source_attempt_id = CASE
                            WHEN excluded.satisfied = 1 THEN excluded.source_attempt_id
                            ELSE aho_module_evidence.source_attempt_id
                        END,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    """,
                    (
                        student_id,
                        evaluation.module_id,
                        evidence_kind,
                        evaluation.score,
                        int(independent_success),
                        attempt_id,
                    ),
                )

            connection.execute(
                """
                UPDATE aho_student_progress
                SET current_competency = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    version = version + 1
                WHERE student_id = ?
                """,
                (evaluation.competency_key, student_id),
            )

            self._refresh_module_mastery(connection, student_id, evaluation.module_id)

        self.record_event(
            student_id,
            session_id,
            "exercise_evaluated",
            {"attempt_id": attempt_id, **evaluation.model_dump(mode="json")},
        )
        return {"attempt_id": attempt_id, "progress": self.get_progress_snapshot(student_id)}

    @staticmethod
    def _competency_status(evaluation: EvaluationResult) -> str:
        if evaluation.result == AttemptResult.CORRECT and not evaluation.used_hint and evaluation.score >= 0.8:
            return "mastered"
        if evaluation.result == AttemptResult.CORRECT_WITH_HINT or evaluation.used_hint:
            return "practicing"
        if evaluation.result in {AttemptResult.INCORRECT, AttemptResult.INCOMPLETE}:
            return "needs_review"
        return "learning"

    def _refresh_module_mastery(
        self, connection: sqlite3.Connection, student_id: str, module_id: int
    ) -> None:
        evidence = connection.execute(
            """
            SELECT evidence_kind, satisfied, best_score
            FROM aho_module_evidence
            WHERE student_id = ? AND module_id = ?
            """,
            (student_id, module_id),
        ).fetchall()
        satisfied = {row["evidence_kind"] for row in evidence if row["satisfied"] == 1}
        score = sum(float(row["best_score"]) for row in evidence) / len(self.REQUIRED_EVIDENCE)
        score = min(score, 1.0)
        mastered = set(self.REQUIRED_EVIDENCE).issubset(satisfied)

        connection.execute(
            """
            UPDATE aho_module_progress
            SET status = ?, mastery_score = ?,
                started_at = COALESCE(started_at, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                completed_at = CASE WHEN ? THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now') ELSE completed_at END,
                checkpoint_attempts = checkpoint_attempts + 1,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE student_id = ? AND module_id = ?
            """,
            ("mastered" if mastered else "in_progress", score, int(mastered), student_id, module_id),
        )

        if mastered:
            current = connection.execute(
                "SELECT current_module FROM aho_student_progress WHERE student_id = ?",
                (student_id,),
            ).fetchone()["current_module"]
            upcoming = next_module_id(module_id)
            if current == module_id and upcoming is not None:
                connection.execute(
                    """
                    UPDATE aho_student_progress
                    SET current_module = ?, current_competency = NULL,
                        independence_level = CASE
                            WHEN independence_level = 'observer' THEN 'guided'
                            WHEN independence_level = 'guided' THEN 'independent'
                            ELSE independence_level
                        END,
                        version = version + 1,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE student_id = ?
                    """,
                    (upcoming, student_id),
                )
                connection.execute(
                    """
                    UPDATE aho_module_progress
                    SET status = 'in_progress',
                        started_at = COALESCE(started_at, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE student_id = ? AND module_id = ?
                    """,
                    (student_id, upcoming),
                )
            elif upcoming is None:
                connection.execute(
                    """
                    UPDATE aho_student_progress
                    SET status = 'completed', independence_level = 'transfer',
                        version = version + 1,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    WHERE student_id = ?
                    """,
                    (student_id,),
                )

    def set_current_module(
        self, student_id: str, module_id: int, *, reason: str, session_id: str | None = None
    ) -> None:
        get_module(module_id)
        self.get_student(student_id)
        with self.factory.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE aho_student_progress
                SET current_module = ?, current_competency = NULL,
                    version = version + 1,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE student_id = ?
                """,
                (module_id, student_id),
            )
            connection.execute(
                """
                UPDATE aho_module_progress
                SET status = CASE WHEN status = 'mastered' THEN status ELSE 'in_progress' END,
                    started_at = COALESCE(started_at, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE student_id = ? AND module_id = ?
                """,
                (student_id, module_id),
            )
        self.record_event(student_id, session_id, "module_routed", {"module_id": module_id, "reason": reason})

    def reset_student(self, student_id: str) -> None:
        student = self.get_student(student_id)
        with self.factory.transaction(write=True) as connection:
            connection.execute("DELETE FROM aho_students WHERE student_id = ?", (student_id,))
        self.create_student(student_id, student["display_name"])
        self.record_event(student_id, None, "progress_reset", {})

    def record_event(
        self, student_id: str, session_id: str | None, event_type: str, payload: dict[str, Any]
    ) -> None:
        with self.factory.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO aho_learning_events(event_id, student_id, session_id, event_type, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), student_id, session_id, event_type, json.dumps(payload, ensure_ascii=False)),
            )

    def export_student(self, student_id: str) -> dict[str, Any]:
        snapshot = self.get_progress_snapshot(student_id)
        with self.factory.transaction() as connection:
            attempts = connection.execute(
                "SELECT * FROM aho_exercise_attempts WHERE student_id = ? ORDER BY created_at",
                (student_id,),
            ).fetchall()
            events = connection.execute(
                "SELECT * FROM aho_learning_events WHERE student_id = ? ORDER BY created_at",
                (student_id,),
            ).fetchall()
        snapshot["all_attempts"] = [dict(row) for row in attempts]
        snapshot["events"] = [dict(row) for row in events]
        return snapshot

    def list_sessions(self, student_id: str) -> list[dict[str, Any]]:
        self.get_student(student_id)
        with self.factory.transaction() as connection:
            rows = connection.execute(
                """
                SELECT session_id, MAX(created_at) AS last_active, COUNT(*) AS message_count
                FROM aho_learning_events
                WHERE student_id = ? AND session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY last_active DESC
                """,
                (student_id,),
            ).fetchall()
        return [dict(row) for row in rows]
