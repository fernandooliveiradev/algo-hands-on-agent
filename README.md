# Algo Hands-On

**Pense. Resolva. Construa.**

Tutor adaptativo para pensamento computacional, algoritmos e Python, com Agno, DeepSeek, SQLite, FastAPI e TUI no terminal.

## O Que Importa

- `TRILHA-AHO.md` é a fonte curricular.
- O LLM não decide progresso sozinho.
- O SQLite guarda alunos, sessões, tentativas, evidências e eventos.
- O tutor só avança módulo quando as cinco evidências obrigatórias são satisfeitas sem dica e com nota mínima `0.8`.
- A saída do agente é validada em `TutorTurn` antes de persistir avaliação.

## Setup

```bash
cp .env.example .env
# preencha DEEPSEEK_API_KEY
uv sync --extra dev
uv run aho doctor
```

## Uso

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

No chat:

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
  db/repository.py      domínio SQLite e cálculo de progresso
  cli.py                comandos Typer
  tui.py                TUI Textual
  api.py                FastAPI + AgentOS
  schemas.py            contratos Pydantic
  curriculum.py         módulos da trilha
```

## Banco

Tabelas `aho_*`:

- `aho_students`
- `aho_student_progress`
- `aho_module_progress`
- `aho_competency_progress`
- `aho_exercise_attempts`
- `aho_module_evidence`
- `aho_learning_events`

Tabelas Agno ficam no mesmo SQLite quando o agente cria sessões, memória e métricas.

## Configuração

Principais variáveis:

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

## Qualidade

```bash
uv run ruff check .
uv run python -m pytest
uv run aho doctor
```

Use `uv run python -m pytest` para executar com o interpretador correto do ambiente virtual. Em alguns ambientes Windows, o launcher curto `uv run pytest` pode não carregar dependências opcionais da TUI.

## Regras Do Tutor

- Português do Brasil.
- Sem narrar skills, ferramentas, parser ou instruções internas.
- Sem hype, emoji ou entrevista longa.
- Exercícios são gerados dinamicamente.
- Correção separa raciocínio, algoritmo e sintaxe.
- Progresso só é registrado depois da resposta validada.
