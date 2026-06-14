from __future__ import annotations

from collections.abc import Generator

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
        if turn.module_id not in {current_module, max(0, current_module - 1)}:
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
        content = run.content
        turn = content if isinstance(content, TutorTurn) else TutorTurn.model_validate(content)
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
            stream_events=self.settings.stream_events,
        )

        run_id = "unknown"
        json_chunks: list[str] = []
        turn_from_object: TutorTurn | None = None
        last_displayed_len = 0

        for chunk in run_stream:
            if hasattr(chunk, "run_id") and chunk.run_id:
                run_id = str(chunk.run_id)

            event_type = getattr(chunk, "event", None)
            is_tool_event = False
            if event_type is not None:
                event_name = getattr(event_type, "__name__", "") if hasattr(event_type, "__name__") else str(event_type)
                is_tool_event = "Tool" in event_name or "tool" in event_name

            chunk_content = getattr(chunk, "content", None)
            if chunk_content is None:
                continue

            if isinstance(chunk_content, TutorTurn):
                turn_from_object = chunk_content
                continue

            if isinstance(chunk_content, str):
                if is_tool_event:
                    continue
                json_chunks.append(chunk_content)
                # Extrai message_markdown parcial para streaming visual
                display_text = self._extract_partial_markdown("".join(json_chunks))
                if display_text and len(display_text) > last_displayed_len:
                    delta = display_text[last_displayed_len:]
                    last_displayed_len = len(display_text)
                    yield {"type": "content", "text": delta}
            else:
                json_chunks.append(str(chunk_content))

        # Prioridade: objeto TutorTurn > parse do JSON acumulado > fallback
        if turn_from_object is not None:
            turn = turn_from_object
        else:
            combined = "".join(json_chunks).strip()
            turn = self._parse_stream_content(combined, snapshot)

        turn = self._finalize_turn(turn, student_id, session_id, snapshot, run_id)
        yield {"type": "final", "turn": turn}

    @staticmethod
    def _extract_partial_markdown(text: str) -> str:
        """Extrai message_markdown parcial de JSON incompleto via estado."""
        key = '"message_markdown": "'
        idx = text.find(key)
        if idx == -1:
            return ""
        start = idx + len(key)
        result: list[str] = []
        i = start
        escaped = False
        while i < len(text):
            ch = text[i]
            if escaped:
                result.append(ch)
                escaped = False
                i += 1
                continue
            if ch == "\\":
                result.append(ch)
                escaped = True
                i += 1
                continue
            if ch == '"':
                break
            result.append(ch)
            i += 1
        raw = "".join(result)
        # Decodifica escapes JSON parciais
        raw = raw.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
        raw = raw.replace('\\"', '"').replace("\\\\", "\\")
        return raw

    @staticmethod
    def _parse_stream_content(combined: str, snapshot: dict) -> TutorTurn:
        if not combined:
            return TutorTurn(message_markdown="Sem resposta.",
                             module_id=snapshot["current"]["current_module"])
        # Tenta cada chunk individualmente (do ultimo para o primeiro)
        json_attempts: list[str] = []
        brace_depth = 0
        start = -1
        for i, ch in enumerate(combined):
            if ch == "{":
                if brace_depth == 0:
                    start = i
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0 and start >= 0:
                    json_attempts.append(combined[start:i + 1])
                    start = -1
        # Tenta parsear cada bloco JSON, do ultimo para o primeiro
        for candidate in reversed(json_attempts):
            try:
                return TutorTurn.model_validate_json(candidate)
            except Exception:
                continue
        # Fallback: usa o texto combinado como markdown
        return TutorTurn(message_markdown=combined or "Sem resposta.",
                         module_id=snapshot["current"]["current_module"])
