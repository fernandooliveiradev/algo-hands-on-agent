from __future__ import annotations

from typing import Any

from agno.agent import Agent

from algo_hands_on.agent_factory import build_agent
from algo_hands_on.config import Settings
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.schemas import TutorTurn


class TutoringService:
    """Orquestra agente, saída estruturada e gravação transacional de progresso."""

    def __init__(self, settings: Settings, repository: ProgressRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.agent: Agent = build_agent(settings)

    def ensure_student(self, student_id: str, display_name: str | None = None) -> dict[str, Any]:
        try:
            return self.repository.get_student(student_id)
        except StudentNotFoundError:
            return self.repository.create_student(student_id, display_name or student_id)

    def run_turn(self, *, student_id: str, session_id: str, message: str) -> TutorTurn:
        self.ensure_student(student_id)
        snapshot = self.repository.get_progress_snapshot(student_id)
        dependencies = {
            "student_progress": snapshot,
            "curriculum_source": "TRILHA-AHO.md",
            "progress_policy": {
                "module_completion_is_computed_by_application": True,
                "minimum_independent_score": 0.8,
                "required_evidence": list(self.repository.REQUIRED_EVIDENCE),
            },
        }

        run = self.agent.run(
            message,
            user_id=student_id,
            session_id=session_id,
            dependencies=dependencies,
            add_dependencies_to_context=True,
        )
        content = run.content
        turn = content if isinstance(content, TutorTurn) else TutorTurn.model_validate(content)

        # Bloqueio defensivo: o agente não pode avaliar módulo distante do módulo atual.
        current_module = snapshot["current"]["current_module"]
        if turn.module_id not in {current_module, max(0, current_module - 1)}:
            turn.module_id = current_module
            if turn.evaluation:
                turn.evaluation.module_id = current_module

        if turn.evaluation:
            exercise_statement = turn.exercise.statement if turn.exercise else None
            self.repository.record_evaluation(
                student_id=student_id,
                session_id=session_id,
                evaluation=turn.evaluation,
                exercise_statement=exercise_statement,
            )

        self.repository.record_event(
            student_id,
            session_id,
            "tutor_turn",
            {
                "turn_type": turn.turn_type.value,
                "module_id": turn.module_id,
                "competency_key": turn.competency_key,
                "next_action": turn.suggested_next_action,
                "run_id": str(run.run_id),
            },
        )
        return turn
