from __future__ import annotations

import logging
from typing import Any

from algo_hands_on.schemas import AttemptResult, TutorTurn

logger = logging.getLogger(__name__)


def pre_run_context(**kwargs: Any) -> None:
    """Pre-hook: registra o inicio da execucao e dados disponiveis no contexto."""
    student_id = kwargs.get("user_id", "desconhecido")
    session_id = kwargs.get("session_id", "desconhecida")
    logger.debug("Pre-run | aluno=%s | sessao=%s", student_id, session_id)


def post_run_validate(**kwargs: Any) -> None:
    """Post-hook: valida o TutorTurn e audita desvios na resposta."""
    content = kwargs.get("content") or kwargs.get("run_output") or kwargs.get("run_response")
    if content is None:
        logger.warning("Post-run | resposta vazia")
        return

    # Extrai o texto/conteudo do RunResponse se for objeto Agno
    if hasattr(content, "content"):
        content = content.content

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
        "Post-run | turn=%s | modulo=%s | competencia=%s | avaliacao=%s",
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
        logger.warning("Post-run | evidencia ausente em avaliacao positiva")
