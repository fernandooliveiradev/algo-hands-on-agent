# Guia: Estruturação de Evaluations no Tutor

## Problema Resolvido

O progresso dos alunos **agora será corretamente salvo no banco de dados** quando o tutor avaliar respostas.

## Como Funciona

### Para o Tutor Agent

Quando você **avaliar uma resposta do aluno**, inclua um bloco JSON estruturado na sua resposta:

```markdown
[Feedback ao aluno em linguagem natural]

<!--EVALUATION_START-->
{
  "result": "correct",
  "score": 0.95,
  "evidence_kind": "direct_application",
  "feedback": "Excelente compreensão!"
}
<!--EVALUATION_END-->

[Próxima instrução para o aluno]
```

### Campos Obrigatórios

- `result` (string): Um dos:
  - `"correct"` - Resposta correta e independente (score ≥ 0.8)
  - `"correct_with_hint"` - Correta, mas com ajuda
  - `"incorrect"` - Resposta errada
  - `"incomplete"` - Incompleta
  - `"not_evaluated"` - Não avaliável

- `score` (número 0.0-1.0): Qualidade da resposta
  - 0.0-0.3: Muito fraca
  - 0.3-0.6: Fraca
  - 0.6-0.8: Satisfatória
  - 0.8-1.0: Excelente (marca como "independente")

- `evidence_kind` (string): Tipo de evidência apresentada:
  - `"direct_application"` - Aplicação direta do conceito
  - `"independent_application"` - Sem dependência
  - `"integration"` - Integração com conceitos anteriores
  - `"diagnosis"` - Diagnóstico/correção de erro
  - `"explanation_transfer"` - Explicação ou transferência

- `feedback` (string): Mensagem de feedback (opcional, pode estar vazio)

### Exemplo Completo

```markdown
Sua resposta sobre decomposição foi estruturada e clara. Você conseguiu identificar as partes principais do problema corretamente.

Para melhorar ainda mais, lembre-se de sempre documentar o porquê de cada subdivisão.

<!--EVALUATION_START-->
{
  "result": "correct",
  "score": 0.92,
  "evidence_kind": "direct_application",
  "feedback": "Decomposição bem estruturada com justificativas claras."
}
<!--EVALUATION_END-->

Agora vamos testar com um problema mais complexo...
```

## Fluxo Interno

1. **Tutor Agent** gera resposta com JSON estruturado
2. **Parser Agent** tenta extrair o JSON
3. **TutoringService** extrai manualmente se o parser não conseguir
4. **Validação**: JSON é convertido para `EvaluationResult` Pydantic
5. **Persistência**: Dados são salvos em:
   - `aho_exercise_attempts`
   - `aho_competency_progress`
   - `aho_module_evidence`
6. **UI**: JSON é removido da mensagem mostrada ao aluno

## O que Está Sendo Salvo

Quando você inclui um bloco EVALUATION estruturado:

```
aho_exercise_attempts:
  ├─ attempt_id (UUID único)
  ├─ result (correct/incorrect)
  ├─ score (0.0-1.0)
  ├─ evidence_kind (tipo de evidência)
  ├─ module_id (módulo atual)
  ├─ competency_key (competência avaliada)
  └─ evaluation_json (JSON completo)

aho_competency_progress:
  ├─ evidence_count (incrementa)
  ├─ independent_successes (se score≥0.8)
  ├─ hinted_successes (se usou hint)
  ├─ failed_attempts (se incorreto)
  ├─ mastery_score (maior score até agora)
  └─ status (learning/practicing/mastered)

aho_module_evidence:
  ├─ evidence_kind (tipo)
  ├─ best_score (melhor score para este tipo)
  ├─ satisfied (1 se score≥0.8, sem hint)
  └─ source_attempt_id (referência ao attempt)
```

## Certificação de Domínio

Um módulo é marcado como `"mastered"` quando o aluno demonstra:

✓ **5 tipos de evidência diferentes** (todos os 5):
  1. Direct Application
  2. Independent Application
  3. Integration
  4. Diagnosis
  5. Explanation Transfer

✓ **Todos com score ≥ 0.8**

✓ **Sem uso de hints** (ou nova tentativa sem hints)

✓ **Domínio de todos os pré-requisitos**

## Checklist para Implementar

- [ ] BASE_INSTRUCTIONS instruem o tutor a incluir JSON
- [ ] PARSER_INSTRUCTIONS instruem o parser a extrair JSON
- [ ] `_extract_evaluation_json()` extrai JSON do markdown
- [ ] JSON é removido da mensagem ao usuário
- [ ] `EvaluationResult.model_validate()` valida os dados
- [ ] `record_evaluation()` persiste no banco
- [ ] Testes unitários passam ✓
- [ ] Testes de integração passam ✓

## Troubleshooting

### JSON não está sendo extraído

**Verificar:**
1. Marcadores estão corretos? `<!--EVALUATION_START-->` e `<!--EVALUATION_END-->`
2. JSON é válido? (teste em https://jsonlint.com)
3. Há espaços em branco? Regex permite espaços

### Score 0.8 vs 0.9

- **0.8+** = conta como "independente" (sem hint)
- **0.6-0.8** = conta como "praticante" 
- **< 0.6** = requer review

### Evidência não aparece no snapsh

Verificar:
1. Há evaluation com `evidence_kind`?
2. Score ≥ 0.8?
3. `result` é `"correct"` ou `"correct_with_hint"`?

## Referências

- [Schemas](../src/algo_hands_on/schemas.py)
- [Repository](../src/algo_hands_on/db/repository.py)
- [Tutoring Service](../src/algo_hands_on/services/tutoring.py)
- [Testes](../tests/test_evaluation_extraction.py)
