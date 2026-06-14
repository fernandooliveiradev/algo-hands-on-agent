from __future__ import annotations

import logging
from typing import Any

from algo_hands_on.schemas import AttemptResult, TutorTurn

logger = logging.getLogger(__name__)


def pre_run_context(context: Any) -> None:
    """Pre-hook: valida que as dependências foram injetadas e registra o início da execução."""
    deps = getattr(context, "dependencies", {}) or {}
    student_id = getattr(context, "user_id", "desconhecido")
    session_id = getattr(context, "session_id", "desconhecida")
    logger.debug(
        "Pre-run | aluno=%s | sessão=%s | módulo=%s",
        student_id,
        session_id,
        deps.get("student_progress", {}).get("current", {}).get("current_module", "?"),
    )


def post_run_validate(context: Any) -> None:
    """Post-hook: valida que o TutorTurn foi produzido e audita desvios."""
    content = getattr(context, "content", None)
    if content is None:
        logger.warning("Post-run | resposta vazia")
        return

    turn: TutorTurn | None = None
    if isinstance(content, TutorTurn):
        turn = content
    elif isinstance(content, dict):
        try:
            turn = TutorTurn.model_validate(content)
        except Exception:
            logger.warning("Post-run | falha ao validar TutorTurn")
            return

    if turn is None:
        return

    logger.debug(
        "Post-run | turn=%s | módulo=%s | competência=%s | avaliação=%s",
        turn.turn_type.value,
        turn.module_id,
        turn.competency_key,
        turn.evaluation.result.value if turn.evaluation else "nenhuma",
    )

    if (
        turn.evaluation
        and turn.evaluation.evidence_kind is None
        and turn.evaluation.result in {AttemptResult.CORRECT, AttemptResult.CORRECT_WITH_HINT}
    ):
        logger.warning("Post-run | evidência ausente em avaliação positiva")
