from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import ValidationError

from algo_hands_on.schemas import AttemptResult, TutorTurn

logger = logging.getLogger(__name__)


def _detect_duplicate_paragraphs(text: str) -> list[str]:
    """Detecta parágrafos duplicados no texto.
    
    Retorna lista de parágrafos que aparecem mais de uma vez.
    """
    if not text:
        return []
    
    # Dividir em parágrafos (separados por 2+ quebras de linha)
    paragraphs = re.split(r'\n\s*\n+', text.strip())
    
    # Normalizar para comparação
    def normalize(p: str) -> str:
        return re.sub(r'\s+', ' ', p.strip().lower())
    
    # Contar ocorrências
    seen = {}
    duplicates = []
    
    for para in paragraphs:
        normalized = normalize(para)
        if not normalized or len(normalized) < 20:  # Ignorar parágrafos muito curtos
            continue
        
        seen[normalized] = seen.get(normalized, 0) + 1
        if seen[normalized] == 2:  # Registrar na segunda ocorrência
            # Retornar original para log legível
            duplicates.append(para[:80] + "..." if len(para) > 80 else para)
    
    return duplicates



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
        except ValidationError:
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

    # Detectar duplicações pedagógicas
    duplicates = _detect_duplicate_paragraphs(turn.message_markdown)
    if duplicates:
        logger.warning(
            "Post-run | DUPLICACAO DETECTADA - resposta repete conteúdo. "
            "Primeiras duplicatas: %s",
            "; ".join(duplicates[:3])
        )
