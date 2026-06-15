# Algo Hands-On

**Pense. Resolva. Construa.**

Algo Hands-On é um tutor adaptativo para pensamento computacional, lógica,
algoritmos e Python. Ele combina Agno, DeepSeek, SQLite, FastAPI, Typer e uma TUI
em terminal para conduzir prática guiada, avaliação estruturada e acompanhamento
persistente de progresso.

O projeto foi desenhado para uma regra central: o modelo de linguagem ensina e
avalia, mas não decide sozinho o avanço curricular. O domínio do aluno é
calculado pela aplicação a partir de evidências persistidas no banco.

## Principais Garantias

- `TRILHA-AHO.md` é a fonte curricular canônica.
- O tutor gera exercícios dinamicamente, respeitando módulo, histórico e nível de independência.
- A resposta do agente é normalizada em `TutorTurn` antes de qualquer persistência pedagógica.
- Correções separam raciocínio, algoritmo e sintaxe.
- Cada turno avaliado entra no banco com nota de `0%` a `100%`.
- O progresso avança quando as 5 evidências do módulo foram cobertas e a média final por evidência atinge `70%`.
- A média final do módulo vai de `0%` a `100%`, usando a melhor nota registrada em cada evidência.
- O SQLite registra alunos, progresso, tentativas, evidências, eventos e dados operacionais do Agno.

## Stack

- Python `>=3.12`
- Agno
- DeepSeek via API compatível com OpenAI
- SQLite com transações explícitas
- FastAPI e AgentOS
- Typer e Rich para CLI
- Textual para TUI
- Pydantic para contratos de dados
- Pytest e Ruff para qualidade

## Instalação

```bash
cp .env.example .env
# edite .env e preencha DEEPSEEK_API_KEY

uv sync --extra dev
uv run aho doctor
```

Variáveis principais:

```env
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat
AHO_DB_PATH=./data/aho.db
AHO_SKILLS_DIR=./skills
AHO_STREAM=true
AHO_MEMORY=true
AHO_SESSION_SUMMARIES=true
AHO_DEBUG=false
AHO_HOST=127.0.0.1
AHO_PORT=7777
```

## Uso Rápido

```bash
uv run aho setup --student-id aluno123 --name "Maria Silva"
uv run aho chat --student-id aluno123
uv run aho progress --student-id aluno123
```

Comandos úteis:

```bash
uv run aho students
uv run aho modules
uv run aho export --student-id aluno123 --output progresso.json
uv run aho reset --student-id aluno123
uv run aho clean
uv run aho serve --reload
```

Dentro do chat:

```text
/ajuda
/progresso
/checkpoint
/historico
/sessoes
/continuar
/exercicio
/dica
/sair
```

## Arquitetura

```text
src/algo_hands_on/
  agent_factory.py      cria agente tutor e parser estruturado
  services/tutoring.py  orquestra Agno, streaming, parser e persistência
  db/connection.py      conexões SQLite transacionais
  db/repository.py      domínio de progresso e cálculo de domínio
  db/schema.sql         schema das tabelas AHO
  db/agno_tables.py     nomes das tabelas Agno no mesmo SQLite
  cli.py                comandos Typer
  tui.py                interface Textual
  api.py                FastAPI + AgentOS
  chat_core.py          comandos locais e renderização de conversa
  schemas.py            contratos Pydantic
  curriculum.py         módulos e competências da trilha
```

Fluxo principal:

```text
Aluno
  -> CLI/TUI/API
  -> TutoringService
  -> Agente tutor Agno
  -> Parser estruturado
  -> TutorTurn validado
  -> ProgressRepository
  -> SQLite
```

## Banco de Dados

O banco padrão fica em `data/aho.db`, configurável por `AHO_DB_PATH`.

Tabelas de domínio AHO:

- `aho_students`
- `aho_student_progress`
- `aho_module_progress`
- `aho_competency_progress`
- `aho_exercise_attempts`
- `aho_module_evidence`
- `aho_learning_events`
- `aho_schema_migrations`

Tabelas Agno usadas no mesmo SQLite:

- `agno_sessions`
- `agno_memories`
- `agno_metrics`
- `agno_evals`
- `agno_schema_versions`

Tabelas Agno preparadas para uso futuro:

- `agno_schedules`
- `agno_schedule_runs`

Essas tabelas de schedule pertencem ao Agno. Hoje não fazem parte do fluxo ativo
do tutor, mas podem servir no futuro para lembretes, revisão espaçada, rotinas de
checkpoint e retomada de alunos inativos.

## Como Ter Certeza de Que o Banco Funciona

Use três níveis de verificação.

1. Verificação de ambiente:

```bash
uv run aho doctor
```

Esse comando confirma Python, chave de API, caminho do SQLite, diretório de
skills e configurações principais.

2. Testes automatizados de persistência:

```bash
uv run python -m pytest tests/test_persistence.py tests/test_integration_evaluation.py tests/test_tutoring_service.py
```

Esses testes cobrem criação de aluno, gravação de tentativa, evidências,
avanço de módulo por média, isolamento por aluno, reset, limpeza do banco, extração de
avaliação e fallback do parser.

3. Smoke test sem chamar LLM:

PowerShell:

```powershell
@'
from pathlib import Path
from tempfile import TemporaryDirectory

from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind

with TemporaryDirectory() as tmp:
    repo = ProgressRepository(Path(tmp) / "aho.db")
    repo.initialize()
    repo.create_student("smoke", "Smoke Test")

    for kind in EvidenceKind:
        repo.record_evaluation(
            student_id="smoke",
            session_id="smoke-session",
            evaluation=EvaluationResult(
                result=AttemptResult.CORRECT,
                score=0.9,
                used_hint=False,
                module_id=0,
                competency_key="objetivo-de-aprendizagem",
                evidence_kind=kind,
            ),
        )

    snapshot = repo.get_progress_snapshot("smoke")
    assert snapshot["modules"][0]["status"] == "mastered"
    assert snapshot["current"]["current_module"] == 1
    assert len(snapshot["recent_attempts"]) == 5
    print("Banco OK: aluno, tentativas, evidências e avanço persistidos.")
'@ | uv run python -
```

Se os três níveis passam, o banco está comunicando com o domínio principal:
schema, repositório, regras de domínio, transações e leitura de progresso.

## Regra de Progressão

O aluno vê uma regra simples:

- cada turno respondido pode gerar uma avaliação registrada no banco;
- cada módulo usa 5 evidências curriculares;
- a aplicação guarda a melhor nota obtida em cada evidência;
- a média final do módulo é a média dessas 5 melhores notas;
- o avanço acontece quando a cobertura chega a `5/5` evidências e a média final fica em `70%` ou mais.

Exemplo:

- se o aluno cobriu 3 evidências com notas `80`, `70` e `60`, a cobertura ainda é `3/5`, então o módulo não avança;
- se ele cobriu as 5 evidências com `80`, `70`, `60`, `70` e `70`, a média final é `70%` e o módulo pode avançar.

## Qualidade

```bash
uv run ruff check .
uv run python -m pytest
uv run aho doctor
```

Use `uv run python -m pytest` para executar com o interpretador correto do
ambiente virtual. Em alguns ambientes Windows, o launcher curto `uv run pytest`
pode não carregar dependências opcionais da TUI.

## Contrato Pedagógico

O tutor deve:

- responder em português do Brasil;
- consultar `TRILHA-AHO.md` como fonte curricular;
- carregar a skill pertinente antes de ensinar;
- não introduzir conceitos posteriores sem diagnóstico de pré-requisito;
- exigir previsão, teste, explicação ou adaptação conforme o estágio;
- registrar tentativas e evidências pelo serviço de progresso;
- nunca afirmar avanço sem persistência confirmada.

As cinco evidências de checkpoint são:

- `direct_application`
- `independent_application`
- `integration`
- `diagnosis`
- `explanation_transfer`

A interface deve deixar isso explícito para o aluno com:

- média atual do módulo;
- meta de avanço de `70%`;
- cobertura atual de evidências;
- quantidade de evidências já acima da meta.

## API

```bash
uv run aho serve --reload
```

Endpoints principais:

- `GET /health`
- `POST /api/v1/students`
- `GET /api/v1/students/{student_id}/progress`
- `POST /api/v1/tutor/turn`
- `POST /api/v1/students/{student_id}/reset`

## Documentação Complementar

- [HELP.md](HELP.md): guia operacional da CLI.
- [TRILHA-AHO.md](TRILHA-AHO.md): trilha curricular canônica.
- [AGENTS.md](AGENTS.md): contrato de comportamento do agente.

## Licença

MIT.
