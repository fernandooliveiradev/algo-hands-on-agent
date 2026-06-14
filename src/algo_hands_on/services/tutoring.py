from __future__ import annotations

import json
import re
from collections.abc import Generator
from typing import Any

from agno.agent import Agent
from pydantic import BaseModel

from algo_hands_on.agent_factory import build_agent, build_parser_agent
from algo_hands_on.config import Settings
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.schemas import TutorTurn

INTERNAL_NARRATION_PATTERNS = [
    re.compile(
        r"(?is)\bvou\s+(?:buscar|carregar|consultar|seguir|usar)\s+(?:as?\s+)?"
        r"(?:orientações|instruções|skills?|ferramentas?|regras?|dependências|contexto|políticas)"
        r".*?(?=(?:\n|Olá|Perfeito|Vamos|Prazer|Agora|Antes|\Z))"
    ),
    re.compile(
        r"(?im)^\s*(?:carregando|consultando|buscando)\s+"
        r"(?:skill|instruções|orientações|ferramentas|contexto).*?$"
    ),
]
EMOJI_PATTERN = re.compile(
    "["
    "\U0001f1e6-\U0001f1ff"
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa70-\U0001faff"
    "\u2600-\u27bf"
    "]+"
)


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
        if isinstance(content, BaseModel):
            return TutorTurn.model_validate(content.model_dump())
        if isinstance(content, dict):
            return TutorTurn.model_validate(content)
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return None
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s*```$", "", text)
            try:
                return TutorTurn.model_validate_json(text)
            except json.JSONDecodeError:
                return None
            except Exception:
                return None
        return None

    @staticmethod
    def _chunk_value(chunk: object, key: str, default: Any = None) -> Any:
        if isinstance(chunk, dict):
            return chunk.get(key, default)
        return getattr(chunk, key, default)

    @classmethod
    def _chunk_event_name(cls, chunk: object) -> str:
        event = cls._chunk_value(chunk, "event")
        if event:
            return str(event)
        return type(chunk).__name__

    @classmethod
    def _chunk_text(cls, chunk: object) -> str | None:
        content = cls._chunk_value(chunk, "content")
        return content if isinstance(content, str) else None

    @staticmethod
    def _append_stream_text(current_text: str, chunk_text: str) -> tuple[str, str]:
        """Retorna texto acumulado e o delta a renderizar.

        Agno costuma enviar deltas em RunContent, mas alguns providers podem
        devolver conteúdo cumulativo. Este helper evita duplicar texto nos dois
        casos.
        """
        if not current_text:
            return chunk_text, chunk_text
        if chunk_text.startswith(current_text):
            delta = chunk_text[len(current_text) :]
            return chunk_text, delta
        return current_text + chunk_text, chunk_text

    @staticmethod
    def _sanitize_tutor_text(text: str, *, strip_right: bool = True) -> str:
        clean = text
        for pattern in INTERNAL_NARRATION_PATTERNS:
            clean = pattern.sub("", clean)
        clean = EMOJI_PATTERN.sub("", clean)
        clean = re.sub(r"[ \t]{2,}", " ", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        clean = clean.lstrip()
        return clean.rstrip() if strip_right else clean

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
        return turn

    def _finalize_turn(self, turn: TutorTurn, student_id: str, session_id: str, snapshot: dict, run_id: str) -> TutorTurn:
        turn = self._guard_module_id(turn, snapshot)
        self._persist_evaluation(turn, student_id, session_id)
        self._record_turn_event(turn, student_id, session_id, run_id=run_id)
        return turn

    @staticmethod
    def _fallback_turn(tutor_text: str, snapshot: dict) -> TutorTurn:
        return TutorTurn(
            message_markdown=tutor_text,
            module_id=snapshot["current"]["current_module"],
        )

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
        tutor_text = self._sanitize_tutor_text(str(run.content or "")).strip()
        try:
            turn = self._parse_turn(
                student_id=student_id,
                session_id=session_id,
                message=message,
                tutor_text=tutor_text,
                snapshot=snapshot,
            )
        except Exception:
            turn = self._fallback_turn(tutor_text, snapshot)
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
        tutor_text = ""
        rendered_text = ""
        final_text = ""
        saw_stream_content = False

        for chunk in run_stream:
            chunk_run_id = self._chunk_value(chunk, "run_id")
            if chunk_run_id:
                run_id = str(chunk_run_id)

            event_name = self._chunk_event_name(chunk)
            chunk_text = self._chunk_text(chunk)

            if event_name in {"RunContent", "RunIntermediateContent"} and chunk_text:
                saw_stream_content = True
                tutor_text, _ = self._append_stream_text(tutor_text, chunk_text)
                clean_text = self._sanitize_tutor_text(tutor_text, strip_right=False)
                rendered_text, clean_delta = self._append_stream_text(rendered_text, clean_text)
                if clean_delta:
                    yield {"type": "content", "text": clean_delta}
                continue

            if event_name in {"RunCompleted", "RunOutput"} and chunk_text:
                final_text = chunk_text

        if not saw_stream_content and final_text:
            tutor_text = final_text

        tutor_text = self._sanitize_tutor_text(tutor_text).strip()
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
            turn = self._fallback_turn(tutor_text, snapshot)
            yield {"type": "warning", "text": f"Parser indisponível: {parse_exc}"}

        turn = self._finalize_turn(turn, student_id, session_id, snapshot, run_id)
        yield {"type": "final", "turn": turn}
