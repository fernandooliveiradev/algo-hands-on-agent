from __future__ import annotations

import json
import logging
import re
from collections.abc import Generator
from typing import Any

from agno.agent import Agent
from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from algo_hands_on.agent_factory import build_agent, build_parser_agent
from algo_hands_on.config import Settings
from algo_hands_on.curriculum import get_module
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.schemas import EvaluationResult, TutorTurn

logger = logging.getLogger(__name__)
AGENT_OPERATIONAL_ERRORS = (OpenAIError, RuntimeError, OSError, TimeoutError)

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
EVALUATION_START = "<!--EVALUATION_START-->"
EVALUATION_END = "<!--EVALUATION_END-->"
EVALUATION_BLOCK_PATTERN = re.compile(
    rf"{re.escape(EVALUATION_START)}.*?{re.escape(EVALUATION_END)}\s*",
    re.DOTALL,
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
        allowed = {current_module, max(0, current_module - 1), max(0, current_module - 2)}
        if turn.module_id not in allowed:
            turn.module_id = current_module
        if turn.evaluation:
            self._normalize_evaluation_context(turn.evaluation, snapshot)
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

    def _record_turn_event(
        self,
        turn: TutorTurn,
        student_id: str,
        session_id: str,
        run_id: str | None,
    ) -> None:
        self.repository.record_event(
            student_id,
            session_id,
            "tutor_turn",
            {
                "turn_type": turn.turn_type.value,
                "module_id": turn.module_id,
                "competency_key": turn.competency_key,
                "next_action": turn.suggested_next_action,
                "run_id": run_id,
            },
        )

    @staticmethod
    def _turn_from_content(content: object) -> TutorTurn | None:
        if isinstance(content, TutorTurn):
            return content
        if isinstance(content, BaseModel):
            try:
                return TutorTurn.model_validate(content.model_dump())
            except ValidationError:
                return None
        if isinstance(content, dict):
            try:
                return TutorTurn.model_validate(content)
            except ValidationError:
                return None
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return None
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s*```$", "", text)
            try:
                return TutorTurn.model_validate_json(text)
            except (json.JSONDecodeError, ValidationError):
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

    @staticmethod
    def _extract_evaluation_json(text: str) -> dict[str, Any] | None:
        start = text.find(EVALUATION_START)
        if start < 0:
            return None
        content_start = start + len(EVALUATION_START)
        end = text.find(EVALUATION_END, content_start)
        if end < 0:
            return None

        try:
            payload = json.loads(text[content_start:end].strip())
        except json.JSONDecodeError:
            logger.warning("Bloco EVALUATION inválido; progresso da tentativa não será salvo.")
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _clean_evaluation_blocks(text: str) -> str:
        return EVALUATION_BLOCK_PATTERN.sub("", text).strip()

    @staticmethod
    def _fallback_competency(snapshot: dict, module_id: int) -> str:
        current = snapshot["current"]
        if module_id == current["current_module"] and current.get("current_competency"):
            return str(current["current_competency"])
        return get_module(module_id).competencies[0]

    @classmethod
    def _coerce_module_id(cls, module_id: object, snapshot: dict) -> int:
        current_module = snapshot["current"]["current_module"]
        allowed = {current_module, max(0, current_module - 1), max(0, current_module - 2)}
        try:
            candidate = int(module_id)
        except (TypeError, ValueError):
            return current_module
        return candidate if candidate in allowed else current_module

    @classmethod
    def _normalize_evaluation_context(cls, evaluation: EvaluationResult, snapshot: dict) -> None:
        evaluation.module_id = cls._coerce_module_id(evaluation.module_id, snapshot)
        if evaluation.competency_key not in get_module(evaluation.module_id).competencies:
            evaluation.competency_key = cls._fallback_competency(snapshot, evaluation.module_id)

    def _evaluation_from_tutor_text(
        self,
        tutor_text: str,
        *,
        turn: TutorTurn,
        snapshot: dict,
    ) -> EvaluationResult | None:
        eval_json = self._extract_evaluation_json(tutor_text)
        if not eval_json:
            return None

        module_id = self._coerce_module_id(
            eval_json.get("module_id", turn.module_id),
            snapshot,
        )
        eval_json["module_id"] = module_id
        eval_json.setdefault(
            "competency_key",
            turn.competency_key or self._fallback_competency(snapshot, module_id),
        )

        try:
            evaluation = EvaluationResult.model_validate(eval_json)
        except ValidationError as exc:
            logger.warning("Evaluation estruturada inválida; progresso não salvo: %s", exc)
            return None
        self._normalize_evaluation_context(evaluation, snapshot)
        return evaluation

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
        clean_text = self._clean_evaluation_blocks(tutor_text)
        turn: TutorTurn | None = None
        try:
            run = self.parser_agent.run(
                parser_input,
                user_id=student_id,
                session_id=f"{session_id}:parser",
                dependencies=self._build_dependencies(student_id),
                add_dependencies_to_context=True,
            )
            turn = self._turn_from_content(run.content)
        except AGENT_OPERATIONAL_ERRORS as exc:
            logger.warning("Parser Agno indisponível; usando fallback determinístico: %s", exc)

        if turn is None:
            turn = self._fallback_turn(clean_text, snapshot)
        turn.message_markdown = clean_text.strip()

        if turn.evaluation is None:
            turn.evaluation = self._evaluation_from_tutor_text(
                tutor_text,
                turn=turn,
                snapshot=snapshot,
            )

        return turn

    def _finalize_turn(
        self,
        turn: TutorTurn,
        student_id: str,
        session_id: str,
        snapshot: dict,
        run_id: str | None,
    ) -> TutorTurn:
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
        turn = self._parse_turn(
            student_id=student_id,
            session_id=session_id,
            message=message,
            tutor_text=tutor_text,
            snapshot=snapshot,
        )
        run_id = str(run.run_id) if run.run_id else None
        return self._finalize_turn(turn, student_id, session_id, snapshot, run_id)

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

        run_id: str | None = None
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

        turn = self._parse_turn(
            student_id=student_id,
            session_id=session_id,
            message=message,
            tutor_text=tutor_text,
            snapshot=snapshot,
        )

        turn = self._finalize_turn(turn, student_id, session_id, snapshot, run_id)
        yield {"type": "final", "turn": turn}
