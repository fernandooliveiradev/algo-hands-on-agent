from __future__ import annotations

from collections.abc import Generator

from agno.agent import Agent

from algo_hands_on.agent_factory import build_agent, build_parser_agent
from algo_hands_on.config import Settings
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.schemas import TutorTurn


class TutoringService:
    """Orquestra agente, saída estruturada e gravação transacional de progresso."""

    def __init__(self, settings: Settings, repository: ProgressRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.agent: Agent = build_agent(settings)
        self.parser_agent: Agent = build_parser_agent(settings)

    def ensure_student(self, student_id: str, display_name: str | None = None) -> None:
        try:
            self.repository.get_student(student_id)
        except StudentNotFoundError:
            self.repository.create_student(student_id, display_name or student_id)

    def _build_dependencies(self, student_id: str) -> dict:
        snapshot = self.repository.get_progress_snapshot(student_id)
        return {
            "student_progress": snapshot,
            "curriculum_source": "TRILHA-AHO.md",
            "progress_policy": {
                "module_completion_is_computed_by_application": True,
                "minimum_independent_score": 0.8,
                "required_evidence": list(self.repository.REQUIRED_EVIDENCE),
            },
        }

    def _guard_module_id(self, turn: TutorTurn, snapshot: dict) -> TutorTurn:
        current_module = snapshot["current"]["current_module"]
        # Permite referenciar até 2 módulos anteriores para remediação, mas nunca futuros
        allowed = {current_module, max(0, current_module - 1), max(0, current_module - 2)}
        if turn.module_id not in allowed:
            turn.module_id = current_module
            if turn.evaluation:
                turn.evaluation.module_id = current_module
        return turn

    def _persist_evaluation(self, turn: TutorTurn, student_id: str, session_id: str) -> None:
        if turn.evaluation:
            exercise_statement = turn.exercise.statement if turn.exercise else None
            self.repository.record_evaluation(
                student_id=student_id,
                session_id=session_id,
                evaluation=turn.evaluation,
                exercise_statement=exercise_statement,
            )

    def _record_turn_event(self, turn: TutorTurn, student_id: str, session_id: str, run_id: str) -> None:
        self.repository.record_event(
            student_id,
            session_id,
            "tutor_turn",
            {
                "turn_type": turn.turn_type.value,
                "module_id": turn.module_id,
                "competency_key": turn.competency_key,
                "next_action": turn.suggested_next_action,
                "run_id": str(run_id),
            },
        )

    @staticmethod
    def _turn_from_content(content: object) -> TutorTurn | None:
        if isinstance(content, TutorTurn):
            return content
        if isinstance(content, dict):
            return TutorTurn.model_validate(content)
        return None

    def _parse_turn(
        self,
        *,
        student_id: str,
        session_id: str,
        message: str,
        tutor_text: str,
        snapshot: dict,
    ) -> TutorTurn:
        parser_input = (
            "Mensagem do aluno:\n"
            f"{message}\n\n"
            "Resposta do tutor:\n"
            f"{tutor_text}"
        )
        run = self.parser_agent.run(
            parser_input,
            user_id=student_id,
            session_id=f"{session_id}:parser",
            dependencies=self._build_dependencies(student_id),
            add_dependencies_to_context=True,
        )
        turn = self._turn_from_content(run.content)
        if turn is None:
            msg = "Agno parser não retornou TutorTurn estruturado."
            raise RuntimeError(msg)
        turn.message_markdown = tutor_text
        if not turn.module_id:
            turn.module_id = snapshot["current"]["current_module"]
        return turn

    def _finalize_turn(self, turn: TutorTurn, student_id: str, session_id: str, snapshot: dict, run_id: str) -> TutorTurn:
        turn = self._guard_module_id(turn, snapshot)
        self._persist_evaluation(turn, student_id, session_id)
        self._record_turn_event(turn, student_id, session_id, run_id=run_id)
        return turn

    def run_turn(self, *, student_id: str, session_id: str, message: str) -> TutorTurn:
        self.ensure_student(student_id)
        snapshot = self.repository.get_progress_snapshot(student_id)

        run = self.agent.run(
            message,
            user_id=student_id,
            session_id=session_id,
            dependencies=self._build_dependencies(student_id),
            add_dependencies_to_context=True,
        )
        tutor_text = str(run.content or "").strip()
        turn = self._parse_turn(
            student_id=student_id,
            session_id=session_id,
            message=message,
            tutor_text=tutor_text,
            snapshot=snapshot,
        )
        return self._finalize_turn(turn, student_id, session_id, snapshot, str(run.run_id))

    def run_turn_stream(
        self, *, student_id: str, session_id: str, message: str
    ) -> Generator[dict, None, None]:
        self.ensure_student(student_id)
        snapshot = self.repository.get_progress_snapshot(student_id)

        run_stream = self.agent.run(
            message,
            user_id=student_id,
            session_id=session_id,
            dependencies=self._build_dependencies(student_id),
            add_dependencies_to_context=True,
            stream=True,
            stream_events=True,
            yield_run_output=True,
        )

        run_id = "unknown"
        text_chunks: list[str] = []
        final_text = ""
        saw_run_response_event = False

        for chunk in run_stream:
            if hasattr(chunk, "run_id") and chunk.run_id:
                run_id = str(chunk.run_id)

            event_name = str(getattr(chunk, "event", ""))
            chunk_content = getattr(chunk, "content", None)

            # Agno emite conteúdo de streaming em eventos RunContent / RunIntermediateContent / RunResponse
            if event_name in {"RunContent", "RunIntermediateContent", "RunResponse"} and isinstance(chunk_content, str):
                saw_run_response_event = True
                text_chunks.append(chunk_content)
                yield {"type": "content", "text": chunk_content}
                continue

            # Fallback: último chunk com texto final (RunCompleted, etc.)
            if isinstance(chunk_content, str) and not saw_run_response_event:
                final_text = chunk_content

        tutor_text = ("".join(text_chunks) or final_text).strip()
        if not tutor_text:
            msg = (
                "Agno não retornou texto ao finalizar o streaming. "
                "Verifique a chave da API DeepSeek e a conectividade."
            )
            raise RuntimeError(msg)

        # Sinaliza ao frontend que terminou o streaming e vai estruturar
        yield {"type": "parsing", "text": "\n\nProcessando resposta..."}

        try:
            turn = self._parse_turn(
                student_id=student_id,
                session_id=session_id,
                message=message,
                tutor_text=tutor_text,
                snapshot=snapshot,
            )
        except Exception as parse_exc:
            # Fallback: cria um turn mínimo com o texto bruto como mensagem
            from algo_hands_on.schemas import TutorTurn

            turn = TutorTurn(
                message_markdown=tutor_text,
                module_id=snapshot["current"]["current_module"],
            )
            yield {"type": "warning", "text": f"Parser indisponível: {parse_exc}"}

        turn = self._finalize_turn(turn, student_id, session_id, snapshot, run_id)
        yield {"type": "final", "turn": turn}
