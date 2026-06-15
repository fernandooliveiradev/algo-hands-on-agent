"""Testes para detecção de duplicações no hook."""

import pytest

from algo_hands_on.hooks import _detect_duplicate_paragraphs


def test_detect_duplicate_paragraphs():
    """Testa detecção de parágrafos duplicados."""
    
    # Teste 1: Texto com duplicação clara
    text = """
    Este é um cenário importante que você precisa entender bem.
    
    Vou agora apresentar o desafio.
    
    Este é um cenário importante que você precisa entender bem.
    """
    
    duplicates = _detect_duplicate_paragraphs(text)
    assert len(duplicates) > 0
    assert "cenário" in duplicates[0].lower()
    
    # Teste 2: Pergunta duplicada
    text = """
    Pergunta: Qual é o resultado dessa operação?
    
    Explicação: Vamos resolver passo a passo.
    
    Pergunta: Qual é o resultado dessa operação?
    """
    
    duplicates = _detect_duplicate_paragraphs(text)
    assert len(duplicates) > 0
    
    # Teste 3: Texto sem duplicação
    text = """
    Primeiro parágrafo com conteúdo.
    
    Segundo parágrafo diferente.
    
    Terceiro parágrafo único.
    """
    
    duplicates = _detect_duplicate_paragraphs(text)
    assert len(duplicates) == 0
    
    # Teste 4: Normalização com espaços diferentes
    text = """
    Você   deve   estudar   muito.
    
    Próxima seção.
    
    Você deve estudar muito.
    """
    
    duplicates = _detect_duplicate_paragraphs(text)
    assert len(duplicates) > 0  # Devem ser detectados como iguais
    
    # Teste 5: Parágrafos curtos são ignorados
    text = """
    Sim.
    
    Não.
    
    Sim.
    """
    
    duplicates = _detect_duplicate_paragraphs(text)
    assert len(duplicates) == 0  # Muito curtos, ignorados
    
    # Teste 6: Cenário real da conversa
    text = """
    Cenário: Você precisa organizar o café da manhã de uma família de 4 pessoas. Cada um come coisas diferentes em horários diferentes. A cozinha tem 1 fogão, 1 forno e 1 micro-ondas.
    
    Pergunta: Que passos você seguiria para planejar e preparar esse café da manhã?
    
    Exercício diagnóstico de raciocínio lógico. Você precisa organizar o café da manhã de uma família de 4 pessoas. Cada um come coisas diferentes em horários diferentes. A cozinha tem 1 fogão, 1 forno e 1 micro-ondas.
    
    Pergunta: Que passos você seguiria para planejar e preparar esse café da manhã?
    """
    
    duplicates = _detect_duplicate_paragraphs(text)
    # Deve detectar ao menos a pergunta duplicada
    assert len(duplicates) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
