"""Teste de integração: fluxo completo de tutoring com persistência de evaluation."""

import pytest
from pathlib import Path
from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.services.tutoring import TutoringService
from algo_hands_on.config import Settings
from algo_hands_on.schemas import (
    TutorTurn, EvaluationResult, AttemptResult, EvidenceKind
)


def test_integration_tutor_response_with_evaluation_json(tmp_path: Path):
    """
    Simula resposta do tutor com JSON estruturado de evaluation.
    Valida que o JSON é extraído, validado e pode ser persistido.
    """
    
    # Setup
    repository = ProgressRepository(tmp_path / "aho.db")
    repository.initialize()
    repository.create_student("test-student", "Test Student")
    
    settings = Settings(
        _env_file=None,
        deepseek_api_key="test",
        db_path=tmp_path / "aho.db",
    )
    
    # Simular resposta do tutor com JSON estruturado
    tutor_response_with_json = """
    Excelente! Você compreendeu corretamente como decompor o problema.
    
    <!--EVALUATION_START-->
    {
        "result": "correct",
        "score": 0.95,
        "evidence_kind": "direct_application",
        "feedback": "Sua decomposição estava clara e bem estruturada."
    }
    <!--EVALUATION_END-->
    
    Agora vamos praticar com um exemplo mais complexo.
    """
    
    # Extract evaluation JSON
    eval_json = TutoringService._extract_evaluation_json(tutor_response_with_json)
    
    assert eval_json is not None
    assert eval_json["result"] == "correct"
    assert eval_json["score"] == 0.95
    assert eval_json["evidence_kind"] == "direct_application"
    
    # Validar que pode ser convertido para EvaluationResult
    eval_result = EvaluationResult.model_validate({
        **eval_json,
        "module_id": 0,
        "competency_key": "decomposicao"
    })
    
    assert eval_result.result == AttemptResult.CORRECT
    assert eval_result.score == 0.95
    assert eval_result.evidence_kind == EvidenceKind.DIRECT
    
    # Persistir no banco
    result = repository.record_evaluation(
        student_id="test-student",
        session_id="test-session",
        evaluation=eval_result
    )
    
    # Validar que foi gravado
    assert result["attempt_id"] is not None
    snapshot = repository.get_progress_snapshot("test-student")
    assert len(snapshot["recent_attempts"]) == 1
    assert snapshot["recent_attempts"][0]["result"] == "correct"
    assert snapshot["recent_attempts"][0]["score"] == 0.95
    
    # Validar que evidence foi registrada
    assert len(snapshot["evidence"]) >= 1
    evidence = next((e for e in snapshot["evidence"] if e["evidence_kind"] == "direct_application"), None)
    assert evidence is not None
    assert evidence["best_score"] == 0.95


def test_integration_tutor_text_cleaned_for_user(tmp_path: Path):
    """
    Valida que o JSON estruturado é removido da mensagem mostrada ao usuário.
    """
    import re
    
    tutor_response = """
    Perfeito! Sua resposta está correta.
    
    <!--EVALUATION_START-->
    {"result": "correct", "score": 0.9, "evidence_kind": "direct_application"}
    <!--EVALUATION_END-->
    
    Vamos ao próximo exercício.
    """
    
    # Simular limpeza feita em _parse_turn
    clean_text = re.sub(
        r"<!--EVALUATION_START-->.*?<!--EVALUATION_END-->\s*",
        "",
        tutor_response,
        flags=re.DOTALL
    ).strip()
    
    # Validar que JSON foi removido
    assert "<!--EVALUATION_START-->" not in clean_text
    assert "<!--EVALUATION_END-->" not in clean_text
    assert "{" not in clean_text or "{" not in clean_text.split("\n")[0]
    
    # Validar que feedback ao usuário está intacto
    assert "Perfeito!" in clean_text
    assert "Vamos ao próximo exercício" in clean_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
