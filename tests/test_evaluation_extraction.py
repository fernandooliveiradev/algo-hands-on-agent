import pytest
from algo_hands_on.services.tutoring import TutoringService


def test_extract_evaluation_json():
    """Testa extração de JSON de evaluation do texto do tutor."""
    
    # Teste 1: JSON bem-formado
    text_with_eval = """
    Ótimo trabalho! Você compreendeu perfeitamente o conceito de decomposição.
    
    <!--EVALUATION_START-->
    {"result": "correct", "score": 0.95, "evidence_kind": "direct_application", "feedback": "Excelente compreensão!"}
    <!--EVALUATION_END-->
    """
    
    eval_json = TutoringService._extract_evaluation_json(text_with_eval)
    assert eval_json is not None
    assert eval_json["result"] == "correct"
    assert eval_json["score"] == 0.95
    assert eval_json["evidence_kind"] == "direct_application"
    
    # Teste 2: Sem JSON de evaluation
    text_without_eval = "Qual é o seu objetivo neste curso?"
    eval_json = TutoringService._extract_evaluation_json(text_without_eval)
    assert eval_json is None
    
    # Teste 3: JSON inválido (deve retornar None)
    text_invalid_json = """
    Sua tentativa não está correta.
    <!--EVALUATION_START-->
    {"result": "incorrect" invalid json here
    <!--EVALUATION_END-->
    """
    eval_json = TutoringService._extract_evaluation_json(text_invalid_json)
    assert eval_json is None


def test_clean_evaluation_markers_from_text():
    """Testa remoção de marcadores de evaluation do texto."""
    import re
    
    text = """
    Isso é feedback para o aluno.
    
    <!--EVALUATION_START-->
    {"result": "correct", "score": 0.9}
    <!--EVALUATION_END-->
    
    Próximo passo...
    """
    
    clean_text = re.sub(
        r"<!--EVALUATION_START-->.*?<!--EVALUATION_END-->\s*",
        "",
        text,
        flags=re.DOTALL
    ).strip()
    
    assert "<!--EVALUATION_START-->" not in clean_text
    assert "<!--EVALUATION_END-->" not in clean_text
    assert "Isso é feedback" in clean_text
    assert "Próximo passo" in clean_text
    assert "{" not in clean_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
